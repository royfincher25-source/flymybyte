"""
FlyMyByte Web Interface - Core Utilities

Memory-optimized utilities for embedded devices (128MB RAM).
"""
import os
import re
import time
import subprocess
import logging
import threading
from collections import OrderedDict
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import List, Tuple, Optional, Any, Dict

LOG_FILE = os.environ.get('LOG_FILE', '/opt/var/log/web_ui.log')
LOG_MAX_BYTES = 100 * 1024
LOG_BACKUP_COUNT = 3

logger = logging.getLogger(__name__)

_logging_initialized = False


def setup_logging():
    """Configure logging with rotation. Called once from app.py."""
    global _logging_initialized
    if _logging_initialized:
        return
    _logging_initialized = True

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    if LOG_FILE:
        try:
            log_dir = os.path.dirname(LOG_FILE)
            if log_dir and not os.path.exists(log_dir):
                os.makedirs(log_dir, exist_ok=True)
            file_handler = RotatingFileHandler(
                LOG_FILE,
                maxBytes=LOG_MAX_BYTES,
                backupCount=LOG_BACKUP_COUNT,
                encoding='utf-8'
            )
            file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
            logging.getLogger().addHandler(file_handler)
            logger.info(f"Log rotation enabled: {LOG_MAX_BYTES} bytes x {LOG_BACKUP_COUNT} files")
        except Exception as e:
            logger.error(f"Failed to setup log rotation: {e}")


class Cache:
    """LRU cache with TTL (30 entries max, thread-safe)."""

    _cache: Dict[str, Any] = {}
    _timestamps: Dict[str, float] = {}
    _access_order: OrderedDict[str, None] = OrderedDict()
    _lock = threading.Lock()
    MAX_ENTRIES: int = 30

    @classmethod
    def set(cls, key: str, value: Any, ttl: int = 60) -> None:
        with cls._lock:
            if len(cls._cache) >= cls.MAX_ENTRIES and key not in cls._cache:
                cls._evict_oldest()
            cls._cache[key] = value
            cls._timestamps[key] = time.time() + ttl
            if key in cls._access_order:
                cls._access_order.move_to_end(key)
            else:
                cls._access_order[key] = None

    @classmethod
    def get(cls, key: str, default: Any = None) -> Any:
        with cls._lock:
            if key not in cls._cache:
                return default
            if time.time() > cls._timestamps.get(key, 0):
                cls._remove(key)
                return default
            if key in cls._access_order:
                cls._access_order.move_to_end(key)
            else:
                cls._access_order[key] = None
            return cls._cache.get(key, default)

    @classmethod
    def is_valid(cls, key: str) -> bool:
        with cls._lock:
            if key not in cls._cache:
                return False
            if time.time() > cls._timestamps.get(key, 0):
                cls._remove(key)
                return False
            return True

    @classmethod
    def _remove(cls, key: str) -> None:
        cls._cache.pop(key, None)
        cls._timestamps.pop(key, None)
        cls._access_order.pop(key, None)

    @classmethod
    def _evict_oldest(cls) -> None:
        if cls._access_order:
            oldest, _ = cls._access_order.popitem(last=False)
            cls._cache.pop(oldest, None)
            cls._timestamps.pop(oldest, None)

    @classmethod
    def clear(cls) -> None:
        cls._cache.clear()
        cls._timestamps.clear()
        cls._access_order.clear()

    @classmethod
    def delete(cls, key: str) -> None:
        """Delete a specific key from cache."""
        with cls._lock:
            cls._remove(key)

    @classmethod
    def get_stats(cls) -> dict:
        return {
            'entries': len(cls._cache),
            'max_entries': cls.MAX_ENTRIES,
            'access_order_len': len(cls._access_order)
        }

    @classmethod
    def cleanup_expired(cls) -> int:
        now = time.time()
        expired = [k for k, ts in cls._timestamps.items() if now > ts]
        for key in expired:
            cls._remove(key)
        return len(expired)


# =============================================================================
# VALIDATION FUNCTIONS - moved to bypass_utils.py
# =============================================================================

def validate_bypass_entry(entry: str) -> bool:
    """Validate bypass list entry (domain, IP, CIDR, or comment)."""
    from .bypass_utils import validate_bypass_entry as _validate
    return _validate(entry)


def is_ip_address(entry: str) -> bool:
    """Check if entry is an IP address (IPv4/IPv6) or CIDR."""
    from .bypass_utils import is_ip_address as _is_ip
    return _is_ip(entry)


