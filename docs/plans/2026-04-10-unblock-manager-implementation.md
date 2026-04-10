# UnblockManager Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Создать единый Python API для всех bypass операций, заменяющий shell скрипты с гибридным fallback.

**Architecture:** UnblockManager инкапсулирует DnsmasqManager + ipset операции + shell fallback. Гибридный режим: сначала пробуем Python, если не работает — shell.

**Tech Stack:** Python 3, Flask, subprocess для shell fallback

---

## Pre-requisites

- [ ] Проверить что DnsmasqManager работает
- [ ] Проверить что refresh_ipset_from_file работает
- [ ] Проверить структуру project (Flask app location)

---

## Task 1: Create UnblockManager

**Files:**
- Create: `src/web_ui/core/unblock_manager.py`

**Step 1: Create the file with basic structure**

```python
"""
FlyMyByte — Unified Unblock Manager

Единый интерфейс для управления bypass (dnsmasq + ipset).
Гибридный режим: Python с shell fallback.

Usage:
    from core.unblock_manager import get_unblock_manager
    
    mgr = get_unblock_manager()
    ok, msg = mgr.update_all()
"""
import os
import logging
import subprocess
import time
from typing import Dict, Tuple, Optional, List
from concurrent.futures import ThreadPoolExecutor, as_completed

from .dnsmasq_manager import DnsmasqManager
from .app_config import WebConfig

logger = logging.getLogger(__name__)


# Константы из shell скриптов
DEFAULT_THREAD_COUNT = 4
IPSET_NAMES = ['unblocksh', 'unblockvless', 'unblocktroj']
UNBLOCK_SCRIPTS = {
    'dnsmasq': '/opt/bin/unblock_dnsmasq.sh',
    'ipset': '/opt/bin/unblock_ipset.sh',
    'update': '/opt/bin/unblock_update.sh',
}


class UnblockManager:
    """Менеджер для полного управления bypass."""
    
    def __init__(self):
        self._dnsmasq = DnsmasqManager()
        self._config = WebConfig()
    
    def update_all(self, timeout: int = 600) -> Tuple[bool, str]:
        """Полное обновление: dnsmasq + ipset."""
        logger.info("[UNBLOCK] Starting full update...")
        
        # Step 1: Очистить ipsets
        self._flush_ipsets()
        
        # Step 2: Обновить dnsmasq конфиги
        ok, msg = self._update_dnsmasq()
        if not ok:
            logger.warning(f"[UNBLOCK] dnsmasq update failed, trying shell: {msg}")
            ok, msg = self._fallback_dnsmasq()
        
        # Step 3: Обновить ipsets
        ok2, msg2 = self._update_ipsets()
        if not ok2:
            logger.warning(f"[UNBLOCK] ipset update failed, trying shell: {msg2}")
            ok2, msg2 = self._fallback_ipset()
        
        # Step 4: Проверить результат
        status = self.get_status()
        total_ips = sum(status['ipsets'].values())
        
        if total_ips > 0:
            logger.info(f"[UNBLOCK] Update complete: {total_ips} IPs")
            return True, f"Updated: {total_ips} IPs in ipsets"
        else:
            return False, "No entries in ipsets"
    
    def update_dnsmasq(self) -> Tuple[bool, str]:
        """Обновить только dnsmasq конфиги (без ipset)."""
        return self._update_dnsmasq()
    
    def update_ipsets(self, max_workers: int = None) -> Tuple[bool, str]:
        """Обновить только ipset (без dnsmasq)."""
        return self._update_ipsets(max_workers)
    
    def get_status(self) -> Dict:
        """Получить статус всех компонентов."""
        return {
            'dnsmasq_running': self._check_dnsmasq(),
            'ipsets': self._get_ipset_counts(),
            'config_exists': os.path.exists('/opt/etc/unblock.dnsmasq'),
        }
    
    def flush_ipsets(self) -> Tuple[bool, str]:
        """Очистить все ipsets."""
        return self._flush_ipsets()
    
    # =========================================================================
    # Private methods
    # =========================================================================
    
    def _check_dnsmasq(self) -> bool:
        """Проверить запущен ли dnsmasq."""
        try:
            result = subprocess.run(['pgrep', 'dnsmasq'], capture_output=True, timeout=3)
            return result.returncode == 0
        except Exception:
            return False
    
    def _get_ipset_counts(self) -> Dict[str, int]:
        """Получить количество записей в каждом ipset."""
        counts = {}
        for name in IPSET_NAMES:
            try:
                result = subprocess.run(
                    ['ipset', 'list', name],
                    capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0:
                    # Подсчёт строк, начинающихся с цифры (IP адреса)
                    lines = [l for l in result.stdout.split('\n') if l.strip() and l.strip()[0].isdigit()]
                    counts[name] = len(lines)
                else:
                    counts[name] = 0
            except Exception:
                counts[name] = 0
        return counts
    
    def _update_dnsmasq(self) -> Tuple[bool, str]:
        """Обновить dnsmasq конфиги через Python."""
        try:
            ok, msg = self._dnsmasq.generate_all()
            if ok:
                self._dnsmasq.restart_dnsmasq()
            return ok, msg
        except Exception as e:
            return False, str(e)
    
    def _update_ipsets(self, max_workers: int = None) -> Tuple[bool, str]:
        """Обновить ipsets из файлов через Python."""
        from .services import refresh_ipset_from_file
        
        if max_workers is None:
            max_workers = DEFAULT_THREAD_COUNT
        
        unblock_dir = self._config.unblock_dir
        files_map = {
            'unblocksh': os.path.join(unblock_dir, 'shadowsocks.txt'),
            'unblockvless': os.path.join(unblock_dir, 'vless.txt'),
            'unblocktroj': os.path.join(unblock_dir, 'trojan.txt'),
        }
        
        total_added = 0
        errors = []
        
        for ipset_name, filepath in files_map.items():
            if not os.path.exists(filepath):
                logger.debug(f"[UNBLOCK] File not found: {filepath}")
                continue
            
            ok, msg = refresh_ipset_from_file(filepath, max_workers)
            if ok:
                # Extract count from message
                import re
                m = re.search(r'(\d+) IPs', msg)
                if m:
                    total_added += int(m.group(1))
            else:
                errors.append(f"{ipset_name}: {msg}")
        
        if errors:
            return False, '; '.join(errors)
        return True, f"Added {total_added} IPs"
    
    def _flush_ipsets(self) -> Tuple[bool, str]:
        """Очистить все ipsets."""
        flushed = []
        for name in IPSET_NAMES:
            try:
                subprocess.run(['ipset', 'flush', name], capture_output=True, timeout=5)
                flushed.append(name)
            except Exception:
                pass
        return True, f"Flushed: {', '.join(flushed)}"
    
    def _fallback_dnsmasq(self) -> Tuple[bool, str]:
        """Fallback: вызвать shell скрипт для dnsmasq."""
        script = UNBLOCK_SCRIPTS['dnsmasq']
        if not os.path.exists(script):
            return False, f"Shell script not found: {script}"
        
        try:
            result = subprocess.run(
                ['sh', script],
                capture_output=True, text=True, timeout=120
            )
            if result.returncode == 0:
                return True, "Shell dnsmasq script completed"
            return False, result.stderr[:200]
        except Exception as e:
            return False, str(e)
    
    def _fallback_ipset(self) -> Tuple[bool, str]:
        """Fallback: вызвать shell скрипт для ipset."""
        script = UNBLOCK_SCRIPTS['ipset']
        if not os.path.exists(script):
            return False, f"Shell script not found: {script}"
        
        try:
            result = subprocess.run(
                ['sh', script],
                capture_output=True, text=True, timeout=600
            )
            if result.returncode == 0:
                return True, "Shell ipset script completed"
            return False, result.stderr[:200]
        except Exception as e:
            return False, str(e)


# Singleton
_instance: Optional[UnblockManager] = None


def get_unblock_manager() -> UnblockManager:
    """Получить экземпляр UnblockManager (singleton)."""
    global _instance
    if _instance is None:
        _instance = UnblockManager()
    return _instance
```

