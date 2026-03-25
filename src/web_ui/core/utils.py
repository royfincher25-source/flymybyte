"""
Bypass Keenetic Web Interface - Core Utilities

Memory-optimized utilities for embedded devices (128MB RAM).
- LRU cache with 50 entry limit (reduced from 100)
- Efficient file operations
- Minimal memory footprint
- Log rotation (100KB × 3 = 300KB max)
"""
import os
import re
import time
import subprocess
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import List, Tuple, Optional, Any, Dict

LOG_FILE = os.environ.get('LOG_FILE', '/opt/var/log/web_ui.log')
LOG_MAX_BYTES = 100 * 1024  # 100KB
LOG_BACKUP_COUNT = 3  # 3 backup files = 300KB max

# Создать logger до использования
logger = logging.getLogger(__name__)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

if LOG_FILE:
    try:
        log_dir = os.path.dirname(LOG_FILE)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)
        # RotatingFileHandler с ротацией для embedded-устройств
        file_handler = RotatingFileHandler(
            LOG_FILE,
            maxBytes=LOG_MAX_BYTES,
            backupCount=LOG_BACKUP_COUNT,
            encoding='utf-8'  # Явно указываем UTF-8
        )
        file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        logging.getLogger().addHandler(file_handler)
        logger.info(f"Log rotation enabled: {LOG_MAX_BYTES} bytes x {LOG_BACKUP_COUNT} files")
    except Exception as e:
        logger.error(f"Failed to setup log rotation: {e}")
        pass


# =============================================================================
# LRU CACHE (MEMORY-OPTIMIZED)
# =============================================================================

import threading


class Cache:
    """
    LRU cache with TTL and memory limit (50 entries for embedded devices).

    Optimized for embedded devices with limited RAM (128MB).
    Reduced from 100 to 50 entries to save ~15KB memory.
    Thread-safe with threading.Lock for concurrent access.

    Attributes:
        _cache: Dictionary storing cached values
        _timestamps: Dictionary storing cache timestamps
        _access_order: List tracking access order for LRU eviction
        _lock: Threading lock for thread safety
        MAX_ENTRIES: Maximum number of cache entries (default: 50)

    Example:
        >>> Cache.set("key", "value", ttl=60)
        >>> Cache.get("key")
        'value'
        >>> Cache.is_valid("key")
        True
    """

    _cache: Dict[str, Any] = {}
    _timestamps: Dict[str, float] = {}
    _access_order: List[str] = []
    _lock = threading.Lock()  # Thread safety for concurrent access
    MAX_ENTRIES: int = 30  # Оптимизировано для KN-1212 (128MB RAM)
    
    @classmethod
    def set(cls, key: str, value: Any, ttl: int = 60) -> None:
        """
        Set cache value with TTL.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds (default: 60)
        """
        with cls._lock:
            # LRU eviction if cache is full
            if len(cls._cache) >= cls.MAX_ENTRIES and key not in cls._cache:
                cls._evict_oldest()

            cls._cache[key] = value
            cls._timestamps[key] = time.time() + ttl

            # Update access order
            if key in cls._access_order:
                cls._access_order.remove(key)
            cls._access_order.append(key)

    @classmethod
    def get(cls, key: str, default: Any = None) -> Any:
        """
        Get cached value.

        Args:
            key: Cache key
            default: Default value if not found or expired

        Returns:
            Cached value or default
        """
        with cls._lock:
            # Check if exists and not expired (inline to avoid reentrant lock)
            if key not in cls._cache:
                return default
            
            if time.time() > cls._timestamps.get(key, 0):
                # Expired - remove
                cls._remove(key)
                return default

            # Update access order
            if key in cls._access_order:
                cls._access_order.remove(key)
                cls._access_order.append(key)

            return cls._cache.get(key, default)

    @classmethod
    def is_valid(cls, key: str) -> bool:
        """
        Check if cache entry is valid (exists and not expired).

        Args:
            key: Cache key

        Returns:
            True if valid, False otherwise
        """
        with cls._lock:
            if key not in cls._cache:
                return False

            if time.time() > cls._timestamps.get(key, 0):
                # Expired - remove
                cls._remove(key)
                return False

            return True
    
    @classmethod
    def _remove(cls, key: str) -> None:
        """Remove cache entry."""
        cls._cache.pop(key, None)
        cls._timestamps.pop(key, None)
        if key in cls._access_order:
            cls._access_order.remove(key)
    
    @classmethod
    def _evict_oldest(cls) -> None:
        """Evict oldest (least recently used) entry."""
        if cls._access_order:
            oldest = cls._access_order[0]
            cls._remove(oldest)
    
    @classmethod
    def clear(cls) -> None:
        """Clear all cache entries."""
        cls._cache.clear()
        cls._timestamps.clear()
        cls._access_order.clear()

    @classmethod
    def get_stats(cls) -> dict:
        """Get cache statistics."""
        return {
            'entries': len(cls._cache),
            'max_entries': cls.MAX_ENTRIES,
            'access_order_len': len(cls._access_order)
        }

    @classmethod
    def cleanup_expired(cls) -> int:
        """
        Remove expired entries from cache.
        
        Returns:
            Number of entries removed
            
        Example:
            >>> removed = Cache.cleanup_expired()
            >>> print(f"Cleaned up {removed} expired entries")
        """
        now = time.time()
        expired = [k for k, ts in cls._timestamps.items() if now > ts]
        for key in expired:
            cls._remove(key)
        return len(expired)


