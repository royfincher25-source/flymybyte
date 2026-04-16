---
phase: code-review
reviewed: 2026-04-16T00:00:00Z
depth: standard
files_reviewed: 11
files_reviewed_list:
  - src/web_ui/routes_bypass.py
  - src/web_ui/core/services.py
  - src/web_ui/core/__init__.py
  - src/web_ui/core/constants.py
  - src/web_ui/core/dnsmasq_manager.py
  - src/web_ui/templates/stats.html
  - src/web_ui/templates/service.html
  - src/web_ui/resources/config/dnsmasq.conf
  - src/web_ui/scripts/install_web.sh
  - MANIFEST.json
  - README.md
findings:
  critical: 1
  warning: 5
  info: 0
  total: 6
status: issues_found
---

# Phase: Code Review Report

**Reviewed:** 2026-04-16
**Depth:** standard
**Files Reviewed:** 11
**Status:** issues_found

## Summary

DNS Spoofing feature removal was partially successful. Core Python code in `routes_bypass.py`, `services.py`, and `core/__init__.py` is clean. However, there are critical issues: `dnsmasq_manager.py` references a non-existent method causing runtime errors, and multiple installer/backup scripts still reference deleted AI files.

## Critical Issues

### CR-01: Broken get_status() method in dnsmasq_manager.py

**File:** `src/web_ui/core/dnsmasq_manager.py:384-385`
**Issue:** The `get_status()` method calls `self.load_ai_domains()` which does not exist. This will cause AttributeError at runtime when status is queried.

**Fix:**
```python
# Remove lines 384-385:
ai_domains = self.load_ai_domains()
status['ai_domains'] = len(ai_domains)

# Or replace with:
status['ai_domains'] = 0  # AI domains removed
```

## Warnings

### WR-01: MANIFEST.json references deleted files

**File:** `MANIFEST.json:269-278`
**Issue:** Manifest still includes deleted files:
- `web_ui/resources/lists/unblock-ai-domains.txt`
- `web_ui/resources/config/unblock-ai.dnsmasq.template`

**Fix:** Remove these entries from MANIFEST.json.

### WR-02: install_web.sh references deleted files

**File:** `src/web_ui/scripts/install_web.sh:200-209`
**Issue:** Script attempts to download deleted files:
- `lists/unblock-ai-domains.txt`
- `config/unblock-ai.dnsmasq.template`

**Fix:** Remove the curl commands for these files (lines 200-209).

### WR-03: Orphaned constants in constants.py

**File:** `src/web_ui/core/constants.py:318-320`
**Issue:** Constants `VPN_DNS_HOST` and `VPN_DNS_PORT` appear orphaned after DNS spoofing removal. They were used by DNSSpoofing class.

**Fix:** Review if these are still needed. If not, remove:
```python
# Remove lines 318-320:
VPN_DNS_HOST = '127.0.0.1'
VPN_DNS_PORT = 40500
```

### WR-04: unblock_manager.py references deleted ai config

**File:** `src/web_ui/core/unblock_manager.py:177`
**Issue:** References `/opt/etc/unblock-ai.dnsmasq` which is deleted.

**Fix:** Remove references to ai_conf or update comment to reflect AI removal.

### WR-05: Multiple scripts reference unblock-ai.dnsmasq

**File:** Multiple files
**Issue:** These files reference the deleted `/opt/etc/unblock-ai.dnsmasq`:
- `src/web_ui/core/emergency_restore.py:186`
- `src/web_ui/core/backup_manager.py:204`
- `src/web_ui/scripts/script.sh:117, 269, 272-273`
- `src/web_ui/resources/scripts/unblock_dnsmasq.sh:32-33, 135-174`

**Fix:** Clean up these references to remove references to deleted AI config.

## Info

No info-level issues found.

---

_Reviewed: 2026-04-16_
_Reviewer: gsd-code-reviewer_
_Depth: standard_