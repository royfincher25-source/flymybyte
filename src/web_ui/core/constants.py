"""
Constants — centralized configuration and paths.

Used by:
- routes_updates.py: FILES_TO_UPDATE, UPDATE_BACKUP_FILES, GITHUB_*, WEB_UI_DIR
- routes_bypass.py: UNBLOCK_DIR, DNSMASQ_BYPASS_CONF, MAX_ENTRIES_PER_REQUEST
- routes_system.py: SERVICE_TOGGLE_CONFIG, INIT_SCRIPTS, DNSMASQ_CONFIG
- routes_vpn.py: SERVICES, CONFIG_PATHS, INIT_SCRIPTS
- core/vpn_manager.py: SERVICE_TOGGLE_CONFIG, INIT_SCRIPTS, PROC_NAME_MAP
- core/services.py: DNSMASQ_AI_CONFIG, AI_DOMAINS_LIST, VPN_DNS_*, MAX_*, INIT_SCRIPTS
- core/dns_ops.py: DNS_CHECK_INTERVAL, DNS_TIMEOUT, DEFAULT_DNS_SERVERS
- core/app_config.py: DEFAULT_WEB_*, DEFAULT_ROUTER_IP, DEFAULT_UNBLOCK_DIR, UNBLOCK_DIR
- core/backup_manager.py: BACKUP_DIR, BACKUP_FILES, INIT_SCRIPTS
- core/dnsmasq_manager.py: DNSMASQ_*, UNBLOCK_DIR, AI_DOMAINS_LIST, VPN_DNS_PORT
- core/ipset_ops.py: IPSET_MAX_BULK_ENTRIES
"""

# =============================================================================
# INPUT VALIDATION
# =============================================================================

MAX_ENTRIES_PER_REQUEST = 100
MAX_ENTRY_LENGTH = 253
MAX_TOTAL_INPUT_SIZE = 50 * 1024

# =============================================================================
# DNS
# =============================================================================

DNS_CHECK_INTERVAL = 300  # Увеличено с 60 до 300 секунд (5 минут) для снижения нагрузки на CPU
DNS_TIMEOUT = 2  # Уменьшено с 3 до 2 секунд (оптимально для локальных DNS)
DNS_FAILURE_THRESHOLD = 5  # Увеличено с 3 до 5 (меньше ложных переключений)

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
# TIMEOUTS
# =============================================================================

SCRIPT_EXECUTION_TIMEOUT = 120
FILE_DOWNLOAD_TIMEOUT = 15
BACKGROUND_RESTART_TIMEOUT = 600  # 10 минут для фонового перезапуска

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
INIT_DIR = '/opt/etc/init.d'
NDM_DIR = '/opt/etc/ndm'
XRAY_DIR = '/opt/etc/xray'

# =============================================================================
# FILE PATHS
# =============================================================================

WEB_UI_LOG_FILE = '/opt/var/log/web_ui.log'
TMP_RESTART_SCRIPT = '/tmp/restart_webui.sh'
DNS_OVERRIDE_FLAG = '/opt/etc/web_ui/.dns_override.flag'  # Постоянный маркер DNS Override

DNSMASQ_CONFIG = '/opt/etc/dnsmasq.conf'
DNSMASQ_AI_CONFIG = '/opt/etc/unblock-ai.dnsmasq'
DNSMASQ_BYPASS_CONF = '/opt/etc/unblock.dnsmasq'
DNSMASQ_AI_TEMPLATE = '/opt/etc/web_ui/resources/config/unblock-ai.dnsmasq.template'

AI_DOMAINS_LIST = '/opt/etc/unblock/ai-domains.txt'

SHADOWSOCKS_CONFIG = '/opt/etc/shadowsocks.json'
TROJAN_CONFIG_DIR = '/opt/etc/trojan'
CRONTAB_FILE = '/opt/etc/crontab'

# =============================================================================
# SCRIPT PATHS
# =============================================================================

SCRIPT_UNBLOCK_IPSET = '/opt/bin/unblock_ipset.sh'
SCRIPT_UNBLOCK_DNSMASQ = '/opt/bin/unblock_dnsmasq.sh'
SCRIPT_UNBLOCK_UPDATE = '/opt/bin/unblock_update.sh'
SCRIPT_EMERGENCY_RESTORE = '/opt/bin/emergency_restore.sh'
SCRIPT_DNSMASQ_WATCHDOG = '/opt/bin/dnsmasq_watchdog.sh'
SCRIPT_ROLLBACK = '/opt/bin/rollback.sh'
SCRIPT_TEST_BYPASS = '/opt/bin/test_bypass.sh'
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

# =============================================================================
# UPDATE FILES
# =============================================================================