# =============================================================================
# VALIDATION FUNCTIONS
# =============================================================================

def validate_bypass_entry(entry: str) -> bool:
    """
    Validate bypass list entry (domain, IP, or comment).
    
    Optimized for minimal memory usage.
    
    Args:
        entry: Entry to validate (domain, IP, or comment)
    
    Returns:
        True if valid, False otherwise
    
    Example:
        >>> validate_bypass_entry("example.com")
        True
        >>> validate_bypass_entry("192.168.1.1")
        True
        >>> validate_bypass_entry("# comment")
        True
        >>> validate_bypass_entry("")
        False
    """
    entry = entry.strip()
    
    # Empty entries are invalid
    if not entry:
        return False
    
    # Comments are valid
    if entry.startswith('#'):
        return True
    
    # Check length (max 253 characters for domain)
    if len(entry) > 253:
        return False
    
    # IPv4 check
    parts = entry.split('.')
    if len(parts) == 4:
        try:
            return all(0 <= int(p) <= 255 for p in parts)
        except ValueError:
            pass  # Not an IP, continue to domain check
    
    # IPv6 check (simple check for colons)
    if ':' in entry:
        return True
    
    # Domain check (must have at least one dot)
    if '.' in entry:
        return True
    
    return False


def is_ip_address(entry: str) -> bool:
    """
    Check if entry is an IP address (IPv4 or IPv6).

    Args:
        entry: Entry to check

    Returns:
        True if IP address, False otherwise

    Example:
        >>> is_ip_address("192.168.1.1")
        True
        >>> is_ip_address("example.com")
        False
        >>> is_ip_address("::1")
        True
    """
    entry = entry.strip()

    # IPv4 check
    parts = entry.split('.')
    if len(parts) == 4:
        try:
            return all(0 <= int(p) <= 255 for p in parts)
        except ValueError:
            pass

    # IPv6 check (simple check for colons)
    if ':' in entry:
        return True

    return False


# =============================================================================
# FILE OPERATIONS
# =============================================================================

