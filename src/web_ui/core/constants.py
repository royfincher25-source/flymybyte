"""
Constants - Centralized configuration and paths

All magic numbers, configuration values, and file paths are stored here.
"""

# =============================================================================
# INPUT VALIDATION
# =============================================================================

MAX_ENTRIES_PER_REQUEST = 100
MAX_ENTRY_LENGTH = 253
MAX_TOTAL_INPUT_SIZE = 50 * 1024

# =============================================================================
# LOGGING
# =============================================================================

LOG_MAX_BYTES = 100 * 1024
LOG_BACKUP_COUNT = 3

# =============================================================================
# CACHE
# =============================================================================

CACHE_MAX_ENTRIES = 30
CACHE_DEFAULT_TTL = 60
SERVICE_STATUS_TTL = 30

# =============================================================================
# DNS
# =============================================================================

DNS_CHECK_INTERVAL = 60
DNS_TIMEOUT = 3
DNS_FAILURE_THRESHOLD = 3

DEFAULT_DNS_SERVERS = {
    'primary': [
        {'name': 'Google DNS', 'host': '8.8.8.8', 'port': 53},
        {'name': 'Cloudflare', 'host': '1.1.1.1', 'port': 53},
    ],
    'backup': [
        {'name': 'Quad9', 'host': '9.9.9.9', 'port': 53},
        {'name': 'OpenDNS', 'host': '208.67.222.222', 'port': 53},
    ],
}

# =============================================================================
# WEB SERVER
# =============================================================================

DEFAULT_WEB_HOST = "0.0.0.0"
DEFAULT_WEB_PORT = 8080
DEFAULT_WEB_PASSWORD = "changeme"
DEFAULT_ROUTER_IP = "192.168.1.1"
DEFAULT_UNBLOCK_DIR = "/opt/etc/unblock/"

MIN_PORT = 1
MAX_PORT = 65535

# =============================================================================
# THREAD POOL & TIMEOUTS
# =============================================================================

THREAD_POOL_WORKERS = 4
SERVICE_RESTART_TIMEOUT = 60
WEB_UI_RESTART_TIMEOUT = 30
SCRIPT_EXECUTION_TIMEOUT = 120
FILE_DOWNLOAD_TIMEOUT = 60
DNSMASQ_RESTART_TIMEOUT = 10

# =============================================================================
# UPDATE
# =============================================================================

UPDATE_SCRIPT_STEPS = 5
UPDATE_PROGRESS_INTERVAL = 3000
UPDATE_RELOAD_DELAY = 3000

# =============================================================================
# IPSET
# =============================================================================

IPSET_MAX_BULK_ENTRIES = 5000
DNS_RESOLVER_BATCH_SIZE = 100

# =============================================================================
# MEMORY MANAGEMENT
# =============================================================================

MEMORY_LOW_THRESHOLD = 20
MEMORY_CRITICAL_THRESHOLD = 10
MEMORY_MODE_NORMAL = 'normal'
MEMORY_MODE_LOW = 'low'
MEMORY_MODE_AGGRESSIVE = 'aggressive'

MEMORY_MODES = {
    MEMORY_MODE_NORMAL: {'cache': 30, 'dns_interval': 60},
    MEMORY_MODE_LOW: {'cache': 15, 'dns_interval': 120},
    MEMORY_MODE_AGGRESSIVE: {'cache': 5, 'dns_interval': 180},
}

# =============================================================================
# GITHUB
# =============================================================================

GITHUB_REPO = 'royfincher25-source/flymybyte'
GITHUB_BRANCH = 'master'
GITHUB_RAW_BASE = f'https://raw.githubusercontent.com/{GITHUB_REPO}/{GITHUB_BRANCH}'

# =============================================================================
# DIRECTORY PATHS
# =============================================================================

WEB_UI_DIR = '/opt/etc/web_ui'
UNBLOCK_DIR = '/opt/etc/unblock'
BACKUP_DIR = '/opt/root/backup'
TMP_DIR = '/tmp'
INIT_DIR = '/opt/etc/init.d'
NDM_DIR = '/opt/etc/ndm'
XRAY_DIR = '/opt/etc/xray'
TOR_DIR = '/opt/etc/tor'

# =============================================================================
# FILE PATHS
# =============================================================================

WEB_UI_LOG_FILE = '/opt/var/log/web_ui.log'
WEB_UI_PIDFILE = '/var/run/web_ui.pid'
TMP_RESTART_SCRIPT = '/tmp/restart_webui.sh'

DNSMASQ_CONFIG = '/opt/etc/dnsmasq.conf'
DNSMASQ_AI_CONFIG = '/opt/etc/unblock-ai.dnsmasq'
DNSMASQ_AI_TEMPLATE = '/opt/etc/web_ui/resources/config/unblock-ai.dnsmasq.template'

AI_DOMAINS_LIST = '/opt/etc/unblock/ai-domains.txt'

SHADOWSOCKS_CONFIG = '/opt/etc/shadowsocks.json'
TROJAN_CONFIG_DIR = '/opt/etc/trojan'
HYSTERIA2_CONFIG = '/opt/etc/hysteria2.json'
CRONTAB_FILE = '/opt/etc/crontab'

