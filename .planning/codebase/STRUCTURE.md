# Codebase Structure

**Analysis Date:** 2026-04-11

## Directory Layout

```
FlyMyByte/
├── src/web_ui/              # Main application directory
│   ├── core/                # Business logic and managers
│   ├── routes_*.py         # Route handlers (blueprints)
│   ├── templates/          # Jinja2 HTML templates
│   ├── static/             # CSS, JS, fonts, icons
│   ├── scripts/           # Installation scripts
│   ├── app.py              # Flask application factory
│   ├── requirements.txt    # Python dependencies
│   └── .env               # Configuration (secret)
├── scripts/                 # Router management scripts
├── bypass_list/            # Domain bypass lists
├── tests/                  # Unit tests
└── docs/                  # Documentation and plans
```

## Directory Purposes

**src/web_ui/core/:**
- Purpose: Business logic, system interactions, managers
- Contains: Python modules for VPN, bypass, DNS, services, configuration
- Key files: `vpn_manager.py`, `dnsmasq_manager.py`, `ipset_ops.py`, `app_config.py`, `services.py`

**src/web_ui/routes_\*.py:**
- Purpose: HTTP route handlers organized by feature
- Contains: 5 blueprint files
- Key files: `routes_core.py`, `routes_vpn.py`, `routes_bypass.py`, `routes_system.py`, `routes_updates.py`

**src/web_ui/templates/:**
- Purpose: HTML pages for web interface
- Contains: Jinja2 templates with bootstrap styling
- Key files: `base.html`, `index.html`, `login.html`, `bypass*.html`

**src/web_ui/static/:**
- Purpose: Client-side assets
- Contains: CSS, JavaScript, icons, fonts
- Key files: `style.css`, `main.js`, icons/svg/*.svg

**scripts/:**
- Purpose: Router management shell scripts
- Contains: Diagnostic and maintenance scripts
- Key files: `check_routing.sh`, `apply_routing.sh`, `restart_web_ui.sh`

**bypass_list/:**
- Purpose: Domain lists for bypass functionality
- Contains: Text files with domains per service
- Key files: `telegram.txt`, `whatsapp.txt`, `openai.txt`, `tiktok.txt`

## Key File Locations

**Entry Points:**
- `src/web_ui/app.py`: Flask app factory, main execution
- `src/web_ui/__init__.py`: Package marker

**Configuration:**
- `src/web_ui/core/constants.py`: Default constants
- `src/web_ui/core/app_config.py`: WebConfig singleton class
- `src/web_ui/requirements.txt`: Python dependencies

**Route Blueprints (in src/web_ui/):**
- `routes_core.py`: Auth routes - login, logout, index
- `routes_vpn.py`: VPN control - enable/disable/status
- `routes_bypass.py`: Bypass list management
- `routes_system.py`: Router commands, restart
- `routes_updates.py`: Firmware updates

**Core Managers (in src/web_ui/core/):**
- `vpn_manager.py`: Xray tunnel management
- `dnsmasq_manager.py`: DNS routing config
- `ipset_ops.py`: IP set operations
- `service_ops.py`: Service control
- `service_locator.py`: Service discovery
- `backup_manager.py`: Configuration backup
- `unblock_manager.py`: Bypass activation

**Utilities (in src/web_ui/core/):**
- `utils.py`: Cache, logging setup
- `decorators.py`: @login_required, @csrf_required
- `parsers.py`: Key configuration parsing
- `exceptions.py`: Custom exceptions

## Naming Conventions

**Files:**
- snake_case.py: All Python modules
- routes_*.py: Route blueprints
- core/*.py: Core modules

**Directories:**
- snake_case: All directories
- core/: Business logic
- scripts/: Shell scripts

**Functions:**
- snake_case: All functions
- Verb_noun: `write_json_config`, `restart_service`
- get_X / set_X: Getters/setters

**Classes:**
- PascalCase: All classes
- Manager suffix: `VPNManager`, `DnsmasqManager`
- Operation suffix: `DNSMonitor`

**Templates:**
- kebab-case.html: HTML templates

## Where to Add New Code

**New Feature Route:**
- Create new `src/web_ui/routes_<feature>.py`
- Define Blueprint with routes
- Register in `src/web_ui/app.py`: `app.register_blueprint(<feature>_bp)`

**New Core Manager:**
- Add to `src/web_ui/core/`
- Follow manager pattern: stateless operations + config generation

**New Template:**
- Add to `src/web_ui/templates/`
- Extend `base.html` for common layout
- Add static styles to `static/style.css`

**New Bypass List:**
- Add to `bypass_list/`
- Format: one domain per line
- Files committed to git (public)

**New Router Script:**
- Add to `scripts/`
- Follow shell script conventions

## Special Directories

**tests/:**
- Purpose: Unit tests
- Generated: No
- Committed: Yes, currently minimal

**src/scripts/:**
- Purpose: Installation helper scripts
- Generated: No
- Committed: Yes

**docs/:**
- Purpose: Plans and documentation
- Generated: No
- Committed: Yes

**src/web_ui/static/icons/:**
- Purpose: SVG icons and generation scripts
- Generated: Yes (from generate-icons.js)
- Committed: Pre-rendered icons in repo

**.git/:**
- Purpose: Git repository metadata
- Generated: Yes (by git)
- Committed: No

---

*Structure analysis: 2026-04-11*