def load_bypass_list(filepath: str) -> List[str]:
    """
    Load bypass list from file with caching.
    
    - Caches for 1 minute or until file changes
    - Skips comments and empty lines
    - Memory-optimized for embedded devices
    
    Args:
        filepath: Path to bypass list file
    
    Returns:
        List of bypass entries (without comments/empty lines)
    
    Example:
        >>> load_bypass_list("/opt/etc/unblock/unblocktor.txt")
        ['example.com', 'test.com']
    """
    cache_key = f'bypass:{filepath}'
    
    # Check cache first
    if Cache.is_valid(cache_key):
        cached = Cache.get(cache_key)
        # Check if file has changed
        try:
            mtime = os.path.getmtime(filepath)
            if cached and mtime == cached.get('mtime'):
                return cached['data']
        except (OSError, IOError):
            pass
    
    # File doesn't exist
    if not os.path.exists(filepath):
        return []
    
    # Load from file
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            # Skip comments and empty lines, preserve order
            data = [
                line.strip() for line in f 
                if line.strip() and not line.strip().startswith('#')
            ]
        
        # Cache with mtime
        try:
            mtime = os.path.getmtime(filepath)
        except (OSError, IOError):
            mtime = time.time()
        
        Cache.set(cache_key, {'data': data, 'mtime': mtime}, ttl=60)
        
        return data
    
    except Exception as e:
        logger.error(f"Error loading bypass list {filepath}: {e}")
        return []


def save_bypass_list(filepath: str, sites: List[str]) -> None:
    """
    Save bypass list to file atomically.
    
    - Atomic write via .tmp file
    - Preserves order (no sorting)
    - Clears cache after save
    - Memory-optimized
    
    Args:
        filepath: Path to bypass list file
        sites: List of bypass entries to save
    
    Example:
        >>> save_bypass_list("/opt/etc/unblock/unblocktor.txt", 
        ...                  ["example.com", "test.com"])
    """
    temp_path = filepath + '.tmp'
    
    try:
        # Atomic write via temporary file
        with open(temp_path, 'w', encoding='utf-8') as f:
            # Preserve original order
            f.write('\n'.join(sites))
        
        # Atomic replace
        os.replace(temp_path, filepath)
        
        # Clear cache for this file
        cache_key = f'bypass:{filepath}'
        Cache._cache.pop(cache_key, None)
        Cache._timestamps.pop(cache_key, None)
        if cache_key in Cache._access_order:
            Cache._access_order.remove(cache_key)
    
    except Exception as e:
        logger.error(f"Error saving bypass list {filepath}: {e}")
        # Cleanup temp file on error
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
    """
    Get path to deployment script.

    Searches in multiple locations:
    1. /opt/bin/ (router production)
    2. /opt/etc/unblock/ (router production)
    3. /opt/etc/ndm/ (router production)
    4. deploy/router/ (development)
    5. Current directory

    Args:
        script_name: Name of script (e.g., 'unblock_update.sh')

    Returns:
        Full path to script or None if not found
    """
    # Router production paths
    possible_paths = [
        f"/opt/bin/{script_name}",
        f"/opt/etc/unblock/{script_name}",
        f"/opt/etc/ndm/{script_name}",
    ]

    # Development paths (relative to project root)
    try:
        project_root = Path(__file__).parent.parent.parent
        dev_paths = [
            project_root / "deploy" / "router" / script_name,
            project_root / "scripts" / "deploy" / script_name,
        ]
        possible_paths.extend(str(p) for p in dev_paths)
    except Exception:
        pass

    # Current directory
    possible_paths.append(script_name)

    # Find first existing path
    for path in possible_paths:
        if os.path.exists(path):
            return path

    return None


def run_unblock_update() -> Tuple[bool, str]:
    """
    Run unblock_update.sh script to apply bypass list changes.
    
    Returns:
        Tuple of (success: bool, output: str)
    
    Example:
        >>> success, output = run_unblock_update()
        >>> if success:
        ...     print("Changes applied successfully")
    """
    script_path = get_script_path('unblock_update.sh')
    
    if not script_path:
        logger.error("unblock_update.sh script not found")
        return False, "Script not found"
    
    try:
        result = subprocess.run(
            ['sh', script_path],
            capture_output=True,
            text=True,
            timeout=60  # 60 second timeout
        )
        
        success = result.returncode == 0
        output = result.stdout.strip() or result.stderr.strip()
        
        if success:
            logger.info(f"unblock_update.sh completed successfully: {output}")
        else:
            logger.error(f"unblock_update.sh failed: {output}")
        
        return success, output
    
    except subprocess.TimeoutExpired:
        logger.error("unblock_update.sh timed out")
        return False, "Timeout"
    except Exception as e:
        logger.error(f"Error running unblock_update.sh: {e}")
        return False, str(e)


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def cleanup_memory() -> None:
    """
    Cleanup memory by clearing cache.
    
    Call periodically to prevent memory leaks on embedded devices.
    
    Example:
        >>> cleanup_memory()  # Call every 100 operations
    """
    Cache.clear()
    logger.debug("Memory cleanup completed")


