#!/bin/sh
# refresh_ipset.sh - Автоматическое обновление ipset для обхода блокировок
# Вызывается при добавлении доменов и периодически через cron/watchdog
# Резолвит домены через внешний DNS (8.8.8.8), а не через stubby

LOGFILE="/opt/var/log/refresh_ipset.log"
mkdir -p /opt/var/log

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') [refresh_ipset] $1" >> "$LOGFILE"
}

log "=== Starting ipset refresh ==="

# Определяем файл и ipset из аргументов или по умолчанию
# Validate ipset name (alphanumeric + underscore only)
case "${1:-}" in
    ''|*[!a-zA-Z0-9_]*)
        [ -n "$1" ] && log "WARNING: Invalid ipset name: $1, using default"
        IPSET_NAME="unblockvless"
        ;;
    *) IPSET_NAME="$1" ;;
esac
BYPASS_FILE="${2:-/opt/etc/unblock/vless.txt}"

# Если передан только ipset (без файла)
if [ -n "$IPSET_NAME" ] && [ -z "$2" ]; then
    # Определяем файл по имени ipset
    case "$IPSET_NAME" in
        unblockvless) BYPASS_FILE="/opt/etc/unblock/vless.txt" ;;
        unblocksh) BYPASS_FILE="/opt/etc/unblock/shadowsocks.txt" ;;
        unblocktroj) BYPASS_FILE="/opt/etc/unblock/trojan.txt" ;;
        unblock*)
            VPN_NAME=$(echo "$1" | sed 's/unblock//')
            BYPASS_FILE="/opt/etc/unblock/${VPN_NAME}.txt"
            ;;
    esac
fi

if [ ! -f "$BYPASS_FILE" ]; then
    log "File $BYPASS_FILE not found, skipping"
    exit 0
fi

# Считаем домены (исключая комментарии и пустые строки)
DOMAIN_COUNT=$(grep -v '^#' "$BYPASS_FILE" 2>/dev/null | grep -v '^$' | wc -l | awk '{print $1}')
log "Processing $DOMAIN_COUNT domains from $BYPASS_FILE -> ipset $IPSET_NAME"

# Создаём ipset если не существует
ipset create $IPSET_NAME hash:net 2>/dev/null

# Очищаем старые IP
ipset flush $IPSET_NAME 2>/dev/null

# Резолвим каждый домен через 8.8.8.8 (НЕ через stubby!)
RESOLVED=0
FAILED=0
while IFS= read -r domain; do
    # Пропускаем комментарии и пустые строки
    [ -z "$domain" ] && continue
    echo "$domain" | grep -q "^#" && continue

    # Пропускаем IP-адреса (они уже в файле для прямого добавления)
    if echo "$domain" | grep -qE '^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}'; then
        ipset add $IPSET_NAME $domain 2>/dev/null
        RESOLVED=$((RESOLVED + 1))
        log "  $domain (direct IP)"
        continue
    fi

    # Убираем wildcard
    domain=$(echo "$domain" | sed 's/^\*\.//')

    # Резолвим через внешний DNS
    IPs=$(nslookup "$domain" 8.8.8.8 2>/dev/null | grep "^Address" | grep -v "::" | grep -v "8.8.8.8" | awk '{print $NF}')

    if [ -n "$IPs" ]; then
        for ip in $IPs; do
            ipset add $IPSET_NAME $ip 2>/dev/null
            RESOLVED=$((RESOLVED + 1))
        done
        log "  $domain -> $IPs"
    else
        FAILED=$((FAILED + 1))
        log "  $domain -> FAILED"
    fi
done < "$BYPASS_FILE"

log "Done: $RESOLVED IPs added, $FAILED domains failed"
ENTRIES=$(ipset list $IPSET_NAME 2>/dev/null | grep -c '^[0-9]')
ENTRIES=${ENTRIES:-0}
log "ipset $IPSET_NAME now has $ENTRIES entries"
