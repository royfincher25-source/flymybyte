"""
Bypass Keenetic Web Interface - Key Parsers and Service Management

Full-featured parsers for VPN keys (VLESS, Shadowsocks, Trojan, Tor).
Memory-optimized for embedded devices (128MB RAM).

Note: Parsers have been extracted to core/parsers/ module.
This file maintains backwards compatibility.
"""
import os
import re
import json
import base64
import logging
import subprocess
import hashlib
from urllib.parse import urlparse, unquote, parse_qs
from typing import Dict, Any, Optional, Tuple

from .utils import Cache, logger
from .parsers.vless_parser import VlessParser
from .parsers.shadowsocks_parser import ShadowsocksParser
from .parsers.trojan_parser import TrojanParser


# =============================================================================
# VLESS PARSER (delegates to core/parsers)
# =============================================================================

def parse_vless_key(key: str) -> Dict[str, Any]:
    """Parse VLESS key - delegates to VlessParser"""
    return VlessParser.parse(key)


def vless_config(key: str) -> Dict[str, Any]:
    """Generate VLESS configuration - delegates to VlessParser"""
    return VlessParser.generate_config(key)


# =============================================================================
# SHADOWSOCKS PARSER (delegates to core/parsers)
# =============================================================================

def parse_shadowsocks_key(key: str) -> Dict[str, Any]:
    """Parse Shadowsocks key - delegates to ShadowsocksParser"""
    return ShadowsocksParser.parse(key)


def shadowsocks_config(key: str) -> Dict[str, Any]:
    """Generate Shadowsocks configuration - delegates to ShadowsocksParser"""
    return ShadowsocksParser.generate_config(key)


# =============================================================================
# TROJAN PARSER (delegates to core/parsers)
# =============================================================================

def parse_trojan_key(key: str) -> Dict[str, Any]:
    """Parse Trojan key - delegates to TrojanParser"""
    return TrojanParser.parse(key)


def trojan_config(key: str) -> Dict[str, Any]:
    """Generate Trojan configuration - delegates to TrojanParser"""
    return TrojanParser.generate_config(key)


# =============================================================================
# HYSTERIA 2 PARSER
# =============================================================================

def parse_hysteria2_key(key: str) -> Dict[str, Any]:
    """
    Parse Hysteria 2 key.
    
    Format: hysteria2://[password]:[sni]@[server]:[port]?[params]#name
    
    Examples:
        hysteria2://mypassword@server.com:443#MyVPN
        hysteria2://mypassword@sni.com@server.com:443?insecure=0#MyVPN
        hysteria2://obfsPassword@sni.com@server.com:443?insecure=0&obfs=sensitive&obfspwd=obfsPassword#MyVPN
    
    Args:
        key: Hysteria 2 key string
    
    Returns:
        Dict with parsed configuration
    
    Raises:
        ValueError: If key format is invalid
    """
    cache_key = f'hysteria2:{hashlib.md5(key.encode()).hexdigest()}'
    
    if Cache.is_valid(cache_key):
        logger.info(f"Hysteria2 cache hit: {cache_key[:20]}...")
        return Cache.get(cache_key)
    
    if not key.startswith('hysteria2://'):
        raise ValueError("Неверный формат ключа Hysteria 2")
    
    key = key.strip()
    key = ''.join(c for c in key if ord(c) >= 32 or c in '\t\n\r')
    key = unquote(key)
    
    try:
        key = key.encode('ascii', 'ignore').decode('ascii')
    except Exception as e:
        logger.error(f"Hysteria2 ASCII encode error: {e}")
    
    logger.info(f"Hysteria2 normalized key: {key[:80]}...")
    
    url = key[11:]
    parsed = urlparse(url)
    
    if not parsed.hostname:
        raise ValueError("Сервер не найден в ключе")
    
    if not parsed.port:
        raise ValueError("Порт не найден в ключе")
    
    auth_info = parsed.username or ''
    if '@' in auth_info:
        auth_parts = auth_info.rsplit('@', 1)
        password = auth_parts[0]
        sni = auth_parts[1] if auth_parts[1] else parsed.hostname
    else:
        password = auth_info
        sni = parsed.hostname
    
    if not password:
        raise ValueError("Пароль не найден в ключе")
    
    params = parse_qs(parsed.query)
    
    result = {
        'password': password,
        'server': parsed.hostname,
        'port': parsed.port,
        'sni': sni,
        'insecure': params.get('insecure', ['0'])[0] == '1',
        'obfs': params.get('obfs', [''])[0],
        'obfs_password': params.get('obfspwd', [''])[0],
        'name': parsed.fragment or 'Hysteria2',
    }
    
    Cache.set(cache_key, result)
    logger.info(f"parse_hysteria2_key: parsed {result['server']}:{result['port']}")
    
    return result