# =============================================================================
# SYSTEM STATS
# =============================================================================

import threading


class MemoryManager:
    """
    Memory manager for embedded devices with auto-optimization.
    
    Monitors memory usage and automatically reduces cache/workers when low.
    Can be enabled/disabled via toggle.
    """
    
    _instance = None
    _lock = threading.Lock()
    
    # Thresholds
    LOW_MEMORY_THRESHOLD_MB = 20  # Free MB to trigger optimization
    AGGRESSIVE_THRESHOLD_MB = 10   # Free MB for aggressive optimization
    
    # Settings
    _enabled = False
    _aggressive_mode = False
    _original_cache_size = 30
    
    # Optimization levels
    NORMAL = {'cache': 30, 'dns_interval': 60}
    LOW = {'cache': 15, 'dns_interval': 120}
    AGGRESSIVE = {'cache': 5, 'dns_interval': 180}
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if hasattr(self, '_initialized'):
            return
        self._initialized = True
        self._monitor_thread = None
        self._running = False
    
    @classmethod
    def enable(cls) -> bool:
        """Enable auto memory optimization"""
        cls._enabled = True
        cls._original_cache_size = Cache.MAX_ENTRIES
        logger.info("Auto memory optimization enabled")
        return True
    
    @classmethod
    def disable(cls) -> bool:
        """Disable auto memory optimization and restore defaults"""
        cls._enabled = False
        Cache.MAX_ENTRIES = cls._original_cache_size
        cls._aggressive_mode = False
        logger.info("Auto memory optimization disabled")
        return True
    
    @classmethod
    def is_enabled(cls) -> bool:
        """Check if auto optimization is enabled"""
        return cls._enabled
    
    @classmethod
    def get_status(cls) -> dict:
        """Get current optimization status"""
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
        """
        Check memory and optimize if needed.
        
        Returns:
            Tuple of (did_optimize, level, free_mb)
        """
        if not cls._enabled:
            return False, 'disabled', 0
        
        stats = get_memory_stats()
        free_mb = stats.get('free_mb', 0)
        
        if free_mb <= cls.AGGRESSIVE_THRESHOLD_MB and not cls._aggressive_mode:
            # Aggressive optimization
            Cache.MAX_ENTRIES = cls.AGGRESSIVE['cache']
            cls._aggressive_mode = True
            logger.warning(f"Aggressive mode: cache={Cache.MAX_ENTRIES}, free={free_mb}MB")
            return True, 'aggressive', free_mb
        
        elif free_mb <= cls.LOW_MEMORY_THRESHOLD_MB and not cls._aggressive_mode:
            # Low memory optimization
            Cache.MAX_ENTRIES = cls.LOW['cache']
            logger.info(f"Low memory mode: cache={Cache.MAX_ENTRIES}, free={free_mb}MB")
            return True, 'low', free_mb
        
        elif free_mb > cls.LOW_MEMORY_THRESHOLD_MB and cls._aggressive_mode:
            # Restore from aggressive
            Cache.MAX_ENTRIES = cls.NORMAL['cache']
            cls._aggressive_mode = False
            logger.info(f"Memory restored: cache={Cache.MAX_ENTRIES}, free={free_mb}MB")
            return True, 'normal', free_mb
        
        return False, 'normal' if not cls._aggressive_mode else 'aggressive', free_mb


