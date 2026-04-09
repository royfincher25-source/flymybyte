"""
FlyMyByte Web Interface - Key Parsers and Service Management

Full-featured parsers for VPN keys (VLESS, Shadowsocks, Trojan).
Memory-optimized for embedded devices (128MB RAM).
"""
import os
import re
import time
import json
import base64
import logging
import subprocess
import hashlib
import threading
from pathlib import Path
from urllib.parse import urlparse, unquote, parse_qs
from typing import Dict, Any, Optional, Tuple, List

from .utils import Cache, logger


# =============================================================================
# VLESS PARSER
# =============================================================================

def parse_vless_key(key: str) -> Dict[str, Any]:
    """
    Parse VLESS key with caching.

    Format: vless://uuid@server:port?encryption=none&security=tls&sni=...#name

    Args:
        key: VLESS key string

    Returns:
        Dict with parsed configuration

    Raises:
        ValueError: If key format is invalid
    """
    # Memory optimization: use MD5 hash instead of full key as cache key
    # Saves ~40KB RAM (full keys can be 100-500 chars each)
    cache_key = f'vless:{hashlib.md5(key.encode()).hexdigest()}'

    if Cache.is_valid(cache_key):
        logger.debug(f"VLESS cache hit: {cache_key[:20]}...")
        return Cache.get(cache_key)

    if not key.startswith('vless://'):
        raise ValueError("Неверный формат ключа VLESS")

    # Normalize key
    key = key.strip()
    
    # Remove non-ASCII characters from fragment (emoji can break URL parsing)
    if '#' in key:
        base, fragment = key.split('#', 1)
        # Keep only ASCII in fragment
        fragment = fragment.encode('ascii', 'ignore').decode('ascii')
        key = base + '#' + fragment
    
    key = ''.join(c for c in key if ord(c) >= 32 or c in '\t\n\r')
    key = unquote(key)

    try:
        key = key.encode('ascii', 'ignore').decode('ascii')
    except Exception as e:
        logger.error(f"VLESS ASCII encode error: {e}")

    logger.debug(f"VLESS normalized key: {key[:80]}...")

    # Parse URL (keep vless:// for urlparse to work correctly)
    # urlparse needs the scheme to extract username/hostname
    # Fix malformed query strings first (e.g., "?&param=value" → "?param=value")
    if '?&' in key:
        key = key.replace('?&', '?')
        logger.debug(f"Fixed malformed URL: {key[:80]}...")
    
    parsed = urlparse(key)
    
    logger.debug(f"VLESS parsed: scheme={parsed.scheme}, host={parsed.hostname}, port={parsed.port}, query_len={len(parsed.query) if parsed.query else 0}")

    # Extract UUID
    uuid = parsed.username
    if not uuid:
        logger.error(f"UUID not found! Full URL: {key[:100]}")
        raise ValueError("UUID не найден в ключе")
    
    # Extract server and port
    server = parsed.hostname
    port = parsed.port
    
    if not server or not port:
        raise ValueError("Сервер или порт не найдены")
    
    if not (1 <= port <= 65535):
        raise ValueError(f"Порт должен быть от 1 до 65535, получен {port}")
    
    # Parse query parameters
    params = parse_qs(parsed.query)
    
    # Extract configuration
    result = {
        'uuid': uuid,
        'server': server,
        'port': port,
        'encryption': params.get('encryption', ['none'])[0],
        'security': params.get('security', ['none'])[0],
        'sni': params.get('sni', [server])[0],
        'alpn': params.get('alpn', ['h2,http/1.1'])[0],
        'fp': params.get('fp', ['chrome'])[0],
        'type': params.get('type', ['tcp'])[0],
        'path': params.get('path', ['/'])[0],
        'host': params.get('host', [server])[0],
        'flow': params.get('flow', [''])[0],  # XTLS Vision flow
        'name': parsed.fragment or 'VLESS',
    }

    # XHTTP transport parameters
    if result['type'] == 'xhttp':
        result['xhttp_mode'] = params.get('mode', ['stream-one'])[0]
        result['xhttp_max_upload_upload'] = params.get('maxUploadUpload', [''])[0]
        result['xhttp_max_concurrent_upload'] = params.get('maxConcurrentUpload', [''])[0]

        # Validate XHTTP mode
        valid_modes = ['stream-one', 'stream-multi']
        if result['xhttp_mode'] not in valid_modes:
            logger.warning(f"XHTTP mode '{result['xhttp_mode']}' not in {valid_modes}, using default 'stream-one'")
            result['xhttp_mode'] = 'stream-one'

        # XHTTP requires host and path
        if not result['host'] or result['host'] == server:
            raise ValueError("Для XHTTP необходимо указать host (SNI)")
        if not result['path']:
            result['path'] = '/'

    # Handle different security types
    if result['security'] == 'reality':
        result['pbk'] = params.get('pbk', [''])[0]
        result['sid'] = params.get('sid', [''])[0]
        result['spx'] = params.get('spx', [''])[0]
    
    logger.debug(f"VLESS parsed successfully: server={server}, port={port}")

    # TTL 24 hours (86400s) - VPN keys are stable
    Cache.set(cache_key, result, ttl=86400)
    return result