def is_cidr(entry: str) -> bool:
    """Check if entry is CIDR notation."""
    from .bypass_utils import is_cidr as _is_cidr
    return _is_cidr(entry)


def load_bypass_list(filepath: str):
    """Load bypass list from file."""
    from .bypass_utils import load_bypass_list as _load
    return _load(filepath)


def save_bypass_list(filepath: str, sites: list):
    """Save bypass list to file."""
    from .bypass_utils import save_bypass_list as _save
    return _save(filepath, sites)


def is_cidr(entry: str) -> bool:
    """Check if entry is CIDR notation (IPv4 or IPv6)."""
    from .bypass_utils import is_cidr as _is_cidr
    return _is_cidr(entry)


# =============================================================================
# FILE OPERATIONS - moved to bypass_utils.py
# =============================================================================

def load_bypass_list(filepath: str) -> List[str]:
    """Load bypass list from file."""
    from .bypass_utils import load_bypass_list as _load
    return _load(filepath)


def save_bypass_list(filepath: str, sites: List[str]) -> None:
    """Save bypass list to file."""
    from .bypass_utils import save_bypass_list as _save
    return _save(filepath, sites)


# =============================================================================
# SCRIPT EXECUTION
# =============================================================================

def get_script_path(script_name: str) -> Optional[str]:
    """Get path to deployment script (searches router + dev locations)."""
    possible_paths = [
        f"/opt/bin/{script_name}",
        f"/opt/etc/unblock/{script_name}",
        f"/opt/etc/ndm/{script_name}",
    ]
    try:
        project_root = Path(__file__).parent.parent.parent
        dev_paths = [
            project_root / "deploy" / "router" / script_name,
            project_root / "scripts" / "deploy" / script_name,
        ]
        possible_paths.extend(str(p) for p in dev_paths)
    except Exception:
        pass
    possible_paths.append(script_name)
    for path in possible_paths:
        if os.path.exists(path):
            return path
    return None


def run_unblock_update() -> Tuple[bool, str]:
    """Run unblock_update.sh to apply bypass list changes. Returns (success, output)."""
    script_path = get_script_path('unblock_update.sh')
    if not script_path:
        logger.error("[UPDATE] unblock_update.sh script not found")
        return False, "Script not found"
    logger.info(f"[UPDATE] Running unblock_update.sh from {script_path}")
    try:
        result = subprocess.run(['sh', script_path], capture_output=True, text=True, timeout=180)
        success = result.returncode == 0
        output = result.stdout.strip() or result.stderr.strip()
        if success:
            logger.info(f"[UPDATE] unblock_update.sh completed: {output}")
        else:
            logger.error(f"[UPDATE] unblock_update.sh failed (code={result.returncode}): {output}")
        return success, output
    except subprocess.TimeoutExpired:
        logger.error("[UPDATE] unblock_update.sh timed out")
        return False, "Timeout"
    except Exception as e:
        logger.error(f"[UPDATE] Error running unblock_update.sh: {e}")
        return False, str(e)


# =============================================================================
# SYSTEM STATS
# =============================================================================


class MemoryManager:
    """Auto memory optimization for embedded devices."""

    _instance = None
    _lock = threading.Lock()
    LOW_MEMORY_THRESHOLD_MB = 20
    AGGRESSIVE_THRESHOLD_MB = 10
    _enabled = False
    _aggressive_mode = False
    _original_cache_size = 30

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    @classmethod
    def enable(cls) -> bool:
        cls._enabled = True
        cls._original_cache_size = Cache.MAX_ENTRIES
        logger.info("Auto memory optimization enabled")
        return True

    @classmethod
    def disable(cls) -> bool:
        cls._enabled = False
        Cache.MAX_ENTRIES = cls._original_cache_size
        cls._aggressive_mode = False
        logger.info("Auto memory optimization disabled")
        return True

    @classmethod
    def get_status(cls) -> dict:
        return {
            'enabled': cls._enabled,
            'aggressive': cls._aggressive_mode,
            'current_cache': Cache.MAX_ENTRIES,
            'original_cache': cls._original_cache_size,
            'low_threshold_mb': cls.LOW_MEMORY_THRESHOLD_MB,
            'aggressive_threshold_mb': cls.AGGRESSIVE_THRESHOLD_MB,
        }

    @classmethod
    def check_and_optimize(cls) -> tuple:
        if not cls._enabled:
            return False, 'disabled', 0
        stats = get_memory_stats()
        free_mb = stats.get('free_mb', 0)
        if free_mb <= cls.AGGRESSIVE_THRESHOLD_MB and not cls._aggressive_mode:
            Cache.MAX_ENTRIES = 5
            cls._aggressive_mode = True
            logger.warning(f"Aggressive mode: cache={Cache.MAX_ENTRIES}, free={free_mb}MB")
            return True, 'aggressive', free_mb
        elif free_mb <= cls.LOW_MEMORY_THRESHOLD_MB and not cls._aggressive_mode:
            Cache.MAX_ENTRIES = 15
            logger.info(f"Low memory mode: cache={Cache.MAX_ENTRIES}, free={free_mb}MB")
            return True, 'low', free_mb
        elif free_mb > cls.LOW_MEMORY_THRESHOLD_MB and cls._aggressive_mode:
            Cache.MAX_ENTRIES = 30
            cls._aggressive_mode = False
            logger.info(f"Memory restored: cache={Cache.MAX_ENTRIES}, free={free_mb}MB")
            return True, 'normal', free_mb
        return False, 'normal' if not cls._aggressive_mode else 'aggressive', free_mb


