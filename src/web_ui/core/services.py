"""
FlyMyByte Web Interface - Service Aggregator

This module imports from specialized modules for backward compatibility.
Moved to separate modules: parsers.py, service_ops.py, ipset_ops.py
"""
import os
import time
import json
import logging
import subprocess
import threading
import re
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple

from .utils import Cache, logger
from .parsers import (
    parse_vless_key,
    vless_config,
    parse_shadowsocks_key,
    shadowsocks_config,
    parse_trojan_key,
    trojan_config,
    parse_proxy_key,
    proxy_config,
)

from .service_ops import (
    restart_service,
    check_service_status,
)

from .ipset_ops import (
    bulk_add_to_ipset,
    bulk_remove_from_ipset,
    ensure_ipset_exists,
)


def refresh_ipset_from_file(filepath: str, ipset_name: str = None) -> Tuple[bool, str]:
    """Refresh ipset from bypass list file (CIDR + IP напрямую, домены через dnsmasq).

    Гарантированный flush перед добавлением:
    1. Подсчёт текущих записей
    2. Flush (ipset -F)
    3. Если flush неудачен — recreate (destroy + create)
    4. Проверка flush (0 записей)
    5. Загрузка CIDR/IP из файла (домены обрабатываются dnsmasq через ipset= rules)
    6. Логирование счётчиков до/после
    """
    from .app_config import WebConfig
    from .dns_ops import resolve_domains_for_ipset
    from .constants import IPSET_MAP

    config = WebConfig()
    real_path = os.path.realpath(filepath)
    real_dir = os.path.realpath(config.unblock_dir)
    if not real_path.startswith(real_dir + os.sep):
        return False, "Invalid file path"

    if not os.path.exists(filepath):
        logger.warning(f"File not found: {filepath}")
        return False, f"File not found: {filepath}"

    # Auto-detect ipset name
    if ipset_name is None:
        filename = os.path.basename(filepath).replace('.txt', '')
        ipset_name = IPSET_MAP.get(filename, f'unblock{filename}')

    # --- Step 1: Count entries BEFORE flush ---
    def count_ipset_entries(name: str) -> int:
        """Count entries in an ipset by counting lines starting with digits."""
        try:
            result = subprocess.run(
                ['ipset', '-L', name],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                return len([
                    line for line in result.stdout.splitlines()
                    if re.match(r'^[0-9]', line)
                ])
            return -1
        except Exception as e:
            logger.warning(f"[IPSET] count_ipset_entries exception for {name}: {e}")
            return -1

    entries_before = count_ipset_entries(ipset_name)
    logger.info(f"[IPSET] Refresh: {ipset_name} has {entries_before} entries before flush")

    # --- Step 2: Flush ipset ---
    flush_ok = False
    try:
        logger.info(f"[IPSET] Flushing {ipset_name}...")
        result = subprocess.run(
            ['ipset', '-F', ipset_name],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            logger.info(f"[IPSET] Flush succeeded for {ipset_name}")
            flush_ok = True
        else:
            logger.warning(f"[IPSET] Flush failed for {ipset_name}: {result.stderr.strip()[:150]}")
    except subprocess.TimeoutExpired:
        logger.warning(f"[IPSET] Flush timeout for {ipset_name}")
    except Exception as e:
        logger.warning(f"[IPSET] Flush exception for {ipset_name}: {e}")

    # --- Step 3: If flush failed — recreate ipset ---
    if not flush_ok:
        logger.warning(f"[IPSET] Flush failed, attempting recreate for {ipset_name}")
        try:
            # Destroy
            logger.info(f"[IPSET] Destroying {ipset_name}...")
            destroy_result = subprocess.run(
                ['ipset', 'destroy', ipset_name],
                capture_output=True, text=True, timeout=10
            )
            if destroy_result.returncode != 0:
                logger.warning(
                    f"[IPSET] Destroy failed for {ipset_name}: "
                    f"{destroy_result.stderr.strip()[:150]}"
                )
                # Destroy may fail if referenced by iptables; try flush again
                logger.info(f"[IPSET] Retrying flush after destroy failure...")
                retry = subprocess.run(
                    ['ipset', '-F', ipset_name],
                    capture_output=True, text=True, timeout=10
                )
                if retry.returncode == 0:
                    flush_ok = True
                    logger.info(f"[IPSET] Retry flush succeeded for {ipset_name}")
                else:
                    logger.error(f"[IPSET] Retry flush also failed: {retry.stderr.strip()[:150]}")
            else:
                # Create
                logger.info(f"[IPSET] Recreating {ipset_name}...")
                create_result = subprocess.run(
                    ['ipset', 'create', ipset_name, 'hash:ip', 'maxelem', '1048576'],
                    capture_output=True, text=True, timeout=10
                )
                if create_result.returncode == 0:
                    flush_ok = True
                    logger.info(f"[IPSET] Recreate succeeded for {ipset_name}")
                else:
                    logger.error(
                        f"[IPSET] Create failed for {ipset_name}: "
                        f"{create_result.stderr.strip()[:150]}"
                    )
        except subprocess.TimeoutExpired:
            logger.warning(f"[IPSET] Recreate timeout for {ipset_name}")
        except Exception as e:
            logger.error(f"[IPSET] Recreate exception for {ipset_name}: {e}")

    # --- Step 4: Verify flush ---
    entries_after_flush = count_ipset_entries(ipset_name)
    if entries_after_flush == 0:
        logger.info(f"[IPSET] Verified: {ipset_name} is empty after flush")
    elif entries_after_flush > 0:
        logger.warning(
            f"[IPSET] Warning: {ipset_name} still has {entries_after_flush} entries after flush — "
            f"entries will accumulate (known limitation: ipset may be referenced by iptables)"
        )
    else:
        logger.warning(f"[IPSET] Could not verify flush result for {ipset_name}")

    # --- Step 5: Add CIDR/IP from file to ipset (domains handled by dnsmasq) ---
    try:
        logger.info(f"[IPSET] Loading entries from file: {filepath}")
        count = resolve_domains_for_ipset(filepath, ipset_name)

        # --- Step 6: Count entries AFTER refresh ---
        entries_final = count_ipset_entries(ipset_name)
        logger.info(
            f"[IPSET] Refresh complete: было {entries_before}, стало {entries_final} записей "
            f"({count} IPs resolved from {filepath})"
        )

        return True, f"Refresh: было {entries_before}, стало {entries_final} записей ({count} resolved)"
    except Exception as e:
        logger.error(f"[IPSET] Refresh failed for {filepath}: {e}")
        return False, str(e)


def write_json_config(config: Dict[str, Any], filepath: str) -> None:
    """Write configuration to JSON file atomically."""
    logger.debug(f"write_json_config: writing to {filepath}")
    temp_path = filepath + '.tmp'

    try:
        os.makedirs(os.path.dirname(filepath), exist_ok=True)

        with open(temp_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)

        os.replace(temp_path, filepath)
        logger.debug(f"write_json_config: config written to {filepath}")

    except Exception as e:
        logger.exception(f"write_json_config: error writing config: {e}")
        try:
            if os.path.exists(temp_path):
                os.remove(temp_path)
        except Exception:
            logger.warning(f"write_json_config: failed to remove temp file {temp_path}")
        raise


def get_local_version():
    """Получить локальную версию"""
    version_file = '/opt/etc/web_ui/VERSION'
    try:
        with open(version_file, 'r', encoding='utf-8') as f:
            return f.read().strip()
    except FileNotFoundError:
        local_version_file = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'VERSION')
        if os.path.exists(local_version_file):
            try:
                with open(local_version_file, 'r', encoding='utf-8') as f:
                    return f.read().strip()
            except Exception:
                pass
        return 'N/A'


def get_remote_version():
    """Получить удалённую версию с GitHub"""
    import requests
    try:
        github_repo = 'royfincher25-source/flymybyte'
        github_branch = 'master'
        url = f'https://raw.githubusercontent.com/{github_repo}/{github_branch}/VERSION'
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            return response.text.strip()
        return 'N/A'
    except Exception as e:
        logger.error(f'Error fetching remote version: {e}')
        return 'N/A'


LIST_CATALOG: Dict[str, Dict[str, Any]] = {
    'anticensor': {
        'name': 'Антицензор',
        'description': 'Обход блокировок Роскомнадзора',
        'url': 'https://raw.githubusercontent.com/zhovner/zaborona_help/master/hosts.txt',
        'format': 'hosts',
    },
    'reestr': {
        'name': 'Реестр запрещённых сайтов',
        'description': 'Официальный реестр запрещённых сайтов РФ',
        'url': 'https://raw.githubusercontent.com/zhovner/zaborona_help/master/reestr.txt',
        'format': 'domains',
    },
    'social': {
        'name': 'Соцсети',
        'description': 'Facebook, Instagram, Twitter, TikTok',
        'domains': [
            'facebook.com',
            'instagram.com',
            'twitter.com',
            'tiktok.com',
            'whatsapp.com',
            'telegram.org',
        ],
        'format': 'domains',
    },
    'streaming': {
        'name': 'Стриминговые сервисы',
        'description': 'Netflix, Spotify, Disney+',
        'domains': [
            'netflix.com',
            'spotify.com',
            'disneyplus.com',
            'hulu.com',
            'amazonprime.com',
        ],
        'format': 'domains',
    },
    'torrents': {
        'name': 'Торрент-трекеры',
        'description': 'RuTracker, ThePirateBay, 1337x',
        'domains': [
            'rutracker.org',
            'thepiratebay.org',
            '1337x.to',
            'torrentz2.eu',
        ],
        'format': 'domains',
    },
}


def get_catalog() -> Dict[str, Dict[str, Any]]:
    """Get full catalog"""
    return LIST_CATALOG


def _parse_list_content(content: str, fmt: str) -> List[str]:
    """Parse list content based on format."""
    domains = []

    for line in content.split('\n'):
        line = line.strip()

        if not line or line.startswith('#'):
            continue

        if fmt == 'hosts':
            parts = line.split()
            if len(parts) >= 2 and not parts[0].startswith('#'):
                domain = parts[1]
                if domain != 'localhost':
                    domains.append(domain)
        else:
            domains.append(line)

    return domains


def download_list(name: str, dest_dir: str) -> tuple:
    """Download list from catalog and save to file."""
    if name not in LIST_CATALOG:
        return False, f"List '{name}' not found", 0

    list_info = LIST_CATALOG[name]
    filename = f"{name}.txt"
    filepath = os.path.join(dest_dir, filename)

    try:
        if 'url' in list_info:
            logger.info(f"Downloading {name} from {list_info['url']}")
            import requests
            response = requests.get(list_info['url'], timeout=30)
            response.raise_for_status()
            domains = _parse_list_content(response.text, list_info['format'])

        elif 'domains' in list_info:
            domains = list_info['domains']

        else:
            return False, "No data source", 0

        temp_path = filepath + '.tmp'
        with open(temp_path, 'w', encoding='utf-8') as f:
            for domain in domains:
                f.write(f"{domain}\n")

        os.replace(temp_path, filepath)

        logger.info(f"Saved {len(domains)} domains to {filepath}")
        return True, f"Downloaded {len(domains)} domains", len(domains)

    except requests.RequestException as e:
        logger.error(f"Download error: {e}")
        return False, f"Download error: {e}", 0
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return False, str(e), 0


try:
    from .constants import (
        AI_DOMAINS_LIST,
        DNSMASQ_AI_CONFIG,
        VPN_DNS_HOST,
        VPN_DNS_PORT,
        MAX_DOMAIN_LENGTH,
        MAX_DOMAINS_COUNT,
        INIT_SCRIPTS,
    )
except ImportError:
    from constants import (
        AI_DOMAINS_LIST,
        DNSMASQ_AI_CONFIG,
        VPN_DNS_HOST,
        VPN_DNS_PORT,
        MAX_DOMAIN_LENGTH,
        MAX_DOMAINS_COUNT,
        INIT_SCRIPTS,
    )


class DNSSpoofing:
    """DNS Spoofing for AI domain bypass."""

    _instance: Optional['DNSSpoofing'] = None
    _lock = threading.Lock()

    def __new__(cls) -> 'DNSSpoofing':
        """Singleton pattern with thread safety"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize DNS spoofing module"""
        if hasattr(self, '_initialized'):
            return

        self._domains: List[str] = []
        self._enabled: bool = False
        self._config_path = DNSMASQ_AI_CONFIG
        self._domains_path = AI_DOMAINS_LIST

        self._initialized = True
        logger.info("[DNS-SPOOF] DNSSpoofing initialized")

    def load_domains(self) -> List[str]:
        """Load AI domains from list file."""
        domains = []
        domains_path = Path(self._domains_path)

        if not domains_path.exists():
            logger.warning(f"[DNS-SPOOF] AI domains list not found: {self._domains_path}")
            return []

        try:
            content = domains_path.read_text(encoding='utf-8')
            logger.debug(f"[DNS-SPOOF] Read {len(content)} bytes from {self._domains_path}")

            for line in content.splitlines():
                line = line.strip()

                if not line or line.startswith('#'):
                    continue

                if line.startswith('*.'):
                    line = line[2:]

                if self._is_ip_address(line):
                    logger.debug(f"[DNS-SPOOF] Skipping IP address: {line}")
                    continue

                if self._validate_domain(line):
                    domains.append(line)
                else:
                    logger.warning(f"[DNS-SPOOF] Invalid domain skipped: {line}")

            if len(domains) > MAX_DOMAINS_COUNT:
                logger.warning(f"[DNS-SPOOF] Too many domains ({len(domains)}), limiting to {MAX_DOMAINS_COUNT}")
                domains = domains[:MAX_DOMAINS_COUNT]

            self._domains = domains
            logger.info(f"[DNS-SPOOF] Loaded {len(domains)} AI domains from {self._domains_path}")

        except Exception as e:
            logger.error(f"[DNS-SPOOF] Error loading AI domains: {e}")
            return []

        return domains

    def _validate_domain(self, domain: str) -> bool:
        """Validate domain name format."""
        if not domain:
            return False

        if len(domain) > MAX_DOMAIN_LENGTH:
            return False

        pattern = r'^[a-zA-Z0-9]([a-zA-Z0-9\-]*[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]*[a-zA-Z0-9])?)+$'
        return bool(re.match(pattern, domain))

    def _is_ip_address(self, entry: str) -> bool:
        """Check if entry is an IP address."""
        ip_pattern = r'^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}$'
        return bool(re.match(ip_pattern, entry))

    def generate_config(self, domains: Optional[List[str]] = None) -> str:
        """Generate dnsmasq configuration for AI domains."""
        if domains is None:
            domains = self.load_domains()

        if not domains:
            logger.warning("[DNS-SPOOF] No domains to generate config for")
            return ""

        lines = [
            "# AI Domains DNS Spoofing",
            "# Generated by dns_spoofing.py",
            f"# Domains count: {len(domains)}",
            "",
        ]

        for domain in domains:
            lines.append(f"server=/{domain}/{VPN_DNS_HOST}#{VPN_DNS_PORT}")

        config = '\n'.join(lines)
        logger.info(f"[DNS-SPOOF] Generated config: {len(domains)} domains, {len(lines)} lines")
        return config

    def write_config(self, config: str) -> Tuple[bool, str]:
        """Write dnsmasq configuration to file (atomic write)."""
        config_path = Path(self._config_path)

        try:
            config_path.parent.mkdir(parents=True, exist_ok=True)

            tmp_path = config_path.with_suffix('.tmp')
            tmp_path.write_text(config, encoding='utf-8')
            tmp_path.replace(config_path)

            logger.info(f"[DNS-SPOOF] Written AI domains config to {self._config_path} ({len(config)} bytes)")
            return True, "OK"

        except Exception as e:
            error_msg = f"Error writing config: {e}"
            logger.error(f"[DNS-SPOOF] {error_msg}")
            return False, error_msg

    def apply_config(self) -> Tuple[bool, str]:
        """Apply dnsmasq configuration and restart dnsmasq."""
        domains = self.load_domains()

        if not domains:
            error_msg = "No AI domains to apply"
            logger.warning(error_msg)
            return False, error_msg

        config = self.generate_config(domains)

        if not config:
            error_msg = "Failed to generate config"
            logger.error(error_msg)
            return False, error_msg

        success, msg = self.write_config(config)

        if not success:
            return False, msg

        success, msg = self._restart_dnsmasq()

        if success:
            self._enabled = True
            logger.info(f"AI domains DNS spoofing enabled ({len(domains)} domains)")
            return True, f"Enabled ({len(domains)} domains)"
        else:
            logger.error(f"Failed to restart dnsmasq: {msg}")
            return False, msg

    def _restart_dnsmasq(self) -> Tuple[bool, str]:
        """Restart dnsmasq service using SIGHUP to reload config."""
        try:
            pid_result = subprocess.run(
                ['pgrep', 'dnsmasq'],
                capture_output=True,
                text=True,
                timeout=5
            )

            if pid_result.returncode == 0 and pid_result.stdout.strip():
                pid = pid_result.stdout.strip().split('\n')[0]
                logger.debug(f"Sending SIGHUP to dnsmasq (PID {pid})")
                kill_result = subprocess.run(
                    ['kill', '-HUP', pid],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if kill_result.returncode == 0:
                    time.sleep(1)
                    logger.info("dnsmasq config reloaded via SIGHUP")
                    return True, "OK"
                else:
                    error_msg = kill_result.stderr.strip() or "kill -HUP failed"
                    logger.error(f"dnsmasq SIGHUP failed: {error_msg}")
                    return False, error_msg
            else:
                dnsmasq_init = INIT_SCRIPTS['dnsmasq']
                if not Path(dnsmasq_init).exists():
                    logger.warning("dnsmasq init script not found")
                    return False, "dnsmasq not installed"

                result = subprocess.run(
                    [dnsmasq_init, 'start'],
                    capture_output=True,
                    text=True,
                    timeout=10
                )

                if result.stdout.strip():
                    logger.debug(f"dnsmasq start stdout: {result.stdout.strip()}")
                if result.stderr.strip():
                    logger.debug(f"dnsmasq start stderr: {result.stderr.strip()}")
                logger.debug(f"dnsmasq start returncode: {result.returncode}")

                time.sleep(1)
                dnsmasq_running = self._check_dnsmasq_status()

                if dnsmasq_running:
                    logger.info("dnsmasq started successfully")
                    return True, "OK"
                else:
                    error_msg = result.stderr.strip() or result.stdout.strip() or "Unknown error"
                    logger.error(f"dnsmasq start failed: returncode={result.returncode}, stdout='{result.stdout.strip()}', stderr='{result.stderr.strip()}'")
                    return False, f"dnsmasq not running after start: {error_msg}"

        except subprocess.TimeoutExpired:
            error_msg = "dnsmasq operation timeout"
            logger.error(error_msg)
            return False, error_msg

        except Exception as e:
            error_msg = f"Error restarting dnsmasq: {e}"
            logger.error(error_msg)
            return False, error_msg

    def disable(self) -> Tuple[bool, str]:
        """Disable DNS spoofing (remove config and reload dnsmasq)."""
        config_path = Path(self._config_path)

        try:
            if config_path.exists():
                config_path.unlink()
                logger.info(f"Removed AI domains config: {self._config_path}")

            try:
                pid_result = subprocess.run(
                    ['pgrep', 'dnsmasq'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )

                if pid_result.returncode == 0 and pid_result.stdout.strip():
                    pid = pid_result.stdout.strip().split('\n')[0]
                    subprocess.run(
                        ['kill', '-HUP', pid],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    time.sleep(1)
                    logger.info("AI domains DNS spoofing disabled (dnsmasq reloaded via SIGHUP)")
                else:
                    logger.warning("dnsmasq not running, config removed — restart manually if needed")
            except Exception as e:
                logger.warning(f"Error during dnsmasq reload after config removal: {e}")

            self._enabled = False
            self._domains = []
            return True, "Disabled"

        except Exception as e:
            error_msg = f"Error disabling DNS spoofing: {e}"
            logger.error(error_msg)
            return False, error_msg

    def get_status(self) -> Dict[str, Any]:
        """Get current DNS spoofing status."""
        config_path = Path(self._config_path)
        domains_path = Path(self._domains_path)

        config_has_content = False
        if config_path.exists():
            try:
                content = config_path.read_text(encoding='utf-8')
                config_has_content = bool(re.search(r'^server=/', content, re.MULTILINE))
            except Exception:
                pass

        if not self._domains and domains_path.exists():
            self.load_domains()

        dnsmasq_running = self._check_dnsmasq_status()

        return {
            'enabled': self._enabled or config_has_content,
            'domain_count': len(self._domains),
            'config_exists': config_has_content,
            'dnsmasq_running': dnsmasq_running,
            'config_path': self._config_path,
            'domains_path': self._domains_path,
        }

    def _check_dnsmasq_status(self) -> bool:
        """Check if dnsmasq is running."""
        try:
            result = subprocess.run(
                ['pgrep', 'dnsmasq'],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except Exception:
            return False

    def test_domain(self, domain: str) -> Dict[str, Any]:
        """Test DNS resolution for a domain."""
        result = {
            'domain': domain,
            'resolved': False,
            'ips': [],
            'dns_server': f'{VPN_DNS_HOST}:{VPN_DNS_PORT}',
            'error': None,
        }

        try:
            try:
                proc_result = subprocess.run(
                    ['nslookup', domain, VPN_DNS_HOST],
                    capture_output=True,
                    text=True,
                    timeout=5
                )

                if proc_result.returncode == 0:
                    ips = re.findall(
                        r'Address(?:es)?\s*\d*:\s*([0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3})',
                        proc_result.stdout
                    )
                    ips = [ip for ip in ips if ip != VPN_DNS_HOST]
                    ips = list(set(ips))

                    if ips:
                        result['resolved'] = True
                        result['ips'] = ips
                        result['dns_server'] = f'{VPN_DNS_HOST}:{VPN_DNS_PORT} (VPN)'
                        return result

            except Exception as e:
                logger.debug(f"test_domain nslookup error for {domain}: {e}")

            try:
                import socket
                addr_info = socket.getaddrinfo(domain, None)
                ips = list(set(info[4][0] for info in addr_info))
                if ips:
                    result['resolved'] = True
                    result['ips'] = ips
                    result['dns_server'] = 'system default'
                    return result
            except Exception as e:
                result['error'] = str(e)

        except Exception as e:
            result['error'] = str(e)
            logger.error(f"test_domain error for {domain}: {e}")

        return result


def apply_dns_spoofing() -> Tuple[bool, str]:
    """Apply DNS spoofing (singleton convenience)."""
    return DNSSpoofing().apply_config()


def disable_dns_spoofing() -> Tuple[bool, str]:
    """Disable DNS spoofing (singleton convenience)."""
    return DNSSpoofing().disable()


def get_dns_spoofing_status() -> Dict[str, Any]:
    """Get DNS spoofing status (singleton convenience)."""
    return DNSSpoofing().get_status()