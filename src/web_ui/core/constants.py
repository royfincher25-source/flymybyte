"""
Constants - Centralized configuration constants

All magic numbers and configuration values are stored here.
Optimized for embedded devices (128MB RAM).
"""

# =============================================================================
# INPUT VALIDATION
# =============================================================================

# Maximum entries per request (DoS protection)
MAX_ENTRIES_PER_REQUEST = 100

# Maximum length of single entry (DNS limit)
MAX_ENTRY_LENGTH = 253

# Maximum total input size (50KB)
MAX_TOTAL_INPUT_SIZE = 50 * 1024

# =============================================================================
# LOGGING
# =============================================================================

# Maximum log file size (100KB)
LOG_MAX_BYTES = 100 * 1024

# Number of backup log files
LOG_BACKUP_COUNT = 3

# =============================================================================
# CACHE
# =============================================================================

# Maximum cache entries (optimized for 128MB RAM)
CACHE_MAX_ENTRIES = 30

# Default cache TTL (seconds)
CACHE_DEFAULT_TTL = 60

# Service status cache TTL (30 seconds)
SERVICE_STATUS_TTL = 30

# =============================================================================
# DNS
# =============================================================================

# DNS check interval (seconds)
DNS_CHECK_INTERVAL = 60

# DNS timeout (seconds)
DNS_TIMEOUT = 3

# Failure threshold before switch
DNS_FAILURE_THRESHOLD = 3

# Default DNS servers
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

# Default web server configuration
DEFAULT_WEB_HOST = "0.0.0.0"
DEFAULT_WEB_PORT = 8080
DEFAULT_WEB_PASSWORD = "changeme"
DEFAULT_ROUTER_IP = "192.168.1.1"
DEFAULT_UNBLOCK_DIR = "/opt/etc/unblock/"

# Port validation range
MIN_PORT = 1
MAX_PORT = 65535

# =============================================================================
# THREAD POOL
# =============================================================================

# Thread pool workers (optimized for KN-1212)
THREAD_POOL_WORKERS = 4

# Service restart timeout (seconds)
SERVICE_RESTART_TIMEOUT = 60

# Web UI restart timeout (seconds)
WEB_UI_RESTART_TIMEOUT = 30

# Script execution timeout (seconds)
SCRIPT_EXECUTION_TIMEOUT = 120

# =============================================================================
# UPDATE
# =============================================================================

# Update script steps
UPDATE_SCRIPT_STEPS = 5  # unblock_update, unblock_dnsmasq, S99unblock, S56dnsmasq, S99web_ui

# File download timeout (seconds)
FILE_DOWNLOAD_TIMEOUT = 60

# Update progress polling interval (milliseconds)
UPDATE_PROGRESS_INTERVAL = 3000

# Auto-reload delay after update (milliseconds)
UPDATE_RELOAD_DELAY = 3000

# =============================================================================
# IPSET
# =============================================================================

# Maximum entries for bulk operations (memory protection)
IPSET_MAX_BULK_ENTRIES = 5000

# Batch size for DNS resolver
DNS_RESOLVER_BATCH_SIZE = 100

# =============================================================================
# MEMORY MANAGEMENT
# =============================================================================

# Memory optimization thresholds (MB)
MEMORY_LOW_THRESHOLD = 20
MEMORY_CRITICAL_THRESHOLD = 10

# Memory manager modes
MEMORY_MODE_NORMAL = 'normal'
MEMORY_MODE_LOW = 'low'
MEMORY_MODE_AGGRESSIVE = 'aggressive'

# Memory mode configurations
MEMORY_MODES = {
    MEMORY_MODE_NORMAL: {'cache': 30, 'dns_interval': 60},
    MEMORY_MODE_LOW: {'cache': 15, 'dns_interval': 120},
    MEMORY_MODE_AGGRESSIVE: {'cache': 5, 'dns_interval': 180},
}

# =============================================================================
# GITHUB
# =============================================================================

# GitHub repository configuration
GITHUB_REPO = 'royfincher25-source/flymybyte'
GITHUB_BRANCH = 'master'

# Raw GitHub URLs
GITHUB_RAW_BASE = f'https://raw.githubusercontent.com/{GITHUB_REPO}/{GITHUB_BRANCH}'

# =============================================================================
# FILE PATHS
# =============================================================================

# Web UI paths
WEB_UI_DIR = '/opt/etc/web_ui'
WEB_UI_PIDFILE = '/var/run/web_ui.pid'
WEB_UI_LOG_FILE = '/opt/var/log/web_ui.log'

# Backup paths
BACKUP_DIR = '/opt/root/backup'

# Temporary paths
TMP_DIR = '/tmp'
TMP_RESTART_SCRIPT = '/tmp/restart_webui.sh'

# =============================================================================
# SERVICE SCRIPTS
# =============================================================================

# Init scripts
INIT_SCRIPTS = {
    'vless': '/opt/etc/init.d/S24xray',
    'hysteria2': '/opt/etc/init.d/S22hysteria2',
    'shadowsocks': '/opt/etc/init.d/S22shadowsocks',
    'trojan': '/opt/etc/init.d/S22trojan',
    'tor': '/opt/etc/init.d/S35tor',
    'unblock': '/opt/etc/init.d/S99unblock',
    'dnsmasq': '/opt/etc/init.d/S56dnsmasq',
    'web_ui': '/opt/etc/init.d/S99web_ui',
}

# Configuration paths
CONFIG_PATHS = {
    'vless': '/opt/etc/xray/vless.json',
    'hysteria2': '/opt/etc/hysteria2.json',
    'shadowsocks': '/opt/etc/shadowsocks.json',
    'trojan': '/opt/etc/trojan.json',
    'tor': '/opt/etc/tor/torrc',
    'dnsmasq': '/opt/etc/dnsmasq.conf',
}
