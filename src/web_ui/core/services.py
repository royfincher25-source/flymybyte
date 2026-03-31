"""
FlyMyByte Web Interface - Key Parsers and Service Management

Full-featured parsers for VPN keys (VLESS, Shadowsocks, Trojan, Tor).
Memory-optimized for embedded devices (128MB RAM).
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
    
    logger.debug(f"Parsed scheme: {parsed.scheme}")
    logger.debug(f"Parsed username: {parsed.username}")
    logger.debug(f"Parsed hostname: {parsed.hostname}")
    logger.debug(f"Parsed port: {parsed.port}")
    logger.debug(f"Parsed query: {parsed.query[:100] if parsed.query else 'None'}")

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
                'tag': 'socks',
                'listen': '127.0.0.1',
                'port': 10810,
                'protocol': 'socks',
                'settings': {
                    'auth': 'noauth',
                    'udp': True,
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
            'rules': [],
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
        cached_result = Cache.get(cache_key)
        logger.debug(f"Shadowsocks cache get вернул: {type(cached_result)}")
        return cached_result
    
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
            logger.debug(f"Shadowsocks method={method}, password={password}")
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
        logger.debug(f"Hysteria2 cache hit: {cache_key[:20]}...")
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
    
    logger.debug(f"Hysteria2 normalized key: {key[:80]}...")
    
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
    logger.debug(f"parse_hysteria2_key: parsed {result['server']}:{result['port']}")
    
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
    logger.debug(f"write_hysteria2_config: writing to {filepath}")
    
    try:
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        temp_path = filepath + '.tmp'
        
        with open(temp_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        
        os.replace(temp_path, filepath)
        logger.debug(f"write_hysteria2_config: config written to {filepath}")
        
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
    
    logger.debug(f"Tor bridges parsed: {len(bridges)} entries")
    return bridges


def tor_config(bridges_text: str) -> Dict[str, Any]:
    """
    Generate Tor configuration from bridges.
    
    Args:
        bridges_text: Multi-line string with bridge entries
    
    Returns:
        Dict with Tor configuration
    """
    logger.debug(f"tor_config: вызов с мостами")
    
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

    try:
        result = subprocess.run(
            ['sh', init_script, 'restart'],
            capture_output=True,
            text=True,
            timeout=60
        )

        success = result.returncode == 0
        output = result.stdout.strip() or result.stderr.strip()

        if success:
            logger.info(f"{service_name} restarted successfully")
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
            # Try pgrep first (faster than running init script)
            script_name = os.path.basename(init_script)
            proc_name = script_name.replace('S', '').split('init')[0]
            pgrep_result = subprocess.run(
                ['pgrep', '-f', init_script],
                capture_output=True, text=True, timeout=5
            )
            if pgrep_result.returncode == 0:
                status = "✅ Активен"
                Cache.set(cache_key, status, ttl=30)
                return status

            # Fallback to init script status check
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
    logger.debug(f"write_json_config: writing to {filepath}")
    temp_path = filepath + '.tmp'

    try:
        os.makedirs(os.path.dirname(filepath), exist_ok=True)

        with open(temp_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)

        os.replace(temp_path, filepath)
        logger.info(f"write_json_config: config written to {filepath}")

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
    logger.debug(f"write_tor_config: writing to {filepath}")
    temp_path = filepath + '.tmp'

    try:
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        with open(temp_path, 'w', encoding='utf-8') as f:
            for key, value in config.items():
                if isinstance(value, list):
                    for item in value:
                        f.write(f"{key} {item}\n")
                else:
                    f.write(f"{key} {value}\n")

        os.replace(temp_path, filepath)
        logger.info(f"write_tor_config: Tor config written to {filepath}")

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
