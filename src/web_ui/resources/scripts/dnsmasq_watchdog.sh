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

# FIX #2: OPTIMIZATION - Check /proc instead of netstat to reduce CPU
check_dnsmasq() {
    for pid_dir in /proc/[0-9]*; do
        if [ -r "$pid_dir/cmdline" ] && grep -q "dnsmasq" "$pid_dir/cmdline" 2>/dev/null; then
            return 0
        fi
    done
    return 1
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
            # FIX #2: Восстанавливаем DNAT только если DNS Override включён
            if [ -f "/tmp/dns_override_enabled" ]; then
                log "dnsmasq:5353 is back, restoring DNAT rules"
                add_dns_dnat
            else
                log "dnsmasq:5353 is back but DNS Override not enabled, not restoring DNAT"
            fi
        fi
        RESTART_ATTEMPTS=0
    else
        # dnsmasq is NOT running
        log_error "dnsmasq:5353 NOT listening!"

        # FIX #2: Удаляем DNAT только если DNS Override был включён
        if [ "$DNS_REDIRECT_ACTIVE" = "true" ] && [ -f "/tmp/dns_override_enabled" ]; then
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