def get_cpu_stats() -> dict:
    """
    Get CPU usage statistics for the system.
    
    Returns:
        dict with cpu_percent
    """
    try:
        # Read /proc/stat to calculate CPU usage
        with open('/proc/stat', 'r') as f:
            lines = f.readlines()
        
        # First line contains overall CPU stats
        for line in lines:
            if line.startswith('cpu '):
                parts = line.split()
                if len(parts) >= 8:
                    # cpu  user nice system idle iowait irq softirq steal guest guest_nice
                    user = int(parts[1])
                    nice = int(parts[2])
                    system = int(parts[3])
                    idle = int(parts[4])
                    iowait = int(parts[5])
                    
                    # Calculate total and work time
                    total = user + nice + system + idle + iowait
                    work = user + nice + system
                    
                    # Get previous stats for delta calculation
                    if not hasattr(get_cpu_stats, 'prev_total'):
                        get_cpu_stats.prev_total = 0
                        get_cpu_stats.prev_work = 0
                    
                    # Calculate percentage
                    total_delta = total - get_cpu_stats.prev_total
                    work_delta = work - get_cpu_stats.prev_work
                    
                    if total_delta > 0:
                        cpu_percent = (work_delta / total_delta) * 100
                    else:
                        cpu_percent = 0
                    
                    # Update previous stats
                    get_cpu_stats.prev_total = total
                    get_cpu_stats.prev_work = work
                    
                    return {'cpu_percent': round(cpu_percent, 1)}
        
        return {'cpu_percent': 0}
    except Exception as e:
        logger.error(f"Failed to get CPU stats: {e}")
        return {'cpu_percent': 0}


def get_memory_stats() -> dict:
    """
    Get memory usage statistics for the system.
    
    Returns:
        dict with total_mb, used_mb, free_mb, percent, cache_entries
    """
    try:
        with open('/proc/meminfo', 'r') as f:
            lines = f.readlines()
        
        mem = {}
        for line in lines:
            parts = line.split()
            if len(parts) >= 2:
                key = parts[0].rstrip(':')
                try:
                    mem[key] = int(parts[1])  # KB
                except ValueError:
                    pass
        
        total = mem.get('MemTotal', 0) / 1024  # MB
        free = mem.get('MemFree', 0) / 1024
        buffers = mem.get('Buffers', 0) / 1024
        cached = mem.get('Cached', 0) / 1024
        available = mem.get('MemAvailable', 0) / 1024  # MB (if available in kernel)

        # Calculate used memory
        # MemAvailable already includes buffers + cached that can be freed
        if available > 0:
            used = total - available
            # Real used memory (excluding reclaimable cache)
            real_used = used
        else:
            # Fallback: estimate used memory
            used = total - free - buffers - cached
            real_used = used

        # For display purposes
        if available > 0:
            display_available = available
        else:
            display_available = free + buffers + cached

        # Calculate percentage based on real used memory (excluding cache)
        # This gives more accurate picture for embedded devices
        percent = (real_used / total * 100) if total > 0 else 0
        
        # Also calculate "raw" percentage (including cache) for reference
        raw_percent = (used / total * 100) if total > 0 else 0

        try:
            cache_stats = Cache.get_stats()
            cache_entries = cache_stats['entries']
            cache_max = cache_stats['max_entries']
        except AttributeError:
            cache_entries = 0
            cache_max = 30

        return {
            'total_mb': round(total, 1),
            'used_mb': round(used, 1),
            'free_mb': round(free, 1),
            'available_mb': round(display_available, 1),
            'cached_mb': round(cached, 1),
            'buffers_mb': round(buffers, 1),
            'real_used_mb': round(real_used, 1),  # Excluding cache
            'percent': round(percent, 1),  # Real percent (excluding cache)
            'raw_percent': round(raw_percent, 1),  # Raw percent (including cache)
            'cache_entries': cache_entries,
            'cache_max': cache_max,
        }
    except Exception as e:
        logger.error(f"Failed to get memory stats: {e}")
        try:
            cache_max = Cache.MAX_ENTRIES
        except AttributeError:
            cache_max = 30
        return {
            'total_mb': 0,
            'used_mb': 0,
            'free_mb': 0,
            'available_mb': 0,
            'cached_mb': 0,
            'percent': 0,
            'cache_entries': 0,
            'cache_max': cache_max,
            'error': str(e)
        }