**Step 2: Verify the file is syntactically correct**

Run: `python -m py_compile src/web_ui/core/unblock_manager.py`
Expected: No output (success)

**Step 3: Test imports**

Run: `cd src/web_ui && python -c "from core.unblock_manager import get_unblock_manager; print('OK')"`
Expected: `OK`

**Step 4: Commit**

```bash
git add src/web_ui/core/unblock_manager.py
git commit -m "feat(unblock): add UnblockManager with Python + shell fallback"
```

---

## Task 2: Add UnblockManager to ServiceLocator

**Files:**
- Modify: `src/web_ui/core/service_locator.py`

**Step 1: Add unblock() function**

Find line ~44 (after backup function) and add:

```python
def unblock():
    """Get unblock manager."""
    from .unblock_manager import get_unblock_manager
    return get_unblock_manager()
```

**Step 2: Add to ServiceLocator class**

Find line ~98 (after key() method) and add:

```python
    @staticmethod
    def unblock():
        """Get unblock manager."""
        return unblock()
```

**Step 3: Add to all_managers()**

Find line ~111-119 and add `'unblock': unblock,` to the dict.

**Step 4: Run syntax check**

Run: `python -m py_compile src/web_ui/core/service_locator.py`
Expected: No output

**Step 5: Test imports**

Run: `cd src/web_ui && python -c "from core.service_locator import ServiceLocator; mgr = ServiceLocator.unblock(); print(type(mgr).__name__)"`
Expected: `UnblockManager`

**Step 6: Commit**

```bash
git add src/web_ui/core/service_locator.py
git commit -m "feat(service_locator): add unblock manager"
```

---

