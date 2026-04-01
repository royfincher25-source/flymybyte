"""
FlyMyByte Web Interface - Application Configuration

Singleton WebConfig class for managing application settings.
"""
import os
import re
import sys
import threading
from pathlib import Path
from typing import Any, Dict, Optional

from .constants import (
    DEFAULT_WEB_HOST,
    DEFAULT_WEB_PORT,
    DEFAULT_WEB_PASSWORD,
    DEFAULT_ROUTER_IP,
    DEFAULT_UNBLOCK_DIR,
    MIN_PORT,
    MAX_PORT,
)

# Import env_parser
WEB_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(WEB_ROOT))

try:
    from env_parser import load_env_file
except ImportError:
    def load_env_file(filepath):
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
    """
    Singleton configuration manager.

    Loads settings from .env file with fallback to defaults.
    Thread-safe with double-check locking.

    Example:
        >>> config = WebConfig()
        >>> config.web_port
        8080
        >>> config.is_valid()
        True
    """

    _instance: Optional['WebConfig'] = None
    _cache: Dict[str, Any] = {}
    _loaded: bool = False
    _env_file: Optional[str] = None
    _lock: threading.Lock = threading.Lock()

    def __new__(cls, env_file: Optional[str] = None) -> 'WebConfig':
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, env_file: Optional[str] = None):
        if not self._loaded:
            self._env_file = env_file
            self._load_config()
            self._loaded = True

    def _load_config(self) -> None:
        """Load configuration from .env file and environment variables."""
        if self._env_file is None:
            module_dir = os.path.dirname(os.path.abspath(__file__))
            parent_dir = os.path.dirname(module_dir)
            self._env_file = os.path.join(parent_dir, '.env')
            if not os.path.exists(self._env_file):
                self._env_file = str(WEB_ROOT / '.env')

        file_config = load_env_file(self._env_file)
        self._cache = {
            'WEB_HOST': os.environ.get('WEB_HOST', file_config.get('WEB_HOST', DEFAULT_WEB_HOST)),
            'WEB_PORT': os.environ.get('WEB_PORT', file_config.get('WEB_PORT', str(DEFAULT_WEB_PORT))),
            'WEB_PASSWORD': os.environ.get('WEB_PASSWORD', file_config.get('WEB_PASSWORD', DEFAULT_WEB_PASSWORD)),
            'ROUTER_IP': os.environ.get('ROUTER_IP', file_config.get('ROUTER_IP', DEFAULT_ROUTER_IP)),
            'UNBLOCK_DIR': os.environ.get('UNBLOCK_DIR', file_config.get('UNBLOCK_DIR', DEFAULT_UNBLOCK_DIR)),
        }

    @property
    def web_host(self) -> str:
        return self._get_value('WEB_HOST', DEFAULT_WEB_HOST)

    @property
    def web_port(self) -> int:
        value = self._get_value('WEB_PORT', str(DEFAULT_WEB_PORT))
        try:
            port = int(value)
            if not (MIN_PORT <= port <= MAX_PORT):
                return DEFAULT_WEB_PORT
            return port
        except (ValueError, TypeError):
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

    def _get_value(self, key: str, default: str) -> Any:
        if not self._loaded:
            self._load_config()
        return self._cache.get(key, default)

    def is_valid(self) -> bool:
        """Check if configuration is valid."""
        if not self.web_password or not self.web_password.strip():
            return False
        if not (MIN_PORT <= self.web_port <= MAX_PORT):
            return False
        if not self._is_valid_ip(self.router_ip):
            return False
        if not self._is_valid_host(self.web_host):
            return False
        return True

    def validate(self) -> bool:
        """Validate configuration, raising ValueError if invalid."""
        if not self.is_valid():
            errors = []
            if not self.web_password or not self.web_password.strip():
                errors.append("WEB_PASSWORD cannot be empty")
            if not (MIN_PORT <= self.web_port <= MAX_PORT):
                errors.append(f"WEB_PORT must be {MIN_PORT}-{MAX_PORT}")
            if not self._is_valid_ip(self.router_ip):
                errors.append(f"ROUTER_IP '{self.router_ip}' is invalid")
            if not self._is_valid_host(self.web_host):
                errors.append(f"WEB_HOST '{self.web_host}' is invalid")
            raise ValueError("; ".join(errors))
        return True

    def _is_valid_ip(self, ip: str) -> bool:
        if not ip:
            return False
        pattern = r'^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$'
        match = re.match(pattern, ip)
        if not match:
            return False
        return all(0 <= int(g) <= 255 for g in match.groups())

    def _is_valid_host(self, host: str) -> bool:
        if not host:
            return False
        if host in ('0.0.0.0', 'localhost', '127.0.0.1'):
            return True
        if self._is_valid_ip(host):
            return True
        pattern = r'^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*$'
        return bool(re.match(pattern, host))

    def to_dict(self) -> Dict[str, Any]:
        return {
            'web_host': self.web_host,
            'web_port': self.web_port,
            'web_password': self.web_password,
            'router_ip': self.router_ip,
            'unblock_dir': self.unblock_dir,
        }

    def __repr__(self) -> str:
        return (
            f"WebConfig(web_host='{self.web_host}', "
            f"web_port={self.web_port}, "
            f"web_password='***', "
            f"router_ip='{self.router_ip}', "
            f"unblock_dir='{self.unblock_dir}')"
        )

    def clear_cache(self) -> None:
        self._cache = {}
        self._loaded = False

    def reload(self) -> None:
        with self._lock:
            self.clear_cache()
            self._load_config()
            self._loaded = True


def get_config(env_file: Optional[str] = None) -> WebConfig:
    """Get WebConfig singleton instance."""
    return WebConfig(env_file=env_file)
