# FlyMyByte Refactoring Roadmap

> **Version:** 1.0
> **Created:** 2026-04-11

---

## Phase 1: Services.py Split

**Status:** ✅ Completed (awaiting router testing)
**Goal:** Split services.py 1553 lines to ~800 lines

**Deliverables:**
- [x] `core/parsers/__init__.py` — Consolidate parsers
- [x] `core/parsers/vless_parser.py` — VLESS config parsing
- [x] `core/parsers/shadowsocks_parser.py` — Shadowsocks parsing
- [x] `core/parsers/trojan_parser.py` — Trojan config parsing
- [x] `core/dns_ops.py` — Keep only DNS monitoring
- [x] Reduce services.py to separate managers

---

## Phase 2: Constants Simplification

**Status:** ✅ Completed (awaiting router testing)
**Goal:** 301 lines → ~200 lines

**Deliverables:**
- [x] Move SERVICES and INIT_SCRIPTS to `app_config.py`
- [ ] FILES_TO_UPDATE → separate JSON/md file (optional)
- [x] Remove unused constants

---

## Phase 3: DNS AI Merge

**Status:** ✅ Completed
**Note:** DNSSpoofing already removed in previous commit

**Deliverables:**
- [x] DNSSpoofing from services.py → DnsmasqManager
- [x] Remove `/dns-spoofing/*` routes (already removed)
- [x] Remove `dns_spoofing.html` (already removed)
- [x] AI domains → unified bypass file (already merged)

---

## Phase 4: Routes Refactoring

**Status:** ✅ Completed (awaiting router testing)
**Goal:** Remove duplication, unify handling

**Deliverables:**
- [x] Common functions → `core/handlers.py`
- [x] Duplicate checks → decorators
- [x] Flash/redirect logic → helpers (routes_vpn.py, routes_bypass.py)

---

## Phase 5: Complete Shell Replacement

**Status:** ✅ Completed
**Goal:** 100% Python for core operations

**Deliverables:**
- [x] `100-redirect.sh` → `IptablesManager` (apply_all_redirects)
- [x] `100-unblock-vpn.sh` → `IptablesManager` (sync_vpn_interfaces)
- [x] `refresh_ipset.sh` → Python (resolve_domains_for_ipset)
- [x] All shell fallbacks tested (via S99unblock)

---

## Success Metrics

- [x] services.py removed (replaced with modules)
- [x] constants.py < 250 lines
- [x] No duplication in routes
- [x] Shell scripts kept for NDM hooks only
- [ ] RAM < 100MB, CPU < 20% (router dependent)

---

## Order of Execution

1. Phase 1 — ✅ Completed
2. Phase 2 — ✅ Completed
3. Phase 3 — ✅ Completed
4. Phase 4 — ✅ Completed
5. Phase 5 — ✅ Completed