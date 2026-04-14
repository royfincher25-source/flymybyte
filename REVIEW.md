---
phase: code-review
reviewed: 2026-04-13T00:00:00Z
depth: standard
files_reviewed: 4
files_reviewed_list:
  - src/web_ui/core/dns_ops.py
  - src/web_ui/core/ipset_ops.py
  - src/web_ui/core/dnsmasq_manager.py
  - src/web_ui/core/unblock_manager.py
findings:
  critical: 2
  warning: 3
  info: 4
  total: 9
status: issues_found
---

# Code Review Report

**Reviewed:** 2026-04-13
**Depth:** standard
**Files Reviewed:** 4
**Status:** issues_found

## Summary

Reviewed 4 core bypass system files for bugs, security vulnerabilities, and code quality issues. Found 2 critical issues (unreachable code and undefined variable), 3 warnings (security and code quality), and 4 informational findings. The most serious issue is the command injection vulnerability in `dns_ops.py` where user-controlled filepath is passed to a shell script without sanitization.

---

## Critical Issues

### CR-01: Unreachable Code After Return Statement

**File:** `src/web_ui/core/dns_ops.py:421-423`
**Issue:** Two lines of code after the return statement are unreachable. The function `resolve_domains_for_ipset()` returns on line 421, but lines 423-424 contain additional code that will never execute.

**Code:**
```python
    logger.info(f"[IPSET] {filepath}: {len(cidr_entries)} CIDR, {len(ip_entries)} IP, {len(domains)} domains")
    return total_added

    logger.info(f"[IPSET] {filepath}: {len(cidr_entries)} CIDR, {len(ip_entries)} IP, {len(domains)} domains resolved")
    return total_added
```

**Fix:**
Remove the unreachable lines 423-424:
```python
    logger.info(f"[IPSET] {filepath}: {len(cidr_entries)} CIDR, {len(ip_entries)} IP, {len(domains)} domains")
    return total_added
```

---

### CR-02: Undefined Variable Usage

**File:** `src/web_ui/core/dnsmasq_manager.py:354`
**Issue:** The variable `DNSMASQ_CONF` is used but never defined in this file. Only `DNSMASQ_CONFIG` is imported from constants (line 22). This will cause a `NameError` at runtime when `test_config()` is called.

**Code:**
```python
def test_config(self) -> Tuple[bool, str]:
    if not os.path.exists(DNSMASQ_CONF):  # Line 354 - DNSMASQ_CONF undefined!
        return False, "dnsmasq.conf not found"
```

**Fix:**
Change `DNSMASQ_CONF` to `DNSMASQ_CONFIG`:
```python
def test_config(self) -> Tuple[bool, str]:
    if not os.path.exists(DNSMASQ_CONFIG):
        return False, "dnsmasq.conf not found"
```

---

## Warnings

### WR-01: Command Injection via shell=True

**File:** `src/web_ui/core/dns_ops.py:404-409`
**Issue:** User-controlled `filepath` and `ipset_name` are passed to a shell script via string interpolation with `shell=True`. This is a command injection vulnerability if these variables can be controlled by external input.

**Code:**
```python
result = subprocess.run(
    f'{RESOLVE_SCRIPT} {filepath} {ipset_name}',
    shell=True,
    capture_output=True,
    text=True,
    timeout=60
)
```

**Fix:**
Use argument list instead of shell string, and validate inputs:
```python
# Validate inputs to prevent injection
if not filepath.startswith('/') or '..' in filepath:
    logger.error(f"[DNS] Invalid filepath: {filepath}")
    return 0

# Use list arguments instead of shell=True
result = subprocess.run(
    [RESOLVE_SCRIPT, filepath, ipset_name],
    shell=False,
    capture_output=True,
    text=True,
    timeout=60
)
```

---

### WR-02: Import Inside Function

**File:** `src/web_ui/core/dnsmasq_manager.py:384`
**Issue:** The `re` module is imported inside the `_is_valid_domain()` method. Importing at module level is more efficient and follows Python best practices.

