#!/bin/sh
# emergency_restore.sh - Экстренное восстановление интернета
# Использовать при потере DNS/интернета после обновления
# Запуск: /opt/bin/emergency_restore.sh

mkdir -p /opt/var/log
LOGFILE="/opt/var/log/emergency_restore.log"
TAG="EMERGENCY"

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') [$TAG] $1" >> "$LOGFILE"
    echo "$1"
}

log_error() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') [$TAG] ERROR: $1" >> "$LOGFILE"
    echo "ERROR: $1"
}

log "=== Emergency restore started ==="

# 1. Убираем DNAT правила DNS redirect
log "Step 1: Removing DNS DNAT rules..."
for proto in udp tcp; do
    while iptables -t nat -C PREROUTING -p "$proto" --dport 53 -j DNAT --to "$(ip -4 addr show br0 | awk '/inet /{print $2}' | cut -d/ -f1 | head -n1):5353" 2>/dev/null; do
        iptables -t nat -D PREROUTING -p "$proto" --dport 53 -j DNAT --to "$(ip -4 addr show br0 | awk '/inet /{print $2}' | cut -d/ -f1 | head -n1):5353" 2>/dev/null
        log "  Removed DNS DNAT rule ($proto)"
    done
done

# 2. Чистим все правила PREROUTING в nat
log "Step 2: Flushing NAT PREROUTING chain..."
iptables -t nat -F PREROUTING 2>/dev/null && log "  NAT PREROUTING flushed" || log_error "  Failed to flush NAT PREROUTING"

# 3. Чистим правила PREROUTING в mangle
log "Step 3: Flushing mangle PREROUTING chain..."
iptables -t mangle -F PREROUTING 2>/dev/null && log "  Mangle PREROUTING flushed" || log_error "  Failed to flush mangle PREROUTING"

# 4. Очищаем ipset
log "Step 4: Flushing ipsets..."
for setname in unblocksh unblockvless unblocktroj unblocksh6 unblockvless6 unblocktroj6; do
    ipset flush "$setname" 2>/dev/null && log "  Flushed $setname" || log "  $setname not found"
done

# 5. Восстанавливаем dnsmasq на стандартном порту
log "Step 5: Restoring dnsmasq..."
if [ -f "/opt/etc/dnsmasq.conf" ]; then
    # Проверяем, не слушает ли dnsmasq порт 5353
    if grep -q "port=5353" /opt/etc/dnsmasq.conf 2>/dev/null; then
        log "  dnsmasq.conf has port=5353, commenting out..."
        sed -i 's/^port=5353/#port=5353/' /opt/etc/dnsmasq.conf
    fi
fi

# 6. Рестартуем dnsmasq
log "Step 6: Restarting dnsmasq..."
if /opt/etc/init.d/S56dnsmasq restart >> "$LOGFILE" 2>&1; then
    log "  dnsmasq restarted"
else
    log_error "  dnsmasq restart failed, trying kill + start..."
    killall dnsmasq 2>/dev/null
    sleep 1
    /opt/etc/init.d/S56dnsmasq start >> "$LOGFILE" 2>&1 && log "  dnsmasq started" || log_error "  dnsmasq start failed"
fi

# 7. Проверяем DNS
log "Step 7: Testing DNS..."
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

# 8. Проверяем интернет
log "Step 8: Testing internet connectivity..."
if curl -s --max-time 5 http://google.com >/dev/null 2>&1; then
    log "  Internet: OK"
else
    log_error "  Internet: FAILED"
fi

log "=== Emergency restore completed ==="
echo ""
echo "========================================="
echo "Emergency restore completed."
echo "Check logs: /opt/var/log/emergency_restore.log"
echo "If internet still not working, try rebooting router."
echo "========================================="
