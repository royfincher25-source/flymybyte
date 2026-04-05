# =============================================================================
# CORE MODULE FOR BYPASS_KEENETIC WEB
# =============================================================================
# Базовые компоненты ядра web-приложения
# =============================================================================

from .app_config import WebConfig
from .decorators import login_required, get_csrf_token, validate_csrf_token, csrf_required
from .utils import (
    validate_bypass_entry,
    load_bypass_list,
    save_bypass_list,
    run_unblock_update,
    Cache,
    cleanup_memory,
    setup_logging,
)
from .services import (
    parse_vless_key,
    vless_config,
    parse_shadowsocks_key,
    shadowsocks_config,
    parse_trojan_key,
    trojan_config,
    parse_tor_bridges,
    tor_config,
    restart_service,
    check_service_status,
    write_json_config,
    write_tor_config,
    bulk_add_to_ipset,
    ensure_ipset_exists,
    bulk_remove_from_ipset,
    get_catalog,
    download_list,
    DNSSpoofing,
    apply_dns_spoofing,
    disable_dns_spoofing,
    get_dns_spoofing_status,
)
from .dns_ops import (
    DNSMonitor,
    check_dns_server,
    get_dns_monitor,
)

__all__ = [
    'WebConfig',
    'login_required',
    'get_csrf_token',
    'validate_csrf_token',
    'csrf_required',
    'validate_bypass_entry',
    'load_bypass_list',
    'save_bypass_list',
    'run_unblock_update',
    'Cache',
    'cleanup_memory',
    'setup_logging',
    'parse_vless_key',
    'vless_config',
    'parse_shadowsocks_key',
    'shadowsocks_config',
    'parse_trojan_key',
    'trojan_config',
    'parse_tor_bridges',
    'tor_config',
    'restart_service',
    'check_service_status',
    'write_json_config',
    'write_tor_config',
    'bulk_add_to_ipset',
    'ensure_ipset_exists',
    'bulk_remove_from_ipset',
    'get_catalog',
    'download_list',
    'DNSSpoofing',
    'apply_dns_spoofing',
    'disable_dns_spoofing',
    'get_dns_spoofing_status',
    'DNSMonitor',
    'check_dns_server',
    'get_dns_monitor',
]