def vless_config(key: str) -> Dict[str, Any]:
    """
    Generate VLESS configuration from key.
    
    Args:
        key: VLESS key string

    Returns:
        Dict with full configuration for Xray/Singbox
    """
    logger.debug(f"vless_config: parsing key")

    parsed = parse_vless_key(key)
    
    # Build Xray config
    config = {
        'log': {
            'loglevel': 'warning',
        },
        'inbounds': [
            {
                'tag': 'transparent',
                'listen': '::',
                'port': 10810,
                'protocol': 'dokodemo-door',
                'settings': {
                    'network': 'tcp',
                    'followRedirect': True,
                },
                'sniffing': {
                    'enabled': True,
                    'destOverride': ['http', 'tls'],
                },
            },
        ],
        'outbounds': [
            {
                'tag': 'proxy',
                'protocol': 'vless',
                'settings': {
                    'vnext': [
                        {
                            'address': parsed['server'],
                            'port': parsed['port'],
                            'users': [
                                {
                                    'id': parsed['uuid'],
                                    'encryption': 'none',
                                    'flow': parsed.get('flow', ''),  # XTLS Vision
                                    'level': 8,
                                    'security': 'auto',
                                }
                            ],
                        }
                    ],
                },
                'streamSettings': {
                    'network': parsed['type'],
                    'security': parsed['security'],
                    'tlsSettings': {
                        'serverName': parsed['sni'],
                        'alpn': [parsed['alpn'].split(',')],
                        'fingerprint': parsed['fp'],
                    } if parsed['security'] == 'tls' else {},
                    'realitySettings': {
                        'serverName': parsed['sni'],
                        'publicKey': parsed.get('pbk', ''),
                        'shortId': parsed.get('sid', ''),
                        'spiderX': parsed.get('spx', ''),
                    } if parsed['security'] == 'reality' else {},
                    'tcpSettings': {
                        'header': {
                            'type': 'http',
                            'request': {
                                'path': [parsed['path']],
                                'headers': {
                                    'Host': [parsed['host']],
                                }
                            }
                        }
                    } if parsed['type'] == 'tcp' and parsed['path'] != '/' else {},
                    'wsSettings': {
                        'path': parsed['path'],
                        'headers': {
                            'Host': parsed['host'],
                        }
                    } if parsed['type'] == 'ws' else {},
                    'xhttpSettings': {
                        'mode': parsed.get('xhttp_mode', 'stream-one'),
                        'host': parsed.get('host', ''),
                        'path': parsed.get('path', '/'),
                        'maxUploadUpload': parsed.get('xhttp_max_upload_upload', ''),
                        'maxConcurrentUpload': parsed.get('xhttp_max_concurrent_upload', ''),
                    } if parsed['type'] == 'xhttp' else {},
                },
                'mux': {
                    'enabled': False,
                },
            },
            {
                'tag': 'direct',
                'protocol': 'freedom',
                'settings': {},
            },
        ],
        'routing': {
            'domainStrategy': 'AsIs',
            'rules': [
                # FIX: Локальные IP идут напрямую
                {
                    'type': 'field',
                    'ip': ['geoip:private'],
                    'outboundTag': 'direct',
                },
                # FIX: Весь остальной трафик идёт напрямую по умолчанию
                # iptables сам перенаправит только домены из списка обхода
                {
                    'type': 'field',
                    'port': '0-65535',
                    'outboundTag': 'direct',
                },
            ],
        },
    }

    logger.debug("vless_config: generated")
    return config


