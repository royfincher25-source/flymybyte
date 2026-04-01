#!/bin/sh
# Применение правил маршрутизации трафика через Shadowsocks/Tor
# Запуск: sh /opt/root/apply_routing.sh

echo "============================================================"
echo "ПРИМЕНЕНИЕ ПРАВИЛ МАРШРУТИЗАЦИИ"
echo "============================================================"
echo ""

# 1. Создание ipset
echo "[1/3] Создание ipset..."
ipset create unblocksh hash:net -exist 2>/dev/null && echo "✅ unblocksh создан" || echo "❌ unblocksh ошибка"
ipset create unblocktor hash:net -exist 2>/dev/null && echo "✅ unblocktor создан" || echo "❌ unblocktor ошибка"
ipset create unblockvless hash:net -exist 2>/dev/null && echo "✅ unblockvless создан" || echo "❌ unblockvless ошибка"
ipset create unblocktroj hash:net -exist 2>/dev/null && echo "✅ unblocktroj создан" || echo "❌ unblocktroj ошибка"
echo ""

# 2. Заполнение ipset из списков обхода
echo "[2/3] Заполнение ipset из списков обхода..."
if [ -f "/opt/bin/unblock_ipset.sh" ]; then
    sh /opt/bin/unblock_ipset.sh
    echo "✅ ipset заполнены"
else
    echo "❌ unblock_ipset.sh не найден"
fi
echo ""

# 3. Применение правил iptables
echo "[3/3] Применение правил iptables..."
if [ -f "/opt/etc/ndm/fs.d/100-redirect.sh" ]; then
    sh /opt/etc/ndm/fs.d/100-redirect.sh
    echo "✅ iptables правила применены"
else
    echo "❌ 100-redirect.sh не найден"
fi
echo ""

# Проверка результатов
echo "============================================================"
echo "ПРОВЕРКА РЕЗУЛЬТАТОВ"
echo "============================================================"
echo ""

echo "ipset:"
for ipset in unblocksh unblocktor unblockvless unblocktroj; do
    if ipset list "$ipset" -n 2>/dev/null | grep -q "^${ipset}$"; then
        count=$(ipset list "$ipset" 2>/dev/null | grep -c "^[0-9]" || echo 0)
        echo "✅ $ipset: $count записей"
    else
        echo "❌ $ipset: не создан"
    fi
done
echo ""

echo "iptables правила (NAT):"
iptables-save 2>/dev/null | grep -E "unblocksh|1082" | head -5 || echo "❌ Правила не найдены"
echo ""

echo "============================================================"
echo "ГОТОВО"
echo "============================================================"
echo ""
echo "Теперь трафик должен перенаправляться через Shadowsocks (порт 1082)"
echo "Проверьте: nslookup rutracker.org 192.168.1.1"
