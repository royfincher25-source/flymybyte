#!/bin/sh
# rollback.sh - Откат к рабочей версии из backup
# Запуск: /opt/bin/rollback.sh [backup_tar.gz_path]
# Без аргумента — использует последний backup из /opt/root/backup/

mkdir -p /opt/var/log
LOGFILE="/opt/var/log/rollback.log"
TAG="ROLLBACK"

BACKUP_ARCHIVE_DIR="/opt/root/backup"
EXTRACT_DIR="/tmp/rollback_extract"

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') [$TAG] $1" >> "$LOGFILE"
    echo "$1"
}

log_error() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') [$TAG] ERROR: $1" >> "$LOGFILE"
    echo "ERROR: $1"
}

log "=== Rollback started ==="

# Determine backup archive to use
if [ -n "$1" ]; then
    BACKUP_FILE="$1"
    log "Using specified backup: $BACKUP_FILE"
else
    # Find latest tar.gz in backup directory
    BACKUP_FILE=$(ls -t "$BACKUP_ARCHIVE_DIR"/update_backup_*.tar.gz 2>/dev/null | head -n1)
    if [ -z "$BACKUP_FILE" ]; then
        log_error "No backup archives found in $BACKUP_ARCHIVE_DIR"
        echo "Usage: $0 [backup_tar.gz_path]"
        echo "Example: $0 /opt/root/backup/update_backup_20260401_161354.tar.gz"
        exit 1
    fi
    log "Using latest backup: $BACKUP_FILE"
fi

if [ ! -f "$BACKUP_FILE" ]; then
    log_error "Backup file not found: $BACKUP_FILE"
    exit 1
fi

# Extract backup to temp directory
rm -rf "$EXTRACT_DIR"
mkdir -p "$EXTRACT_DIR"
log "Extracting backup to $EXTRACT_DIR..."
if tar -xzf "$BACKUP_FILE" -C "$EXTRACT_DIR" 2>&1; then
    log "  Extracted successfully"
else
    log_error "  Extraction failed"
    rm -rf "$EXTRACT_DIR"
    exit 1
fi

# 1. Stop all services
log "Step 1: Stopping services..."
/opt/etc/init.d/S99unblock stop >> "$LOGFILE" 2>&1 && log "  S99unblock stopped" || log "  S99unblock stop failed"
killall python3 2>/dev/null && log "  Python UI stopped" || log "  Python UI not running"

# 2. Clear iptables rules
log "Step 2: Clearing iptables rules..."
iptables -t nat -F PREROUTING 2>/dev/null && log "  NAT PREROUTING flushed" || log_error "  NAT PREROUTING flush failed"
iptables -t mangle -F PREROUTING 2>/dev/null && log "  Mangle PREROUTING flushed" || log_error "  Mangle PREROUTING flush failed"

# 3. Flush ipsets
log "Step 3: Flushing ipsets..."
for setname in unblocksh unblocktor unblockvless unblocktroj unblocksh6 unblocktor6 unblockvless6 unblocktroj6; do
    ipset flush "$setname" 2>/dev/null
    ipset destroy "$setname" 2>/dev/null
done
log "  All ipsets flushed and destroyed"

# 4. Restore web_ui Python files
log "Step 4: Restoring web_ui files..."
if [ -d "$EXTRACT_DIR/etc/web_ui" ]; then
    cp -rf "$EXTRACT_DIR/etc/web_ui/"* /opt/etc/web_ui/
    log "  web_ui files restored"
else
    log_error "  No web_ui backup found in archive"
fi

# 5. Restore xray config
log "Step 5: Restoring xray config..."
if [ -d "$EXTRACT_DIR/etc/xray" ]; then
    cp -rf "$EXTRACT_DIR/etc/xray/"* /opt/etc/xray/ 2>/dev/null && log "  xray files restored" || log "  No xray files to restore"
fi

# 6. Restore shadowsocks config
log "Step 6: Restoring shadowsocks config..."
if [ -f "$EXTRACT_DIR/etc/shadowsocks.json" ]; then
    cp -f "$EXTRACT_DIR/etc/shadowsocks.json" /opt/etc/shadowsocks.json 2>/dev/null && log "  shadowsocks.json restored" || log "  shadowsocks.json restore failed"
fi

# 7. Restore unblock source files
log "Step 7: Restoring unblock source files..."
if [ -d "$EXTRACT_DIR/etc/unblock" ]; then
    cp -rf "$EXTRACT_DIR/etc/unblock/"* /opt/etc/unblock/ 2>/dev/null && log "  unblock files restored" || log "  No unblock files to restore"
fi

# 8. Restore dnsmasq config
log "Step 8: Restoring dnsmasq config..."
if [ -f "$EXTRACT_DIR/etc/dnsmasq.conf" ]; then
    cp -f "$EXTRACT_DIR/etc/dnsmasq.conf" /opt/etc/dnsmasq.conf
    log "  dnsmasq.conf restored from backup"
elif [ -f "/opt/etc/dnsmasq.conf.bak" ]; then
    cp -f /opt/etc/dnsmasq.conf.bak /opt/etc/dnsmasq.conf
    log "  dnsmasq.conf restored from .bak"
fi

# 9. Remove new scripts that didn't exist in backup
log "Step 9: Removing new scripts..."
rm -f /opt/bin/unblock_ipset.sh && log "  Removed unblock_ipset.sh" || log "  unblock_ipset.sh not found"
rm -f /opt/etc/ndm/netfilter.d/100-redirect.sh && log "  Removed 100-redirect.sh" || log "  100-redirect.sh not found"
rm -f /opt/etc/init.d/S99unblock && log "  Removed S99unblock" || log "  S99unblock not found"
rm -f /opt/bin/emergency_restore.sh && log "  Removed emergency_restore.sh" || log "  emergency_restore.sh not found"
rm -f /opt/bin/dnsmasq_watchdog.sh && log "  Removed dnsmasq_watchdog.sh" || log "  dnsmasq_watchdog.sh not found"
killall dnsmasq_watchdog.sh 2>/dev/null

# 10. Restart dnsmasq
log "Step 10: Restarting dnsmasq..."
/opt/etc/init.d/S56dnsmasq restart >> "$LOGFILE" 2>&1 && log "  dnsmasq restarted" || log_error "  dnsmasq restart failed"

# 11. Test DNS
log "Step 11: Testing DNS..."
sleep 2
if nslookup google.com 8.8.8.8 >/dev/null 2>&1; then
    log "  DNS via 8.8.8.8: OK"
else
    log_error "  DNS via 8.8.8.8: FAILED"
fi

if nslookup google.com 127.0.0.1 >/dev/null 2>&1; then
    log "  DNS via 127.0.0.1: OK"
else
    log_error "  DNS via 127.0.0.1: FAILED"
fi

# 12. Start web UI
log "Step 12: Starting web UI..."
cd /opt/etc/web_ui && python3 app.py >> /opt/var/log/web_ui.log 2>&1 &
log "  Web UI started (PID: $!)"

# Cleanup
rm -rf "$EXTRACT_DIR"
log "Cleanup: removed $EXTRACT_DIR"

log "=== Rollback completed ==="
echo ""
echo "========================================="
echo "Rollback completed."
echo "Backup used: $BACKUP_FILE"
echo "Check logs: /opt/var/log/rollback.log"
echo "Web UI should be available at: http://<router_ip>:8080"
echo "========================================="