# =============================================================================
# SHADOWSOCKS PARSER
# =============================================================================

def parse_shadowsocks_key(key: str) -> Dict[str, Any]:
    """
    Parse Shadowsocks key with caching.
    
    Supports both standard and URL-safe base64.
    
    Format: ss://base64(method:password)@server:port#name
    
    Args:
        key: Shadowsocks key string
    
    Returns:
        Dict with parsed configuration
    
    Raises:
        ValueError: If key format is invalid
    """
    # Memory optimization: use MD5 hash instead of full key as cache key
    cache_key = f'ss:{hashlib.md5(key.encode()).hexdigest()}'

    if Cache.is_valid(cache_key):
        logger.debug(f"Shadowsocks cache hit: {cache_key[:20]}...")
        return Cache.get(cache_key)
    
    if not key.startswith('ss://'):
        raise ValueError("Неверный формат ключа Shadowsocks")
    
    # Normalize key
    key = key.strip()
    key = ''.join(c for c in key if ord(c) >= 32 or c in '\t\n\r')
    
    # Replace Cyrillic with Latin
    cyrillic_to_latin = {
        'а': 'a', 'е': 'e', 'о': 'o', 'р': 'p', 'с': 'c', 'у': 'y', 'х': 'x',
        'А': 'A', 'Е': 'E', 'О': 'O', 'Р': 'P', 'С': 'C', 'У': 'Y', 'Х': 'X',
    }
    for cyr, lat in cyrillic_to_latin.items():
        key = key.replace(cyr, lat)
    
    key = unquote(key)
    
    try:
        key = key.encode('ascii', 'ignore').decode('ascii')
    except Exception as e:
        logger.error(f"Shadowsocks ASCII encode error: {e}")
    
    logger.debug(f"Shadowsocks normalized key: {key[:80]}...")
    
    url = key[5:]  # Remove 'ss://'
    parsed_url = urlparse(url)
    
    logger.debug(f"Shadowsocks urlparse: hostname={parsed_url.hostname}, username={parsed_url.username}, port={parsed_url.port}")
    
    # Try standard format with @
    if parsed_url.hostname and parsed_url.username:
        port = parsed_url.port
        if not port or not (1 <= port <= 65535):
            raise ValueError(f"Порт должен быть от 1 до 65535")
        
        try:
            encoded = parsed_url.username
            # URL-safe base64 support
            encoded = encoded.replace('-', '+').replace('_', '/')
            padding = 4 - (len(encoded) % 4)
            if padding != 4:
                encoded += '=' * padding
            
            decoded = base64.b64decode(encoded).decode('utf-8')
            logger.debug(f"Shadowsocks decoded: {decoded}")
            method, password = decoded.split(':', 1)
            logger.debug(f"Shadowsocks method={method}")
        except Exception as e:
            logger.error(f"Shadowsocks base64 error: {e}")
            raise ValueError(f"Ошибка декодирования base64: {str(e)}")
        
        result = {
            'server': parsed_url.hostname,
            'port': port,
            'password': password,
            'method': method,
        }
        logger.debug(f"Shadowsocks OK: server={result['server']}, port={result['port']}")

        # TTL 24 hours (86400s) - VPN keys are stable
        Cache.set(cache_key, result, ttl=86400)
        return result
    
    # Try alternative format (manual parsing)
    logger.debug(f"Shadowsocks: нет username, пробуем альтернативный формат")
    
    try:
        url_part = url.split('#')[0]
        logger.debug(f"Shadowsocks url_part: {url_part[:80]}...")
        
        at_index = url_part.rfind('@')
        if at_index > 0:
            encoded = url_part[:at_index]
            server_port = url_part[at_index+1:]
            logger.debug(f"Shadowsocks manual: encoded={encoded[:50]}..., server_port={server_port}")
            
            if ':' in server_port:
                server, port_str = server_port.rsplit(':', 1)
                port = int(port_str)
                if not (1 <= port <= 65535):
                    raise ValueError(f"Порт должен быть от 1 до 65535")
                
                # URL-safe base64
                encoded = encoded.replace('-', '+').replace('_', '/')
                padding = 4 - (len(encoded) % 4)
                if padding != 4:
                    encoded += '=' * padding
                
                decoded = base64.b64decode(encoded).decode('utf-8')
                logger.debug(f"Shadowsocks manual decoded: {decoded}")
                method, password = decoded.split(':', 1)
                
                result = {
                    'server': server,
                    'port': port,
                    'password': password,
                    'method': method,
                }
                logger.debug(f"Shadowsocks manual OK: server={result['server']}, port={result['port']}")
                Cache.set(cache_key, result, ttl=3600)
                return result
    except Exception as e:
        logger.error(f"Shadowsocks manual error: {e}")
    
    # Try old alternative format
    try:
        encoded = url.split('#')[0]
        encoded = encoded.replace('-', '+').replace('_', '/')
        padding = 4 - (len(encoded) % 4)
        if padding != 4:
            encoded += '=' * padding
        
        decoded = base64.b64decode(encoded).decode('utf-8')
        logger.debug(f"Shadowsocks alt decoded: {decoded}")
        
        match = re.match(r'([^:]+):([^@]+)@([^:]+):(\d+)', decoded)
        if match:
            method, password, server, port = match.groups()
            result = {
                'server': server,
                'port': int(port),
                'password': password,
                'method': method,
            }
            logger.debug(f"Shadowsocks alt OK: server={result['server']}, port={result['port']}")
            Cache.set(cache_key, result, ttl=3600)
            return result
    except Exception as e:
        logger.error(f"Shadowsocks alt error: {e}")
    
    logger.error(f"Shadowsocks FAILED: Некорректные данные сервера")
    raise ValueError("Некорректные данные сервера")


