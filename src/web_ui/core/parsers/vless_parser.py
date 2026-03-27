"""
VLESS Parser

Parses VLESS protocol keys and generates Xray configuration.
"""
import hashlib
import logging
from urllib.parse import urlparse, unquote, parse_qs
from typing import Dict, Any

from ..utils import Cache, logger


class VlessParser:
    """VLESS key parser"""

    @staticmethod
    def parse(key: str) -> Dict[str, Any]:
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
            logger.info(f"VLESS cache hit: {cache_key[:20]}...")
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

        logger.info(f"VLESS normalized key: {key[:80]}...")

        if '?&' in key:
            key = key.replace('?&', '?')
            logger.debug(f"Fixed malformed URL: {key[:80]}...")
        
        parsed = urlparse(key)
        
        logger.debug(f"Parsed scheme: {parsed.scheme}")
        logger.debug(f"Parsed username: {parsed.username}")
        logger.debug(f"Parsed hostname: {parsed.hostname}")
        logger.debug(f"Parsed port: {parsed.port}")
        logger.debug(f"Parsed query: {parsed.query[:100] if parsed.query else 'None'}")

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

        if result['security'] == 'reality':
            result['pbk'] = params.get('pbk', [''])[0]
            result['sid'] = params.get('sid', [''])[0]
            result['spx'] = params.get('spx', [''])[0]
        
        logger.info(f"VLESS parsed successfully: server={server}, port={port}")

        Cache.set(cache_key, result, ttl=86400)
        return result

    @staticmethod
    def generate_config(key: str) -> Dict[str, Any]:
        """
        Generate VLESS configuration from key.
        
        Args:
            key: VLESS key string

        Returns:
            Dict with full configuration for Xray/Singbox
        """
        logger.debug(f"vless_config: parsing key")

        parsed = VlessParser.parse(key)
        
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
                                        'flow': parsed.get('flow', ''),
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
