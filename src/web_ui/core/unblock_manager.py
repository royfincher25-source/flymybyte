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
        self._dnsmasq = DnsmasqManager()
        self._config = WebConfig()
    
    def update_all(self, timeout: int = 600) -> Tuple[bool, str]:
        """Полное обновление: dnsmasq + ipset."""
        logger.info("[UNBLOCK] Starting full update...")
        
        self._flush_ipsets()
        
        ok, msg = self._update_dnsmasq()
        if not ok:
            logger.warning(f"[UNBLOCK] dnsmasq update failed, trying shell: {msg}")
            ok, msg = self._fallback_dnsmasq()
        
        ok2, msg2 = self._update_ipsets()
        if not ok2:
            logger.warning(f"[UNBLOCK] ipset update failed, trying shell: {msg2}")
            ok2, msg2 = self._fallback_ipset()
        
        status = self.get_status()
        total_ips = sum(status['ipsets'].values())
        
        if total_ips > 0:
            logger.info(f"[UNBLOCK] Update complete: {total_ips} IPs")
            return True, f"Updated: {total_ips} IPs in ipsets"
        else:
            return False, "No entries in ipsets"
    
    def update_dnsmasq(self) -> Tuple[bool, str]:
        """Обновить только dnsmasq конфиги (без ipset)."""
        return self._update_dnsmasq()
    
    def update_ipsets(self, max_workers: int = None) -> Tuple[bool, str]:
        """Обновить только ipset (без dnsmasq)."""
        return self._update_ipsets(max_workers)
    
    def get_status(self) -> Dict:
        """Получить статус всех компонентов."""
        return {
            'dnsmasq_running': self._check_dnsmasq(),
            'ipsets': self._get_ipset_counts(),
            'config_exists': os.path.exists('/opt/etc/unblock.dnsmasq'),
        }
    
    def flush_ipsets(self) -> Tuple[bool, str]:
        """Очистить все ipsets."""
        return self._flush_ipsets()
    
    def _check_dnsmasq(self) -> bool:
        """Проверить запущен ли dnsmasq."""
        try:
            result = subprocess.run(['pgrep', 'dnsmasq'], capture_output=True, timeout=3)
            return result.returncode == 0
        except Exception:
            return False
    
    def _get_ipset_counts(self) -> Dict[str, int]:
        """Получить количество записей в каждом ipset."""
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
                else:
                    counts[name] = 0
            except Exception:
                counts[name] = 0
        return counts
    
    def _update_dnsmasq(self) -> Tuple[bool, str]:
        """Обновить dnsmasq конфиги через Python."""
        try:
            ok, msg = self._dnsmasq.generate_all()
            if ok:
                self._dnsmasq.restart_dnsmasq()
            return ok, msg
        except Exception as e:
            return False, str(e)
    
    def _update_ipsets(self, max_workers: int = None) -> Tuple[bool, str]:
        """Обновить ipsets из файлов через Python."""
        from .services import refresh_ipset_from_file
        
        if max_workers is None:
            max_workers = DEFAULT_THREAD_COUNT
        
        unblock_dir = self._config.unblock_dir
        files_map = {
            'unblocksh': os.path.join(unblock_dir, 'shadowsocks.txt'),
            'unblockvless': os.path.join(unblock_dir, 'vless.txt'),
            'unblocktroj': os.path.join(unblock_dir, 'trojan.txt'),
        }
        
        total_added = 0
        errors = []
        
        for ipset_name, filepath in files_map.items():
            if not os.path.exists(filepath):
                logger.debug(f"[UNBLOCK] File not found: {filepath}")
                continue
            
            ok, msg = refresh_ipset_from_file(filepath, max_workers)
            if ok:
                m = re.search(r'(\d+) IPs', msg)
                if m:
                    total_added += int(m.group(1))
            else:
                errors.append(f"{ipset_name}: {msg}")
        
        if errors:
            return False, '; '.join(errors)
        return True, f"Added {total_added} IPs"
    
    def _flush_ipsets(self) -> Tuple[bool, str]:
        """Очистить все ipsets."""
        flushed = []
        for name in IPSET_NAMES:
            try:
                subprocess.run(['ipset', 'flush', name], capture_output=True, timeout=5)
                flushed.append(name)
            except Exception:
                pass
        return True, f"Flushed: {', '.join(flushed)}"
    
    def _fallback_dnsmasq(self) -> Tuple[bool, str]:
        """Fallback: вызвать shell скрипт для dnsmasq."""
        script = UNBLOCK_SCRIPTS['dnsmasq']
        if not os.path.exists(script):
            return False, f"Shell script not found: {script}"
        
        try:
            result = subprocess.run(
                ['sh', script],
                capture_output=True, text=True, timeout=120
            )
            if result.returncode == 0:
                return True, "Shell dnsmasq script completed"
            return False, result.stderr[:200]
        except Exception as e:
            return False, str(e)
    
    def _fallback_ipset(self) -> Tuple[bool, str]:
        """Fallback: вызвать shell скрипт для ipset."""
        script = UNBLOCK_SCRIPTS['ipset']
        if not os.path.exists(script):
            return False, f"Shell script not found: {script}"
        
        try:
            result = subprocess.run(
                ['sh', script],
                capture_output=True, text=True, timeout=600
            )
            if result.returncode == 0:
                return True, "Shell ipset script completed"
            return False, result.stderr[:200]
        except Exception as e:
            return False, str(e)


_instance: Optional[UnblockManager] = None


def get_unblock_manager() -> UnblockManager:
    """Получить экземпляр UnblockManager (singleton)."""
    global _instance
    if _instance is None:
        _instance = UnblockManager()
    return _instance