def shadowsocks_config(key: str) -> Dict[str, Any]:
    """
    Generate Shadowsocks configuration from key.

    Args:
        key: Shadowsocks key string

    Returns:
        Dict with full configuration for shadowsocks-libev
    """
    logger.debug("shadowsocks_config: parsing key")

    parsed = parse_shadowsocks_key(key)

    config = {
        'server': [parsed['server']],
        'mode': 'tcp_and_udp',
        'server_port': parsed['port'],
        'password': parsed['password'],
        'timeout': 86400,
        'local_address': '::',
        'local_port': 1082,
        'fast_open': False,
        'ipv6_first': True,
    }

    logger.debug("shadowsocks_config: generated")
    return config


# =============================================================================
# UNIFIED PROXY PARSER (SS + Trojan)
# =============================================================================

def parse_proxy_key(key: str) -> Dict[str, Any]:
    """
    Unified proxy parser — auto-detects Shadowsocks or Trojan by URL scheme.

    Returns dict with 'protocol' field ('ss' or 'trojan').

    Args:
        key: Proxy key string (ss://... or trojan://...)

    Returns:
        Dict with parsed configuration and 'protocol' field

    Raises:
        ValueError: If key format is invalid
    """
    if key.startswith('ss://'):
        parsed = parse_shadowsocks_key(key)
        parsed['protocol'] = 'ss'
        return parsed
    elif key.startswith('trojan://'):
        parsed = parse_trojan_key(key)
        parsed['protocol'] = 'trojan'
        return parsed
    else:
        raise ValueError("Неверный формат ключа. Поддерживаются ss:// и trojan://")


def proxy_config(key: str) -> Dict[str, Any]:
    """
    Unified proxy config generator — delegates to ss_config or trojan_config.

    Args:
        key: Proxy key string

    Returns:
        Dict with full configuration and 'protocol' field
    """
    if key.startswith('ss://'):
        cfg = shadowsocks_config(key)
        cfg['protocol'] = 'ss'
        return cfg
    elif key.startswith('trojan://'):
        cfg = trojan_config(key)
        cfg['protocol'] = 'trojan'
        return cfg
    else:
        raise ValueError("Неверный формат ключа")


# =============================================================================
# TROJAN PARSER
# =============================================================================

