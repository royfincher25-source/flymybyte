"""
VPN Manager — handles VPN service start/stop/toggle operations.

Extracted from routes_vpn.py to encapsulate toggle logic.
DETAILED LOGGING added for debugging (2026-04-11).
"""
import logging
import os
import re
import socket
import subprocess
import time
import traceback
from typing import Tuple, Optional

from .app_config import INIT_SCRIPTS, CONFIG_PATHS, SERVICES, WebConfig
from .constants import SERVICE_TOGGLE_CONFIG, PROC_NAME_MAP
from .services import restart_service, check_service_status, refresh_ipset_from_file
from .utils import Cache
from .iptables_manager import get_iptables_manager

logger = logging.getLogger(__name__)


class VPNManager:
    """Manager for VPN service operations."""

    def __init__(self, service_name: str):
        logger.debug(f"[VPN] __init__ called for '{service_name}'")
        if service_name not in SERVICES:
            raise ValueError(f"Unknown service: {service_name}")

        self.service_name = service_name
        self.svc_info = SERVICES[service_name]
        self.toggle_config = SERVICE_TOGGLE_CONFIG.get(service_name, {})

        self.config_path = CONFIG_PATHS.get(service_name, self.svc_info.get('config'))
        self.init_script = INIT_SCRIPTS.get(service_name, self.svc_info.get('init'))
        self.ipset_name = self.toggle_config.get('ipset', '')
        self.port = self.toggle_config.get('port', 0)

        logger.debug(
            f"[VPN] {service_name}: config={self.config_path}, "
            f"init={self.init_script}, ipset={self.ipset_name}, port={self.port}"
        )

    @property
    def name(self) -> str:
        return self.svc_info['name']

    def is_configured(self) -> bool:
        result = os.path.exists(self.config_path)
        logger.debug(f"[VPN] is_configured({self.service_name}): {result} (path={self.config_path})")
        return result

    def is_running(self) -> bool:
        logger.debug(f"[VPN] is_running({self.service_name}) called")
        if not os.path.exists(self.init_script):
            logger.warning(f"[VPN] is_running: init script not found: {self.init_script}")
            return False
        Cache.delete(f'status:{self.init_script}')
        status = check_service_status(self.init_script) == '✅ Активен'
        logger.debug(f"[VPN] is_running({self.service_name}): {status}")
        return status

    def get_status(self) -> str:
        logger.debug(f"[VPN] get_status({self.service_name}) called")
        if not os.path.exists(self.init_script):
            return '❌ Скрипт не найден'

        if not self.is_configured():
            return '❌ Не настроен'

        Cache.delete(f'status:{self.init_script}')
        status = check_service_status(self.init_script)
        logger.debug(f"[VPN] get_status({self.service_name}): {status}")
        return status

    def start(self) -> Tuple[bool, str]:
        """Start the VPN service with detailed logging."""
        logger.info(f"[VPN] >>> START {self.service_name}")
        logger.debug(f"[VPN]   init_script: {self.init_script}")
        logger.debug(f"[VPN]   config_path: {self.config_path}")

        if not os.path.exists(self.init_script):
            logger.error(f"[VPN]   FAIL: init script not found")
            return False, f'Init script not found: {self.init_script}'

        try:
            logger.info(f"[VPN]   Running init script start...")
            result = subprocess.run(
                ['sh', self.init_script, 'start'],
                capture_output=True,
                text=True,
                timeout=15
            )
            logger.info(f"[VPN]   init start: rc={result.returncode}, stdout={result.stdout.strip()}, stderr={result.stderr.strip()}")

            logger.info(f"[VPN]   Calling restart_service...")
            success, output = restart_service(self.name, self.init_script)
            Cache.delete(f'status:{self.init_script}')
            logger.info(f"[VPN]   restart_service result: success={success}, output={output}")

            if success:
                logger.info(f"[VPN]   Setting up bypass rules...")
                self._setup_bypass_rules()
                logger.info(f"[VPN] <<< START {self.service_name}: OK")
                return True, f'{self.name} started'
            else:
                logger.warning(f"[VPN] <<< START {self.service_name}: FAILED after restart")
                return False, f'Started but error: {output}'

        except subprocess.TimeoutExpired:
            logger.error(f"[VPN] <<< START {self.service_name}: TIMEOUT")
            return False, 'Timeout during start'
        except Exception as e:
            logger.error(f"[VPN] <<< START {self.service_name}: EXCEPTION: {e}\n{traceback.format_exc()}")
            return False, str(e)

    def stop(self) -> Tuple[bool, str]:
        """Stop the VPN service with detailed logging."""
        logger.info(f"[VPN] >>> STOP {self.service_name}")
        logger.debug(f"[VPN]   init_script: {self.init_script}")
        logger.debug(f"[VPN]   ipset_name: {self.ipset_name}, port: {self.port}")

        pid: Optional[str] = None

        try:
            if os.path.exists(self.init_script):
                logger.info(f"[VPN]   Running init script stop...")
                result = subprocess.run(
                    ['sh', self.init_script, 'stop'],
                    capture_output=True,
                    text=True,
                    timeout=15
                )
                stop_output = result.stdout + result.stderr
                logger.info(f"[VPN]   init stop: rc={result.returncode}, output={stop_output.strip()}")

                pid = self._extract_pid(stop_output)
                if not pid:
                    proc_name = PROC_NAME_MAP.get(self.service_name, self.service_name)
                    logger.debug(f"[VPN]   No PID from output, checking /proc for '{proc_name}'")
                    try:
                        for pid_dir in os.listdir('/proc'):
                            if not pid_dir.isdigit():
                                continue
                            cmdline_path = f'/proc/{pid_dir}/cmdline'
                            try:
                                with open(cmdline_path, 'rb') as f:
                                    cmdline = f.read().decode('utf-8', errors='ignore')
                                    if proc_name in cmdline:
                                        pid = pid_dir
                                        logger.debug(f"[VPN]   Found PID via /proc: {pid}")
                                        break
                            except (FileNotFoundError, PermissionError):
                                continue
                    except Exception as e:
                        logger.debug(f"[VPN]   /proc check failed: {e}")
                else:
                    logger.debug(f"[VPN]   Extracted PID from output: {pid}")
            else:
                logger.warning(f"[VPN]   init script not found, skipping stop")

            logger.info(f"[VPN]   Sleeping 2s for process to exit...")
            time.sleep(2)

            if pid:
                logger.info(f"[VPN]   Force killing PID {pid}...")
                self._force_kill(int(pid))
            else:
                logger.info(f"[VPN]   No PID to force kill")

            logger.info(f"[VPN]   Removing iptables redirect for {self.ipset_name}:{self.port}...")
            ipt = get_iptables_manager()
            ipt.remove_vpn_redirect(self.ipset_name, self.port)

            Cache.delete(f'status:{self.init_script}')
            final_status = check_service_status(self.init_script)
            logger.info(f"[VPN]   Final status check: {final_status}")

            if final_status != '✅ Активен':
                logger.info(f"[VPN] <<< STOP {self.service_name}: OK (stopped)")
                return True, f'{self.name} stopped (key saved)'
            else:
                logger.warning(f"[VPN] <<< STOP {self.service_name}: STILL ACTIVE")
                return False, f'{self.name} still active after stop'

        except subprocess.TimeoutExpired:
            logger.error(f"[VPN] <<< STOP {self.service_name}: TIMEOUT")
            return False, 'Timeout during stop'
        except Exception as e:
            logger.error(f"[VPN] <<< STOP {self.service_name}: EXCEPTION: {e}\n{traceback.format_exc()}")
            return False, str(e)

    def toggle(self) -> Tuple[bool, str]:
        """Toggle service on/off with detailed logging."""
        logger.info(f"[VPN] >>> TOGGLE {self.service_name}")
        running = self.is_running()
        logger.info(f"[VPN]   is_running={running}, deciding action...")
        if running:
            logger.info(f"[VPN]   Service running, calling stop()")
            result = self.stop()
        else:
            logger.info(f"[VPN]   Service NOT running, calling start()")
            result = self.start()
        logger.info(f"[VPN] <<< TOGGLE {self.service_name}: result={result}")
        return result

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
                logger.info(f"[VPN]   Process {pid} alive, sending SIGKILL")
                subprocess.run(['kill', '-9', str(pid)], capture_output=True, timeout=5)
                time.sleep(2)
            else:
                logger.info(f"[VPN]   Process {pid} already dead")
        except Exception as e:
            logger.debug(f"[VPN] Kill check error: {e}")

    def _setup_bypass_rules(self) -> None:
        """Setup ipset and iptables rules with detailed logging."""
        logger.info(f"[VPN] >>> _setup_bypass_rules for {self.service_name}")
        logger.debug(f"[VPN]   ipset={self.ipset_name}, port={self.port}")

        if not self.ipset_name or self.port <= 0:
            logger.warning(f"[VPN]   Skipping: ipset_name='{self.ipset_name}', port={self.port}")
            return

        cfg = WebConfig()
        bypass_file = os.path.join(cfg.unblock_dir, f"{self.service_name}.txt")
        logger.debug(f"[VPN]   bypass_file={bypass_file}")

        if os.path.exists(bypass_file):
            logger.info(f"[VPN]   Refreshing ipset from {bypass_file}")
            ok, msg = refresh_ipset_from_file(bypass_file)
            if ok:
                logger.info(f"[VPN]   ipset refreshed: {msg}")
            else:
                logger.warning(f"[VPN]   ipset refresh failed: {msg}")
        else:
            logger.warning(f"[VPN]   bypass file not found, creating empty ipset")
            try:
                subprocess.run(
                    ['ipset', 'create', self.ipset_name, 'hash:net'],
                    capture_output=True
                )
            except Exception as e:
                logger.debug(f"[VPN]   ipset create error (may already exist): {e}")

        # Check port listening with retry
        # Xray на MIPS-роутере может запускаться медленно — даём 20 секунд
        logger.info(f"[VPN]   Waiting for port {self.port} to be listening (up to 20s)...")
        if not self._wait_for_port(self.port, attempts=20, interval=1):
            logger.error(
                f"[VPN]   Port {self.port} not listening after retries, "
                f"skipping iptables rules for {self.service_name}"
            )
            return

        logger.info(f"[VPN]   Port {self.port} is listening, adding iptables redirect...")
        ipt = get_iptables_manager()
        ok, msg = ipt.add_vpn_redirect(self.ipset_name, self.port)
        logger.info(f"[VPN]   iptables result: ok={ok}, msg={msg}")
        logger.info(f"[VPN] <<< _setup_bypass_rules for {self.service_name}: DONE")

    def _wait_for_port(self, port: int, attempts: int = 5, interval: float = 1.0) -> bool:
        """Wait for port with retry and detailed logging."""
        logger.debug(f"[VPN] _wait_for_port(port={port}, attempts={attempts}, interval={interval})")
        for attempt in range(1, attempts + 1):
            listening = self._is_port_listening(port)
            logger.debug(f"[VPN]   attempt {attempt}/{attempts}: listening={listening}")
            if listening:
                if attempt > 1:
                    logger.info(f"[VPN]   Port {port} ready on attempt {attempt}/{attempts}")
                return True
            if attempt < attempts:
                logger.debug(f"[VPN]   attempt {attempt} failed, sleeping {interval}s...")
                time.sleep(interval)
        logger.warning(f"[VPN]   Port {port} not ready after {attempts} attempts")
        return False

    def _is_port_listening(self, port: int) -> bool:
        """Check if a TCP port is listening on localhost."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        try:
            result = sock.connect_ex(('127.0.0.1', port))
            listening = result == 0
            logger.debug(f"[VPN] _is_port_listening(127.0.0.1:{port}): connect_ex={result}, listening={listening}")
            return listening
        except OSError as e:
            logger.debug(f"[VPN] _is_port_listening({port}) OSError: {e}")
            return False
        finally:
            sock.close()


def get_vpn_manager(service_name: str) -> VPNManager:
    """Factory function for VPNManager."""
    logger.debug(f"[VPN] get_vpn_manager('{service_name}') called")
    return VPNManager(service_name)