FILES_TO_UPDATE = {
    'VERSION': f'{WEB_UI_DIR}/VERSION',
    'web_ui/.env.example': f'{WEB_UI_DIR}/.env.example',
    'web_ui/__init__.py': f'{WEB_UI_DIR}/__init__.py',
    'web_ui/app.py': f'{WEB_UI_DIR}/app.py',
    'web_ui/core/__init__.py': f'{WEB_UI_DIR}/core/__init__.py',
    'web_ui/core/constants.py': f'{WEB_UI_DIR}/core/constants.py',
    'web_ui/core/utils.py': f'{WEB_UI_DIR}/core/utils.py',
    'web_ui/core/services.py': f'{WEB_UI_DIR}/core/services.py',
    'web_ui/core/dns_ops.py': f'{WEB_UI_DIR}/core/dns_ops.py',
    'web_ui/core/app_config.py': f'{WEB_UI_DIR}/core/app_config.py',
    'web_ui/core/update_progress.py': f'{WEB_UI_DIR}/core/update_progress.py',
    'web_ui/core/decorators.py': f'{WEB_UI_DIR}/core/decorators.py',
    'web_ui/core/ipset_ops.py': f'{WEB_UI_DIR}/core/ipset_ops.py',
    'web_ui/core/emergency_restore.py': f'{WEB_UI_DIR}/core/emergency_restore.py',
    'web_ui/core/dnsmasq_manager.py': f'{WEB_UI_DIR}/core/dnsmasq_manager.py',
    'web_ui/core/iptables_manager.py': f'{WEB_UI_DIR}/core/iptables_manager.py',
    'web_ui/routes_core.py': f'{WEB_UI_DIR}/routes_core.py',
    'web_ui/routes_system.py': f'{WEB_UI_DIR}/routes_system.py',
    'web_ui/routes_vpn.py': f'{WEB_UI_DIR}/routes_vpn.py',
    'web_ui/routes_bypass.py': f'{WEB_UI_DIR}/routes_bypass.py',
    'web_ui/routes_updates.py': f'{WEB_UI_DIR}/routes_updates.py',
    'web_ui/static/main.js': f'{WEB_UI_DIR}/static/main.js',
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
    'web_ui/static/fonts/flymybyte-icons.css': f'{WEB_UI_DIR}/static/fonts/flymybyte-icons.css',
    'web_ui/static/fonts/flymybyte-icons.woff2': f'{WEB_UI_DIR}/static/fonts/flymybyte-icons.woff2',
    'web_ui/resources/lists/unblock-ai-domains.txt': AI_DOMAINS_LIST,
    'web_ui/resources/config/unblock-ai.dnsmasq.template': DNSMASQ_AI_TEMPLATE,
    'web_ui/resources/scripts/unblock_dnsmasq.sh': f'{WEB_UI_DIR}/resources/scripts/unblock_dnsmasq.sh',
    'web_ui/resources/scripts/emergency_restore.sh': SCRIPT_EMERGENCY_RESTORE,
    'web_ui/resources/scripts/dnsmasq_watchdog.sh': SCRIPT_DNSMASQ_WATCHDOG,
    'web_ui/resources/scripts/rollback.sh': SCRIPT_ROLLBACK,
    'web_ui/resources/scripts/test_bypass.sh': SCRIPT_TEST_BYPASS,
}

# =============================================================================
# BACKUP FILES
# =============================================================================

BACKUP_FILES = [
    f'{WEB_UI_DIR}',
    f'{XRAY_DIR}',
    f'{TROJAN_CONFIG_DIR}',
    SHADOWSOCKS_CONFIG,
    '/opt/etc/proxy.json',      # Proxy config
    f'{UNBLOCK_DIR}',
    DNSMASQ_AI_CONFIG,
    AI_DOMAINS_LIST,
    DNSMASQ_BYPASS_CONF,        # Bypass dnsmasq config (generated)
    DNSMASQ_CONFIG,
    CRONTAB_FILE,
    '/opt/bin',
    f'{NDM_DIR}',
    f'{INIT_DIR}',
    SCRIPT_INSTALL,
    WEB_UI_LOG_FILE,
]

UPDATE_BACKUP_FILES = [
    f'{WEB_UI_DIR}',
    f'{XRAY_DIR}',
    f'{TROJAN_CONFIG_DIR}',
    SHADOWSOCKS_CONFIG,
    f'{UNBLOCK_DIR}',
    DNSMASQ_AI_CONFIG,
    AI_DOMAINS_LIST,
    DNSMASQ_CONFIG,
    CRONTAB_FILE,
    '/opt/bin',
    f'{NDM_DIR}',
    f'{INIT_DIR}',
]

# =============================================================================
# IPSET MAPPING
# =============================================================================

IPSET_MAP = {
    'vless': 'unblockvless',
    'proxy': 'unblockproxy',
    'shadowsocks': 'unblocksh',
    'ss': 'unblocksh',
    'trojan': 'unblocktroj',
}

# Maximum entries per ipset bulk operation
IPSET_MAX_BULK_ENTRIES = 5000

# =============================================================================
# SERVICE PROCESS NAMES (для pgrep)
# =============================================================================

PROC_NAME_MAP = {
    'shadowsocks': 'ss-redir',
    'vless': 'xray',
    'trojan': 'trojan',
}

# =============================================================================
# SERVICE TOGGLE CONFIG (ipset + port)
# =============================================================================

SERVICE_TOGGLE_CONFIG = {
    'vless': {'ipset': 'unblockvless', 'port': 10810},
    'proxy': {'ipset': 'unblockproxy', 'port': 1080},
    'shadowsocks': {'ipset': 'unblocksh', 'port': 1082},
    'trojan': {'ipset': 'unblocktroj', 'port': 10829},
}

# =============================================================================
# DNS SPOOFING
# =============================================================================

VPN_DNS_HOST = '127.0.0.1'
VPN_DNS_PORT = 40500
MAX_DOMAIN_LENGTH = 253
MAX_DOMAINS_COUNT = 1000
