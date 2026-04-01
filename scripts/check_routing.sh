#!/bin/sh
# Проверка маршрутизации трафика
# Запуск: ssh root@192.168.1.1 -p 222 "sh /opt/root/check_routing.sh"

echo "============================================================"
echo "ПРОВЕРКА МАРШРУТИЗАЦИИ ТРАФИКА"
echo "============================================================"
echo ""

# 1. Проверка ipset
echo "[1/5] Проверка ipset..."
if command -v ipset > /dev/null; then
    echo "✅ ipset доступен"
    echo "   Существующие ipset:"
    ipset list -n 2>/dev/null | while read name; do
        count=$(ipset list "$name" 2>/dev/null | grep -c "^[0-9]" || echo 0)
        echo "   → $name: $count записей"
    done
    
    # Проверка конкретных ipset для обхода
    for ipset in unblocksh unblocktor unblockvless unblocktroj unblock unblock_domains; do
        if ipset list "$ipset" -n 2>/dev/null | grep -q "^${ipset}$"; then
            count=$(ipset list "$ipset" 2>/dev/null | grep -c "^[0-9]" || echo 0)
            echo "   ✅ $ipset: $count записей"
        else
            echo "   ❌ $ipset: не создан"
        fi
    done
else
    echo "❌ ipset не доступен (требуется модуль ядра)"
fi
echo ""

# 2. Проверка iptables (NAT)
echo "[2/5] Проверка iptables (NAT)..."
if command -v iptables > /dev/null; then
    echo "✅ iptables доступен"
    echo "   Правила NAT для Shadowsocks (порт 1082):"
    iptables-save 2>/dev/null | grep -E "1082|shadowsocks|ss-redir" | head -5 || echo "   ❌ Правила не найдены"
    
    echo "   Правила REDIRECT:"
    iptables-save 2>/dev/null | grep "REDIRECT" | head -5 || echo "   ❌ Правила не найдены"
else
    echo "❌ iptables не доступен"
fi
echo ""

# 3. Проверка маршрутизации (ip rule)
echo "[3/5] Проверка маршрутизации (ip rule)..."
if command -v ip > /dev/null; then
    echo "✅ ip доступен"
    echo "   Таблица маршрутизации:"
    ip rule show 2>/dev/null | head -10 || echo "   ❌ Не удалось получить"
    
    echo "   Таблицы маршрутизации:"
    cat /opt/etc/iproute2/rt_tables 2>/dev/null | tail -5 || echo "   ❌ Файл не найден"
else
    echo "❌ ip не доступен"
fi
echo ""

# 4. Проверка dnsmasq (ipset интеграция)
echo "[4/5] Проверка интеграции dnsmasq + ipset..."
DNSMASQ_CONF="/opt/etc/dnsmasq.conf"
if [ -f "$DNSMASQ_CONF" ]; then
    echo "✅ dnsmasq.conf найден"
    echo "   Настройки ipset:"
    grep -i "ipset" "$DNSMASQ_CONF" || echo "   ❌ Настройки ipset не найдены"
else
    echo "❌ dnsmasq.conf не найден"
fi
echo ""

# 5. Проверка скрипта unblock_dnsmasq.sh
echo "[5/5] Проверка скрипта unblock_dnsmasq.sh..."
UNBLOCK_DNS="/opt/bin/unblock_dnsmasq.sh"
if [ -f "$UNBLOCK_DNS" ]; then
    echo "✅ Скрипт найден"
    echo "   Последние 10 строк:"
    tail -10 "$UNBLOCK_DNS" | sed 's/^/   /'
else
    echo "❌ Скрипт не найден"
fi
echo ""

# Итоговая сводка
echo "============================================================"
echo "ИТОГОВАЯ СВОДКА"
echo "============================================================"

errors=0

# Проверка ключевых компонентов маршрутизации
! ipset list unblocksh -n 2>/dev/null | grep -q "^unblocksh$" && errors=$((errors + 1))
iptables-save 2>/dev/null | grep -q "1082" || errors=$((errors + 1))
[ ! -f "$DNSMASQ_CONF" ] && errors=$((errors + 1))

if [ $errors -eq 0 ]; then
    echo "✅ МАРШРУТИЗАЦИЯ НАСТРОЕНА КОРРЕКТНО"
else
    echo "❌ НАЙДЕНО ПРОБЛЕМ: $errors"
    echo ""
    echo "Возможные причины:"
    echo "1. ipset не создан — запустите /opt/bin/unblock_ipset.sh"
    echo "2. iptables правила не применены — проверьте скрипт 100-redirect.sh"
    echo "3. dnsmasq не настроен для ipset — проверьте dnsmasq.conf"
fi

echo ""
echo "============================================================"
