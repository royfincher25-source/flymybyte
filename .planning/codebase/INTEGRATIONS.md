# External Integrations

**Analysis Date:** 2026-04-11

## APIs & External Services

**Update Servers:**
- Remote version check and file downloads via HTTP
- Client: `requests` library
- Usage: `requests.get(url, timeout=N)` in `core/services.py` and `routes_updates.py`
- Endpoints: Dynamic URLs from version/config data

**No External Data APIs:**
- No cloud databases
- No external authentication providers (local password-based auth)
- No third-party monitoring services

## Data Storage

**Databases:**
- None (flat-file configuration)

**File Storage:**
- Local filesystem only
- Configuration directory: `/opt/etc/unblock/`
- Backup directory: `/opt/etc/unblock/backup/`
- Log files: `/opt/var/log/web_ui.log`

**Caching:**
- In-memory caching via `core.utils.Cache` class
- No external caching services

## Authentication & Identity

**Auth Provider:**
- Built-in password authentication
- Implementation: `WEB_PASSWORD` from environment or config file
- Session management via Flask sessions with CSRF tokens

## Monitoring & Observability

**Error Tracking:**
- None (no external error tracking)

**Logs:**
- File-based logging to configurable path
- Log file: `/opt/var/log/web_ui.log` (configurable via `LOG_FILE` env var)
- Uses Python `logging` module

## CI/CD & Deployment

**Hosting:**
- Keenetic router (embedded Linux)
- Custom deployment via shell scripts in `resources/scripts/`

**CI Pipeline:**
- None (manual deployment via manifest)

## Environment Configuration

**Required env vars:**
- `WEB_PASSWORD` - Admin password (critical)
- `ROUTER_IP` - Router management IP
- `UNBLOCK_DIR` - Configuration directory
- `WEB_PORT` - Server port
- `LOG_FILE` - Log file path

**Optional env vars:**
- `WEB_HOST` - Bind address
- `SECRET_KEY` - Flask session key
- `LOG_LEVEL` - Logging threshold

**Secrets location:**
- Plain text in `.env` file or environment
- No encryption

## Webhooks & Callbacks

**Incoming:**
- None (no webhooks received)

**Outgoing:**
- None (no outbound webhooks)

---

*Integration audit: 2026-04-11*