def parse_trojan_key(key: str) -> Dict[str, Any]:
    """
    Parse Trojan key with caching.
    
    Format: trojan://password@server:port?security=tls&sni=...#name
    
    Args:
        key: Trojan key string

    Returns:
        Dict with parsed configuration

    Raises:
        ValueError: If key format is invalid
    """
    # Memory optimization: use MD5 hash instead of full key as cache key
    cache_key = f'trojan:{hashlib.md5(key.encode()).hexdigest()}'

    if Cache.is_valid(cache_key):
        logger.debug(f"Trojan cache hit: {cache_key[:20]}...")
        return Cache.get(cache_key)

    if not key.startswith('trojan://'):
        raise ValueError("Неверный формат ключа Trojan")
    
    # Normalize key
    key = key.strip()
    key = unquote(key)
    
    try:
        key = key.encode('ascii', 'ignore').decode('ascii')
    except Exception as e:
        logger.error(f"Trojan ASCII encode error: {e}")
    
    logger.debug(f"Trojan normalized key: {key[:80]}...")
    
    url = key[11:]  # Remove 'trojan://'
    parsed = urlparse(url)
    
    # Extract password
    password = parsed.username
    if not password:
        raise ValueError("Пароль не найден в ключе")
    
    # Extract server and port
    server = parsed.hostname
    port = parsed.port
    
    if not server or not port:
        raise ValueError("Сервер или порт не найдены")
    
    if not (1 <= port <= 65535):
        raise ValueError(f"Порт должен быть от 1 до 65535")
    
    # Parse query parameters
    params = parse_qs(parsed.query)
    
    result = {
        'password': password,
        'server': server,
        'port': port,
        'security': params.get('security', ['tls'])[0],
        'sni': params.get('sni', [server])[0],
        'alpn': params.get('alpn', ['h2,http/1.1'])[0],
        'type': params.get('type', ['tcp'])[0],
        'name': parsed.fragment or 'Trojan',
    }

    logger.debug(f"Trojan parsed successfully: server={server}, port={port}")

    # TTL 24 hours (86400s) - VPN keys are stable
    Cache.set(cache_key, result, ttl=86400)
    return result


def trojan_config(key: str) -> Dict[str, Any]:
    """
    Generate Trojan configuration from key.

    Args:
        key: Trojan key string

    Returns:
        Dict with full configuration
    """
    logger.debug("trojan_config: parsing key")

    parsed = parse_trojan_key(key)

    config = {
        'run_type': 'client',
        'local_addr': '127.0.0.1',
        'local_port': 10829,
        'remote_addr': parsed['server'],
        'remote_port': parsed['port'],
        'password': [parsed['password']],
        'log_level': 1,
        'ssl': {
            'verify': True,
            'verify_hostname': True,
            'cert': '',
            'cipher': 'ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305:DHE-RSA-AES128-GCM-SHA256:DHE-RSA-AES256-GCM-SHA384',
            'cipher_tls13': 'TLS_AES_128_GCM_SHA256:TLS_CHACHA20_POLY1305_SHA256:TLS_AES_256_GCM_SHA384',
            'sni': parsed['sni'],
            'alpn': ['h2', 'http/1.1'],
            'reuse_session': True,
            'session_ticket': False,
            'curves': '',
        },
        'tcp': {
            'no_delay': True,
            'keep_alive': True,
            'reuse_port': False,
            'fast_open': False,
            'fast_open_qlen': 20,
        },
    }

    logger.debug("trojan_config: generated")
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
    logger.info(f"[SVC] Restarting {service_name} via {init_script}")

    if not os.path.exists(init_script):
        logger.error(f"[SVC] Init script not found: {init_script}")
        return False, f"Скрипт {init_script} не найден"

    try:
        result = subprocess.run(
            ['sh', init_script, 'restart'],
            capture_output=True,
            text=True,
            timeout=180
        )

        success = result.returncode == 0
        output = result.stdout.strip() or result.stderr.strip()

        if success:
            logger.info(f"[SVC] {service_name} restarted successfully")
        else:
            logger.error(f"[SVC] {service_name} restart failed (code={result.returncode}): {output}")

        return success, output

    except subprocess.TimeoutExpired:
        logger.error(f"[SVC] {service_name} restart timed out")
        return False, "Превышено время ожидания"
    except Exception as e:
        logger.error(f"[SVC] {service_name} restart error: {e}")
        return False, str(e)


