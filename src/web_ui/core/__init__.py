# =============================================================================
# CORE MODULE FOR BYPASS_KEENETIC WEB
# =============================================================================
# Базовые компоненты ядра web-приложения
# =============================================================================

from .app_config import WebConfig
from .utils import (
    validate_bypass_entry,
    load_bypass_list,
    save_bypass_list,
    run_unblock_update,
    Cache,
    cleanup_memory
)
from .services import (
    # VLESS
    parse_vless_key,
    vless_config,
    # Shadowsocks
    parse_shadowsocks_key,
    shadowsocks_config,
    # Trojan
    parse_trojan_key,
    trojan_config,
    # Tor
    parse_tor_bridges,
    tor_config,
    # Service management
    restart_service,
    check_service_status,
    # Config writers
    write_json_config,
    write_tor_config,
)
from .dns_monitor import (
    DNSMonitor,
    check_dns_server,
    get_dns_monitor,
)

__all__ = [
    # Config
    'WebConfig',
    # Bypass utilities
    'validate_bypass_entry',
    'load_bypass_list',
    'save_bypass_list',
    'run_unblock_update',
    'Cache',
    'cleanup_memory',
    # Key parsers
    'parse_vless_key',
    'vless_config',
    'parse_shadowsocks_key',
    'shadowsocks_config',
    'parse_trojan_key',
    'trojan_config',
    'parse_tor_bridges',
    'tor_config',
    # Service management
    'restart_service',
    'check_service_status',
    # Config writers
    'write_json_config',
    'write_tor_config',
    # DNS Monitor
    'DNSMonitor',
    'check_dns_server',
    'get_dns_monitor',
]
