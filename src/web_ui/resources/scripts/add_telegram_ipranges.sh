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

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

log "=== Добавление IP-диапазонов Telegram в ipset $IPSET_NAME ==="

# Проверяем существует ли ipset
if ! ipset list -n | grep -q "^${IPSET_NAME}$"; then
    log "Создание ipset $IPSET_NAME..."
    ipset create "$IPSET_NAME" hash:net
    if [ $? -eq 0 ]; then
        log "✅ ipset $IPSET_NAME создан"
    else
        log "❌ Ошибка создания ipset $IPSET_NAME"
        exit 1
    fi
fi

# Список IP-диапазонов Telegram
# Источник: https://core.telegram.org/resources/cidr.txt
IP_RANGES="149.154.160.0/20
149.154.164.0/22
149.154.168.0/21
91.108.4.0/22
95.161.64.0/19
5.255.255.0/24
185.76.151.0/24"

ADDED=0
SKIPPED=0
ERRORS=0

for cidr in $IP_RANGES; do
    # Проверяем, нет ли уже этого диапазона в ipset
    if ipset test "$IPSET_NAME" "$cidr" 2>/dev/null; then
        log "  ⏭️  $cidr уже есть в ipset"
        SKIPPED=$((SKIPPED + 1))
    else
        # Добавляем диапазон
        ipset add "$IPSET_NAME" "$cidr"
        if [ $? -eq 0 ]; then
            log "  ✅ Добавлен $cidr"
            ADDED=$((ADDED + 1))
        else
            log "  ❌ Ошибка добавления $cidr"
            ERRORS=$((ERRORS + 1))
        fi
    fi
done

log ""
log "=== Результат ==="
log "  Добавлено: $ADDED"
log "  Уже было:  $SKIPPED"
log "  Ошибок:    $ERRORS"
log ""
log "Всего записей в ipset $IPSET_NAME: $(ipset list "$IPSET_NAME" 2>/dev/null | grep -c '^[0-9]')"
log "=== Готово ==="