def hysteria2_config(key: str) -> Dict[str, Any]:
    """
    Generate Hysteria 2 configuration from key.

    Args:
        key: Hysteria 2 key string

    Returns:
        Dict with full configuration for hysteria server
    """
    logger.debug("hysteria2_config: parsing key")

    parsed = parse_hysteria2_key(key)

    config = {
        'server': f"{parsed['server']}:{parsed['port']}",
        'auth': {
            'type': 'password',
            'password': parsed['password'],
        },
        'tls': {
            'enabled': True,
            'insecure': parsed['insecure'],
            'sni': parsed['sni'],
            'alpn': ['h3'],
        },
        'bandwidth': None,
        'socks5': {
            'listen': '127.0.0.1:1080',
        },
        'http': {
            'listen': '127.0.0.1:8080',
        },
    }

    if parsed['obfs'] and parsed['obfs_password']:
        config['obfs'] = {
            'type': parsed['obfs'],
            'password': parsed['obfs_password'],
        }

    logger.debug("hysteria2_config: generated")
    return config


def write_hysteria2_config(config: Dict[str, Any], filepath: str) -> None:
    """
    Write Hysteria 2 configuration to file.
    
    Args:
        config: Configuration dict
        filepath: Path to write config
    """
    logger.info(f"write_hysteria2_config: writing to {filepath}")
    
    try:
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        temp_path = filepath + '.tmp'
        
        with open(temp_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        
        os.replace(temp_path, filepath)
        logger.info(f"write_hysteria2_config: config written to {filepath}")
        
    except Exception as e:
        logger.error(f"write_hysteria2_config: error writing config: {e}")
        raise


# =============================================================================
# TOR PARSER
# =============================================================================

def parse_tor_bridges(bridges_text: str) -> list:
    """
    Parse Tor bridge lines.
    
    Format: bridge [transport] IP:ORPort [fingerprint] [options]
    
    Args:
        bridges_text: Multi-line string with bridge entries
    
    Returns:
        List of valid bridge entries
    """
    bridges = []
    
    for line in bridges_text.strip().split('\n'):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        
        # Validate bridge format
        if line.startswith('bridge '):
            bridges.append(line)
        elif ':' in line and '.' in line:
            # Try to parse as IP:Port
            bridges.append(f'bridge {line}')
    
    logger.info(f"Tor bridges parsed: {len(bridges)} entries")
    return bridges


def tor_config(bridges_text: str) -> Dict[str, Any]:
    """
    Generate Tor configuration from bridges.
    
    Args:
        bridges_text: Multi-line string with bridge entries
    
    Returns:
        Dict with Tor configuration
    """
    logger.info(f"tor_config: вызов с мостами")
    
    bridges = parse_tor_bridges(bridges_text)
    
    config = {
        'ClientOnly': 1,
        'SOCKSPort': '127.0.0.1:9141',
        'DNSPort': '127.0.0.1:9053',
        'Log': 'notice file /opt/var/log/tor.log',
        'DataDirectory': '/opt/var/lib/tor',
        'GeoIPFile': '/opt/share/tor/geoip',
        'GeoIPv6File': '/opt/share/tor/geoip6',
    }
    
    if bridges:
        config['UseBridges'] = 1
        for bridge in bridges:
            config[f'Bridge'] = bridge.replace('bridge ', '')

    logger.debug(f"tor_config: generated ({len(bridges)} bridges)")
    return config


# =============================================================================
# SERVICE MANAGEMENT
# =============================================================================

def restart_service(service_name: str, init_script: str) -> Tuple[bool, str]:
    """
    Restart a service using init script.

    Args:
        service_name: Human-readable service name
        init_script: Path to init script

    Returns:
        Tuple of (success: bool, output: str)
    """
    logger.info(f"restart_service: {service_name} via {init_script}")

    if not os.path.exists(init_script):
        logger.error(f"Init script not found: {init_script}")
        return False, f"Скрипт {init_script} не найден"

    logger.info(f"restart_service: running ['sh', {init_script}, 'restart']")
    try:
        result = subprocess.run(
            ['sh', init_script, 'restart'],
            capture_output=True,
            text=True,
            timeout=60
        )
        logger.info(f"restart_service: {service_name} completed with returncode={result.returncode}")

        success = result.returncode == 0
        output = result.stdout.strip() or result.stderr.strip()

        if success:
            logger.info(f"{service_name} restarted successfully: {output}")
        else:
            logger.error(f"{service_name} restart failed: {output}")

        return success, output

    except subprocess.TimeoutExpired:
        logger.error(f"{service_name} restart timed out")
        return False, "Превышено время ожидания"
    except Exception as e:
        logger.error(f"{service_name} restart error: {e}")
        return False, str(e)


def check_service_status(init_script: str) -> str:
    """
    Check service status with caching (30s TTL).

    Caching reduces CPU load by avoiding frequent subprocess calls.

    Args:
        init_script: Path to init script

    Returns:
        Status string
    """
    import logging
    logger = logging.getLogger(__name__)
    
    # Cache status for 30 seconds to reduce CPU load
    cache_key = f'status:{init_script}'
    cached_status = Cache.get(cache_key)
    if cached_status:
        return cached_status

    logger.debug(f"Checking status for {init_script}")
    
    if not os.path.exists(init_script):
        logger.warning(f"Init script not found: {init_script}")
        status = "❌ Скрипт не найден"
    else:
        try:
            logger.debug(f"Running: sh {init_script} status")
            result = subprocess.run(
                ['sh', init_script, 'status'],
                capture_output=True,
                text=True,
                timeout=10
            )
            logger.debug(f"Status result: returncode={result.returncode}, stdout={result.stdout[:100] if result.stdout else 'empty'}")

            if result.returncode == 0:
                status = "✅ Активен"
            else:
                # Проверяем вывод на наличие ключевых слов
                output = result.stdout + result.stderr
                if "not running" in output.lower() or "stopped" in output.lower():
                    status = "❌ Не активен"
                elif "alive" in output.lower() or "running" in output.lower():
                    status = "✅ Активен"
                else:
                    status = "❌ Не активен"

        except subprocess.TimeoutExpired:
            logger.error(f"Timeout checking status for {init_script}")
            status = "⏱️  Таймаут проверки"
        except FileNotFoundError:
            logger.warning(f"File not found: {init_script}")
            status = "❌ Скрипт не найден"
        except PermissionError:
            logger.error(f"Permission denied: {init_script}")
            status = "❌ Нет прав на скрипт"
        except Exception as e:
            logger.error(f"Error checking status for {init_script}: {e}")
            status = f"❓ Ошибка: {str(e)}"

    # Cache for 30 seconds
    Cache.set(cache_key, status, ttl=30)
    logger.debug(f"Status for {init_script}: {status}")
    return status


# =============================================================================
# CONFIG WRITER
# =============================================================================

def write_json_config(config: Dict[str, Any], filepath: str) -> None:
    """
    Write configuration to JSON file atomically.

    Args:
        config: Configuration dict
        filepath: Path to output file
    """
    logger.info(f"write_json_config: writing to {filepath}")
    temp_path = filepath + '.tmp'

    try:
        logger.info(f"write_json_config: creating directory {os.path.dirname(filepath)}")
        # Создать директорию если не существует
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        logger.debug(f"Directory created or exists: {os.path.dirname(filepath)}")

        logger.info(f"write_json_config: opening temp file {temp_path}")
        logger.debug(f"Writing config to {temp_path}")
        with open(temp_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        logger.info(f"write_json_config: config written to {temp_path}")

        logger.info(f"write_json_config: replacing {temp_path} with {filepath}")
        os.replace(temp_path, filepath)
        logger.info(f"write_json_config: config written to {filepath} successfully")

    except Exception as e:
        logger.error(f"write_json_config: error writing config: {e}")
        logger.error(f"Exception type: {type(e).__name__}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        try:
            if os.path.exists(temp_path):
                os.remove(temp_path)
        except Exception:
            pass
        raise


def write_tor_config(config: Dict[str, Any], filepath: str) -> None:
    """
    Write Tor configuration to file.

    Args:
        config: Configuration dict
        filepath: Path to output file
    """
    logger.info(f"write_tor_config: writing to {filepath}")
    temp_path = filepath + '.tmp'

    try:
        logger.info(f"write_tor_config: creating directory {os.path.dirname(filepath)}")
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        logger.info(f"write_tor_config: opening temp file {temp_path}")
        with open(temp_path, 'w', encoding='utf-8') as f:
            for key, value in config.items():
                if isinstance(value, list):
                    for item in value:
                        f.write(f"{key} {item}\n")
                else:
                    f.write(f"{key} {value}\n")
        logger.info(f"write_tor_config: config written to {temp_path}")

        logger.info(f"write_tor_config: replacing {temp_path} with {filepath}")
        os.replace(temp_path, filepath)
        logger.info(f"write_tor_config: Tor config written to {filepath} successfully")

    except Exception as e:
        logger.error(f"write_tor_config: error writing config: {e}")
        logger.error(f"Exception type: {type(e).__name__}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        try:
            if os.path.exists(temp_path):
                os.remove(temp_path)
        except Exception:
            pass
        raise


def create_backup(backup_type='full'):
    """
    Create backup of all flymybyte files.
    
    Args:
        backup_type: 'full' or 'custom'
    
    Returns:
        Tuple of (success: bool, message: str)
    """
    import shutil
    import tarfile
    from datetime import datetime
    
    try:
        backup_dir = '/opt/root/backup'
        os.makedirs(backup_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_file = f'{backup_dir}/backup_{timestamp}.tar.gz'
        
        files_to_backup = [
            '/opt/etc/web_ui',
            '/opt/etc/xray',
            '/opt/etc/tor',
            '/opt/etc/unblock',
            '/opt/bin',
            '/opt/etc/dnsmasq.conf',
            '/opt/etc/crontab',
            '/opt/etc/shadowsocks.json',
            '/opt/etc/trojan',
            '/opt/etc/hysteria2.json',
            '/opt/etc/ndm',
            '/opt/etc/init.d',
            '/opt/root/script.sh',
            '/opt/etc/unblock-ai.dnsmasq',
            '/opt/etc/unblock/ai-domains.txt',
        ]
        
        existing_files = [f for f in files_to_backup if os.path.exists(f)]
        
        if not existing_files:
            return False, 'Нет файлов для бэкапа'
        
        with tarfile.open(backup_file, 'w:gz') as tar:
            for f in existing_files:
                tar.add(f, arcname=os.path.basename(f))
        
        backup_size = os.path.getsize(backup_file)
        size_mb = backup_size / 1024 / 1024
        
        return True, f'Бэкап создан: {backup_file} ({size_mb:.1f} МБ, {len(existing_files)} объектов)'
    
    except Exception as e:
        logger.error(f'Backup error: {e}')
        return False, str(e)


def get_local_version():
    """Получить локальную версию"""
    # На роутере VERSION файл находится в /opt/etc/web_ui/
    version_file = '/opt/etc/web_ui/VERSION'
    try:
        with open(version_file, 'r', encoding='utf-8') as f:
            return f.read().strip()
    except FileNotFoundError:
        # Для разработки: проверяем локальный файл VERSION в корне проекта
        import os
        local_version_file = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'VERSION')
        if os.path.exists(local_version_file):
            try:
                with open(local_version_file, 'r', encoding='utf-8') as f:
                    return f.read().strip()
            except:
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
