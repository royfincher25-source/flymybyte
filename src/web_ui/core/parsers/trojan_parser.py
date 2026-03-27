"""
Trojan Parser

Parses Trojan protocol keys and generates configuration.
"""
import hashlib
import logging
from urllib.parse import urlparse, unquote, parse_qs
from typing import Dict, Any

from ..utils import Cache, logger


class TrojanParser:
    """Trojan key parser"""

    @staticmethod
    def parse(key: str) -> Dict[str, Any]:
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
            logger.info(f"Trojan cache hit: {cache_key[:20]}...")
            return Cache.get(cache_key)

        if not key.startswith('trojan://'):
            raise ValueError("Неверный формат ключа Trojan")
        
        key = key.strip()
        key = unquote(key)
        
        try:
            key = key.encode('ascii', 'ignore').decode('ascii')
        except Exception as e:
            logger.error(f"Trojan ASCII encode error: {e}")
        
        logger.info(f"Trojan normalized key: {key[:80]}...")
        
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

        logger.info(f"Trojan parsed successfully: server={server}, port={port}")

        Cache.set(cache_key, result, ttl=86400)
        return result

    @staticmethod
    def generate_config(key: str) -> Dict[str, Any]:
        """
        Generate Trojan configuration from key.

        Args:
            key: Trojan key string

        Returns:
            Dict with full configuration
        """
        logger.debug("trojan_config: parsing key")

        parsed = TrojanParser.parse(key)

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