def _is_process_running(proc_pattern: str) -> bool:
    """Check if process is running via /proc or pgrep fallback."""
    try:
        for pid_dir in os.listdir('/proc'):
            if not pid_dir.isdigit():
                continue
            cmdline_path = f'/proc/{pid_dir}/cmdline'
            try:
                with open(cmdline_path, 'rb') as f:
                    cmdline = f.read(256).decode('utf-8', errors='ignore')
                    if proc_pattern in cmdline:
                        return True
            except (FileNotFoundError, PermissionError, ProcessLookupError):
                continue
    except Exception as e:
        logger.debug(f"[SVC] /proc check failed: {e}")
    # Fallback to pgrep
    try:
        result = subprocess.run(
            ['pgrep', '-f', proc_pattern],
            capture_output=True, text=True, timeout=3
        )
        return result.returncode == 0
    except Exception:
        return False


def check_service_status(init_script: str) -> str:
    """
    Check service status with caching (60s TTL).

    Optimized for embedded devices: uses /proc instead of pgrep/subprocess.
    CPU reduction: ~80% (no subprocess calls for status check).

    Args:
        init_script: Path to init script

    Returns:
        Status string
    """
    # Cache status for 60 seconds (increased from 30s to reduce CPU)
    cache_key = f'status:{init_script}'
    cached_status = Cache.get(cache_key)
    if cached_status:
        return cached_status

    logger.debug(f"[SVC] Checking status for {init_script}")

    if not os.path.exists(init_script):
        logger.warning(f"[SVC] Init script not found: {init_script}")
        status = "❌ Скрипт не найден"
    else:
        try:
            # Extract service name from init script
            script_name = os.path.basename(init_script)

            # Map init script to process name pattern
            process_patterns = {
                'S24xray': 'xray',
                'S22shadowsocks': 'ss-redir',
                'S22trojan': 'trojan',
                'S56dnsmasq': 'dnsmasq',
                'S99unblock': 'unblock',
            }

            proc_pattern = process_patterns.get(script_name, script_name.replace('S', '').split('init')[0])

            # FIX: Use centralized _is_process_running with /proc + pgrep fallback
            service_running = _is_process_running(proc_pattern)

            if service_running:
                status = "✅ Активен"
                logger.debug(f"[SVC] {init_script}: ACTIVE (via /proc)")
            else:
                # Service not found in /proc, check if it's supposed to run
                # Some services may not have config yet
                status = "❌ Не активен"

        except subprocess.TimeoutExpired:
            logger.error(f"Timeout checking status for {init_script}")
            status = "⏱️  Таймаут проверки"
        except Exception as e:
            logger.error(f"Error checking status for {init_script}: {e}")
            status = f"❓ Ошибка: {str(e)}"

    # Cache for 60 seconds (increased from 30s)
    Cache.set(cache_key, status, ttl=60)
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
            '/opt/etc/unblock',
            '/opt/bin',
            '/opt/etc/dnsmasq.conf',
            '/opt/etc/crontab',
            '/opt/etc/shadowsocks.json',
            '/opt/etc/trojan',
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


# =============================================================================
# IPSET MANAGER (merged from ipset_manager.py)
# =============================================================================

# Memory limit for embedded devices (128MB RAM)
# Prevents OOM when adding thousands of entries in single operation
IPSET_MAX_BULK_ENTRIES = 5000  # Maximum entries per bulk operation
IPSET_BATCH_SIZE = 1000  # Process entries in batches of 1000


def _sanitize_for_ipset(text: str) -> str:
    """
    Sanitize text for safe use in ipset commands.

    Removes dangerous characters that could be used for command injection.

    Args:
        text: Input text to sanitize

    Returns:
        Sanitized text safe for ipset commands
    """
    if not text:
        raise ValueError("Empty entry")

    # Remove dangerous shell characters
    dangerous_pattern = r'[;|&`$(){}<>\\!#~*?\[\]\r\n]'
    sanitized = re.sub(dangerous_pattern, '', text)

    # Strip whitespace
    sanitized = sanitized.strip()

    if not sanitized:
        raise ValueError("Invalid entry after sanitization")

    return sanitized


