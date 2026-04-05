# FlyMyByte Full Optimization Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Reduce codebase by ~40% through dead code removal, module consolidation, and architectural cleanup without breaking functionality.

**Architecture:** Flatten over-engineered layers, merge small modules into focused ones, eliminate unused code. Keep Flask + Jinja2 + Waitress stack.

**Tech Stack:** Python 3.8+, Flask 3.0.0, Jinja2, requests, waitress

**Principles:**
- DRY — remove all duplication
- YAGNI — delete everything not used in production
- No backward compatibility — break old imports freely
- Frequent commits — one per task

---

## Phase 1: Dead Code Removal

### Task 1.1: Remove env_parser.py (73 lines, zero imports)

**Files:**
- Delete: `src/web_ui/env_parser.py`
- No other changes needed — file is never imported

**Verification:**
```bash
cd H:\disk_e\dell\FlyMyByte && grep -r "env_parser" src/web_ui/
```
Expected: No results (except .gitignore or docs)

**Step:** Delete file, commit.

---

### Task 1.2: Remove core/update_service.py imports (broken, file missing)

**Files:**
- Modify: `src/web_ui/routes_service.py` — remove imports of `update_service`
- The update logic uses `create_update_backup` and `download_file` — inline these into routes_service.py

**Current broken imports (line ~60):**
```python
from core.update_service import (
    create_update_backup, download_file, download_all_files,
    FILES_TO_UPDATE, GITHUB_REPO, GITHUB_BRANCH, GITHUB_RAW_BASE,
    WEB_UI_DIR, TMP_DIR, BACKUP_DIR,
)
```

**Replace with direct implementation in `routes_service.py`:**
- Move `create_update_backup` logic inline (simple tarfile operation)
- Move `download_file` and `download_all_files` inline
- Move constants that are only used here

**Step:** Inline the update logic, remove broken imports, commit.

---

### Task 1.3: Remove core/backup_service.py (90 lines, only 3 functions used)

**Files:**
- Modify: `src/web_ui/routes_service.py` — inline 3 functions:
  - `create_backup()` → inline as `_create_backup()`
  - `get_backup_list()` → inline as `_list_backups()`
  - `delete_backup()` → inline as `_delete_backup()`
- Delete: `src/web_ui/core/backup_service.py`

**Step:** Inline functions, delete module, commit.

---

### Task 1.4: Remove core/decorators.py (63 lines, only csrf decorator used)

**Files:**
- Modify: `src/web_ui/routes_service.py` — inline `csrf_required` decorator
- Modify: `src/web_ui/core/__init__.py` — remove decorator export
- Delete: `src/web_ui/core/decorators.py`

**Inline code:**
```python
def csrf_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        from flask import request, abort, session
        token = request.form.get('csrf_token') or request.headers.get('X-CSRF-Token')
        if not token or token != session.get('csrf_token'):
            abort(403)
        return f(*args, **kwargs)
    return decorated
```

**Step:** Inline decorator, delete module, commit.

---

## Phase 2: Module Consolidation

### Task 2.1: Merge dns_manager.py + dns_monitor.py + dns_resolver.py into dns_ops.py

**Rationale:** These 3 modules (447 lines total) serve one feature: DNS monitoring. They should be one file.

**Files:**
- Create: `src/web_ui/core/dns_ops.py` (merged ~350 lines after cleanup)
- Delete: `src/web_ui/core/dns_manager.py` (104 lines)
- Delete: `src/web_ui/core/dns_monitor.py` (242 lines)
- Delete: `src/web_ui/core/dns_resolver.py` (201 lines)
- Modify: `src/web_ui/routes_service.py` — update imports
- Modify: `src/web_ui/app.py` — update DNSMonitor import
- Modify: `src/web_ui/core/__init__.py` — update exports

**Structure of dns_ops.py:**
```python
# DNS Operations Module
# Consolidates: dns_manager, dns_monitor, dns_resolver

# Classes:
class DNSMonitor:          # From dns_monitor.py, simplified
    ...

# Functions:
def update_dnsmasq_dns(...)  # From dns_manager.py
def check_dns_server(...)    # From dns_monitor.py
def resolve_domains_batch(...) # From dns_resolver.py (only used function)
```

