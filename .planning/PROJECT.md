# FlyMyByte Project

> **Created:** 2026-04-11

---

## Project Overview

**Name:** FlyMyByte
**Type:** Web UI for Keenetic Router VPN Bypass

FlyMyByte is a Flask web application providing a user-friendly interface for managing VPN tunnel bypass on Keenetic routers. Allows users to control domain-based traffic routing around VPN tunnels.

---

## Technology Stack

**Framework:** Flask (Python)
**Language:** Python 3
**Web Server:** Built-in Flask server (WSGI)
**Target Platform:** Keenetic Router (embedded Linux)

**Key Dependencies:**
- Flask
- requests (HTTP updates)
- python-dotenv (config)
- dnsmasq (DNS routing)
- iptables (routing rules)
- ipset (IP collections)

---

## Architecture

- **Pattern:** Blueprint-based MVC
- **Configuration:** Single-file .env
- **State:** Session-based auth, singleton WebConfig
- **Core:** Manager classes for VPN, DNS, IPSet operations

---

## Key Features

1. **VPN Tunnel Management** — Enable/disable Xray tunnel
2. **Domain Bypass** — Route specific domains around VPN
3. **DNS Routing** — Domain-based traffic steering
4. **Backup & Restore** — Configuration backup system
5. **Firmware Updates** — Remote update checking

---

## Current Version

**Version:** 2.9.3
**Status:** Refactoring in progress

---

## Repository

- **Location:** Local filesystem
- **Structure:**
  - `src/web_ui/` — Main application
  - `scripts/` — Router management scripts
  - `bypass_list/` — Domain lists
  - `docs/plans/` — Refactoring plans
  - `.planning/codebase/` — Codebase analysis

---

## Development Status

- Refactoring plan phases 1-4 documented
- Phase 3 (DNS AI merge) pending discussion
- Phase 5 (100% Python) remaining
- Router testing required before Phase 3