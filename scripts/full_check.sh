#!/bin/sh
# Полная диагностика после перезагрузки
# Запуск: sh /opt/root/full_check.sh

echo "============================================================"
echo "ПОЛНАЯ ДИАГНОСТИКА ПОСЛЕ ПЕРЕЗАГРУЗКИ"
echo "============================================================"
echo ""

errors=0
warnings=0

# 1. Shadowsocks
echo "[1/8] Проверка Shadowsocks..."
if [ -f "/opt/etc/shadowsocks.json" ]; then
    echo "✅ Конфигурация найдена"
    if pgrep -f ss-redir > /dev/null; then
        echo "✅ Shadowsocks запущен (PID: $(pgrep -f ss-redir))"
    else
        echo "❌ Shadowsocks НЕ запущен"
        errors=$((errors + 1))
    fi
else
    echo "❌ Конфигурация НЕ найдена"
    errors=$((errors + 1))
fi
echo ""

# 2. dnsmasq
echo "[2/8] Проверка dnsmasq..."
if pgrep -x dnsmasq > /dev/null; then
    echo "✅ dnsmasq запущен (PID: $(pgrep -x dnsmasq))"
else
    echo "❌ dnsmasq НЕ запущен"
    errors=$((errors + 1))
fi

if netstat -tlnp 2>/dev/null | grep -q ":53"; then
    echo "✅ Порт 53 слушается"
else
    echo "❌ Порт 53 НЕ слушается"
    errors=$((errors + 1))
fi
echo ""

# 3. DNS Override
echo "[3/8] Проверка DNS Override..."
if ndmc -c 'show running' 2>/dev/null | grep -q 'dns-override'; then
    echo "✅ DNS Override включен"
else
    echo "❌ DNS Override ВЫКЛЮЧЕН"
    errors=$((errors + 1))
fi
echo ""

# 4. ipset
echo "[4/8] Проверка ipset..."
for ipset_name in unblocksh unblocktor unblockvless unblocktroj; do
    if ipset list "$ipset_name" -n 2>/dev/null | grep -q "^${ipset_name}$"; then
        count=$(ipset list "$ipset_name" 2>/dev/null | grep -c "^[0-9]" 2>/dev/null || echo "0")
        if [ "$count" -gt 0 ] 2>/dev/null; then
            echo "✅ $ipset_name: $count записей"
        else
            echo "⚠️  $ipset_name: пуст (0 записей)"
            warnings=$((warnings + 1))
        fi
    else
        echo "❌ $ipset_name: НЕ создан"
        errors=$((errors + 1))
    fi
done
echo ""

# 5. iptables правила
echo "[5/8] Проверка iptables (NAT)..."
nat_rules=$(iptables-save -t nat 2>/dev/null | grep -c "REDIRECT.*1082" 2>/dev/null || echo "0")
if [ "$nat_rules" -gt 0 ] 2>/dev/null; then
    echo "✅ NAT правила есть: $nat_rules правил"
    iptables-save -t nat 2>/dev/null | grep "1082" | head -3 | sed 's/^/   /'
else
    echo "❌ NAT правила НЕ найдены"
    echo "   Трафик НЕ перенаправляется через Shadowsocks!"
    errors=$((errors + 1))
fi
echo ""

# 6. Веб-интерфейс
echo "[6/8] Проверка веб-интерфейса..."
if netstat -tlnp 2>/dev/null | grep -q ":8080"; then
    echo "✅ Веб-интерфейс запущен (порт 8080 слушается)"
else
    echo "❌ Веб-интерфейс НЕ запущен"
    errors=$((errors + 1))
fi
echo ""

# 7. Тест DNS
echo "[7/8] Тест DNS..."
dns_result=$(nslookup google.com 192.168.1.1 2>&1 | grep -E "Address|Адрес" | grep -v "192.168.1.1" | head -1)
if [ -n "$dns_result" ]; then
    echo "✅ DNS работает (google.com разрешается)"
    echo "   $dns_result" | sed 's/^/   /'
