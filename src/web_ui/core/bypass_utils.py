"""
FlyMyByte - Bypass List Utilities

Bypass file operations: load, save, validate.
Extracted from utils.py for better organization.
"""
import os
import time
import logging
from typing import List, Tuple

from .cache import Cache
from .constants import UNBLOCK_DIR

logger = logging.getLogger(__name__)


def validate_bypass_entry(entry: str) -> bool:
    """Validate bypass entry (IP, CIDR, or domain)."""
    if not entry or len(entry) > 253:
        return False
    
    entry = entry.strip()
    
    if entry.startswith(('#', '!', ';')):
        return False
    
    if entry.startswith(('*', '@')):
        entry = entry[1:].strip()
        if not entry:
            return False
    
    if '/' in entry:
        return is_cidr(entry)
    
    if entry[0].isdigit():
        return is_ip_address(entry)
    
    return is_domain(entry)


def is_ip_address(entry: str) -> bool:
    """Check if entry is a valid IP address."""
    parts = entry.split('.')
    if len(parts) != 4:
        return False
    try:
        return all(0 <= int(p) <= 255 for p in parts)
    except ValueError:
        return False


def is_cidr(entry: str) -> bool:
    """Check if entry is a valid CIDR notation."""
    if '/' not in entry:
        return False
    try:
        ip, mask = entry.split('/')
        parts = ip.split('.')
        if len(parts) != 4:
            return False
        if not all(0 <= int(p) <= 255 for p in parts):
            return False
        mask = int(mask)
        return 0 <= mask <= 32
    except (ValueError, IndexError):
        return False


def is_domain(entry: str) -> bool:
    """Check if entry looks like a valid domain."""
    import re
    return bool(re.match(r'^[a-z0-9]([a-z0-9\-\.]*[a-z0-9])?$', entry, re.I))


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
            os.remove(temp_path)
        except OSError:
            pass