#!/opt/bin/python3
"""
Unblock CLI - Python альтернатива shell скриптам.
Usage: unblock.py [update|dnsmasq|ipset|status|apply-redirects|sync-vpn]

Этот скрипт вызывается из S99unblock как гибридная альтернатива shell.

Логирование:
- Вывод в stdout/stderr для S99unblock
- Также пишется в Python лог (/opt/var/log/web_ui.log)
"""
import sys
import os

sys.path.insert(0, '/opt/etc/web_ui')

# Настроить логирование для CLI
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(levelname)s %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('/opt/var/log/unblock.log', mode='a') if os.path.exists('/opt/var/log') else logging.NullHandler()
    ]
)

from core.unblock_manager import get_unblock_manager

def main():
    print("=" * 60)
    print("unblock.py CLI started")
    print(f"Arguments: {sys.argv}")
    print("=" * 60)
    
    if len(sys.argv) < 2:
        print("Usage: unblock.py [update|dnsmasq|ipset|status]")
        sys.exit(1)
    
    cmd = sys.argv[1]
    print(f"Command: {cmd}")
    
    mgr = get_unblock_manager()
    
    if cmd == 'update':
        print(">>> Calling mgr.update_all()...")
        ok, msg = mgr.update_all(timeout=600)
        print(f"<<< Result: ok={ok}, msg={msg}")
        print(msg)
        sys.exit(0 if ok else 1)
    
    elif cmd == 'dnsmasq':
        print(">>> Calling mgr.update_dnsmasq()...")
        ok, msg = mgr.update_dnsmasq()
        print(f"<<< Result: ok={ok}, msg={msg}")
        print(msg)
        sys.exit(0 if ok else 1)
    
    elif cmd == 'ipset':
        print(">>> Calling mgr.update_ipsets()...")
        ok, msg = mgr.update_ipsets()
        print(f"<<< Result: ok={ok}, msg={msg}")
        print(msg)
        sys.exit(0 if ok else 1)
    
    elif cmd == 'status':
        print(">>> Calling mgr.get_status()...")
        import json
        status = mgr.get_status()
        print(f"<<< Result: {status}")
        print(json.dumps(status, indent=2))
        sys.exit(0)
    
    elif cmd == 'apply-redirects':
        print(">>> Calling mgr.apply_redirects()...")
        from core.iptables_manager import apply_all_redirects
        ok, msg = apply_all_redirects()
        print(f"<<< Result: ok={ok}, msg={msg}")
        print(msg)
        sys.exit(0 if ok else 1)
    
    elif cmd == 'sync-vpn':
        print(">>> Syncing VPN interfaces...")
        from core.iptables_manager import sync_vpn_interfaces, get_vpn_interfaces
        vpn_interfaces = get_vpn_interfaces()
        print(f"Found VPN interfaces: {vpn_interfaces}")
        sync_vpn_interfaces()
        print("VPN sync complete")
        sys.exit(0)
    
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)


if __name__ == '__main__':
    main()