## Task 3: Update routes_updates.py to use UnblockManager

**Files:**
- Modify: `src/web_ui/routes_updates.py` (find relevant update endpoints)

**Step 1: Find the update endpoint**

Run: `grep -n "unblock_update\|update.*bypass" src/web_ui/routes_updates.py`
Expected: Find the route that calls unblock_update.sh

**Step 2: Replace shell call with Python**

Find the code that calls `unblock_update.sh` and replace with:

```python
from core.service_locator import ServiceLocator

# В функции обновления bypass:
unblock_mgr = ServiceLocator.unblock()
ok, msg = unblock_mgr.update_all(timeout=600)
```

**Step 3: Commit**

```bash
git add src/web_ui/routes_updates.py
git commit -m "refactor(routes_updates): use UnblockManager instead of shell"
```

---

## Task 4: Update S99unblock with hybrid mode

**Files:**
- Modify: `src/web_ui/resources/scripts/S99unblock`

**Step 1: Add Python fallback logic**

After line ~30 (after dnsmasq restart), add:

```bash
# Step 2a: Try Python first (if available)
if [ -x "/opt/bin/unblock.py" ]; then
    log "Trying Python unblock.py..."
    if /opt/bin/unblock.py update >> "$LOGFILE" 2>&1; then
        log "Python unblock.py completed successfully"
        PYTHON_OK=true
    else
        log_error "Python unblock.py failed, falling back to shell"
        PYTHON_OK=false
    fi
else
    log "Python unblock.py not found, using shell scripts"
    PYTHON_OK=false
fi
```

**Step 2: Modify ipset step to check PYTHON_OK**

Replace the unblock_ipset.sh call with:

```bash
if [ "$PYTHON_OK" = "true" ]; then
    # Already done in unblock.py update
    log "IPSet already updated by Python"
else
    # Fallback to shell
    if /opt/bin/unblock_ipset.sh >> "$LOGFILE" 2>&1; then
        ...
```

**Step 3: Commit**

```bash
git add src/web_ui/resources/scripts/S99unblock
git commit -m "feat(S99unblock): add Python fallback for unblock operations"
```

---

## Task 5: Test on router (manual)

**Step 1: Deploy to router**

Upload the new files to the router:
- `src/web_ui/core/unblock_manager.py`
- Updated `service_locator.py`
- Updated `routes_updates.py`
- Updated `S99unblock`

**Step 2: Test Python unblock**

```bash
# SSH to router
/opt/bin/python3 -c "from core.unblock_manager import get_unblock_manager; m = get_unblock_manager(); print(m.get_status())"
```

Expected: JSON with dnsmasq_running and ipsets counts

**Step 3: Test full update**

```bash
/opt/bin/python3 -c "from core.unblock_manager import get_unblock_manager; m = get_unblock_manager(); ok, msg = m.update_all(); print(ok, msg)"
```

Expected: `True` with IP count

**Step 4: Test S99unblock**

```bash
S99unblock start
```

Expected: Works with Python fallback

---

## Task 6: Create CLI wrapper for unblock.py

**Files:**
- Create: `src/web_ui/resources/scripts/unblock.py`

**Step 1: Create CLI wrapper**

```python
#!/opt/bin/python3
"""
Unblock CLI - Python alternative to shell scripts.
Usage: unblock.py [update|dnsmasq|ipset|status]
"""
import sys
import os

# Add web_ui to path
sys.path.insert(0, '/opt/etc/web_ui')

from core.unblock_manager import get_unblock_manager

def main():
    if len(sys.argv) < 2:
        print("Usage: unblock.py [update|dnsmasq|ipset|status]")
        sys.exit(1)
    
    cmd = sys.argv[1]
    mgr = get_unblock_manager()
    
    if cmd == 'update':
        ok, msg = mgr.update_all(timeout=600)
        print(msg)
        sys.exit(0 if ok else 1)
    
    elif cmd == 'dnsmasq':
        ok, msg = mgr.update_dnsmasq()
        print(msg)
        sys.exit(0 if ok else 1)
    
    elif cmd == 'ipset':
        ok, msg = mgr.update_ipsets()
        print(msg)
        sys.exit(0 if ok else 1)
    
    elif cmd == 'status':
        import json
        print(json.dumps(mgr.get_status(), indent=2))
        sys.exit(0)
    
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)

if __name__ == '__main__':
    main()
```

**Step 2: Make executable and test**

Run: `chmod +x src/web_ui/resources/scripts/unblock.py`

**Step 3: Commit**

```bash
git add src/web_ui/resources/scripts/unblock.py
git commit -m "feat(unblock): add Python CLI wrapper"
```

---

## Summary

After completion:
- ✅ `core/unblock_manager.py` provides unified API
- ✅ Shell fallback if Python fails
- ✅ `S99unblock` tries Python first, then shell
- ✅ Web interface uses Python API
- ✅ All tests pass

**Total commits: ~6**