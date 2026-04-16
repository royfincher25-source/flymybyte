"""
Backup Manager — handles all backup/restore operations.

Extracted from routes_system.py to eliminate code duplication.
"""
import logging
import os
import tarfile
import shutil
import re
import time
from datetime import datetime
from typing import List, Dict, Tuple, Optional

from .constants import BACKUP_DIR, BACKUP_FILES
from .app_config import INIT_SCRIPTS
from .config import TIMEOUT_BACKUP_RESTART
from .exceptions import BackupError

logger = logging.getLogger(__name__)


class RestoreStatus:
    """Thread-safe restore status container."""
    
    _instance: Optional['RestoreStatus'] = None
    
    def __init__(self):
        self._data = {
            'running': False,
            'success': False,
            'message': '',
            'step': ''
        }
    
    @classmethod
    def get_instance(cls) -> 'RestoreStatus':
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def get(self) -> Dict:
        return dict(self._data)
    
    def set(self, running: bool, success: bool, message: str, step: str) -> None:
        self._data['running'] = running
        self._data['success'] = success
        self._data['message'] = message
        self._data['step'] = step
    
    def reset(self) -> None:
        self._data = {'running': False, 'success': False, 'message': '', 'step': ''}


class BackupManager:
    """Manager for backup and restore operations."""
    
    def __init__(self, backup_dir: str = BACKUP_DIR):
        self.backup_dir = backup_dir
    
    def _arcname(self, path: str) -> str:
        """Normalize path for archive."""
        if path.startswith('/opt/'):
            return path[5:]
        if path.startswith('/opt'):
            return path[4:]
        return os.path.basename(path)
    
    def create(self, backup_type: str = 'full') -> Tuple[bool, str]:
        """
        Create a backup archive.
        
        Args:
            backup_type: 'full' or 'update'
            
        Returns:
            Tuple of (success, message)
        """
        try:
            os.makedirs(self.backup_dir, exist_ok=True)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            prefix = 'update_backup' if backup_type == 'update' else 'backup'
            backup_file = f'{self.backup_dir}/{prefix}_{timestamp}.tar.gz'
            
            existing_files = [f for f in BACKUP_FILES if os.path.exists(f)]
            if not existing_files:
                return False, 'No files to backup'
            
            with tarfile.open(backup_file, 'w:gz') as tar:
                for f in existing_files:
                    tar.add(f, arcname=self._arcname(f))
            
            backup_size = os.path.getsize(backup_file)
            size_mb = backup_size / 1024 / 1024
            return True, f'Backup created: {backup_file} ({size_mb:.1f} MB, {len(existing_files)} objects)'
        except Exception as e:
            logger.error(f'Backup error: {e}')
            return False, str(e)
    
    def list(self) -> List[Dict]:
        """
        Get list of available backups.
        
        Returns:
            List of backup info dicts sorted by date (newest first)
        """
        backups = []
        if not os.path.exists(self.backup_dir):
            return backups
        
        for item in sorted(os.listdir(self.backup_dir), reverse=True):
            if (item.startswith('backup_') or item.startswith('update_backup_')) and item.endswith('.tar.gz'):
                item_path = os.path.join(self.backup_dir, item)
                try:
                    size = os.path.getsize(item_path)
                    match = re.match(r'(backup|update_backup)_(\d{8})_(\d{6})\.tar\.gz', item)
                    if match:
                        date_str = match.group(2)
                        time_str = match.group(3)
                    else:
                        date_str = item
                        time_str = ''
                    backups.append({
                        'name': item,
                        'path': item_path,
                        'size': size,
                        'date': f"{date_str[6:8]}.{date_str[4:6]}.{date_str[0:4]}",
                        'time': f"{time_str[0:2]}:{time_str[2:4]}" if time_str else '',
                    })
                except Exception as e:
                    logger.error(f"Error processing backup {item}: {e}")
        return backups
    
    def delete(self, backup_name: str) -> Tuple[bool, str]:
        """Delete a backup by name."""
        backup_path = os.path.join(self.backup_dir, backup_name)
        if not backup_name or not os.path.exists(backup_path):
            return False, 'Backup not found'
        try:
            os.remove(backup_path)
            return True, f'Backup {backup_name} deleted'
        except Exception as e:
            return False, f'Delete error: {e}'
    
    def restore_async(self, backup_name: str) -> Tuple[bool, str]:
        """
        Start async restore process.
        
        Args:
            backup_name: Name of backup to restore
            
        Returns:
            Tuple of (started, message)
        """
        import subprocess
        
        backup_path = os.path.join(self.backup_dir, backup_name)
        if not backup_name or not os.path.exists(backup_path):
            return False, 'Backup not found'
        
        status = RestoreStatus.get_instance()
        if status.get()['running']:
            return False, 'Restore already in progress'
        
        def _do_restore():
            status.set(True, False, 'Starting restore...', 'init')
            tmp_dir = f'/tmp/restore_{int(time.time())}'
            
            try:
                # Step 1: Stop web UI
                status.set(True, False, 'Stopping web interface...', 'stopping_webui')
                logger.info("[RESTORE] Stopping web UI")
                try:
                    subprocess.run(['sh', INIT_SCRIPTS['web_ui'], 'stop'], capture_output=True, timeout=10)
                except Exception:
                    pass
                time.sleep(2)
                try:
                    subprocess.run(['killall', '-9', 'python3'], capture_output=True, timeout=5)
                except Exception:
                    pass
                time.sleep(2)
                
                # Step 2: Extract to temp dir
                status.set(True, False, 'Extracting archive...', 'extracting')
                logger.info("[RESTORE] Extracting to %s", tmp_dir)
                os.makedirs(tmp_dir, exist_ok=True)
                with tarfile.open(backup_path, 'r:gz') as tar:
                    tar.extractall(tmp_dir)
                
                # Step 3: Copy files
                status.set(True, False, 'Copying files...', 'copying')
                logger.info("[RESTORE] Copying files")
                
                restore_map = {
                    'etc/web_ui': '/opt/etc/web_ui',
                    'etc/xray': '/opt/etc/xray',
                    'etc/trojan': '/opt/etc/trojan',
                    'etc/unblock': '/opt/etc/unblock',
                    'etc/init.d': '/opt/etc/init.d',
                    'etc/ndm': '/opt/etc/ndm',
                    'etc/dnsmasq.conf': '/opt/etc/dnsmasq.conf',
                    'etc/crontab': '/opt/etc/crontab',
                    'bin': '/opt/bin',
                    'root': '/opt/root',
                    'var/log': '/opt/var/log',
                }
                
                for src_rel, dst_abs in restore_map.items():
                    src_path = os.path.join(tmp_dir, src_rel)
                    if os.path.exists(src_path):
                        if os.path.isdir(src_path):
                            if os.path.exists(dst_abs):
                                shutil.rmtree(dst_abs, ignore_errors=True)
                            shutil.copytree(src_path, dst_abs, dirs_exist_ok=True)
                        else:
                            os.makedirs(os.path.dirname(dst_abs), exist_ok=True)
                            shutil.copy2(src_path, dst_abs)
                        logger.info("[RESTORE] Restored %s -> %s", src_rel, dst_abs)
                
                # Step 4: Restore permissions
                status.set(True, False, 'Restoring permissions...', 'permissions')
                try:
                    for d in ['/opt/bin', '/opt/etc/init.d']:
                        if os.path.exists(d):
                            for f in os.listdir(d):
                                fp = os.path.join(d, f)
                                if os.path.isfile(fp):
                                    os.chmod(fp, 0o755)
                except Exception as e:
                    logger.warning("[RESTORE] Permission restore error: %s", e)
                
                # Step 5: Restart dnsmasq
                status.set(True, False, 'Restarting dnsmasq...', 'restarting_dnsmasq')
                try:
                    subprocess.run(['sh', INIT_SCRIPTS['dnsmasq'], 'restart'], capture_output=True, timeout=15)
                except Exception as e:
                    logger.warning("[RESTORE] dnsmasq restart error: %s", e)
                
                # Step 6: Restart web UI
                status.set(True, False, 'Restarting web interface...', 'restarting_webui')
                try:
                    subprocess.Popen(
                        ['sh', INIT_SCRIPTS['web_ui'], 'start'],
                        start_new_session=True,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                except Exception as e:
                    logger.warning("[RESTORE] web_ui start error: %s", e)
                
                # Step 7: Cleanup
                status.set(True, False, 'Cleaning up...', 'cleanup')
                try:
                    shutil.rmtree(tmp_dir, ignore_errors=True)
                except Exception:
                    pass
                
                status.set(False, True, 'Restore completed. Reboot router.', 'done')
                logger.info("[RESTORE] Restore completed successfully")
                
            except Exception as e:
                logger.error("[RESTORE] Restore failed: %s", e, exc_info=True)
                status.set(False, False, f'Restore error: {e}', 'error')
                try:
                    subprocess.Popen(
                        ['sh', INIT_SCRIPTS['web_ui'], 'start'],
                        start_new_session=True,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                except Exception:
                    pass
        
        import threading
        thread = threading.Thread(target=_do_restore, daemon=True)
        thread.start()
        return True, 'Restore started in background'
    
    def get_restore_status(self) -> Dict:
        """Get current restore operation status."""
        return RestoreStatus.get_instance().get()


# Singleton instance
_backup_manager: Optional[BackupManager] = None


def get_backup_manager() -> BackupManager:
    """Get singleton BackupManager instance."""
    global _backup_manager
    if _backup_manager is None:
        _backup_manager = BackupManager()
    return _backup_manager