def get_cpu_stats() -> dict:
    """Get CPU usage from /proc/stat."""
    from .system_utils import get_cpu_stats as _get_cpu
    return _get_cpu()


def get_memory_stats() -> dict:
    """Get memory usage from /proc/meminfo."""
    from .system_utils import get_memory_stats as _get_mem
    return _get_mem()


# Cache for get_memory_stats (5 second TTL)
_memory_stats_cache = {'data': None, 'timestamp': 0}
_MEMORY_STATS_TTL = 5  # seconds


def get_memory_stats() -> dict:
    """Get memory usage from /proc/meminfo (cached 5s)."""
    now = time.time()
    if _memory_stats_cache['data'] is not None and (now - _memory_stats_cache['timestamp']) < _MEMORY_STATS_TTL:
        return _memory_stats_cache['data']
    try:
        with open('/proc/meminfo', 'r') as f:
            lines = f.readlines()
        mem = {}
        for line in lines:
            parts = line.split()
            if len(parts) >= 2:
                key = parts[0].rstrip(':')
                try:
                    mem[key] = int(parts[1])
                except ValueError:
                    pass
        total = mem.get('MemTotal', 0) / 1024
        free = mem.get('MemFree', 0) / 1024
        buffers = mem.get('Buffers', 0) / 1024
        cached = mem.get('Cached', 0) / 1024
        available = mem.get('MemAvailable', 0) / 1024
        if available > 0:
            used = total - available
            real_used = used
            display_available = available
        else:
            used = total - free - buffers - cached
            real_used = used
            display_available = free + buffers + cached
        percent = (real_used / total * 100) if total > 0 else 0
        raw_percent = (used / total * 100) if total > 0 else 0
        try:
            cache_stats = Cache.get_stats()
            cache_entries = cache_stats['entries']
            cache_max = cache_stats['max_entries']
        except AttributeError:
            cache_entries = 0
            cache_max = 30
        result = {
            'total_mb': round(total, 1),
            'used_mb': round(used, 1),
            'free_mb': round(free, 1),
            'available_mb': round(display_available, 1),
            'cached_mb': round(cached, 1),
            'buffers_mb': round(buffers, 1),
            'real_used_mb': round(real_used, 1),
            'percent': round(percent, 1),
            'raw_percent': round(raw_percent, 1),
            'cache_entries': cache_entries,
            'cache_max': cache_max,
        }
        _memory_stats_cache['data'] = result
        _memory_stats_cache['timestamp'] = now
        return result
    except Exception as e:
        logger.error(f"Failed to get memory stats: {e}")
        try:
            cache_max = Cache.MAX_ENTRIES
        except AttributeError:
            cache_max = 30
        return {
            'total_mb': 0, 'used_mb': 0, 'free_mb': 0,
            'available_mb': 0, 'cached_mb': 0, 'percent': 0,
            'cache_entries': 0, 'cache_max': cache_max, 'error': str(e)
        }


# ===========================================================================
# Version functions (moved from services.py)
# ===========================================================================

def get_local_version() -> str:
    """Get local version from VERSION file."""
    version_file = '/opt/etc/web_ui/VERSION'
    try:
        with open(version_file, 'r', encoding='utf-8') as f:
            return f.read().strip()
    except FileNotFoundError:
        local_version_file = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'VERSION')
        if os.path.exists(local_version_file):
            try:
                with open(local_version_file, 'r', encoding='utf-8') as f:
                    return f.read().strip()
            except Exception:
                pass
        return 'N/A'


