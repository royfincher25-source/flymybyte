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
# VALIDATION FUNCTIONS
# =============================================================================

def validate_bypass_entry(entry: str) -> bool:
    """Validate bypass list entry (domain, IP, or comment)."""
    entry = entry.strip()
    if not entry:
        return False
    if entry.startswith('#'):
        return True
    if len(entry) > 253:
        return False
    parts = entry.split('.')
    if len(parts) == 4:
        try:
            return all(0 <= int(p) <= 255 for p in parts)
        except ValueError:
            pass
    if ':' in entry:
        return True
    if '.' in entry:
        return True
    return False


def is_ip_address(entry: str) -> bool:
    """Check if entry is an IP address (IPv4 or IPv6)."""
    entry = entry.strip()
    parts = entry.split('.')
    if len(parts) == 4:
        try:
            return all(0 <= int(p) <= 255 for p in parts)
        except ValueError:
            pass
    if ':' in entry:
        return True
    return False


# =============================================================================
# FILE OPERATIONS
# =============================================================================

def load_bypass_list(filepath: str) -> List[str]:
    """Load bypass list from file with mtime-based caching (60s TTL)."""
    cache_key = f'bypass:{filepath}'
    if Cache.is_valid(cache_key):
        cached = Cache.get(cache_key)
        try:
            mtime = os.path.getmtime(filepath)
            if cached and mtime == cached.get('mtime'):
                return cached['data']
        except (OSError, IOError):
            pass
    if not os.path.exists(filepath):
        logger.warning(f"[BYPASS] File not found: {filepath}")
        return []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = [line.strip() for line in f if line.strip() and not line.strip().startswith('#')]
        try:
            mtime = os.path.getmtime(filepath)
        except (OSError, IOError):
            mtime = time.time()
        Cache.set(cache_key, {'data': data, 'mtime': mtime}, ttl=60)
        logger.info(f"[BYPASS] Loaded {len(data)} entries from {filepath}")
        return data
    except Exception as e:
        logger.error(f"[BYPASS] Error loading {filepath}: {e}")
        return []


def save_bypass_list(filepath: str, sites: List[str]) -> None:
    """Save bypass list to file atomically (via .tmp + os.replace)."""
    temp_path = filepath + '.tmp'
    try:
        with open(temp_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(sites))
        os.replace(temp_path, filepath)
        cache_key = f'bypass:{filepath}'
        Cache._cache.pop(cache_key, None)
        Cache._timestamps.pop(cache_key, None)
        Cache._access_order.pop(cache_key, None)
        logger.info(f"[BYPASS] Saved {len(sites)} entries to {filepath}")
    except Exception as e:
        logger.error(f"[BYPASS] Error saving {filepath}: {e}")
        try:
            if os.path.exists(temp_path):
                os.remove(temp_path)
        except (OSError, IOError):
            pass
        raise


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
    """Get CPU usage from /proc/stat. Returns {'cpu_percent': float}."""
    try:
        with open('/proc/stat', 'r') as f:
            lines = f.readlines()
        for line in lines:
            if line.startswith('cpu '):
                parts = line.split()
                if len(parts) >= 8:
                    user = int(parts[1])
                    nice = int(parts[2])
                    system = int(parts[3])
                    idle = int(parts[4])
                    iowait = int(parts[5])
                    total = user + nice + system + idle + iowait
                    work = user + nice + system
                    if not hasattr(get_cpu_stats, 'prev_total'):
                        get_cpu_stats.prev_total = 0
                        get_cpu_stats.prev_work = 0
                    total_delta = total - get_cpu_stats.prev_total
                    work_delta = work - get_cpu_stats.prev_work
                    cpu_percent = (work_delta / total_delta) * 100 if total_delta > 0 else 0
                    get_cpu_stats.prev_total = total
                    get_cpu_stats.prev_work = work
                    return {'cpu_percent': round(cpu_percent, 1)}
        return {'cpu_percent': 0}
    except Exception as e:
        logger.error(f"Failed to get CPU stats: {e}")
        return {'cpu_percent': 0}


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
