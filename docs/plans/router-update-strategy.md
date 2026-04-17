# Router Update Strategy

## Files to Update

### New Files (create)
- `core/bypass_utils.py` - NEW
- `core/system_utils.py` - NEW

### Modified Files
- `core/__init__.py` - exports updated
- `core/utils.py` - delegates to new modules

### Key Bugfixes
- `core/dnsmasq_manager.py` - restore ipset= directives
- `core/dns_ops.py` - flush ipset before resolve
- `core/iptables_manager.py` - add_dns_redirect on startup

---

## Update Order (Critical!)

**Phase 1: Create new files FIRST**

```bash
# Create new modules first
curl -o /opt/etc/web_ui/core/bypass_utils.py "https://raw.githubusercontent.com/royfincher25-source/flymybyte/refactoring/src/web_ui/core/bypass_utils.py"
curl -o /opt/etc/web_ui/core/system_utils.py "https://raw.githubusercontent.com/royfincher25-source/flymybyte/refactoring/src/web_ui/core/system_utils.py"
chmod 644 /opt/etc/web_ui/core/bypass_utils.py
chmod 644 /opt/etc/web_ui/core/system_utils.py
```

**Phase 2: Update core files**

```bash
# Update __init__.py (exports new modules)
curl -o /opt/etc/web_ui/core/__init__.py "https://raw.githubusercontent.com/royfincher25-source/flymybyte/refactoring/src/web_ui/core/__init__.py"

# Update utils.py (delegates to new modules)
curl -o /opt/etc/web_ui/core/utils.py "https://raw.githubusercontent.com/royfincher25-source/flymybyte/refactoring/src/web_ui/core/utils.py"

# Update dnsmasq_manager.py (ipset= fix)
curl -o /opt/etc/web_ui/core/dnsmasq_manager.py "https://raw.githubusercontent.com/royfincher25-source/flymybyte/refactoring/src/web_ui/core/dnsmasq_manager.py"

# Update dns_ops.py (flush ipset fix)
curl -o /opt/etc/web_ui/core/dns_ops.py "https://raw.githubusercontent.com/royfincher25-source/flymybyte/refactoring/src/web_ui/core/dns_ops.py"

# Update iptables_manager.py
curl -o /opt/etc/web_ui/core/iptables_manager.py "https://raw.githubusercontent.com/royfincher25-source/flymybyte/refactoring/src/web_ui/core/iptables_manager.py"
```

**Phase 3: Restart Web UI**

```bash
# Restart web UI to apply changes
killall python3
cd /opt/etc/web_ui && python3 app.py &
```

---

## Verification

```bash
# Test imports
python3 -c "from core import bypass_utils, system_utils; print('OK')"

# Check web UI
curl -s http://127.0.0.1:80/ | head -5
```

---

## Rollback (if issues)

```bash
# Restore from git
cd /opt/etc/web_ui
git checkout -- core/
```