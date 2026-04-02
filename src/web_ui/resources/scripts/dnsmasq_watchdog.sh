#!/bin/sh
# dnsmasq_watchdog.sh - Мониторит dnsmasq:5353 и убирает DNAT если он упал
# Запускать в фоне: /opt/bin/dnsmasq_watchdog.sh &
# Или добавить в S99unblock start

mkdir -p /opt/var/log
LOGFILE="/opt/var/log/dnsmasq_watchdog.log"
TAG="DNS-WD"

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') [$TAG] $1" >> "$LOGFILE"
}

log_error() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') [$TAG] ERROR: $1" >> "$LOGFILE"
}

log "=== Watchdog started ==="

DNS_REDIRECT_ACTIVE=true
CHECK_INTERVAL=15
RESTART_ATTEMPTS=0
MAX_RESTART_ATTEMPTS=3

get_local_ip() {
    ip -4 addr show br0 | awk '/inet /{print $2}' | cut -d/ -f1 | grep -E '^(192\.168\.|10\.|172\.(1[6-9]|2[0-9]|3[0-1])\.)' | head -n1
}

check_dnsmasq() {
    netstat -tlnp 2>/dev/null | grep -q ":5353 " || ss -tlnp 2>/dev/null | grep -q ":5353 "
}

remove_dns_dnat() {
    local_ip=$(get_local_ip)
    [ -z "$local_ip" ] && local_ip="192.168.1.1"

    for proto in udp tcp; do
        while iptables -t nat -C PREROUTING -p "$proto" --dport 53 -j DNAT --to "$local_ip:5353" 2>/dev/null; do
            iptables -t nat -D PREROUTING -p "$proto" --dport 53 -j DNAT --to "$local_ip:5353" 2>/dev/null
        done
    done
    DNS_REDIRECT_ACTIVE=false
    log "DNS DNAT rules removed"
}

add_dns_dnat() {
    local_ip=$(get_local_ip)
    [ -z "$local_ip" ] && local_ip="192.168.1.1"

    for proto in udp tcp; do
        if ! iptables -t nat -C PREROUTING -p "$proto" --dport 53 -j DNAT --to "$local_ip:5353" 2>/dev/null; then
            iptables -I PREROUTING -w -t nat -p "$proto" --dport 53 -j DNAT --to "$local_ip:5353" 2>/dev/null
        fi
    done
    DNS_REDIRECT_ACTIVE=true
    log "DNS DNAT rules restored"
}

while true; do
    if check_dnsmasq; then
        # dnsmasq is running
        if [ "$DNS_REDIRECT_ACTIVE" = "false" ]; then
            log "dnsmasq:5353 is back, restoring DNAT rules"
            add_dns_dnat
        fi
        RESTART_ATTEMPTS=0
    else
        # dnsmasq is NOT running
        log_error "dnsmasq:5353 NOT listening!"

        if [ "$DNS_REDIRECT_ACTIVE" = "true" ]; then
            log_error "Removing DNS DNAT to prevent internet loss"
            remove_dns_dnat
        fi

        # Try to restart dnsmasq
        if [ "$RESTART_ATTEMPTS" -lt "$MAX_RESTART_ATTEMPTS" ]; then
            RESTART_ATTEMPTS=$((RESTART_ATTEMPTS + 1))
            log "Restart attempt $RESTART_ATTEMPTS/$MAX_RESTART_ATTEMPTS..."
            /opt/etc/init.d/S56dnsmasq restart >> "$LOGFILE" 2>&1
            sleep 5
        else
            log_error "Max restart attempts reached, will retry after cooldown"
            sleep 60
            RESTART_ATTEMPTS=0
        fi
        continue
    fi

    sleep "$CHECK_INTERVAL"
done