# =============================================================================
# SCRIPT PATHS
# =============================================================================

SCRIPT_UNBLOCK_IPSET = '/opt/bin/unblock_ipset.sh'
SCRIPT_UNBLOCK_DNSMASQ = '/opt/bin/unblock_dnsmasq.sh'
SCRIPT_UNBLOCK_UPDATE = '/opt/bin/unblock_update.sh'
SCRIPT_INSTALL = '/opt/root/script.sh'

# =============================================================================
# SERVICE CONFIGURATIONS
# =============================================================================

SERVICES = {
    'vless': {
        'name': 'VLESS',
        'init': f'{INIT_DIR}/S24xray',
        'config': f'{XRAY_DIR}/vless.json',
    },
    'hysteria2': {
        'name': 'Hysteria 2',
        'init': f'{INIT_DIR}/S22hysteria2',
        'config': HYSTERIA2_CONFIG,
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
    'tor': {
        'name': 'Tor',
        'init': f'{INIT_DIR}/S35tor',
        'config': f'{TOR_DIR}/torrc',
    },
}

INIT_SCRIPTS = {
    'vless': SERVICES['vless']['init'],
    'hysteria2': SERVICES['hysteria2']['init'],
    'shadowsocks': SERVICES['shadowsocks']['init'],
    'trojan': SERVICES['trojan']['init'],
    'tor': SERVICES['tor']['init'],
    'unblock': f'{INIT_DIR}/S99unblock',
    'dnsmasq': f'{INIT_DIR}/S56dnsmasq',
    'web_ui': f'{INIT_DIR}/S99web_ui',
}

CONFIG_PATHS = {
    'vless': SERVICES['vless']['config'],
    'hysteria2': SERVICES['hysteria2']['config'],
    'shadowsocks': SERVICES['shadowsocks']['config'],
    'trojan': SERVICES['trojan']['config'],
    'tor': SERVICES['tor']['config'],
    'dnsmasq': DNSMASQ_CONFIG,
}

# =============================================================================
# UPDATE FILES
# =============================================================================

FILES_TO_UPDATE = {
    'VERSION': f'{WEB_UI_DIR}/VERSION',
    'web_ui/.env.example': f'{WEB_UI_DIR}/.env.example',
    'web_ui/__init__.py': f'{WEB_UI_DIR}/__init__.py',
    'web_ui/routes_service.py': f'{WEB_UI_DIR}/routes_service.py',
    'web_ui/routes_keys.py': f'{WEB_UI_DIR}/routes_keys.py',
    'web_ui/routes_bypass.py': f'{WEB_UI_DIR}/routes_bypass.py',
    'web_ui/app.py': f'{WEB_UI_DIR}/app.py',
    'web_ui/env_parser.py': f'{WEB_UI_DIR}/env_parser.py',
    'web_ui/core/__init__.py': f'{WEB_UI_DIR}/core/__init__.py',
    'web_ui/core/constants.py': f'{WEB_UI_DIR}/core/constants.py',
    'web_ui/core/utils.py': f'{WEB_UI_DIR}/core/utils.py',
    'web_ui/core/services.py': f'{WEB_UI_DIR}/core/services.py',
    'web_ui/core/decorators.py': f'{WEB_UI_DIR}/core/decorators.py',
    'web_ui/core/backup_service.py': f'{WEB_UI_DIR}/core/backup_service.py',
    'web_ui/core/update_service.py': f'{WEB_UI_DIR}/core/update_service.py',
    'web_ui/core/dns_monitor.py': f'{WEB_UI_DIR}/core/dns_monitor.py',
    'web_ui/core/dns_manager.py': f'{WEB_UI_DIR}/core/dns_manager.py',
    'web_ui/core/dns_resolver.py': f'{WEB_UI_DIR}/core/dns_resolver.py',
    'web_ui/core/ipset_manager.py': f'{WEB_UI_DIR}/core/ipset_manager.py',
    'web_ui/core/app_config.py': f'{WEB_UI_DIR}/core/app_config.py',
    'web_ui/core/list_catalog.py': f'{WEB_UI_DIR}/core/list_catalog.py',
    'web_ui/core/update_progress.py': f'{WEB_UI_DIR}/core/update_progress.py',
    'web_ui/core/dns_spoofing.py': f'{WEB_UI_DIR}/core/dns_spoofing.py',
    'web_ui/resources/scripts/S99unblock': f'{INIT_DIR}/S99unblock',
    'web_ui/resources/scripts/S99web_ui': f'{INIT_DIR}/S99web_ui',
    'web_ui/resources/scripts/100-redirect.sh': f'{NDM_DIR}/netfilter.d/100-redirect.sh',
    'web_ui/resources/scripts/100-unblock-vpn.sh': f'{NDM_DIR}/ifstatechanged.d/100-unblock-vpn.sh',
    'web_ui/resources/scripts/100-ipset.sh': f'{NDM_DIR}/fs.d/100-ipset.sh',
    'web_ui/resources/scripts/unblock_ipset.sh': SCRIPT_UNBLOCK_IPSET,
    'web_ui/resources/scripts/unblock_dnsmasq.sh': SCRIPT_UNBLOCK_DNSMASQ,
    'web_ui/resources/scripts/unblock_update.sh': SCRIPT_UNBLOCK_UPDATE,
    'web_ui/resources/config/dnsmasq.conf': DNSMASQ_CONFIG,
    'web_ui/resources/config/crontab': CRONTAB_FILE,
    'web_ui/scripts/script.sh': SCRIPT_INSTALL,
    'web_ui/templates/base.html': f'{WEB_UI_DIR}/templates/base.html',
    'web_ui/templates/login.html': f'{WEB_UI_DIR}/templates/login.html',
    'web_ui/templates/index.html': f'{WEB_UI_DIR}/templates/index.html',
    'web_ui/templates/keys.html': f'{WEB_UI_DIR}/templates/keys.html',
    'web_ui/templates/bypass.html': f'{WEB_UI_DIR}/templates/bypass.html',
    'web_ui/templates/install.html': f'{WEB_UI_DIR}/templates/install.html',
    'web_ui/templates/stats.html': f'{WEB_UI_DIR}/templates/stats.html',
    'web_ui/templates/service.html': f'{WEB_UI_DIR}/templates/service.html',
    'web_ui/templates/updates.html': f'{WEB_UI_DIR}/templates/updates.html',
    'web_ui/templates/bypass_view.html': f'{WEB_UI_DIR}/templates/bypass_view.html',
    'web_ui/templates/bypass_add.html': f'{WEB_UI_DIR}/templates/bypass_add.html',
    'web_ui/templates/bypass_remove.html': f'{WEB_UI_DIR}/templates/bypass_remove.html',
    'web_ui/templates/bypass_catalog.html': f'{WEB_UI_DIR}/templates/bypass_catalog.html',
    'web_ui/templates/key_generic.html': f'{WEB_UI_DIR}/templates/key_generic.html',
    'web_ui/templates/backup.html': f'{WEB_UI_DIR}/templates/backup.html',
    'web_ui/templates/dns_monitor.html': f'{WEB_UI_DIR}/templates/dns_monitor.html',
    'web_ui/templates/logs.html': f'{WEB_UI_DIR}/templates/logs.html',
    'web_ui/templates/dns_spoofing.html': f'{WEB_UI_DIR}/templates/dns_spoofing.html',
    'web_ui/static/style.css': f'{WEB_UI_DIR}/static/style.css',
    'web_ui/resources/lists/unblock-ai-domains.txt': AI_DOMAINS_LIST,
    'web_ui/resources/config/unblock-ai.dnsmasq.template': DNSMASQ_AI_TEMPLATE,
    'web_ui/resources/scripts/unblock_dnsmasq.sh': f'{WEB_UI_DIR}/resources/scripts/unblock_dnsmasq.sh',
}

# =============================================================================
# BACKUP FILES
# =============================================================================

BACKUP_FILES = [
    # Web UI
    f'{WEB_UI_DIR}',
    # VPN configs
    f'{XRAY_DIR}',
    f'{TOR_DIR}',
    f'{TROJAN_CONFIG_DIR}',
    SHADOWSOCKS_CONFIG,
    HYSTERIA2_CONFIG,
    # Bypass lists
    f'{UNBLOCK_DIR}',
    DNSMASQ_AI_CONFIG,
    AI_DOMAINS_LIST,
    # System configs
    DNSMASQ_CONFIG,
    CRONTAB_FILE,
    # Scripts
    '/opt/bin',
    f'{NDM_DIR}',
    f'{INIT_DIR}',
    # Install script
    SCRIPT_INSTALL,
    # Logs (optional, useful for debugging)
    WEB_UI_LOG_FILE,
]

UPDATE_BACKUP_FILES = [
    # Web UI
    f'{WEB_UI_DIR}',
    # VPN configs
    f'{XRAY_DIR}',
    f'{TOR_DIR}',
    f'{TROJAN_CONFIG_DIR}',
    SHADOWSOCKS_CONFIG,
    HYSTERIA2_CONFIG,
    # Bypass lists
    f'{UNBLOCK_DIR}',
    DNSMASQ_AI_CONFIG,
    AI_DOMAINS_LIST,
    # System configs
    DNSMASQ_CONFIG,
    CRONTAB_FILE,
    # Scripts
    '/opt/bin',
    f'{NDM_DIR}',
    f'{INIT_DIR}',
]

UPDATE_BACKUP_FILES = [
    f'{WEB_UI_DIR}',
    f'{XRAY_DIR}',
    f'{TOR_DIR}',
    f'{UNBLOCK_DIR}',
    SHADOWSOCKS_CONFIG,
    f'{INIT_DIR}/trojan.json',
    DNSMASQ_AI_CONFIG,
    AI_DOMAINS_LIST,
]

# =============================================================================
# DNS SPOOFING
# =============================================================================

VPN_DNS_HOST = '127.0.0.1'
VPN_DNS_PORT = 40500
MAX_DOMAIN_LENGTH = 253
MAX_DOMAINS_COUNT = 1000
