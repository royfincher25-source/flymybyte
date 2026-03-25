"""
DNS Monitor - Automatic DNS channel availability checking

Monitors primary and backup DNS servers, switches on failure.
Optimized for embedded devices (128MB RAM).

Architecture: Background thread with periodic checks, automatic switch on failure.
Tech Stack: Python 3.8+, threading, socket, Flask 3.0.0
"""
import threading
import time
import socket
import logging
import traceback
from typing import Dict, List, Optional, Any
from datetime import datetime

logger = logging.getLogger(__name__)

# Default DNS servers
DEFAULT_DNS_SERVERS = {
    'primary': [
        {'name': 'Google DNS', 'host': '8.8.8.8', 'port': 53},
        {'name': 'Cloudflare', 'host': '1.1.1.1', 'port': 53},
    ],
    'backup': [
        {'name': 'Quad9', 'host': '9.9.9.9', 'port': 53},
        {'name': 'OpenDNS', 'host': '208.67.222.222', 'port': 53},
    ],
}

CHECK_INTERVAL = 60  # Оптимизировано для KN-1212 (было: 30)
TIMEOUT = 3  # Оптимизировано для KN-1212 (было: 2)
FAILURE_THRESHOLD = 3  # Switch after 3 consecutive failures


def check_dns_server(host: str, port: int = 53, timeout: float = 2.0) -> Dict[str, Any]:
    """
    Check if DNS server is reachable.

    Args:
        host: DNS server IP
        port: DNS port (default 53)
        timeout: Timeout in seconds

    Returns:
        Dict with success, latency_ms, error
    """
    start_time = time.time()
    try:
        # Simple TCP connection test
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()

        latency_ms = (time.time() - start_time) * 1000

        if result == 0:
            return {
                'success': True,
                'latency_ms': round(latency_ms, 2),
                'host': host,
                'port': port,
            }
        else:
            return {
                'success': False,
                'latency_ms': round(latency_ms, 2),
                'host': host,
                'port': port,
                'error': f'Connection failed (code {result})',
            }

    except socket.timeout:
        return {
            'success': False,
            'latency_ms': round((time.time() - start_time) * 1000, 2),
            'host': host,
            'port': port,
            'error': 'Timeout',
        }
    except Exception as e:
        return {
            'success': False,
            'latency_ms': round((time.time() - start_time) * 1000, 2),
            'host': host,
            'port': port,
            'error': str(e),
        }


class DNSMonitor:
    """
    Background DNS monitoring service.

    Singleton pattern - only one instance allowed.
    Runs in background thread, checks DNS servers periodically.
    """

    _instance: Optional['DNSMonitor'] = None
    _lock = threading.Lock()

    def __new__(cls) -> 'DNSMonitor':
        """Singleton pattern with thread safety"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize monitor"""
        if hasattr(self, '_initialized'):
            return

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._current_server: Optional[Dict] = None
        self._last_check: Optional[datetime] = None
        self._failures = 0
        self._servers = DEFAULT_DNS_SERVERS.copy()

        self._initialized = True
        logger.info("DNSMonitor initialized")

    def start(self) -> None:
        """Start background monitoring"""
        if self._running:
            logger.warning("DNSMonitor already running")
            return

        self._running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()
        logger.info("DNSMonitor started")

    def stop(self) -> None:
        """Stop background monitoring"""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
            if self._thread.is_alive():
                logger.error("DNSMonitor thread did not stop gracefully")
        logger.info("DNSMonitor stopped")

    def is_running(self) -> bool:
        """Check if monitor is running"""
        return self._running

    def get_status(self) -> Dict[str, Any]:
        """Get current monitor status"""
        return {
            'running': self._running,
            'current_server': self._current_server,
            'last_check': self._last_check.isoformat() if self._last_check else None,
            'failures': self._failures,
        }

    def _monitor_loop(self) -> None:
        """Background monitoring loop"""
        logger.info("DNSMonitor loop started")

        while self._running:
            try:
                # Check current server
                if self._current_server:
                    result = check_dns_server(
                        self._current_server['host'],
                        self._current_server['port'],
                        TIMEOUT
                    )

                    if result['success']:
                        self._failures = 0
                        logger.debug(f"DNS check OK: {self._current_server['name']} ({result['latency_ms']}ms)")
                    else:
                        self._failures += 1
                        logger.warning(f"DNS check failed: {self._current_server['name']} - {result['error']}")

                        # Switch to backup after 3 consecutive failures
                        if self._failures >= FAILURE_THRESHOLD:
                            self._switch_to_backup()

                else:
                    # No current server - select best from primary
                    self._select_best_primary()

                self._last_check = datetime.now()

            except Exception as e:
                logger.error(f"DNSMonitor error: {e}\n{traceback.format_exc()}")

            # Wait for next check
            time.sleep(CHECK_INTERVAL)

    def _select_best_primary(self) -> None:
        """Select best primary DNS server"""
        best_server = None
        best_latency = float('inf')

        for server in self._servers['primary']:
            result = check_dns_server(server['host'], server['port'], TIMEOUT)
            if result['success'] and result['latency_ms'] < best_latency:
                best_server = server
                best_latency = result['latency_ms']

        if best_server:
            self._current_server = best_server
            logger.info(f"Selected primary DNS: {best_server['name']} ({best_latency}ms)")

            # Update dnsmasq config
            from .dns_manager import update_dnsmasq_dns
            success, msg = update_dnsmasq_dns(best_server['host'])
            if success:
                logger.info(f"dnsmasq updated to use {best_server['name']}")
            else:
                logger.error(f"Failed to update dnsmasq: {msg}")
        else:
            # Try backup
            self._switch_to_backup()

    def _switch_to_backup(self) -> None:
        """Switch to backup DNS server"""
        logger.warning("Switching to backup DNS")

        for server in self._servers['backup']:
            result = check_dns_server(server['host'], server['port'], TIMEOUT)
            if result['success']:
                self._current_server = server
                self._failures = 0

                # Update dnsmasq config
                from .dns_manager import update_dnsmasq_dns
                success, msg = update_dnsmasq_dns(server['host'])
                if success:
                    logger.info(f"Switched to backup DNS: {server['name']} (dnsmasq updated)")
                else:
                    logger.error(f"Failed to update dnsmasq: {msg}")

                return

        logger.error("No working backup DNS found")
        self._current_server = None


# Global instance for routes
def get_dns_monitor() -> DNSMonitor:
    """Get DNS monitor instance"""
    return DNSMonitor()
