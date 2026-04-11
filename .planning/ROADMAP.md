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

**Status:** 🔶 Pending Discussion
**Discussion Required Before Proceeding

**Deliverables:**
- [ ] DNSSpoofing from services.py → DnsmasqManager
- [ ] Remove `/dns-spoofing/*` routes
- [ ] Remove `dns_spoofing.html`
- [ ] AI domains → unified bypass file
- [ ] Full DNS routing testing required

**Blocker:** Requires thorough testing on router to avoid breaking working AI bypass

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

**Status:** Not Started
**Goal:** 100% Python for core operations

**Deliverables:**
- [ ] `100-redirect.sh` → `IptablesManager`
- [ ] `100-unblock-vpn.sh` → `IptablesManager`
- [ ] `refresh_ipset.sh` → services.py function
- [ ] All shell fallbacks tested

---

## Success Metrics

- [ ] services.py < 1000 lines
- [ ] constants.py < 250 lines
- [ ] No duplication in routes
- [ ] All shell fallbacks tested
- [ ] RAM < 100MB, CPU < 20%

---

## Order of Execution

1. Phase 1 — ✅ Completed (awaiting test)
2. Phase 2 — ✅ Completed (awaiting test)
3. Phase 3 — 🔶 Awaiting router testing (risk)
4. Phase 4 — ✅ Completed (awaiting test)
5. Phase 5 — Not Started