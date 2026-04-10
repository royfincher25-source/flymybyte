"""
FlyMyByte — Unified Unblock Manager

Единый интерфейс для управления bypass (dnsmasq + ipset).
Гибридный режим: Python с shell fallback.

Usage:
    from core.unblock_manager import get_unblock_manager
    
    mgr = get_unblock_manager()
    ok, msg = mgr.update_all()
"""
import os
import re
import logging
import subprocess
import time
from typing import Dict, Tuple, Optional

from .dnsmasq_manager import DnsmasqManager
from .app_config import WebConfig

logger = logging.getLogger(__name__)

DEFAULT_THREAD_COUNT = 4
IPSET_NAMES = ['unblocksh', 'unblockvless', 'unblocktroj']
UNBLOCK_SCRIPTS = {
    'dnsmasq': '/opt/bin/unblock_dnsmasq.sh',
    'ipset': '/opt/bin/unblock_ipset.sh',
    'update': '/opt/bin/unblock_update.sh',
}


class UnblockManager:
    """Менеджер для полного управления bypass."""
    
    def __init__(self):
        logger.info("[UNBLOCK] Initializing UnblockManager...")
        self._dnsmasq = DnsmasqManager()
        self._config = WebConfig()
        logger.info(f"[UNBLOCK] Config loaded: unblock_dir={self._config.unblock_dir}")
    
    def update_all(self, timeout: int = 600) -> Tuple[bool, str]:
        """Полное обновление: dnsmasq + ipset."""
        start_time = time.time()
        logger.info("=" * 60)
        logger.info("[UNBLOCK] ===== STARTING FULL UPDATE =====")
        logger.info(f"[UNBLOCK] Timeout: {timeout}s")
        logger.info("=" * 60)
        
        # Логируем начальное состояние
        status_before = self.get_status()
        logger.info(f"[UNBLOCK] Status BEFORE update:")
        logger.info(f"  - dnsmasq running: {status_before['dnsmasq_running']}")
        logger.info(f"  - ipsets: {status_before['ipsets']}")
        
        # Step 1: Flush ipsets
        logger.info("[UNBLOCK] Step 1: Flushing ipsets...")
        flush_ok, flush_msg = self._flush_ipsets()
        logger.info(f"[UNBLOCK] Flush result: {flush_ok} - {flush_msg}")
        
        # Step 2: Update dnsmasq
        logger.info("[UNBLOCK] Step 2: Updating dnsmasq (Python)...")
        ok, msg = self._update_dnsmasq()
        logger.info(f"[UNBLOCK] dnsmasq update result: {ok} - {msg}")
        
        if not ok:
            logger.warning("[UNBLOCK] Python dnsmasq failed, trying shell fallback...")
            ok, msg = self._fallback_dnsmasq()
            logger.info(f"[UNBLOCK] Shell dnsmasq fallback result: {ok} - {msg}")
        
        # Step 3: Update ipsets
        logger.info("[UNBLOCK] Step 3: Updating ipsets (Python)...")
        ok2, msg2 = self._update_ipsets()
        logger.info(f"[UNBLOCK] ipset update result: {ok2} - {msg2}")
        
        if not ok2:
            logger.warning("[UNBLOCK] Python ipset failed, trying shell fallback...")
            ok2, msg2 = self._fallback_ipset()
            logger.info(f"[UNBLOCK] Shell ipset fallback result: {ok2} - {msg2}")
        
        # Логируем конечное состояние
        status_after = self.get_status()
        total_ips = sum(status_after['ipsets'].values())
        
        elapsed = time.time() - start_time
        logger.info(f"[UNBLOCK] Status AFTER update:")
        logger.info(f"  - dnsmasq running: {status_after['dnsmasq_running']}")
        logger.info(f"  - ipsets: {status_after['ipsets']}")
        logger.info(f"  - total IPs: {total_ips}")
        logger.info(f"[UNBLOCK] Elapsed time: {elapsed:.2f}s")
        
        if total_ips > 0:
            logger.info(f"[UNBLOCK] ===== UPDATE COMPLETE: {total_ips} IPs =====")
            logger.info("=" * 60)
            return True, f"Updated: {total_ips} IPs in ipsets"
        else:
            logger.error("[UNBLOCK] ===== UPDATE FAILED: No entries in ipsets =====")
            logger.error("=" * 60)
            return False, "No entries in ipsets"
    
    def update_dnsmasq(self) -> Tuple[bool, str]:
        """Обновить только dnsmasq конфиги (без ipset)."""
        logger.info("[UNBLOCK] update_dnsmasq() called")
        return self._update_dnsmasq()
    
    def update_ipsets(self, max_workers: int = None) -> Tuple[bool, str]:
        """Обновить только ipset (без dnsmasq)."""
        logger.info("[UNBLOCK] update_ipsets() called")
        return self._update_ipsets(max_workers)
    
    def get_status(self) -> Dict:
        """Получить статус всех компонентов."""
        status = {
            'dnsmasq_running': self._check_dnsmasq(),
            'ipsets': self._get_ipset_counts(),
            'config_exists': os.path.exists('/opt/etc/unblock.dnsmasq'),
        }
        logger.debug(f"[UNBLOCK] get_status(): {status}")
        return status
    
    def flush_ipsets(self) -> Tuple[bool, str]:
        """Очистить все ipsets."""
        logger.info("[UNBLOCK] flush_ipsets() called")
        return self._flush_ipsets()
    
    def _check_dnsmasq(self) -> bool:
        """Проверить запущен ли dnsmasq."""
        logger.debug("[UNBLOCK] Checking dnsmasq status...")
        try:
            result = subprocess.run(['pgrep', 'dnsmasq'], capture_output=True, timeout=3)
            is_running = result.returncode == 0
            logger.debug(f"[UNBLOCK] dnsmasq running: {is_running}")
            return is_running
        except Exception as e:
            logger.warning(f"[UNBLOCK] Error checking dnsmasq: {e}")
            return False
    
    def _get_ipset_counts(self) -> Dict[str, int]:
        """Получить количество записей в каждом ipset."""
        logger.debug("[UNBLOCK] Getting ipset counts...")
        counts = {}
        for name in IPSET_NAMES:
            try:
                result = subprocess.run(
                    ['ipset', 'list', name],
                    capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0:
                    lines = [l for l in result.stdout.split('\n') if l.strip() and l.strip()[0].isdigit()]
                    counts[name] = len(lines)
                    logger.debug(f"[UNBLOCK] ipset {name}: {counts[name]} entries")
                else:
                    counts[name] = 0
                    logger.debug(f"[UNBLOCK] ipset {name}: not found")
            except Exception as e:
                counts[name] = 0
                logger.warning(f"[UNBLOCK] Error getting {name} count: {e}")
        return counts
    
    def _update_dnsmasq(self) -> Tuple[bool, str]:
        """Обновить dnsmasq конфиги через Python."""
        logger.info("[UNBLOCK] _update_dnsmasq() - Python path")
        
        # Логируем конфиги
        bypass_conf = '/opt/etc/unblock.dnsmasq'
        ai_conf = '/opt/etc/unblock-ai.dnsmasq'
        logger.info(f"[UNBLOCK] Checking config files:")
        logger.info(f"  - {bypass_conf}: exists={os.path.exists(bypass_conf)}")
        logger.info(f"  - {ai_conf}: exists={os.path.exists(ai_conf)}")
        
        try:
            logger.info("[UNBLOCK] Generating all configs (bypass + AI)...")
            ok, msg = self._dnsmasq.generate_all()
            logger.info(f"[UNBLOCK] generate_all(): {ok} - {msg}")
            
            if ok:
                logger.info("[UNBLOCK] Restarting dnsmasq...")
                restart_ok, restart_msg = self._dnsmasq.restart_dnsmasq()
                logger.info(f"[UNBLOCK] restart_dnsmasq(): {restart_ok} - {restart_msg}")
                
                if not restart_ok:
                    logger.warning(f"[UNBLOCK] dnsmasq restart failed: {restart_msg}")
                    return False, f"Restart failed: {restart_msg}"
            else:
                logger.warning(f"[UNBLOCK] generate_all() returned false: {msg}")
            
            return ok, msg
        except Exception as e:
            logger.error(f"[UNBLOCK] Exception in _update_dnsmasq(): {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False, str(e)
    
    def _update_ipsets(self, max_workers: int = None) -> Tuple[bool, str]:
        """Обновить ipsets из файлов через Python."""
        logger.info("[UNBLOCK] _update_ipsets() - Python path")
        
        if max_workers is None:
            max_workers = DEFAULT_THREAD_COUNT
        logger.info(f"[UNBLOCK] Using max_workers={max_workers}")
        
        unblock_dir = self._config.unblock_dir
        logger.info(f"[UNBLOCK] unblock_dir: {unblock_dir}")
        
        files_map = {
            'unblocksh': os.path.join(unblock_dir, 'shadowsocks.txt'),
            'unblockvless': os.path.join(unblock_dir, 'vless.txt'),
            'unblocktroj': os.path.join(unblock_dir, 'trojan.txt'),
        }
        
        logger.info(f"[UNBLOCK] Files to process:")
        for ipset_name, filepath in files_map.items():
            exists = os.path.exists(filepath)
            logger.info(f"  - {ipset_name}: {filepath} (exists={exists})")
        
        total_added = 0
        errors = []
        
        for ipset_name, filepath in files_map.items():
            if not os.path.exists(filepath):
                logger.warning(f"[UNBLOCK] File not found: {filepath}, skipping")
                continue
            
            logger.info(f"[UNBLOCK] Processing: {ipset_name} from {filepath}")
            
            try:
                from .services import refresh_ipset_from_file
                ok, msg = refresh_ipset_from_file(filepath, max_workers)
                logger.info(f"[UNBLOCK] refresh_ipset_from_file({ipset_name}): {ok} - {msg}")
                
                if ok:
                    m = re.search(r'(\d+) IPs', msg)
                    if m:
                        count = int(m.group(1))
                        total_added += count
                        logger.info(f"[UNBLOCK] Added {count} IPs to {ipset_name}")
                else:
                    errors.append(f"{ipset_name}: {msg}")
                    logger.error(f"[UNBLOCK] Error processing {ipset_name}: {msg}")
            except Exception as e:
                logger.error(f"[UNBLOCK] Exception processing {ipset_name}: {e}")
                import traceback
                logger.error(traceback.format_exc())
                errors.append(f"{ipset_name}: {str(e)}")
        
        logger.info(f"[UNBLOCK] Total IPs added: {total_added}")
        if errors:
            logger.error(f"[UNBLOCK] Errors: {errors}")
            return False, '; '.join(errors)
        
        return True, f"Added {total_added} IPs"
    
    def _flush_ipsets(self) -> Tuple[bool, str]:
        """Очистить все ipsets."""
        logger.info("[UNBLOCK] Flushing all ipsets...")
        flushed = []
        for name in IPSET_NAMES:
            try:
                logger.debug(f"[UNBLOCK] Flushing {name}...")
                result = subprocess.run(['ipset', 'flush', name], capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    flushed.append(name)
                    logger.debug(f"[UNBLOCK] Flushed {name}")
                else:
                    logger.warning(f"[UNBLOCK] Failed to flush {name}: {result.stderr}")
            except Exception as e:
                logger.warning(f"[UNBLOCK] Exception flushing {name}: {e}")
        
        msg = f"Flushed: {', '.join(flushed)}"
        logger.info(f"[UNBLOCK] Flush result: {msg}")
        return True, msg
    
    def _fallback_dnsmasq(self) -> Tuple[bool, str]:
        """Fallback: вызвать shell скрипт для dnsmasq."""
        logger.info("[UNBLOCK] ===== FALLBACK: Calling shell dnsmasq script =====")
        script = UNBLOCK_SCRIPTS['dnsmasq']
        
        if not os.path.exists(script):
            logger.error(f"[UNBLOCK] Shell script not found: {script}")
            return False, f"Shell script not found: {script}"
        
        logger.info(f"[UNBLOCK] Executing: sh {script}")
        try:
            result = subprocess.run(
                ['sh', script],
                capture_output=True, text=True, timeout=120
            )
            logger.info(f"[UNBLOCK] Shell exit code: {result.returncode}")
            if result.stdout:
                logger.info(f"[UNBLOCK] Shell stdout: {result.stdout[:500]}")
            if result.stderr:
                logger.warning(f"[UNBLOCK] Shell stderr: {result.stderr[:500]}")
            
            if result.returncode == 0:
                logger.info("[UNBLOCK] Shell dnsmasq script completed successfully")
                return True, "Shell dnsmasq script completed"
            else:
                logger.error(f"[UNBLOCK] Shell failed with code {result.returncode}")
                return False, result.stderr[:200]
        except subprocess.TimeoutExpired:
            logger.error("[UNBLOCK] Shell dnsmasq script timed out")
            return False, "Timeout"
        except Exception as e:
            logger.error(f"[UNBLOCK] Exception running shell: {e}")
            return False, str(e)
    
    def _fallback_ipset(self) -> Tuple[bool, str]:
        """Fallback: вызвать shell скрипт для ipset."""
        logger.info("[UNBLOCK] ===== FALLBACK: Calling shell ipset script =====")
        script = UNBLOCK_SCRIPTS['ipset']
        
        if not os.path.exists(script):
            logger.error(f"[UNBLOCK] Shell script not found: {script}")
            return False, f"Shell script not found: {script}"
        
        logger.info(f"[UNBLOCK] Executing: sh {script}")
        try:
            result = subprocess.run(
                ['sh', script],
                capture_output=True, text=True, timeout=600
            )
            logger.info(f"[UNBLOCK] Shell exit code: {result.returncode}")
            if result.stdout:
                logger.info(f"[UNBLOCK] Shell stdout: {result.stdout[:500]}")
            if result.stderr:
                logger.warning(f"[UNBLOCK] Shell stderr: {result.stderr[:500]}")
            
            if result.returncode == 0:
                logger.info("[UNBLOCK] Shell ipset script completed successfully")
                return True, "Shell ipset script completed"
            else:
                logger.error(f"[UNBLOCK] Shell failed with code {result.returncode}")
                return False, result.stderr[:200]
        except subprocess.TimeoutExpired:
            logger.error("[UNBLOCK] Shell ipset script timed out")
            return False, "Timeout"
        except Exception as e:
            logger.error(f"[UNBLOCK] Exception running shell: {e}")
            return False, str(e)


_instance: Optional[UnblockManager] = None


def get_unblock_manager() -> UnblockManager:
    """Получить экземпляр UnblockManager (singleton)."""
    global _instance
    if _instance is None:
        logger.info("[UNBLOCK] Creating UnblockManager singleton")
        _instance = UnblockManager()
    return _instance