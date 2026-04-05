"""
DNS Operations Module

Consolidates: dns_manager, dns_monitor, dns_resolver
All DNS-related functionality in one module for embedded devices (128MB RAM).
"""
import subprocess
import socket
import threading
import time
import re
import logging
import traceback
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime

from .constants import (
    DNSMASQ_CONFIG,
    INIT_SCRIPTS,
    DEFAULT_DNS_SERVERS,
    DNS_CHECK_INTERVAL,
    DNS_TIMEOUT,
    DNS_FAILURE_THRESHOLD,
)
from .utils import is_ip_address

logger = logging.getLogger(__name__)

# =============================================================================
# DNS Manager (formerly dns_manager.py)
# =============================================================================

DNSMASQ_RESTART_CMD = [INIT_SCRIPTS['dnsmasq'], 'restart']


def update_dnsmasq_dns(server_host: str, fallback_servers: list = None) -> Tuple[bool, str]:
    """
    Update dnsmasq to use specific DNS server(s) with fallbacks.

    Args:
        server_host: Primary DNS server IP address
        fallback_servers: List of fallback DNS servers (default: ['1.1.1.1'])

    Returns:
        Tuple of (success: bool, message: str)
    """
    if fallback_servers is None:
        fallback_servers = ['1.1.1.1']

    logger.info(f"[DNS] Updating dnsmasq: primary={server_host}, fallbacks={fallback_servers}")

    try:
        config_path = Path(DNSMASQ_CONFIG)
        if not config_path.exists():
            logger.warning(f"[DNS] dnsmasq config not found: {DNSMASQ_CONFIG}, skipping update")
            return True, "dnsmasq not configured"

        content = config_path.read_text()
        logger.debug(f"[DNS] Read dnsmasq config: {len(content)} bytes")

        # Remove existing bare server= lines, keep domain-specific ones
        lines = []
        removed_servers = 0
        for line in content.split('\n'):
            stripped = line.strip()
            if stripped.startswith('server=/'):
                lines.append(line)
            elif stripped.startswith('server='):
                removed_servers += 1
                pass
            else:
                lines.append(line)

        logger.debug(f"[DNS] Removed {removed_servers} old server= lines, keeping {len(lines)} lines")

        # Add new server lines: primary + fallbacks
        lines.append(f'server={server_host}')
        for fb in fallback_servers:
            lines.append(f'server={fb}')

        # Atomic write via .tmp file
        tmp_path = config_path.with_suffix('.tmp')
        tmp_path.write_text('\n'.join(lines))
        tmp_path.replace(config_path)

        logger.info(f"[DNS] Written new dnsmasq config: {server_host} + {len(fallback_servers)} fallback(s)")

        # Restart dnsmasq
        result = subprocess.run(
            DNSMASQ_RESTART_CMD,
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode == 0:
            logger.info(f"[DNS] dnsmasq restarted successfully")
            return True, "OK"
        else:
            error_msg = result.stderr.strip() or result.stdout.strip() or f"dnsmasq restart failed (code {result.returncode})"
            logger.error(f"[DNS] dnsmasq restart failed: {error_msg}")
            return False, error_msg

    except subprocess.TimeoutExpired:
        error_msg = "dnsmasq restart timeout"
        logger.error(f"[DNS] {error_msg}")
        return False, error_msg

    except Exception as e:
        error_msg = f"Error updating dnsmasq: {e}"
        logger.error(f"[DNS] {error_msg}")
        return False, error_msg


# =============================================================================
# DNS Monitor (formerly dns_monitor.py)
# =============================================================================

CHECK_INTERVAL = DNS_CHECK_INTERVAL
TIMEOUT = DNS_TIMEOUT
FAILURE_THRESHOLD = DNS_FAILURE_THRESHOLD


def check_dns_server(host: str, port: int = 53, timeout: float = 2.0) -> Dict[str, Any]:
    """
    Check if DNS server is reachable via TCP connection test.

    Args:
        host: DNS server IP
        port: DNS port (default 53)
        timeout: Timeout in seconds

    Returns:
        Dict with success, latency_ms, error
    """
    start_time = time.time()
    try:
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

                        if self._failures >= FAILURE_THRESHOLD:
                            self._switch_to_backup()

                else:
                    self._select_best_primary()

                self._last_check = datetime.now()

            except Exception as e:
                logger.error(f"DNSMonitor error: {e}\n{traceback.format_exc()}")

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

            fallback = [s['host'] for s in self._servers['primary'] if s['host'] != best_server['host']]
            success, msg = update_dnsmasq_dns(best_server['host'], fallback_servers=fallback)
            if success:
                logger.info(f"dnsmasq updated to use {best_server['name']}")
            else:
                logger.error(f"Failed to update dnsmasq: {msg}")
        else:
            self._switch_to_backup()

    def _switch_to_backup(self) -> None:
        """Switch to backup DNS server"""
        logger.warning("Switching to backup DNS")

        for server in self._servers['backup']:
            result = check_dns_server(server['host'], server['port'], TIMEOUT)
            if result['success']:
                self._current_server = server
                self._failures = 0

                fallback = [s['host'] for s in self._servers['backup'] if s['host'] != server['host']]
                success, msg = update_dnsmasq_dns(server['host'], fallback_servers=fallback)
                if success:
                    logger.info(f"Switched to backup DNS: {server['name']} (dnsmasq updated)")
                else:
                    logger.error(f"Failed to update dnsmasq: {msg}")

                return

        logger.error("No working backup DNS found")
        self._current_server = None


def get_dns_monitor() -> DNSMonitor:
    """Get DNS monitor instance"""
    return DNSMonitor()


# =============================================================================
# DNS Resolver (formerly dns_resolver.py)
# =============================================================================

MAX_WORKERS = 10  # Maximum parallel workers for 128MB RAM
DEFAULT_TIMEOUT = 5.0  # DNS resolution timeout in seconds
DNS_SERVER = "8.8.8.8"  # External DNS server for reliable resolution


def resolve_single(domain: str, timeout: float = DEFAULT_TIMEOUT) -> List[str]:
    """
    Resolve a single domain to IP addresses using nslookup.

    Args:
        domain: Domain name to resolve
        timeout: Resolution timeout in seconds (default: 5.0)

    Returns:
        List of IP addresses
    """
    try:
        result = subprocess.run(
            ["nslookup", domain, DNS_SERVER],
            capture_output=True,
            text=True,
            timeout=timeout
        )

        ips = re.findall(r'Address:\s*([0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3})', result.stdout)
        ips = [ip for ip in ips if ip != DNS_SERVER]
        ips = list(set(ips))

        logger.debug(f"Resolved {domain} -> {ips}")
        return ips
    except subprocess.TimeoutExpired:
        logger.warning(f"Timeout resolving {domain}")
        return []
    except subprocess.SubprocessError as e:
        logger.warning(f"Failed to resolve {domain}: {e}")
        return []
    except Exception as e:
        logger.error(f"Unexpected error resolving {domain}: {e}")
        return []


def parallel_resolve(domains: List[str], max_workers: int = MAX_WORKERS) -> Dict[str, List[str]]:
    """
    Resolve multiple domains in parallel.

    Args:
        domains: List of domains to resolve
        max_workers: Maximum parallel workers (default: 10 for embedded)

    Returns:
        Dict mapping domain -> list of IPs
    """
    if not domains:
        return {}

    valid_domains = list(set(
        domain for domain in domains
        if domain and isinstance(domain, str) and domain.strip()
    ))

    if not valid_domains:
        return {}

    max_workers = min(max_workers, MAX_WORKERS)
    results = {}

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_domain = {
            executor.submit(resolve_single, domain): domain
            for domain in valid_domains
        }

        for future in as_completed(future_to_domain):
            domain = future_to_domain[future]
            try:
                ips = future.result()
                if ips:
                    results[domain] = ips
            except Exception as e:
                logger.error(f"Error resolving {domain}: {e}")
                results[domain] = []

    logger.info(f"Resolved {len(results)}/{len(valid_domains)} domains")
    return results


def resolve_domains_for_ipset(filepath: str, max_workers: int = MAX_WORKERS) -> int:
    """
    Resolve domains from bypass list file and add to ipset.

    Args:
        filepath: Path to bypass list file
        max_workers: Parallel workers (default: 10)

    Returns:
        Number of IPs added to ipset
    """
    from .utils import load_bypass_list
    from .services import bulk_add_to_ipset, ensure_ipset_exists

    entries = load_bypass_list(filepath)
    domains = [e for e in entries if not is_ip_address(e)]

    if not domains:
        logger.info(f"No domains to resolve in {filepath}")
        return 0

    BATCH_SIZE = 500
    total_ips_added = 0

    for i in range(0, len(domains), BATCH_SIZE):
        batch_domains = domains[i:i + BATCH_SIZE]
        resolved = parallel_resolve(batch_domains, max_workers)

        batch_ips = set()
        for domain, ips in resolved.items():
            batch_ips.update(ips)

        if batch_ips:
            ensure_ipset_exists('unblock_domains')
            success, msg = bulk_add_to_ipset('unblock_domains', list(batch_ips))
            if success:
                total_ips_added += len(batch_ips)
                logger.info(f"Batch {i // BATCH_SIZE + 1}: added {len(batch_ips)} IPs")
            else:
                logger.error(f"Failed to add batch IPs: {msg}")

    logger.info(f"Total: added {total_ips_added} resolved IPs to ipset")
    return total_ips_added
