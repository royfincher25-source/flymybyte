# IPset Timeout Fix - Analysis and Resolution

## Problem

Telegram (and other VLESS bypass domains) stopped working after 1-5 minutes after:
- Reboot
- "Restart Unblock" button press
- Shadowsocks toggle
- Web UI restart

## Root Causes

### 1. Flush on Service Restart
- **File:** `unblock_ipset.sh`
- **Issue:** When VPN service (xray) was restarting, script detected service as "not running" and flushed ipset
- **Fix:** Removed flush, now preserves existing entries

### 2. Flush on S99unblock Restart
- **File:** `S99unblock`
- **Issue:** `stop` action flushed all ipsets before start
- **Fix:** Removed flush from stop/restart actions

### 3. Flush on Web UI Startup
- **File:** `app.py`
- **Issue:** At startup, ipset was flushed before loading IP/CIDR from files
- **Fix:** Removed flush, preserves existing entries

### 4. IP Expiration (Timeout 300s)
- **Files:** `ipset_ops.py`, `resolve_bypass.sh`
- **Issue:** IPset was created with `timeout 300` (5 minutes). All IPs automatically expired every 5 minutes!
- **Fix:** Removed timeout, IPs persist indefinitely

## Files Modified

1. `src/web_ui/app.py` - Removed ipset flush on startup
2. `src/web_ui/core/ipset_ops.py` - Removed timeout when creating ipset
3. `src/web_ui/resources/scripts/S99unblock` - Removed flush in stop/restart
4. `src/web_ui/resources/scripts/resolve_bypass.sh` - Removed timeout
5. `src/web_ui/resources/scripts/unblock_ipset.sh` - Preserve entries on service down

## Result

- IPset now contains ~2800 IPs (vs 21 before)
- IPs persist indefinitely (no expiration)
- Telegram works continuously without interruption

## Future Considerations

### If IPset Grows Too Large
Option: Add cron job to refresh every 2-3 hours:
```bash
# Add to crontab
0 */3 * * * /opt/bin/unblock.py update
```

### Original Timeout Rationale
Was intended to prevent CDN round-robin DNS accumulation. However, with 160 domains (~2800 IPs) this is not a practical concern.

## Status: RESOLVED ✅

Version: 2.14.2
Date: 2026-04-28