def get_remote_version() -> str:
    """Get remote version from GitHub."""
    import requests
    try:
        github_repo = 'royfincher25-source/flymybyte'
        url = f'https://api.github.com/repos/{github_repo}/contents/VERSION'
        response = requests.get(url, timeout=10, headers={
            'Accept': 'application/vnd.github.v3+json',
            'Cache-Control': 'no-cache',
        })
        if response.status_code == 200:
            import base64
            data = response.json()
            content = base64.b64decode(data['content']).decode('utf-8')
            return content.strip()
        raw_url = f'https://raw.githubusercontent.com/{github_repo}/master/VERSION'
        raw_resp = requests.get(raw_url, timeout=10)
        if raw_resp.status_code == 200:
            return raw_resp.text.strip()
        return 'N/A'
    except Exception as e:
        logger.error(f'Error fetching remote version: {e}')
        return 'N/A'


# ===========================================================================
# Bypass catalog functions (moved from services.py)
# ===========================================================================

LIST_CATALOG: Dict[str, Dict[str, Any]] = {
    'anticensor': {
        'name': 'Антицензор',
        'description': 'Обход блокировок Роскомнадзора',
        'url': 'https://raw.githubusercontent.com/zhovner/zaborona_help/master/hosts.txt',
        'format': 'hosts',
    },
    'reestr': {
        'name': 'Реестр запрещённых сайтов',
        'description': 'Официальный реестр запрещённых сайтов РФ',
        'url': 'https://raw.githubusercontent.com/zhovner/zaborona_help/master/reestr.txt',
        'format': 'domains',
    },
    'social': {
        'name': 'Соцсети',
        'description': 'Facebook, Instagram, Twitter, TikTok',
        'domains': ['facebook.com', 'instagram.com', 'twitter.com', 'tiktok.com', 'whatsapp.com', 'telegram.org'],
        'format': 'domains',
    },
    'streaming': {
        'name': 'Стриминговые сервисы',
        'description': 'Netflix, Spotify, Disney+',
        'domains': ['netflix.com', 'spotify.com', 'disneyplus.com', 'hulu.com', 'amazonprime.com'],
        'format': 'domains',
    },
    'torrents': {
        'name': 'Торрент-трекеры',
        'description': 'RuTracker, ThePirateBay, 1337x',
        'domains': ['rutracker.org', 'thepiratebay.org', '1337x.to', 'torrentz2.eu'],
        'format': 'domains',
    },
}


def get_catalog() -> Dict[str, Dict[str, Any]]:
    """Get full catalog of bypass lists."""
    return LIST_CATALOG


def _parse_list_content(content: str, fmt: str) -> List[str]:
    """Parse list content based on format."""
    domains = []
    for line in content.split('\n'):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if fmt == 'hosts':
            parts = line.split()
            if len(parts) >= 2 and not parts[0].startswith('#'):
                domain = parts[1]
                if domain != 'localhost':
                    domains.append(domain)
        else:
            domains.append(line)
    return domains


def download_list(name: str, dest_dir: str) -> Tuple[bool, str, int]:
    """Download list from catalog and save to file."""
    import requests
    if name not in LIST_CATALOG:
        return False, f"List '{name}' not found", 0
    
    list_info = LIST_CATALOG[name]
    filename = f"{name}.txt"
    filepath = os.path.join(dest_dir, filename)
    
    try:
        if 'url' in list_info:
            logger.info(f"Downloading {name} from {list_info['url']}")
            response = requests.get(list_info['url'], timeout=30)
            response.raise_for_status()
            domains = _parse_list_content(response.text, list_info['format'])
        elif 'domains' in list_info:
            domains = list_info['domains']
        else:
            return False, "No data source", 0
        
        temp_path = filepath + '.tmp'
        with open(temp_path, 'w', encoding='utf-8') as f:
            for domain in domains:
                f.write(f"{domain}\n")
        os.replace(temp_path, filepath)
        logger.info(f"Saved {len(domains)} domains to {filepath}")
        return True, f"Downloaded {len(domains)} domains", len(domains)
    except requests.RequestException as e:
        logger.error(f"Download error: {e}")
        return False, f"Download error: {e}", 0
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return False, str(e), 0
