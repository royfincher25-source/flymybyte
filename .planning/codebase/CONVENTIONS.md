# Coding Conventions

**Analysis Date:** 2026-04-11

## Naming Patterns

**Files:**
- Snake_case for Python modules: `utils.py`, `parsers.py`, `service_ops.py`
- Route modules prefixed with `routes_`: `routes_core.py`, `routes_bypass.py`, `routes_vpn.py`
- Blueprint modules: `handlers.py`, `decorators.py`, `exceptions.py`

**Functions:**
- snake_case for functions and methods: `parse_vless_key()`, `get_memory_stats()`, `validate_bypass_entry()`
- Underscore prefix for private functions: `_sanitize_dnsmasq_conf()`, `_check_dnsmasq_status()`

**Variables:**
- snake_case: `cache_key`, `web_password`, `real_path`
- Class names use PascalCase: `DNSSpoofing`, `MemoryManager`, `FlyMyByteError`

**Types:**
- Custom exceptions end with `Error`: `ServiceError`, `ValidationError`, `NetworkError`
- Type hints used extensively in core modules

## Code Style

**Formatting:**
- 4-space indentation (PEP 8)
- Maximum line length: ~100 characters (visible in `parsers.py` and `utils.py`)
- Blank lines between function definitions (2 lines in module, 1 in class)

**Linting:**
- Not configured - no `.pylintrc`, `.flake8`, or similar

**Imports:**
- Standard library first, then third-party, then local
- Relative imports for internal modules: `from .utils import Cache`
- Absolute imports in route modules: `from core.decorators import login_required`

```python
# Order in routes_core.py:
import secrets
import logging
from flask import Blueprint, render_template, ...
from core.decorators import ...
```

## Error Handling

**Pattern: Custom Exception Hierarchy**

`src/web_ui/core/exceptions.py` defines a structured exception hierarchy:

```python
class FlyMyByteError(Exception):
    def __init__(self, message: str, details: Optional[Any] = None):
        super().__init__(message)
        self.message = message
        self.details = details

class ServiceError(FlyMyByteError): pass
class ConfigError(FlyMyByteError): pass
class ValidationError(FlyMyByteError): pass
class NetworkError(FlyMyByteError): pass
```

**Usage in Code:**
- Parser functions raise `ValueError` with Russian error messages
- Service operations raise custom exceptions from `exceptions.py`
- Route handlers catch exceptions and return flash messages

**Logging:**
- All modules use module-level `logger = logging.getLogger(__name__)`
- Log levels: INFO for operations, WARNING for recoverable issues, ERROR for failures
- Structured logging with context: `logger.info(f"[BYPASS] Loaded {len(data)} entries")`

## Logging

**Framework:** Python standard `logging` module

**Patterns:**
```python
# Module-level logger
logger = logging.getLogger(__name__)

# With context prefix
logger.info(f"[IPSET] Refreshing from file: {filepath}")
logger.warning(f"[DNS-SPOOF] Too many domains ({len(domains)})")
logger.error(f"Failed to get CPU stats: {e}")
```

**Rotation:**
- `RotatingFileHandler` in `utils.py`: 100KB max, 3 backups
- Log file: `/opt/var/log/web_ui.log` (configurable via `LOG_FILE` env var)

## Comments

**When to Comment:**
- Complex parsing logic (`parsers.py`) - detailed docstrings
- Configuration generation - inline comments for field meanings
- Workarounds and assumptions - inline Russian comments

**JSDoc/TSDoc:**
- Not used (Python-only project)
- Function docstrings in Google style:

```python
def parse_vless_key(key: str) -> Dict[str, Any]:
    """
    Parse VLESS key with caching.

    Format: vless://uuid@server:port?encryption=none&security=tls&sni=...#name

    Args:
        key: VLESS key string

    Returns:
        Dict with parsed configuration

    Raises:
        ValueError: If key format is invalid
    """
```

## Function Design

**Size:** 
- Parsers in `parsers.py` are 50-120 lines
- Service functions in `utils.py` are 20-80 lines
- Route handlers typically <30 lines

**Parameters:**
- Type hints on all public functions
- Default values for optional parameters: `ttl=60`, `max_workers=10`

**Return Values:**
- Consistent tuple returns for operations: `Tuple[bool, str]` for success/error
- Dict returns for status queries: `Dict[str, Any]`

## Module Design

**Exports:**
- Re-export in `services.py` for backward compatibility:
```python
from .parsers import (
    parse_vless_key,
    vless_config,
    ...
)
```

**Barrel Files:**
- `core/__init__.py` exists but minimal
- Route modules each register their own blueprint in `app.py`

## Cross-Cutting Concerns

**Authentication:** `@login_required` decorator in `decorators.py`

**CSRF Protection:** 
- `@csrf_required` decorator for POST routes
- Session-based tokens: `session['csrf_token'] = secrets.token_hex(32)`

**Input Validation:**
- `validate_bypass_entry()` in `utils.py`
- Parser functions validate format and raise `ValueError`

**Memory Optimization:**
- `MemoryManager` singleton for embedded device optimization
- LRU cache with TTL in `Cache` class (30 entries max)

---

*Convention analysis: 2026-04-11*