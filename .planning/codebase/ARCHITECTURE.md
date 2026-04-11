# Architecture

**Analysis Date:** 2026-04-11

## Pattern Overview

**Overall:** Blueprint-based Flask MVC Web Application

This is a Flask web application providing a web interface for managing VPN bypass functionality on Keenetic routers. The architecture follows a modular blueprint pattern with separation between routing (controllers), core business logic, and templated views.

**Key Characteristics:**
- Flask Blueprint pattern for route modularization
- Manager classes for domain-specific operations
- Singleton configuration via WebConfig
- CSRF-protected session authentication

## Layers

**Routes Layer (Controllers):**
- Purpose: HTTP request handling, session management, view dispatch
- Location: `src/web_ui/routes_*.py`
- Contains: Route definitions with decorators
- Depends on: Core managers, decorators
- Used by: Flask app registration

**Core Layer (Business Logic):**
- Purpose: All domain-specific operations and system interactions
- Location: `src/web_ui/core/`
- Contains: Managers, operations, parsers, utilities
- Depends on: Router system commands (`iptables`, `dnsmasq`, `ipset`)
- Used by: Route handlers

**Configuration Layer:**
- Purpose: Application settings and .env management
- Location: `src/web_ui/core/app_config.py`, `src/web_ui/core/constants.py`
- Contains: WebConfig singleton, default constants
- Depends on: .env file
- Used by: All layers

**View Layer (Templates):**
- Purpose: HTML rendering with bootstrap styling
- Location: `src/web_ui/templates/`
- Contains: Jinja2 templates
- Depends on: Static assets
- Used by: Route handlers via `render_template()`

## Data Flow

**User Authentication Flow:**

1. User requests `/login` → `routes_core.login()`
2. Login renders `login.html` with CSRF token
3. User submits password POST → `routes_core.login()` validate
4. Success: session['authenticated'] = True → redirect to index
5. Failure: redirect back to login with flash message

**VPN Tunnel Activation Flow:**

1. User clicks "Enable VPN" → POST to routes_vpn
2. Route validates session and CSRF token
3. Calls `vpn_manager.enable_vpn()` 
4. Writes JSON config to /opt/etc/xray config
5. Adds iptables rules via `iptables_manager`
6. Restarts xray service via `service_ops.restart_service()`
7. Returns success/error to UI

**Bypass List Activation Flow:**

1. User selects bypass file → POST to routes_bypass
2. Route calls `unblock_manager.activate_bypass()`
3. Resolves domains to IPs via `dns_ops.resolve_domains_for_ipset()`
4. Adds IPs to ipset via `ipset_ops.bulk_add_to_ipset()`
5. Updates dnsmasq conf via `dnsmasq_manager`
6. Restarts dnsmasq service
7. Adds iptables rules for routing traffic

**State Management:**

- **Session State:** Flask session with authenticated flag and CSRF token
- **Configuration State:** WebConfig singleton loaded from .env
- **Runtime State:** Process status from shell commands (service status, iptables rules)

## Key Abstractions

**ServiceManager Abstraction:**
- Purpose: Manage router services (xray, dnsmasq, openvpn)
- Examples: `src/web_ui/core/service_ops.py`
- Pattern: Wrapper around `systemctl`/`service` shell commands

**VPNManager Abstraction:**
- Purpose: Manage Xray tunnel configuration and iptables
- Examples: `src/web_ui/core/vpn_manager.py`
- Pattern: JSON config generation + iptables rule management

** DnsmasqManager Abstraction:**
- Purpose: Manage dnsmasq domain-based routing configuration
- Examples: `src/web_ui/core/dnsmasq_manager.py`
- Pattern: Configuration file generation with domain mappings

**IPSetManager Abstraction:**
- Purpose: Manage ipset collections for IP-based routing
- Examples: `src/web_ui/core/ipset_ops.py`
- Pattern: Domain resolution + ipset bulk operations

## Entry Points

**Web Application Entry:**
- Location: `src/web_ui/app.py`
- Triggers: Direct execution (`python app.py`) or WSGI server
- Responsibilities: Flask app factory, blueprint registration, DNS monitor init, graceful shutdown

**Route Blueprints:**
- `routes_core.py`: Authentication (`/login`, `/logout`, `/`)
- `routes_system.py`: System commands and restart (`/system/*`)
- `routes_vpn.py`: VPN tunnel management (`/vpn/*`)
- `routes_bypass.py`: Bypass list management (`/bypass/*`)
- `routes_updates.py`: Firmware updates (`/updates/*`)

## Error Handling

**Strategy:** Graceful degradation with logging

**Patterns:**
- Service operations: Return (success, message) tuples
- Route handlers: try/except with flash messages
- Startup: Warnings logged but app continues
- Authentication: Silent redirect on CSRF failure

**Logging:**
- Uses Python `logging` module
- Configured via `core.utils.setup_logging()`
- Logs to syslog/warnings (router log aggregation)

## Cross-Cutting Concerns

**Authentication:**
- Session-based with secret_key from environment or auto-generated
- Password comparison via `secrets.compare_digest()` (timing-safe)

**CSRF Protection:**
- Token generated per session via `secrets.token_hex(32)`
- Decorator `@csrf_required` for POST routes
- Context processor injects token to all templates

**Configuration Loading:**
- Singleton WebConfig with threading lock
- Loads from .env file in same directory
- Environment variables override .env file

---

*Architecture analysis: 2026-04-11*