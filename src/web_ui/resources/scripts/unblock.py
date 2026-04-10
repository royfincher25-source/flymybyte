#!/opt/bin/python3
"""
Unblock CLI - Python альтернатива shell скриптам.
Usage: unblock.py [update|dnsmasq|ipset|status]

Этот скрипт вызывается из S99unblock как гибридная альтернатива shell.
"""
import sys
import os

sys.path.insert(0, '/opt/etc/web_ui')

from core.unblock_manager import get_unblock_manager


def main():
    if len(sys.argv) < 2:
        print("Usage: unblock.py [update|dnsmasq|ipset|status]")
        sys.exit(1)
    
    cmd = sys.argv[1]
    mgr = get_unblock_manager()
    
    if cmd == 'update':
        ok, msg = mgr.update_all(timeout=600)
        print(msg)
        sys.exit(0 if ok else 1)
    
    elif cmd == 'dnsmasq':
        ok, msg = mgr.update_dnsmasq()
        print(msg)
        sys.exit(0 if ok else 1)
    
    elif cmd == 'ipset':
        ok, msg = mgr.update_ipsets()
        print(msg)
        sys.exit(0 if ok else 1)
    
    elif cmd == 'status':
        import json
        print(json.dumps(mgr.get_status(), indent=2))
        sys.exit(0)
    
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)


if __name__ == '__main__':
    main()