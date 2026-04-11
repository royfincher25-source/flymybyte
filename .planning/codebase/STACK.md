# Technology Stack

## Описание проекта

**FlyMyByte** — веб-интерфейс для управления VPN-туннелями и обходом блокировок на роутерах Keenetic.

Веб-приложение предоставляет графический интерфейс для:
- Включения/выключения VPN-туннелей (Xray/V2Ray)
- Управления списками обхода блокировок (Telegram, WhatsApp, OpenAI, TikTok и др.)
- Настройки DNS-перенаправления через dnsmasq
- Мониторинга состояния системы и управления службами
- Обновления прошивки роутера

Предназначен для работы на роутерах Keenetic с установленной системой Entware и Python 3.x.

**Analysis Date:** 2026-04-11

## Languages

**Primary:**
- Python 3.x - Main language for web UI, router management, and automation scripts

**Secondary:**
- JavaScript - Frontend interactivity (static/main.js)

## Runtime

**Environment:**
- Python 3.x on embedded Linux (Keenetic router)
- No separate runtime required (uses system Python)

**Package Manager:**
- pip (requirements.txt)
- No lockfile present

## Frameworks

**Core:**
- Flask 3.0.0 - Web application framework
- Jinja2 3.1.2 - Template engine (bundled with Flask)
- Werkzeug 3.0.0 - WSGI utilities (bundled with Flask)

**Server:**
- waitress 2.1.2 - Production WSGI server (lightweight, ~2MB)

## Key Dependencies

**HTTP/API Clients:**
- requests >=2.31.0 - HTTP library for downloading updates and API calls via `requests.get()`

**Core Application:**
- Flask 3.0.0 - Web framework with session management, CSRF protection
- waitress 2.1.2 - Production server (threads=4, connection_limit=10)

**Infrastructure:**
- subprocess - Shell command execution for router CLI (iptables, dnsmasq, service ops)
- threading - Background monitoring

## Configuration

**Environment:**
- Environment variables via `os.environ.get()`:
  - `WEB_HOST` - Server binding address (default: 0.0.0.0)
  - `WEB_PORT` - Server port (default: 8080)
  - `WEB_PASSWORD` - Authentication password
  - `ROUTER_IP` - Router management IP (default: 192.168.1.1)
  - `UNBLOCK_DIR` - Configuration directory (default: /opt/etc/unblock/)
  - `LOG_FILE` - Log file path (default: /opt/var/log/web_ui.log)
  - `SECRET_KEY` - Flask session secret (auto-generated if missing)
  - `LOG_LEVEL` - Logging level (default: INFO)

**Config File:**
- `.env` file for persistent configuration (see `.env.example`)

**Templates:**
- 17 Jinja2 templates in `src/web_ui/templates/`

## Platform Requirements

**Development:**
- Python 3.x with pip
- Flask and dependencies installed

**Production:**
- Keenetic router with embedded Linux
- Python 3.x available in system
- iptables, dnsmasq, ipset system utilities
- ~7MB total disk footprint (with waitress)

---

*Stack analysis: 2026-04-11*