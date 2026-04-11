"""
FlyMyByte Web Interface - Application Configuration

Singleton WebConfig class for managing application settings.
Includes SERVICES, INIT_SCRIPTS, CONFIG_PATHS moved from constants.py
"""
import os
import re
import threading
from pathlib import Path
from typing import Any, Optional

from .constants import (
    DEFAULT_WEB_HOST,
    DEFAULT_WEB_PORT,
    DEFAULT_WEB_PASSWORD,
    DEFAULT_ROUTER_IP,
    DEFAULT_UNBLOCK_DIR,
    MIN_PORT,
    MAX_PORT,
    INIT_DIR,
    XRAY_DIR,
    TROJAN_CONFIG_DIR,
    SHADOWSOCKS_CONFIG,
    WEB_UI_DIR,
    DNSMASQ_CONFIG,
    CRONTAB_FILE,
)

WEB_ROOT = Path(__file__).parent.parent

try:
    from env_parser import load_env_file
except ImportError:
    def load_env_file(filepath: str) -> dict:
        env = {}
        if os.path.exists(filepath):
            with open(filepath, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        match = re.match(r'^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$', line)
                        if match:
                            key, value = match.group(1), match.group(2)
                            if (value.startswith('"') and value.endswith('"')) or \
                               (value.startswith("'") and value.endswith("'")):
                                value = value[1:-1]
                            env[key] = value
        return env


class WebConfig:
    """Singleton configuration manager loaded from .env file."""

    _instance: Optional['WebConfig'] = None
    _lock: threading.Lock = threading.Lock()
    _loaded: bool = False

    def __new__(cls, env_file: Optional[str] = None) -> 'WebConfig':
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, env_file: Optional[str] = None):
        if not WebConfig._loaded:
            self._cache: dict = {}
            if env_file is None:
                env_file = str(WEB_ROOT / '.env')
            self._load_config(env_file)
            WebConfig._loaded = True

    def _load_config(self, env_file: str) -> None:
        file_config = load_env_file(env_file)
        self._cache = {
            'WEB_HOST': os.environ.get('WEB_HOST', file_config.get('WEB_HOST', DEFAULT_WEB_HOST)),
            'WEB_PORT': os.environ.get('WEB_PORT', file_config.get('WEB_PORT', str(DEFAULT_WEB_PORT))),
            'WEB_PASSWORD': os.environ.get('WEB_PASSWORD', file_config.get('WEB_PASSWORD', DEFAULT_WEB_PASSWORD)),
            'ROUTER_IP': os.environ.get('ROUTER_IP', file_config.get('ROUTER_IP', DEFAULT_ROUTER_IP)),
            'UNBLOCK_DIR': os.environ.get('UNBLOCK_DIR', file_config.get('UNBLOCK_DIR', DEFAULT_UNBLOCK_DIR)),
        }

    def _get_value(self, key: str, default: Any) -> Any:
        return self._cache.get(key, default)

    @property
    def web_host(self) -> str:
        return self._get_value('WEB_HOST', DEFAULT_WEB_HOST)

    @property
    def web_port(self) -> int:
        try:
            port = int(self._get_value('WEB_PORT', str(DEFAULT_WEB_PORT)))
            if MIN_PORT <= port <= MAX_PORT:
                return port
        except (ValueError, TypeError):
            pass
        return DEFAULT_WEB_PORT

    @property
    def web_password(self) -> str:
        return self._get_value('WEB_PASSWORD', DEFAULT_WEB_PASSWORD)

    @property
    def router_ip(self) -> str:
        return self._get_value('ROUTER_IP', DEFAULT_ROUTER_IP)

    @property
    def unblock_dir(self) -> str:
        return self._get_value('UNBLOCK_DIR', DEFAULT_UNBLOCK_DIR)

    def is_valid(self) -> bool:
        if not self.web_password or not self.web_password.strip():
            return False
        if not (MIN_PORT <= self.web_port <= MAX_PORT):
            return False
        if not self._is_valid_ip(self.router_ip):
            return False
        if not self._is_valid_host(self.web_host):
            return False
        return True

    @staticmethod
    def _is_valid_ip(ip: str) -> bool:
        if not ip:
            return False
        match = re.match(r'^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$', ip)
        if not match:
            return False
        return all(0 <= int(g) <= 255 for g in match.groups())

    @staticmethod
    def _is_valid_host(host: str) -> bool:
        if not host:
            return False
        if host in ('0.0.0.0', 'localhost', '127.0.0.1'):
            return True
        if WebConfig._is_valid_ip(host):
            return True
        pattern = r'^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*$'
        return bool(re.match(pattern, host))


SERVICES = {
    'vless': {
        'name': 'VLESS',
        'init': f'{INIT_DIR}/S24xray',
        'config': f'{XRAY_DIR}/vless.json',
    },
    'proxy': {
        'name': 'Прокси',
        'init': f'{INIT_DIR}/S22proxy',
        'config': '/opt/etc/proxy.json',
    },
    'shadowsocks': {
        'name': 'Shadowsocks',
        'init': f'{INIT_DIR}/S22shadowsocks',
        'config': SHADOWSOCKS_CONFIG,
    },
    'trojan': {
        'name': 'Trojan',
        'init': f'{INIT_DIR}/S22trojan',
        'config': f'{INIT_DIR}/trojan.json',
    },
}

INIT_SCRIPTS = {
    'vless': SERVICES['vless']['init'],
    'proxy': SERVICES['proxy']['init'],
    'shadowsocks': SERVICES['shadowsocks']['init'],
    'trojan': SERVICES['trojan']['init'],
    'unblock': f'{INIT_DIR}/S99unblock',
    'dnsmasq': f'{INIT_DIR}/S56dnsmasq',
    'web_ui': f'{INIT_DIR}/S99web_ui',
}

CONFIG_PATHS = {
    'vless': SERVICES['vless']['config'],
    'proxy': SERVICES['proxy']['config'],
    'shadowsocks': SERVICES['shadowsocks']['config'],
    'trojan': SERVICES['trojan']['config'],
    'dnsmasq': DNSMASQ_CONFIG,
}
