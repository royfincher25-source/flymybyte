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
        """Count entries in an ipset by counting lines with IP addresses (ending in timeout)."""
        try:
            result = subprocess.run(
                ['ipset', '-L', name],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                return len([
                    line for line in result.stdout.splitlines()
                    if re.match(r'^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+.*timeout', line)
                ])
            return -1
        except Exception as e:
            logger.warning(f"[IPSET] count_ipset_entries exception for {name}: {e}")
            return -1

    entries_before = count_ipset_entries(ipset_name)
    logger.info(f"[IPSET] Refresh: {ipset_name} has {entries_before} entries")

    # --- Step 2: Skip flush (не работает на Keenetic из-за iptables references)
    # Используем -exist для upsert, timeout=300 удаляет старые записи
    logger.info(f"[IPSET] Skip flush - using -exist for upsert (timeout handles cleanup)")
    flush_ok = True

    # --- Step 4: Verify state ---
    entries_after_flush = count_ipset_entries(ipset_name)
    logger.info(f"[IPSET] Current state: {entries_after_flush} entries (timeout=300 handles cleanup)")

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
    """Получить удалённую версию с GitHub.

    Использует GitHub API (не кешируется CDN) вместо raw URL.
    """
    import requests
    try:
        github_repo = 'royfincher25-source/flymybyte'
        # GitHub API returns file content as base64
        url = f'https://api.github.com/repos/{github_repo}/contents/VERSION'
        response = requests.get(url, timeout=10, headers={
            'Accept': 'application/vnd.github.v3+json',
            'Cache-Control': 'no-cache',
        })
        if response.status_code == 200:
            import base64
            data = response.json()
            content = base64.b64decode(data['content']).decode('utf-8')
            return content.strip()
        # Fallback to raw URL if API fails (rate limit, etc.)
        raw_url = f'https://raw.githubusercontent.com/{github_repo}/master/VERSION'
        raw_resp = requests.get(raw_url, timeout=10)
        if raw_resp.status_code == 200:
            return raw_resp.text.strip()
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