"""
VPN Manager — handles VPN service start/stop/toggle operations.

Extracted from routes_vpn.py to encapsulate toggle logic.
"""
import logging
import os
import subprocess
import time
import re
from typing import Tuple, Optional

from .constants import SERVICE_TOGGLE_CONFIG, PROC_NAME_MAP
from .app_config import INIT_SCRIPTS, CONFIG_PATHS, SERVICES
from .config import TIMEOUT_SERVICE_RESTART
from .services import restart_service, check_service_status, refresh_ipset_from_file
from .utils import Cache
from .iptables_manager import get_iptables_manager
from .app_config import WebConfig
from .exceptions import ServiceError

logger = logging.getLogger(__name__)


class VPNManager:
    """Manager for VPN service operations."""
    
    def __init__(self, service_name: str):
        if service_name not in SERVICES:
            raise ValueError(f"Unknown service: {service_name}")
        
        self.service_name = service_name
        self.svc_info = SERVICES[service_name]
        self.toggle_config = SERVICE_TOGGLE_CONFIG.get(service_name, {})
        
        self.config_path = CONFIG_PATHS.get(service_name, self.svc_info.get('config'))
        self.init_script = INIT_SCRIPTS.get(service_name, self.svc_info.get('init'))
        self.ipset_name = self.toggle_config.get('ipset', '')
        self.port = self.toggle_config.get('port', 0)
    
    @property
    def name(self) -> str:
        return self.svc_info['name']
    
    def is_configured(self) -> bool:
        """Check if service has a config file."""
        return os.path.exists(self.config_path)
    
    def is_running(self) -> bool:
        """Check if service is currently running."""
        if not os.path.exists(self.init_script):
            return False
        Cache.delete(f'status:{self.init_script}')
        return check_service_status(self.init_script) == '✅ Активен'
    
    def get_status(self) -> str:
        """Get service status string."""
        if not os.path.exists(self.init_script):
            return '❌ Скрипт не найден'
        
        if not self.is_configured():
            return '❌ Не настроен'
        
        Cache.delete(f'status:{self.init_script}')
        return check_service_status(self.init_script)
    
    def start(self) -> Tuple[bool, str]:
        """
        Start the VPN service.
        
        Returns:
            Tuple of (success, message)
        """
        if not os.path.exists(self.init_script):
            return False, f'Init script not found: {self.init_script}'
        
        logger.info(f"[VPN] Starting {self.service_name}")
        
        try:
            result = subprocess.run(
                ['sh', self.init_script, 'start'],
                capture_output=True,
                text=True,
                timeout=15
            )
            logger.info(f"[VPN] {self.service_name} start: rc={result.returncode}")
            
            time.sleep(2)
            
            success, output = restart_service(self.name, self.init_script)
            Cache.delete(f'status:{self.init_script}')
            
            if success:
                self._setup_bypass_rules()
                return True, f'{self.name} started'
            else:
                return False, f'Started but error: {output}'
                
        except Exception as e:
            logger.error(f"[VPN] {self.service_name} start error: {e}")
            return False, str(e)
    
    def stop(self) -> Tuple[bool, str]:
        """
        Stop the VPN service.
        
        Returns:
            Tuple of (success, message)
        """
        logger.info(f"[VPN] Stopping {self.service_name}")
        
        try:
            if os.path.exists(self.init_script):
                result = subprocess.run(
                    ['sh', self.init_script, 'stop'],
                    capture_output=True,
                    text=True,
                    timeout=15
                )
                stop_output = result.stdout + result.stderr
                logger.info(f"[VPN] {self.service_name} stop: rc={result.returncode}")
                
                pid = self._extract_pid(stop_output)
                if not pid:
                    proc_name = PROC_NAME_MAP.get(self.service_name, self.service_name)
                    pgrep_result = subprocess.run(
                        ['pgrep', '-f', proc_name],
                        capture_output=True,
                        text=True,
                        timeout=3
                    )
                    if pgrep_result.returncode == 0 and pgrep_result.stdout.strip():
                        pid = pgrep_result.stdout.strip().split('\n')[0]
            
            time.sleep(2)
            
            if pid:
                self._force_kill(int(pid))
            
            # FIX: Не очищаем ipset при остановке сервиса!
            # ipset должен оставаться для других работающих сервисов
            # Очистка происходит только при полном обновлении через S99unblock
            
            ipt = get_iptables_manager()
            ipt.remove_vpn_redirect(self.ipset_name, self.port)
            
            Cache.delete(f'status:{self.init_script}')
            final_status = check_service_status(self.init_script)
            
            if final_status != '✅ Активен':
                return True, f'{self.name} stopped (key saved)'
            else:
                return False, f'{self.name} still active after stop'
                
        except Exception as e:
            logger.error(f"[VPN] {self.service_name} stop error: {e}")
            return False, str(e)
    
    def toggle(self) -> Tuple[bool, str]:
        """
        Toggle service on/off.
        
        Returns:
            Tuple of (success, message)
        """
        if self.is_running():
            return self.stop()
        return self.start()
    
    def _extract_pid(self, output: str) -> Optional[str]:
        """Extract PID from script output."""
        match = re.search(r'PID:\s*(\d+)', output)
        if match:
            return match.group(1)
        return None
    
    def _force_kill(self, pid: int) -> None:
        """Force kill process if still alive."""
        try:
            kill_check = subprocess.run(
                ['kill', '-0', str(pid)],
                capture_output=True,
                text=True,
                timeout=3
            )
            if kill_check.returncode == 0:
                logger.info(f"[VPN] Force killing PID {pid}")
                subprocess.run(['kill', '-9', str(pid)], capture_output=True, timeout=5)
                time.sleep(2)
        except Exception as e:
            logger.debug(f"[VPN] Kill check error: {e}")
    
    def _setup_bypass_rules(self) -> None:
        """Setup ipset and iptables rules after starting."""
        if not self.ipset_name or self.port <= 0:
            return
        
        logger.info(f"[VPN] Setting up bypass rules for {self.service_name}")
        
        cfg = WebConfig()
        bypass_file = os.path.join(cfg.unblock_dir, f"{self.service_name}.txt")
        
        if os.path.exists(bypass_file):
            ok, msg = refresh_ipset_from_file(bypass_file)
            if ok:
                logger.info(f"[VPN] ipset refreshed: {msg}")
            else:
                logger.warning(f"[VPN] ipset refresh failed: {msg}")
        else:
            try:
                subprocess.run(
                    ['ipset', 'create', self.ipset_name, 'hash:net'],
                    capture_output=True
                )
            except Exception:
                pass
        
        ipt = get_iptables_manager()
        ipt.add_vpn_redirect(self.ipset_name, self.port)


def get_vpn_manager(service_name: str) -> VPNManager:
    """Factory function for VPNManager."""
    return VPNManager(service_name)