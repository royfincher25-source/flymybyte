"""
Key Manager — handles VPN key validation and configuration.

Extracted from routes_vpn.py to encapsulate key parsing logic.
"""
import logging
from typing import Dict, Tuple, Optional, Callable

from .parsers import (
    parse_vless_key,
    parse_shadowsocks_key,
    parse_trojan_key,
    parse_proxy_key,
    vless_config,
    shadowsocks_config,
    trojan_config,
    proxy_config,
    write_json_config,
)
from .service_ops import restart_service
from .vpn_manager import VPNManager

logger = logging.getLogger(__name__)


class KeyManager:
    """Manager for VPN key operations."""
    
    # Service parser mappings
    PARSERS: Dict[str, Dict] = {
        'vless': {
            'parser': parse_vless_key,
            'config_gen': vless_config,
            'config_writer': write_json_config,
            'error_msg': 'Invalid VLESS key: missing server/port',
        },
        'proxy': {
            'parser': parse_proxy_key,
            'config_gen': proxy_config,
            'config_writer': write_json_config,
            'error_msg': 'Invalid key: missing server/port',
        },
        'shadowsocks': {
            'parser': parse_proxy_key,
            'config_gen': shadowsocks_config,
            'config_writer': write_json_config,
            'error_msg': 'Invalid Shadowsocks key: missing server/port',
        },
        'trojan': {
            'parser': parse_proxy_key,
            'config_gen': trojan_config,
            'config_writer': write_json_config,
            'error_msg': 'Invalid Trojan key: missing server/port',
        },
    }
    
    def validate(self, key: str, service: str) -> Dict:
        """
        Validate and parse a VPN key.
        
        Args:
            key: The VPN key string
            service: Service name (vless, shadowsocks, trojan, proxy)
            
        Returns:
            Parsed key dict
            
        Raises:
            ValidationError: If key is invalid
        """
        if service not in self.PARSERS:
            raise ValidationError(f'Unsupported service: {service}')
        
        parser_info = self.PARSERS[service]
        parser = parser_info['parser']
        
        if not key or not key.strip():
            raise ValidationError('Key is empty')
        
        try:
            parsed = parser(key.strip())
            if not parsed.get('server') or not parsed.get('port'):
                raise ValidationError(parser_info['error_msg'])
            return parsed
        except Exception as e:
            if isinstance(e, ValidationError):
                raise
            raise ParseError(f'Failed to parse key: {e}')
    
    def save_config(self, key: str, service: str, config_path: str) -> Tuple[bool, str]:
        """
        Save key configuration and optionally restart service.
        
        Args:
            key: The VPN key
            service: Service name
            config_path: Path to config file
            restart: Whether to restart service after saving
            
        Returns:
            Tuple of (success, message)
        """
        if service not in self.PARSERS:
            return False, f'Unsupported service: {service}'
        
        parser_info = self.PARSERS[service]
        
        try:
            parsed = self.validate(key, service)
            config_gen = parser_info['config_gen']
            config_writer = parser_info['config_writer']
            
            config = config_gen(key)
            config_writer(config, config_path)
            
            logger.info(f"[KEY] Config saved for {service}: {config_path}")
            return True, f'Config saved for {service}'
            
        except (ValidationError, ParseError) as e:
            logger.error(f"[KEY] Validation failed for {service}: {e}")
            return False, str(e)
        except Exception as e:
            logger.error(f"[KEY] Save failed for {service}: {e}")
            return False, f'Save error: {e}'
    
    def configure_and_restart(self, key: str, service: str, config_path: str, 
                              init_script: str, service_display_name: str,
                              timeout: int = 30) -> Tuple[bool, str]:
        """
        Full workflow: validate key, save config, restart service.
        
        Args:
            key: VPN key
            service: Service name
            config_path: Path to config file
            init_script: Path to init script
            service_display_name: Display name for messages
            timeout: Restart timeout in seconds
            
        Returns:
            Tuple of (success, message)
        """
        ok, msg = self.save_config(key, service, config_path)
        if not ok:
            return False, msg
        
        try:
            from concurrent.futures import ThreadPoolExecutor, TimeoutError
            
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(restart_service, service_display_name, init_script)
                success, output = future.result(timeout=timeout)
                
                if success:
                    return True, f'{service_display_name} configured and restarted'
                else:
                    return True, f'Config saved, restart error: {output}'
                    
        except TimeoutError:
            return True, f'Config saved, restart timeout ({timeout}s)'
        except Exception as e:
            return True, f'Config saved, error: {e}'


def get_key_manager() -> KeyManager:
    """Get KeyManager singleton."""
    if not hasattr(get_key_manager, '_instance'):
        get_key_manager._instance = KeyManager()
    return get_key_manager._instance