**Code:**
```python
@staticmethod
def _is_valid_domain(domain: str) -> bool:
    if not domain or len(domain) > 253:
        return False
    import re  # <-- Should be at module level
    return bool(re.match(r'^[a-z0-9]([a-z0-9\-\.]*[a-z0-9])?$', domain))
```

**Fix:**
Move `import re` to the top of the file (line 16 area) and remove from function.

---

### WR-03: Magic Number Without Explanation

**File:** `src/web_ui/core/dns_ops.py:416`
**Issue:** Hardcoded value `24065` assigned to `total_added` without explanation. This appears to be a placeholder or test value that could cause incorrect return values.

**Code:**
```python
if result.returncode == 0:
    logger.info(f"[DNS] {result.stdout.strip()}")
    total_added = 24065  # <-- Magic number, unclear purpose
```

**Fix:**
Either parse the actual count from script output or use a named constant:
```python
# Parse actual added count from script output
match = re.search(r'(\d+) added', result.stdout)
total_added = int(match.group(1)) if match else 0
```

---

## Info

### IN-01: Duplicate Import Statement

**File:** `src/web_ui/core/dns_ops.py:375-376, 401`
**Issue:** The `subprocess` module is imported twice - once at module level (line 7) and again inside function (line 401). Also, `os` is imported inside the function but should use the already-imported `Path` from line 14.

**Code:**
```python
# Line 401 - duplicate import
import subprocess
# Also line 375 imports os which is already available
import os
from .utils import load_bypass_list
```

**Fix:**
Remove duplicate imports inside function - use module-level imports.

---

### IN-02: Unused Import

**File:** `src/web_ui/core/dns_ops.py:14`
**Issue:** `Path` from pathlib is imported but never used in `resolve_domains_for_ipset()`. The code uses string operations with `os.path.exists()` and `Path(filepath).stem`.

**Code:**
```python
from pathlib import Path  # imported but not used in this function
```

**Fix:**
Remove unused import or refactor to use `Path`:
```python
filepath_path = Path(filepath)
ipset_name = IPSET_MAP.get(filepath_path.stem, f'unblock{filepath_path.stem}')
```

---

### IN-03: Inconsistent Error Handling Pattern

**File:** `src/web_ui/core/unblock_manager.py:249-256`
**Issue:** The `_flush_ipsets()` method doesn't return `False` when flushing fails - it always returns `True` even if some ipsets failed to flush. This masks errors from callers.

**Code:**
```python
def _flush_ipsets(self) -> Tuple[bool, str]:
    """Очистить все ipsets."""
    logger.info("[UNBLOCK] Flushing all ipsets...")
    flushed = []
    for name in IPSET_NAMES:
        try:
            # ... flush logic ...
        except Exception as e:
            logger.warning(...)
    
    msg = f"Flushed: {', '.join(flushed)}"
    return True, msg  # <-- Always returns True!
```

**Fix:**
Return failure if no ipsets were flushed:
```python
if not flushed:
    logger.error("[UNBLOCK] No ipsets were flushed")
    return False, "No ipsets flushed"

return True, msg
```

---

### IN-04: Inconsistent Variable Naming

**File:** `src/web_ui/core/ipset_ops.py:182`
**Issue:** Mixed naming convention - `IPSET_TIMEOUT` is a constant (all caps) but defined inside a function. Consider moving to module level if it's meant to be a constant configuration value.

**Code:**
```python
def ensure_ipset_exists(setname: str, settype: str = 'hash:ip') -> Tuple[bool, str]:
    IPSET_TIMEOUT = 300  # seconds - constant but defined in function
```

**Fix:**
Move constant to module level:
```python
# At module level (around line 14)
IPSET_DEFAULT_TIMEOUT = 300  # seconds - IPs auto-expire after 5 minutes
```

---

_Reviewed: 2026-04-13_
_Reviewer: the agent (gsd-code-reviewer)_
_Depth: standard_