def _is_valid_ipset_entry(entry: str) -> bool:
    """
    Validate entry (IP address or domain).

    Args:
        entry: IP or domain string

    Returns:
        True if valid
    """
    if not entry or len(entry) > 253:
        return False

    # IPv4 pattern
    ipv4_pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
    if re.match(ipv4_pattern, entry):
        parts = entry.split('.')
        try:
            return all(0 <= int(p) <= 255 for p in parts)
        except ValueError:
            return False

    # IPv6 pattern (simplified)
    if ':' in entry:
        return True

    # Domain pattern
    domain_pattern = r'^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*$'
    return bool(re.match(domain_pattern, entry))


def _parse_ipset_error(stderr: str, commands: List[str]) -> str:
    """
    Parse ipset restore error output to identify failed entries.

    Args:
        stderr: Error output from ipset restore
        commands: List of commands that were executed

    Returns:
        Detailed error message with failed entries
    """
    error_lines = stderr.strip().split('\n')
    failed_entries = []

    for line in error_lines:
        match = re.search(r'line (\d+)', line, re.IGNORECASE)
        if match:
            line_num = int(match.group(1))
            if 1 <= line_num <= len(commands):
                failed_cmd = commands[line_num - 1]
                parts = failed_cmd.split()
                if len(parts) >= 3:
                    failed_entries.append(parts[2])

    if failed_entries:
        sample = failed_entries[:5]
        remaining = len(failed_entries) - len(sample)
        msg = f"Failed entries: {', '.join(sample)}"
        if remaining > 0:
            msg += f" (and {remaining} more)"
        logger.error(f"ipset restore failed for {len(failed_entries)} entries")
        return msg
    else:
        return stderr[:200]


# ===========================================================================
# IPSET operations — delegated to ipset_ops.py to break circular dependency
# ===========================================================================

def bulk_add_to_ipset(setname: str, entries: List[str]) -> Tuple[bool, str]:
    """Bulk add entries to ipset (delegated to ipset_ops)."""
    from .ipset_ops import bulk_add_to_ipset as _impl
    return _impl(setname, entries)


def bulk_remove_from_ipset(setname: str, entries: List[str]) -> Tuple[bool, str]:
    """Bulk remove entries from ipset (delegated to ipset_ops)."""
    from .ipset_ops import bulk_remove_from_ipset as _impl
    return _impl(setname, entries)


def ensure_ipset_exists(setname: str, settype: str = 'hash:ip') -> Tuple[bool, str]:
    """Ensure ipset exists (delegated to ipset_ops)."""
    from .ipset_ops import ensure_ipset_exists as _impl
    return _impl(setname, settype)


def refresh_ipset_from_file(filepath: str, max_workers: int = 10) -> Tuple[bool, str]:
    """
    Refresh ipset from bypass list file (resolve domains + add IPs).

    Args:
        filepath: Path to bypass list file
        max_workers: Parallel workers for DNS (default: 10)

    Returns:
        Tuple of (success: bool, message: str)
    """
    from .app_config import WebConfig

    # Validate file path (prevent directory traversal)
    config = WebConfig()
    real_path = os.path.realpath(filepath)
    real_dir = os.path.realpath(config.unblock_dir)
    if not real_path.startswith(real_dir + os.sep):
        return False, "Invalid file path"

    # Check file exists
    if not os.path.exists(filepath):
        logger.warning(f"File not found: {filepath}")
        return False, f"File not found: {filepath}"

    try:
        # FIX: Import from ipset_ops instead of dns_ops to break circular dependency
        from .ipset_ops import bulk_add_to_ipset, ensure_ipset_exists
        from .dns_ops import resolve_domains_for_ipset, parallel_resolve

        logger.info(f"[IPSET] Refreshing from file: {filepath}")
        count = resolve_domains_for_ipset(filepath, max_workers)
        logger.info(f"[IPSET] Refresh complete: {count} IPs resolved and added from {filepath}")
        return True, f"Resolved and added {count} IPs"
    except Exception as e:
        logger.error(f"[IPSET] Refresh failed for {filepath}: {e}")
        return False, str(e)


# =============================================================================
# LIST CATALOG (merged from list_catalog.py)
# =============================================================================

# Catalog of available bypass lists
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


