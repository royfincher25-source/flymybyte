"""
FlyMyByte Web Interface - Environment Configuration

Lightweight .env parser for embedded devices.
Memory usage: < 1MB vs ~5MB for python-dotenv.
"""
import os
import re
from typing import Any, Dict, Optional


def parse_env_line(line: str):
    """Parse a single .env file line."""
    line = line.strip()
    if not line or line.startswith('#'):
        return None, None
    match = re.match(r'^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$', line)
    if not match:
        return None, None
    key = match.group(1)
    value = match.group(2)
    if (value.startswith('"') and value.endswith('"')) or \
       (value.startswith("'") and value.endswith("'")):
        value = value[1:-1]
    return key, value


def load_env_file(filepath: str) -> Dict[str, str]:
    """Load .env file into a dictionary."""
    env_vars: Dict[str, str] = {}
    try:
        with open(filepath, 'r') as f:
            for line in f:
                key, value = parse_env_line(line)
                if key is not None:
                    env_vars[key] = value
    except (FileNotFoundError, IOError):
        pass
    return env_vars


def load_env(filepath: Optional[str] = None) -> Dict[str, str]:
    """Load .env and set into os.environ (only if not already set)."""
    if filepath is None:
        import sys
        script_dir = os.path.dirname(os.path.abspath(sys.modules['__main__'].__file__))
        filepath = os.path.join(script_dir, '.env')
    env_vars = load_env_file(filepath)
    for key, value in env_vars.items():
        if key not in os.environ:
            os.environ[key] = value
    return env_vars


def get_env(key: str, default: Any = None) -> Any:
    """Get environment variable."""
    return os.environ.get(key, default)


def get_env_int(key: str, default: int = 0) -> int:
    """Get integer environment variable."""
    try:
        return int(os.environ.get(key, default))
    except (ValueError, TypeError):
        return default


def get_env_bool(key: str, default: bool = False) -> bool:
    """Get boolean environment variable."""
    value = os.environ.get(key, '').lower()
    if value in ('true', '1', 'yes', 'on'):
        return True
    return default
