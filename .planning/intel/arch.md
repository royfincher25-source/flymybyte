---
updated_at: "2026-04-12T18:14:50Z"
---

## Architecture Overview

Flask-based web interface for Keenetic router bypass management. Uses blueprint-based modular routing with 5 functional areas (core, vpn, bypass, system, updates). Targets Python 3.8+ runtime on Entware-equipped Keenetic routers.

## Key Components

| Component | Path | Responsibility |
|-----------|------|---------------|
| Flask App Factory | src/web_ui/app.py | Application setup, blueprint registration, waitress server |
| Core Routes | src/web_ui/routes_core.py | Authentication, login/logout, index |
| VPN Routes | src/web_ui/routes_vpn.py | VPN key management, service toggle |
| Bypass Routes | src/web_ui/routes_bypass.py | Bypass lists, DNS spoofing |
| System Routes | src/web_ui/routes_system.py | Service management, backup, DNS override |
| Update Routes | src/web_ui/routes_updates.py | Updates, install, remove |
| VPN Managers | src/web_ui/core/vpn_manager.py, key_manager.py | Service lifecycle, config generation |
| DNS Ops | src/web_ui/core/dns_ops.py | DNS monitoring, domain resolution |
| Dnsmasq Manager | src/web_ui/core/dnsmasq_manager.py | dnsmasq config generation |
| ipset Operations | src/web_ui/core/ipset_ops.py | Bulk ipset management |
| Key Parsers | src/web_ui/core/parsers.py | VLESS, Shadowsocks, Trojan key parsing |

## Data Flow

HTTP Request → Blueprint Route → Service Manager → Init Script / dnsmasq / iptables
1. User authentication via session-based login
2. Route handler validates request, CSRF check
3. Service manager executes VPN/service operations
4. dnsmasq/iptables updates applied
5. Response rendered via Jinja2 templates

## Conventions

- Blueprint prefix: route URL namespace (vpn., bypass., system., updates., core.)
- Service configs: /opt/etc/{service}.json
- Init scripts: /opt/etc/init.d/S{XX}{service}
- Bypass lists: /opt/etc/unblock/{list}.txt
- DNS configs: /opt/etc/unblock*.dnsmasq
- Async operations: background scripts with pid tracking