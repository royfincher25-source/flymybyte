#!/bin/sh
# ========================================
# Добавление IP-диапазонов Telegram в ipset
# ========================================
# Этот скрипт автоматически добавляет все известные
# IP-диапазоны Telegram в ipset unblockvless
#
# Использование:
# sh /opt/etc/web_ui/resources/scripts/add_telegram_ipranges.sh

IPSET_NAME="${1:-unblockvless}"
IPSET_NAME_V6="${IPSET_NAME}6"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

log "=== Добавление IP-диапазонов Telegram в ipset ==="

# Создаём ipset для IPv4
if ! ipset list -n | grep -q "^${IPSET_NAME}$"; then
    log "Создание ipset $IPSET_NAME (IPv4)..."
    ipset create "$IPSET_NAME" hash:net
    if [ $? -eq 0 ]; then
        log "✅ ipset $IPSET_NAME создан"
    else
        log "❌ Ошибка создания ipset $IPSET_NAME"
        exit 1
    fi
else
    log "ipset $IPSET_NAME уже существует"
fi

# Создаём ipset для IPv6 (family inet6)
if ! ipset list -n | grep -q "^${IPSET_NAME_V6}$"; then
    log "Создание ipset $IPSET_NAME_V6 (IPv6)..."
    ipset create "$IPSET_NAME_V6" hash:net family inet6
    if [ $? -eq 0 ]; then
        log "✅ ipset $IPSET_NAME_V6 создан"
    else
        log "❌ Ошибка создания ipset $IPSET_NAME_V6"
    fi
else
    log "ipset $IPSET_NAME_V6 уже существует"
fi

# Список IP-диапазонов Telegram (IPv4)
# Источник: https://core.telegram.org/resources/cidr.txt
IP_RANGES_V4="149.154.160.0/20
149.154.164.0/22
149.154.168.0/21
91.108.4.0/22
95.161.64.0/19
5.255.255.0/24
185.76.151.0/24
149.154.64.0/21
149.154.80.0/21
149.154.88.0/21
149.154.96.0/21
149.154.104.0/21"

# Список IP-диапазонов Telegram (IPv6)
# Источник: https://core.telegram.org/resources/cidr.txt
IP_RANGES_V6="2001:67c:4e8::/32
2001:b40:1::/36
2001:df4:3800::/48"

ADDED_V4=0
SKIPPED_V4=0
ERRORS_V4=0

ADDED_V6=0
SKIPPED_V6=0
ERRORS_V6=0

log "=== Добавление IPv4 диапазонов ==="
for cidr in $IP_RANGES_V4; do
    if ipset test "$IPSET_NAME" "$cidr" 2>/dev/null; then
        log "  ⏭️  $cidr уже есть"
        SKIPPED_V4=$((SKIPPED_V4 + 1))
    else
        ipset add "$IPSET_NAME" "$cidr"
        if [ $? -eq 0 ]; then
            log "  ✅ $cidr"
            ADDED_V4=$((ADDED_V4 + 1))
        else
            log "  ❌ $cidr"
            ERRORS_V4=$((ERRORS_V4 + 1))
        fi
    fi
done

log "=== Добавление IPv6 диапазонов ==="
for cidr in $IP_RANGES_V6; do
    if ipset test "$IPSET_NAME_V6" "$cidr" 2>/dev/null; then
        log "  ⏭️  $cidr уже есть"
        SKIPPED_V6=$((SKIPPED_V6 + 1))
    else
        ipset add "$IPSET_NAME_V6" "$cidr"
        if [ $? -eq 0 ]; then
            log "  ✅ $cidr"
            ADDED_V6=$((ADDED_V6 + 1))
        else
            log "  ❌ $cidr"
            ERRORS_V6=$((ERRORS_V6 + 1))
        fi
    fi
done

log ""
log "=== Результат ==="
log "  IPv4: добавлено $ADDED_V4, было $SKIPPED_V4, ошибок $ERRORS_V4"
log "  IPv6: добавлено $ADDED_V6, было $SKIPPED_V6, ошибок $ERRORS_V6"
log "=== Готово ==="