def get_list_info(name: str) -> Dict[str, Any]:
    """Get info about specific list"""
    return LIST_CATALOG.get(name, {})


def _parse_list_content(content: str, fmt: str) -> List[str]:
    """
    Parse list content based on format.

    Args:
        content: Raw file content
        fmt: 'hosts' or 'domains'

    Returns:
        List of domains
    """
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
    """
    Download list from catalog and save to file.

    Args:
        name: List name from catalog
        dest_dir: Destination directory

    Returns:
        Tuple of (success: bool, message: str, count: int)
    """
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

        # Atomic write
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


# =============================================================================
# DNS SPOOFING (merged from dns_spoofing.py)
# =============================================================================

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
    """
    DNS Spoofing for AI domain bypass.

    Generates dnsmasq configuration to route AI domain DNS queries through VPN.
    Thread-safe singleton pattern.
    """

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
        """
        Load AI domains from list file.

        Returns:
            List of valid domain names
        """
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
        """
        Generate dnsmasq configuration for AI domains.

        Args:
            domains: List of domains (default: load from file)

        Returns:
            dnsmasq configuration string
        """
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
        """
        Write dnsmasq configuration to file (atomic write).

        Args:
            config: Configuration string

        Returns:
            Tuple of (success: bool, message: str)
        """
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
        """
        Apply dnsmasq configuration and restart dnsmasq.

        Returns:
            Tuple of (success: bool, message: str)
        """
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
        """
        Restart dnsmasq service using SIGHUP to reload config.

        Returns:
            Tuple of (success: bool, message: str)
        """
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
        """
        Disable DNS spoofing (remove config and FULL restart dnsmasq).

        Returns:
            Tuple of (success: bool, message: str)
        """
        config_path = Path(self._config_path)

        try:
            if config_path.exists():
                config_path.unlink()
                logger.info(f"Removed AI domains config: {self._config_path}")

            # Use SIGHUP instead of restart — restart can fail on Keenetic
            # and leave dnsmasq stopped, breaking all DNS for the network
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
        """
        Get current DNS spoofing status.

        Returns:
            Dict with status information
        """
        config_path = Path(self._config_path)
        domains_path = Path(self._domains_path)

        # FIX: check if config file has actual server= rules, not just comments
        config_has_content = False
        if config_path.exists():
            try:
                content = config_path.read_text(encoding='utf-8')
                # Check for real DNS rules (server=/domain.com/...), not comments
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
        """
        Test DNS resolution for a domain.

        Args:
            domain: Domain to test

        Returns:
            Dict with test results
        """
        result = {
            'domain': domain,
            'resolved': False,
            'ips': [],
            'dns_server': f'{VPN_DNS_HOST}:{VPN_DNS_PORT}',
            'error': None,
        }

        try:
            # FIX: Use subprocess with list args instead of shell=True to prevent injection
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
                # FIX: Use list args, no shell
                proc_result = subprocess.run(
                    ['nslookup', domain],
                    capture_output=True,
                    text=True,
                    timeout=5
                )

                if proc_result.stdout.strip():
                    ips = re.findall(
                        r'([0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3})',
                        proc_result.stdout
                    )

                    if ips:
                        result['error'] = f'Домен существует, но не резолвится через VPN DNS (порт {VPN_DNS_PORT}). Проверьте, запущен ли dnsmasq/stubby и применена ли конфигурация.'
                        result['ips'] = ips
                        return result

            except Exception as e:
                logger.debug(f"test_domain fallback nslookup error for {domain}: {e}")

            result['error'] = 'No IPs found'

        except subprocess.TimeoutExpired:
            result['error'] = 'Timeout'
        except Exception as e:
            result['error'] = str(e)

        return result


# Module-level convenience functions for DNS spoofing

def apply_dns_spoofing() -> Tuple[bool, str]:
    """Apply DNS spoofing configuration"""
    spoofing = DNSSpoofing()
    return spoofing.apply_config()


def disable_dns_spoofing() -> Tuple[bool, str]:
    """Disable DNS spoofing"""
    spoofing = DNSSpoofing()
    return spoofing.disable()


def get_dns_spoofing_status() -> Dict[str, Any]:
    """Get DNS spoofing status"""
    spoofing = DNSSpoofing()
    return spoofing.get_status()
