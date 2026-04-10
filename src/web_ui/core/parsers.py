"""
FlyMyByte Web Interface - Key Parsers

Parsers for VPN keys (VLESS, Shadowsocks, Trojan).
Memory-optimized for embedded devices (128MB RAM).
"""
import base64
import hashlib
import logging
import re
from typing import Dict, Any
from urllib.parse import urlparse, unquote, parse_qs

from .utils import Cache, logger


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
    cache_key = f'vless:{hashlib.md5(key.encode()).hexdigest()}'

    if Cache.is_valid(cache_key):
        logger.debug(f"VLESS cache hit: {cache_key[:20]}...")
        return Cache.get(cache_key)

    if not key.startswith('vless://'):
        raise ValueError("Неверный формат ключа VLESS")

    key = key.strip()
    
    if '#' in key:
        base, fragment = key.split('#', 1)
        fragment = fragment.encode('ascii', 'ignore').decode('ascii')
        key = base + '#' + fragment
    
    key = ''.join(c for c in key if ord(c) >= 32 or c in '\t\n\r')
    key = unquote(key)

    try:
        key = key.encode('ascii', 'ignore').decode('ascii')
    except Exception as e:
        logger.error(f"VLESS ASCII encode error: {e}")

    logger.debug(f"VLESS normalized key: {key[:80]}...")

    if '?&' in key:
        key = key.replace('?&', '?')
        logger.debug(f"Fixed malformed URL: {key[:80]}...")
    
    parsed = urlparse(key)
    
    logger.debug(f"VLESS parsed: scheme={parsed.scheme}, host={parsed.hostname}, port={parsed.port}, query_len={len(parsed.query) if parsed.query else 0}")

    uuid = parsed.username
    if not uuid:
        logger.error(f"UUID not found! Full URL: {key[:100]}")
        raise ValueError("UUID не найден в ключе")
    
    server = parsed.hostname
    port = parsed.port
    
    if not server or not port:
        raise ValueError("Сервер или порт не найдены")
    
    if not (1 <= port <= 65535):
        raise ValueError(f"Порт должен быть от 1 до 65535, получен {port}")
    
    params = parse_qs(parsed.query)
    
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
        'flow': params.get('flow', [''])[0],
        'name': parsed.fragment or 'VLESS',
    }

    if result['type'] == 'xhttp':
        result['xhttp_mode'] = params.get('mode', ['stream-one'])[0]
        result['xhttp_max_upload_upload'] = params.get('maxUploadUpload', [''])[0]
        result['xhttp_max_concurrent_upload'] = params.get('maxConcurrentUpload', [''])[0]

        valid_modes = ['stream-one', 'stream-multi']
        if result['xhttp_mode'] not in valid_modes:
            logger.warning(f"XHTTP mode '{result['xhttp_mode']}' not in {valid_modes}, using default 'stream-one'")
            result['xhttp_mode'] = 'stream-one'

        if not result['host'] or result['host'] == server:
            raise ValueError("Для XHTTP необходимо указать host (SNI)")
        if not result['path']:
            result['path'] = '/'

    if result['security'] == 'reality':
        result['pbk'] = params.get('pbk', [''])[0]
        result['sid'] = params.get('sid', [''])[0]
        result['spx'] = params.get('spx', [''])[0]
    
    logger.debug(f"VLESS parsed successfully: server={server}, port={port}")

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
    logger.debug("vless_config: parsing key")

    parsed = parse_vless_key(key)
    
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
                                    'flow': parsed.get('flow', ''),
                                }
                            ]
                        }
                    ]
                },
                'streamSettings': {
                    'network': parsed['type'],
                    'security': parsed['security'],
                    'tlsSettings': {
                        'serverName': parsed['sni'],
                        'alpn': parsed['alpn'].split(','),
                        'fingerprint': parsed['fp'],
                    } if parsed['security'] in ('tls', 'reality') else {},
                } if parsed['type'] != 'tcp' else {},
            },
            {
                'tag': 'direct',
                'protocol': 'freedom',
            },
        ],
        'routing': {
            'domainStrategy': 'IPIfNonMatch',
            'rules': [
                {
                    'type': 'field',
                    'outboundTag': 'direct',
                    'domain': [
                        'geosite:category-ads-all',
                    ]
                },
                {
                    'type': 'field',
                    'outboundTag': 'direct',
                    'ip': [
                        'geoip:private',
                    ]
                }
            ]
        }
    }

    if parsed['type'] != 'tcp':
        config['outbounds'][0]['streamSettings']['wsSettings'] = {
            'path': parsed['path'],
            'headers': {
                'Host': parsed['host'],
            }
        }

    logger.debug("vless_config: generated")
    return config


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
    cache_key = f'ss:{hashlib.md5(key.encode()).hexdigest()}'

    if Cache.is_valid(cache_key):
        logger.debug(f"Shadowsocks cache hit: {cache_key[:20]}...")
        return Cache.get(cache_key)
    
    if not key.startswith('ss://'):
        raise ValueError("Неверный формат ключа Shadowsocks")
    
    key = key.strip()
    key = ''.join(c for c in key if ord(c) >= 32 or c in '\t\n\r')
    
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
    
    url = key[5:]
    parsed_url = urlparse(url)
    
    logger.debug(f"Shadowsocks urlparse: hostname={parsed_url.hostname}, username={parsed_url.username}, port={parsed_url.port}")
    
    if parsed_url.hostname and parsed_url.username:
        port = parsed_url.port
        if not port or not (1 <= port <= 65535):
            raise ValueError(f"Порт должен быть от 1 до 65535")
        
        try:
            encoded = parsed_url.username
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

        Cache.set(cache_key, result, ttl=86400)
        return result
    
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
    cache_key = f'trojan:{hashlib.md5(key.encode()).hexdigest()}'

    if Cache.is_valid(cache_key):
        logger.debug(f"Trojan cache hit: {cache_key[:20]}...")
        return Cache.get(cache_key)

    if not key.startswith('trojan://'):
        raise ValueError("Неверный формат ключа Trojan")
    
    key = key.strip()
    key = unquote(key)
    
    try:
        key = key.encode('ascii', 'ignore').decode('ascii')
    except Exception as e:
        logger.error(f"Trojan ASCII encode error: {e}")
    
    logger.debug(f"Trojan normalized key: {key[:80]}...")
    
    url = key[11:]
    parsed = urlparse(url)
    
    password = parsed.username
    if not password:
        raise ValueError("Пароль не найден в ключе")
    
    server = parsed.hostname
    port = parsed.port
    
    if not server or not port:
        raise ValueError("Сервер или порт не найдены")
    
    if not (1 <= port <= 65535):
        raise ValueError(f"Порт должен быть от 1 до 65535")
    
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

    Cache.set(cache_key, result, ttl=86400)
    return result


