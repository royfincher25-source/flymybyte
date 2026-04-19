#!/bin/sh
# vpn_watchdog.sh - Мониторит VPN сервисы (VLESS, Shadowsocks, Trojan) и перезапускает при падении
# Запускать в фоне: /opt/bin/vpn_watchdog.sh &
# Или добавить в S99unblock start

LOCKFILE="/tmp/vpn_watchdog.pid"
if [ -f "$LOCKFILE" ]; then
    OLD_PID=$(cat "$LOCKFILE")
    if kill -0 "$OLD_PID" 2>/dev/null; then
        echo "VPN Watchdog already running (PID $OLD_PID), exiting"
        exit 0
    else
        rm -f "$LOCKFILE"
    fi
fi
echo $$ > "$LOCKFILE"

mkdir -p /opt/var/log
LOGFILE="/opt/var/log/vpn_watchdog.log"
TAG="VPN-WD"

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') [$TAG] $1" >> "$LOGFILE"
}

log_error() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') [$TAG] ERROR: $1" >> "$LOGFILE"
}

cleanup() {
    rm -f "$LOCKFILE"
    log "=== VPN Watchdog stopped ==="
    exit 0
}
trap cleanup EXIT TERM INT

log "=== VPN Watchdog started (PID $$) ==="

CHECK_INTERVAL=30
MAX_RESTART_ATTEMPTS=3
RESTART_COOLDOWN=60

SERVICES="vless shadowsocks trojan"

get_service_info() {
    case "$1" in
        vless)
            echo "xray|/opt/etc/init.d/S24xray|/opt/etc/xray/vless.json|unblockvless,443"
            ;;
        shadowsocks)
            echo "ss-redir|/opt/etc/init.d/S22shadowsocks|/opt/etc/shadowsocks/config.json,unblocksh,8388"
            ;;
        trojan)
            echo "trojan|/opt/etc/init.d/S22trojan|/opt/etc/trojan.json|unblocktroj,10829"
            ;;
    esac
}

check_process() {
    proc_name="$1"
    for pid_dir in /proc/[0-9]*; do
        if [ -r "$pid_dir/cmdline" ] && grep -q "$proc_name" "$pid_dir/cmdline" 2>/dev/null; then
            return 0
        fi
    done
    return 1
}

is_service_disabled() {
    svc="$1"
    case "$svc" in
        vless)
            [ -f /tmp/vpn_disabled_vless ] && return 0
            ;;
        shadowsocks)
            [ -f /tmp/vpn_disabled_shadowsocks ] && return 0
            ;;
        trojan)
            [ -f /tmp/vpn_disabled_trojan ] && return 0
            ;;
    esac
    return 1
}

restart_service() {
    svc="$1"
    info=$(get_service_info "$svc")
    proc=$(echo "$info" | cut -d'|' -f1)
    init_script=$(echo "$info" | cut -d'|' -f2)
    ipset_data=$(echo "$info" | cut -d'|' -f4)
    
    if [ -f "$init_script" ]; then
        log "Restarting $svc via $init_script..."
        sh "$init_script" restart >> "$LOGFILE" 2>&1
        return $?
    else
        log_error "Init script not found: $init_script"
        return 1
    fi
}

while true; do
    for svc in $SERVICES; do
        info=$(get_service_info "$svc")
        proc=$(echo "$info" | cut -d'|' -f1)
        init_script=$(echo "$info" | cut -d'|' -f2)
        config=$(echo "$info" | cut -d'|' -f3)
        ipset_data=$(echo "$info" | cut -d'|' -f4)
        ipset_name=$(echo "$ipset_data" | cut -d',' -f1)
        port=$(echo "$ipset_data" | cut -d',' -f2)
        
        if [ ! -f "$config" ]; then
            continue
        fi
        
        # Проверяем, не отключен ли сервис пользователем
        if is_service_disabled "$svc"; then
            continue
        fi
        
        if check_process "$proc"; then
            eval "RESTART_ATTEMPTS_$svc=0"
        else
            log_error "$svc ($proc) NOT running!"
            
            eval "attempts=\$RESTART_ATTEMPTS_$svc"
            if [ -z "$attempts" ]; then
                attempts=0
            fi
            
            if [ "$attempts" -lt "$MAX_RESTART_ATTEMPTS" ]; then
                attempts=$((attempts + 1))
                eval "RESTART_ATTEMPTS_$svc=$attempts"
                
                log "Restart attempt $attempts/$MAX_RESTART_ATTEMPTS for $svc..."
                if restart_service "$svc"; then
                    log "$svc restarted successfully"
                    sleep 10
                    
                    if check_process "$proc"; then
                        log "$svc is back, iptables OK"
                        eval "RESTART_ATTEMPTS_$svc=0"
                    else
                        log_error "$svc still not running after restart"
                    fi
                else
                    log_error "Failed to restart $svc"
                fi
            else
                log_error "Max restart attempts reached for $svc, waiting cooldown..."
                sleep "$RESTART_COOLDOWN"
                eval "RESTART_ATTEMPTS_$svc=0"
            fi
        fi
    done
    
    sleep "$CHECK_INTERVAL"
done