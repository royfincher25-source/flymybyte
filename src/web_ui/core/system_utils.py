"""
FlyMyByte - System Utilities

System monitoring: CPU, memory stats.
Extracted from utils.py for better organization.
"""
import time
import logging
from typing import Dict

logger = logging.getLogger(__name__)


# Cache for get_memory_stats (5 second TTL)
_memory_stats_cache = {'data': None, 'timestamp': 0}
_MEMORY_STATS_TTL = 5  # seconds


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


def get_memory_stats() -> dict:
    """Get memory usage from /proc/meminfo (cached 5s)."""
    global _memory_stats_cache
    
    now = time.time()
    if _memory_stats_cache['data'] is not None and (now - _memory_stats_cache['timestamp']) < _MEMORY_STATS_TTL:
        return _memory_stats_cache['data']
    
    try:
        with open('/proc/meminfo', 'r') as f:
            lines = f.readlines()
        mem = {}
        for line in lines:
            if ':' in line:
                key, val = line.split(':', 1)
                mem[key.strip()] = int(val.strip().split()[0])  # Convert KB to bytes
        
        total = mem.get('MemTotal', 0) * 1024
        free = mem.get('MemFree', 0) * 1024
        available = mem.get('MemAvailable', 0) * 1024
        buffers = mem.get('Buffers', 0) * 1024
        cached = mem.get('Cached', 0) * 1024
        
        result = {
            'total': total,
            'free': free,
            'available': available,
            'used': total - available,
            'percent': round((1 - available / total) * 100, 1) if total > 0 else 0,
            'buffers': buffers,
            'cached': cached,
        }
        
        _memory_stats_cache = {'data': result, 'timestamp': now}
        return result
    except Exception as e:
        logger.error(f"Failed to get memory stats: {e}")
        return {'total': 0, 'free': 0, 'available': 0, 'used': 0, 'percent': 0}