else
    echo "❌ DNS НЕ работает"
    errors=$((errors + 1))
fi
echo ""

# 8. Логи
echo "[8/8] Проверка логов..."
if [ -f "/opt/var/log/web_ui.log" ]; then
    error_count=$(grep -c "ERROR" /opt/var/log/web_ui.log 2>/dev/null || echo "0")
    if [ "$error_count" -gt 0 ] 2>/dev/null; then
        echo "⚠️  Найдено ошибок в логе: $error_count"
        echo "   Последние ошибки:"
        grep "ERROR" /opt/var/log/web_ui.log | tail -3 | sed 's/^/   /'
        warnings=$((warnings + 1))
    else
        echo "✅ Ошибок в логе нет"
    fi
else
    echo "❌ Лог файл НЕ найден"
    errors=$((errors + 1))
fi
echo ""

# Итоговая сводка
echo "============================================================"
echo "ИТОГОВАЯ СВОДКА"
echo "============================================================"
echo "Ошибки: $errors"
echo "Предупреждения: $warnings"
echo ""

if [ $errors -eq 0 ]; then
    echo "✅ ВСЕ СИСТЕМЫ РАБОТАЮТ НОРМАЛЬНО"
    echo ""
    echo "Если сайты всё равно не открываются:"
    echo "1. Проверьте браузер (отключите прокси/расширения)"
    echo "2. Попробуйте другой браузер/устройство"
    echo "3. Проверьте: nslookup rutracker.org 192.168.1.1"
else
    echo "❌ НАЙДЕНЫ ПРОБЛЕМЫ"
    echo ""
    if [ $errors -ge 5 ]; then
        echo "⚠️  КРИТИЧЕСКОЕ СОСТОЯНИЕ! Требуется восстановление:"
        echo ""
        echo "1. Перезапустите веб-интерфейс:"
        echo "   sh /opt/root/restart_web_ui.sh"
        echo ""
        echo "2. Примените правила маршрутизации:"
        echo "   sh /opt/bin/unblock_ipset.sh && sh /opt/etc/ndm/fs.d/100-redirect.sh"
        echo ""
        echo "3. Проверьте DNS Override через веб-интерфейс"
    else
        echo "Рекомендуется исправить ошибки по списку выше"
    fi
fi

echo ""
echo "============================================================"

# Быстрые команды для исправления
if [ $errors -gt 0 ]; then
    echo ""
    echo "БЫСТРЫЕ КОМАНДЫ ДЛЯ ИСПРАВЛЕНИЯ:"
    echo "================================"
    echo ""
    
    if ! pgrep -f ss-redir > /dev/null; then
        echo "# Перезапуск Shadowsocks:"
        echo "/opt/etc/init.d/S22shadowsocks restart"
        echo ""
    fi
    
    if ! pgrep -x dnsmasq > /dev/null; then
        echo "# Перезапуск dnsmasq:"
        echo "/opt/etc/init.d/S56dnsmasq restart"
        echo ""
    fi
    
    if ! netstat -tlnp 2>/dev/null | grep -q ":8080"; then
        echo "# Перезапуск веб-интерфейса:"
        echo "/opt/etc/init.d/S99web_ui restart"
        echo ""
    fi
    
    nat_rules=$(iptables-save -t nat 2>/dev/null | grep -c "REDIRECT.*1082" 2>/dev/null || echo "0")
    if [ "$nat_rules" = "0" ]; then
        echo "# Применение правил маршрутизации:"
        echo "sh /opt/bin/unblock_ipset.sh && sh /opt/etc/ndm/netfilter.d/100-redirect.sh"
        echo ""
    fi
    
    if [ -z "$dns_result" ]; then
        echo "# Проверка DNS (вручную):"
        echo "nslookup google.com 192.168.1.1"
        echo ""
    fi
fi

echo "============================================================"