def trojan_config(key: str) -> Dict[str, Any]:
    """
    Generate Trojan configuration from key.

    Args:
        key: Trojan key string

    Returns:
        Dict with full configuration for Trojan
    """
    logger.debug("trojan_config: parsing key")

    parsed = parse_trojan_key(key)

    config = {
        'run_type': 'client',
        'local_addr': '::',
        'local_port': 1083,
        'remote_addr': parsed['server'],
        'remote_port': parsed['port'],
        'password': [parsed['password']],
        'ssl': {
            'verify': True,
            'verify_hostname': True,
            'sni': parsed['sni'],
            'alpn': parsed['alpn'].split(','),
        },
        'tcp': {
            'no_delay': True,
            'keep_alive': True,
        },
    }

    logger.debug("trojan_config: generated")
    return config


def parse_proxy_key(key: str) -> Dict[str, Any]:
    """
    Unified proxy parser — auto-detects Shadowsocks or Trojan by URL scheme.

    Args:
        key: Proxy key string (ss:// or trojan://)

    Returns:
        Dict with parsed configuration

    Raises:
        ValueError: If key format is invalid
    """
    key = key.strip()

    if key.startswith('ss://'):
        return parse_shadowsocks_key(key)
    elif key.startswith('trojan://'):
        return parse_trojan_key(key)
    elif key.startswith('vless://'):
        return parse_vless_key(key)
    else:
        raise ValueError("Неверный формат ключа")


def proxy_config(key: str) -> Dict[str, Any]:
    """
    Generate proxy configuration (auto-detect type).

    Args:
        key: Proxy key string

    Returns:
        Dict with configuration

    Raises:
        ValueError: If key format is invalid
    """
    key = key.strip()

    if key.startswith('ss://'):
        return shadowsocks_config(key)
    elif key.startswith('trojan://'):
        return trojan_config(key)
    elif key.startswith('vless://'):
        return vless_config(key)
    else:
        raise ValueError("Неверный формат ключа")