**Step:** Create merged file, update imports, delete old files, commit.

---

### Task 2.2: Merge ipset_manager.py into services.py

**Rationale:** ipset_manager (365 lines) is only used by routes_service for `refresh_ipset_from_file`. The ipset operations are part of service management.

**Files:**
- Modify: `src/web_ui/core/services.py` — add ipset functions from ipset_manager
- Delete: `src/web_ui/core/ipset_manager.py`
- Modify: `src/web_ui/routes_service.py` — update imports
- Modify: `src/web_ui/core/__init__.py` — update exports

**Step:** Move ipset code into services.py, update imports, commit.

---

### Task 2.3: Merge list_catalog.py into services.py

**Rationale:** list_catalog (164 lines) provides catalog of bypass lists. It's a data utility, fits in services.

**Files:**
- Modify: `src/web_ui/core/services.py` — append catalog data + functions
- Delete: `src/web_ui/core/list_catalog.py`
- Modify: `src/web_ui/routes_service.py` — update imports
- Modify: `src/web_ui/core/__init__.py` — update exports

**Step:** Move catalog code, commit.

---

### Task 2.4: Merge dns_spoofing.py into services.py

**Rationale:** dns_spoofing (630 lines) is a single-feature module. After merging ipset and catalog, services.py is the natural home.

**Files:**
- Modify: `src/web_ui/core/services.py` — append DNSSpoofing class
- Delete: `src/web_ui/core/dns_spoofing.py`
- Modify: `src/web_ui/routes_service.py` — update all dns_spoofing imports
- Modify: `src/web_ui/core/__init__.py` — update exports

**Step:** Move DNS spoofing code, commit.

---

## Phase 3: Route File Splitting

### Task 3.1: Split routes_service.py into 4 focused route files

**Current:** `routes_service.py` = 1275 lines, 47 routes, one file

**Target:**
| File | Routes | Lines (est) |
|------|--------|-------------|
| `routes_core.py` | `/`, `/login`, `/logout`, `/status` | ~80 |
| `routes_system.py` | `/service/*`, `/stats`, `/logs` | ~350 |
| `routes_vpn.py` | `/keys/*` | ~250 |
| `routes_bypass.py` | `/bypass/*`, `/dns-spoofing/*` | ~400 |
| `routes_updates.py` | `/service/updates*`, `/install/*`, `/remove` | ~200 |

**Files:**
- Create: `src/web_ui/routes_core.py`
- Create: `src/web_ui/routes_system.py`
- Create: `src/web_ui/routes_vpn.py`
- Create: `src/web_ui/routes_bypass.py`
- Create: `src/web_ui/routes_updates.py`
- Modify: `src/web_ui/app.py` — register 5 blueprints instead of 1
- Delete: `src/web_ui/routes_service.py`

**Step:** Split file by route category, create blueprints, register in app.py, commit.

---

## Phase 4: Core Module Cleanup

### Task 4.1: Simplify core/__init__.py

**Current:** 66 lines of re-exports from submodules

**Target:** 10-15 lines — only export what routes actually import

**Files:**
- Modify: `src/web_ui/core/__init__.py`

**Step:** Remove unused exports, keep only what's imported by route files, commit.

---

### Task 4.2: Simplify utils.py (739 → ~300 lines)

**Current:** utils.py contains:
- Logging setup
- Input validation
- LRU cache
- Bypass list loader
- File readers
- Various helpers

**Target:** Keep only what's actually used:
- `setup_logging()` — keep
- `load_bypass_list()` — keep (used by routes + stats)
- `get_local_version()` — keep (used by app.py)
- Remove: unused validation helpers, duplicate file readers

**Files:**
- Modify: `src/web_ui/core/utils.py`

**Step:** Audit each function, remove unused, commit.

---

### Task 4.3: Simplify constants.py (336 → ~180 lines)

**Current:** Has duplicate `UPDATE_BACKUP_FILES` definition (already fixed), many unused constants

