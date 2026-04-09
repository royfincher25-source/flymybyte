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
    IPSET_MAP,
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
        # Patterns to sanitize (obsolete ipsets removed in v2.7.0)
        OBSOLETE_PATTERNS = [
            'ipset=/onion/unblocktor',
            'ipset=/onion/unblock4-tor',
            'ipset=/onion/unblock6-tor',
            'conf-file=/opt/etc/unblock-tor.dnsmasq',
        ]
        removed_obsolete = 0
        for line in content.split('\n'):
            stripped = line.strip()
            # Remove obsolete Tor references
            if any(pattern in stripped for pattern in OBSOLETE_PATTERNS):
                removed_obsolete += 1
                continue
            if stripped.startswith('server=/'):
                lines.append(line)
            elif stripped.startswith('server='):
                removed_servers += 1
                pass
            else:
                lines.append(line)

        if removed_obsolete > 0:
            logger.info(f"[DNS] Removed {removed_obsolete} obsolete lines (Tor references)")

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
    Optimized: reduced timeout and added early exit for faster response.

    Args:
        host: DNS server IP
        port: DNS port (default 53)
        timeout: Timeout in seconds

    Returns:
        Dict with success, latency_ms, error
    """
    start_time = time.time()
    sock = None
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))

        latency_ms = (time.time() - start_time) * 1000

        if result == 0:
            sock.close()
            return {
                'success': True,
                'latency_ms': round(latency_ms, 2),
                'host': host,
                'port': port,
            }
        else:
            sock.close()
            return {
                'success': False,
                'latency_ms': round(latency_ms, 2),
                'host': host,
                'port': port,
                'error': f'Connection failed (code {result})',
            }

    except socket.timeout:
        if sock:
            sock.close()
        return {
            'success': False,
            'latency_ms': round((time.time() - start_time) * 1000, 2),
            'host': host,
            'port': port,
            'error': 'Timeout',
        }
    except Exception as e:
        if sock:
            sock.close()
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
        """Background monitoring loop - optimized for low CPU usage"""
        logger.info("DNSMonitor loop started")
        check_count = 0

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
                        # Логируем только каждый 10-й успешный check для снижения нагрузки на I/O
                        check_count += 1
                        if check_count % 10 == 0:
                            logger.debug(f"DNS check OK: {self._current_server['name']} ({result['latency_ms']}ms)")
                    else:
                        self._failures += 1
                        logger.warning(f"DNS check failed: {self._current_server['name']} - {result['error']} (failures: {self._failures}/{FAILURE_THRESHOLD})")

                        if self._failures >= FAILURE_THRESHOLD:
                            logger.warning(f"DNS failure threshold reached, switching to backup")
                            self._switch_to_backup()

                else:
                    logger.info("No current DNS server, selecting best primary")
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
            # FIX: Не перезаписываем dnsmasq.conf при каждом запуске.
            # dnsmasq уже настроен на 1.1.1.1 + 8.8.8.8 в dnsmasq.conf.
            # Автоматическая перезапись может ломать DNS если провайдер блокирует Cloudflare.
            # Мониторинг только логирует статус, НЕ меняет конфиг.
            logger.debug(f"[DNS] Not updating dnsmasq config — using pre-configured DNS servers")
        else:
            self._switch_to_backup()

    def _switch_to_backup(self) -> None:
        """Switch to backup DNS server (only for monitoring, not config update)."""
        logger.warning("Switching to backup DNS")

        for server in self._servers['backup']:
            result = check_dns_server(server['host'], server['port'], TIMEOUT)
            if result['success']:
                self._current_server = server
                self._failures = 0
                # FIX: Не перезаписываем dnsmasq.conf — только меняем внутреннее состояние
                logger.info(f"Monitoring switched to backup DNS: {server['name']}")
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
    Resolve a single domain to IP addresses using socket.getaddrinfo.

    Args:
        domain: Domain name to resolve
        timeout: Resolution timeout in seconds (default: 5.0)

    Returns:
        List of IP addresses
    """
    # Skip wildcard domains (*.example.com) — DNS cannot resolve them
    if domain.startswith('*.'):
        return []
    # Skip domains with @ads suffix (tracking/ads lists)
    if ' @ads' in domain or ' @trackers' in domain:
        return []

    try:
        # FIX: Use socket.getaddrinfo instead of nslookup subprocess
        # nslookup on BusyBox often fails or has different output format
        socket.setdefaulttimeout(timeout)
        results = socket.getaddrinfo(domain, None, socket.AF_INET, socket.SOCK_STREAM)
        ips = list(set(r[4][0] for r in results))
        logger.debug(f"Resolved {domain} -> {ips}")
        return ips
    except socket.gaierror as e:
        logger.debug(f"Failed to resolve {domain}: {e}")
        return []
    except socket.timeout:
        logger.debug(f"Timeout resolving {domain}")
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


def resolve_domains_for_ipset(filepath: str, max_workers: int = MAX_WORKERS, ipset_name: Optional[str] = None) -> int:
    """
    Resolve domains from bypass list file and add to ipset.

    Args:
        filepath: Path to bypass list file
        max_workers: Parallel workers (default: 10)
        ipset_name: Target ipset name (auto-detect from filepath if None)

    Returns:
        Number of IPs added to ipset
    """
    from .utils import load_bypass_list
    from .ipset_ops import bulk_add_to_ipset, ensure_ipset_exists

    entries = load_bypass_list(filepath)
    domains = [e for e in entries if not is_ip_address(e)]

    if not domains:
        logger.info(f"No domains to resolve in {filepath}")
        return 0

    # Auto-detect ipset name from filepath
    if ipset_name is None:
        filename = Path(filepath).stem  # e.g. "vless" from "vless.txt"
        ipset_name = IPSET_MAP.get(filename, f'unblock{filename}')

    BATCH_SIZE = 500
    total_ips_added = 0

    for i in range(0, len(domains), BATCH_SIZE):
        batch_domains = domains[i:i + BATCH_SIZE]
        resolved = parallel_resolve(batch_domains, max_workers)

        batch_ips = set()
        for domain, ips in resolved.items():
            batch_ips.update(ips)

        if batch_ips:
            ensure_ipset_exists(ipset_name)
            success, msg = bulk_add_to_ipset(ipset_name, list(batch_ips))
            if success:
                total_ips_added += len(batch_ips)
                logger.info(f"Batch {i // BATCH_SIZE + 1}: added {len(batch_ips)} IPs to {ipset_name}")
            else:
                logger.error(f"Failed to add batch IPs: {msg}")

    logger.info(f"Total: added {total_ips_added} resolved IPs to ipset {ipset_name}")
    return total_ips_added
