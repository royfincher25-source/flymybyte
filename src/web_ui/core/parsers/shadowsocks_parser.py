"""
Shadowsocks Parser

Parses Shadowsocks protocol keys and generates configuration.
"""
import base64
import hashlib
import logging
import re
from urllib.parse import urlparse, unquote
from typing import Dict, Any

from ..utils import Cache, logger


class ShadowsocksParser:
    """Shadowsocks key parser"""

    @staticmethod
    def parse(key: str) -> Dict[str, Any]:
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
            logger.info(f"Shadowsocks cache hit: {cache_key[:20]}...")
            cached_result = Cache.get(cache_key)
            logger.info(f"Shadowsocks cache get вернул: {type(cached_result)}")
            return cached_result
        
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
        
        logger.info(f"Shadowsocks normalized key: {key[:80]}...")
        
        url = key[5:]
        parsed_url = urlparse(url)
        
        logger.info(f"Shadowsocks urlparse: hostname={parsed_url.hostname}, username={parsed_url.username}, port={parsed_url.port}")
        
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
                logger.info(f"Shadowsocks decoded: {decoded}")
                method, password = decoded.split(':', 1)
                logger.info(f"Shadowsocks method={method}, password={password}")
            except Exception as e:
                logger.error(f"Shadowsocks base64 error: {e}")
                raise ValueError(f"Ошибка декодирования base64: {str(e)}")
            
            result = {
                'server': parsed_url.hostname,
                'port': port,
                'password': password,
                'method': method,
            }
            logger.info(f"Shadowsocks OK: server={result['server']}, port={result['port']}")

            Cache.set(cache_key, result, ttl=86400)
            return result
        
        logger.info(f"Shadowsocks: нет username, пробуем альтернативный формат")
        
        try:
            url_part = url.split('#')[0]
            logger.info(f"Shadowsocks url_part: {url_part[:80]}...")
            
            at_index = url_part.rfind('@')
            if at_index > 0:
                encoded = url_part[:at_index]
                server_port = url_part[at_index+1:]
                logger.info(f"Shadowsocks manual: encoded={encoded[:50]}..., server_port={server_port}")
                
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
                    logger.info(f"Shadowsocks manual decoded: {decoded}")
                    method, password = decoded.split(':', 1)
                    
                    result = {
                        'server': server,
                        'port': port,
                        'password': password,
                        'method': method,
                    }
                    logger.info(f"Shadowsocks manual OK: server={result['server']}, port={result['port']}")
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
            logger.info(f"Shadowsocks alt decoded: {decoded}")
            
            match = re.match(r'([^:]+):([^@]+)@([^:]+):(\d+)', decoded)
            if match:
                method, password, server, port = match.groups()
                result = {
                    'server': server,
                    'port': int(port),
                    'password': password,
                    'method': method,
                }
                logger.info(f"Shadowsocks alt OK: server={result['server']}, port={result['port']}")
                Cache.set(cache_key, result, ttl=3600)
                return result
        except Exception as e:
            logger.error(f"Shadowsocks alt error: {e}")
        
        logger.error(f"Shadowsocks FAILED: Некорректные данные сервера")
        raise ValueError("Некорректные данные сервера")

    @staticmethod
    def generate_config(key: str) -> Dict[str, Any]:
        """
        Generate Shadowsocks configuration from key.

        Args:
            key: Shadowsocks key string

        Returns:
            Dict with full configuration for shadowsocks-libev
        """
        logger.debug("shadowsocks_config: parsing key")

        parsed = ShadowsocksParser.parse(key)

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