**Remove:**
- `MEMORY_*` constants (not used)
- `DNS_*` constants duplicated across modules
- `THREAD_POOL_WORKERS` (not used)
- `UPDATE_PROGRESS_INTERVAL`, `UPDATE_RELOAD_DELAY` (not used)
- `SCRIPT_*` constants that are only in update file list
- Second `UPDATE_BACKUP_FILES` duplicate

**Files:**
- Modify: `src/web_ui/core/constants.py`

**Step:** Remove unused constants, commit.

---

### Task 4.4: Simplify app_config.py (208 → ~60 lines)

**Current:** WebConfig is a 208-line class with property validation, defaults, file watching

**Target:** Simple dataclass or dict:
```python
class WebConfig:
    web_host: str = "0.0.0.0"
    web_port: int = 8080
    web_password: str = "changeme"
    router_ip: str = "192.168.1.1"
    unblock_dir: str = "/opt/etc/unblock"
```

**Files:**
- Modify: `src/web_ui/core/app_config.py`

**Step:** Simplify to dataclass, commit.

---

## Phase 5: Template Cleanup

### Task 5.1: Remove macros.html (127 lines, mostly unused)

**Current:** Contains `page_header`, `service_icon`, `info_card` macros. Only `page_header` used in 1-2 places.

**Target:** Inline the 1-2 usages, delete file.

**Files:**
- Modify: Any template using macros (check `{% import "macros.html" %}`)
- Delete: `src/web_ui/templates/macros.html`
- Modify: `src/web_ui/templates/base.html` — remove import

**Step:** Inline macros, delete file, commit.

---

### Task 5.2: Consolidate install/remove templates

**Current:** `install.html` (120 lines) + inline logic in routes

**Target:** Single template with conditional blocks

**Files:**
- Modify: `src/web_ui/templates/install.html` — no changes needed, just verify it works

**Step:** Review, commit if changes needed.

---

### Task 5.3: Remove dns_monitor.html template (if DNS Monitor feature is removed)

**Decision needed:** DNS Monitor checks DNS via TCP connect (not actual DNS resolution). It's a weak feature.

**If removing:**
- Delete: `src/web_ui/templates/dns_monitor.html`
- Modify: `src/web_ui/templates/service.html` — remove DNS Monitor section
- Modify: routes for `/service/dns-monitor/*`

**Step:** Remove DNS Monitor UI + routes, commit.

---

## Phase 6: Final Cleanup

### Task 6.1: Remove empty tests directory

**Files:**
- Delete: `tests/` directory (empty)

**Step:** Delete, commit.

---

### Task 6.2: Update QWEN.md documentation

**Current:** Documents non-existent files (`routes_keys.py`, `routes_bypass.py`)

**Target:** Accurate architecture documentation

**Files:**
- Modify: `QWEN.md`

**Step:** Update file list, architecture diagram, commit.

---

### Task 6.3: Update CHANGELOG.md and VERSION

**Files:**
- Modify: `VERSION` → `2.0.0`
- Modify: `CHANGELOG.md` — add 2.0.0 section with breaking changes

**Step:** Update, commit, tag.

---

## Expected Results

| Metric | Before | After | Change |
|--------|--------|-------|--------|
| Python files | 13 | 9 | -31% |
| Template files | 19 | 18 | -5% |
| Total Python lines | ~5736 | ~3000 | -48% |
| Largest file | routes_service.py (1275) | routes_bypass.py (~400) | -69% |
| core/ files | 13 | 6 | -54% |
| Dead code | ~500 lines | 0 | -100% |

---

## Risk Assessment

| Risk | Mitigation |
|------|-----------|
| Update functionality breaks | Inline code tested before removal |
| Import errors after merge | Commit per-file, verify imports |
| Template break after macro removal | Test all templates render |

---

## Execution Order

1. Dead code removal (safe, no side effects)
2. Module consolidation (medium risk, test imports)
3. Route splitting (higher risk, careful with blueprints)
4. Core cleanup (depends on 2-3)
5. Template cleanup (safe)
6. Final cleanup + docs (safe)

**Total estimated tasks:** 16
**Execution approach:** Subagent-driven, one task at a time, review after each
