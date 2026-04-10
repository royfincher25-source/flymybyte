"""
Centralized configuration for FlyMyByte.

This module provides a single source of truth for all configurable
values including timeouts, limits, and cache TTLs.
"""
from dataclasses import dataclass, field
from typing import Dict, Any


@dataclass
class Timeouts:
    """Timeout configurations."""
    SERVICE_RESTART: int = 180
    SCRIPT_EXECUTION: int = 120
    BACKGROUND_RESTART: int = 600
    FILE_DOWNLOAD: int = 15
    DNS_QUERY: int = 2
    IPSET_OPERATION: int = 30
    DNSMASQ_RESTART: int = 15


@dataclass
class CacheConfig:
    """Cache TTL configurations (in seconds)."""
    DEFAULT: int = 60
    DNS: int = 86400
    STATUS: int = 60
    STATS: int = 30


@dataclass
class Limits:
    """Limit configurations."""
    MAX_ENTRIES_PER_REQUEST: int = 100
    MAX_ENTRY_LENGTH: int = 253
    MAX_TOTAL_INPUT_SIZE: int = 50 * 1024
    MAX_DOMAINS_COUNT: int = 1000
    IP_BULK_SIZE: int = 5000
    MIN_PORT: int = 1
    MAX_PORT: int = 65535


@dataclass
class DNSConfig:
    """DNS-related configurations."""
    CHECK_INTERVAL: int = 300
    TIMEOUT: int = 2
    FAILURE_THRESHOLD: int = 5
    VPN_DNS_HOST: str = '127.0.0.1'
    VPN_DNS_PORT: int = 40500


@dataclass
class AppConfig:
    """
    Main application configuration container.
    
    Use Settings.load() to get configuration from environment or defaults.
    """
    timeouts: Timeouts = field(default_factory=Timeouts)
    cache: CacheConfig = field(default_factory=CacheConfig)
    limits: Limits = field(default_factory=Limits)
    dns: DNSConfig = field(default_factory=DNSConfig)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for backward compatibility."""
        return {
            'TIMEOUT_SERVICE_RESTART': self.timeouts.SERVICE_RESTART,
            'TIMEOUT_SCRIPT': self.timeouts.SCRIPT_EXECUTION,
            'TIMEOUT_BACKUP_RESTART': self.timeouts.BACKGROUND_RESTART,
            'DEFAULT_CACHE_TTL': self.cache.DEFAULT,
            'DNS_CACHE_TTL': self.cache.DNS,
            'STATUS_CACHE_TTL': self.cache.STATUS,
            'MAX_ENTRIES_PER_REQUEST': self.limits.MAX_ENTRIES_PER_REQUEST,
            'MAX_ENTRY_LENGTH': self.limits.MAX_ENTRY_LENGTH,
            'MAX_TOTAL_INPUT_SIZE': self.limits.MAX_TOTAL_INPUT_SIZE,
            'MAX_DOMAINS_COUNT': self.limits.MAX_DOMAINS_COUNT,
            'IP_BULK_SIZE': self.limits.IP_BULK_SIZE,
            'MIN_PORT': self.limits.MIN_PORT,
            'MAX_PORT': self.limits.MAX_PORT,
            'DNS_CHECK_INTERVAL': self.dns.CHECK_INTERVAL,
            'DNS_TIMEOUT': self.dns.TIMEOUT,
            'DNS_FAILURE_THRESHOLD': self.dns.FAILURE_THRESHOLD,
            'VPN_DNS_HOST': self.dns.VPN_DNS_HOST,
            'VPN_DNS_PORT': self.dns.VPN_DNS_PORT,
        }


# Global singleton instance
_config: AppConfig | None = None


def get_config() -> AppConfig:
    """Get global configuration instance (singleton)."""
    global _config
    if _config is None:
        _config = AppConfig()
    return _config


# Backward compatibility - expose constants directly
TIMEOUT_SERVICE_RESTART = 180
TIMEOUT_SCRIPT = 120
TIMEOUT_BACKUP_RESTART = 600
FILE_DOWNLOAD_TIMEOUT = 15

DEFAULT_CACHE_TTL = 60
DNS_CACHE_TTL = 86400
STATUS_CACHE_TTL = 60

MAX_ENTRIES_PER_REQUEST = 100
MAX_ENTRY_LENGTH = 253
MAX_TOTAL_INPUT_SIZE = 50 * 1024
IPSET_MAX_BULK_ENTRIES = 5000
MAX_DOMAINS_COUNT = 1000

DNS_CHECK_INTERVAL = 300
DNS_TIMEOUT = 2
DNS_FAILURE_THRESHOLD = 5

MIN_PORT = 1
MAX_PORT = 65535