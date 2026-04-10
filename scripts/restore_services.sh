#!/bin/sh
# restore_services.sh - Полное восстановление всех сервисов FlyMyByte
# Использовать при проблемах с работой bypass после обновлений

set -e

echo "========================================"
echo "ВОССТАНОВЛЕНИЕ СЕРВИСОВ FLYMYBYTE"
echo "========================================"
echo ""

# Проверка что мы на роутере
if [ ! -d "/opt/etc/web_ui" ]; then
    echo "ОШИБКА: Не найдена директория /opt/etc/web_ui"
    exit 1
fi

echo "[1/8] Остановка всех сервисов..."
echo "  - Остановка веб-интерфейса..."
killall -9 python3 2>/dev/null || true
killall -9 web_ui 2>/dev/null || true
echo "  - Остановка watchdog..."
killall -9 dnsmasq_watchdog.sh 2>/dev/null || true
echo "  - Очистка iptables..."
iptables -t nat -F PREROUTING 2>/dev/null || true
echo "  - Очистка ipsets..."
ipset flush unblocksh 2>/dev/null || true
ipset flush unblockvless 2>/dev/null || true
ipset flush unblocktroj 2>/dev/null || true

echo ""
echo "[2/8] Проверка директорий..."
echo "  - unblock dir: $(ls -la /opt/etc/unblock/ 2>/dev/null | wc -l) файлов"
echo "  - scripts: $(ls -la /opt/bin/*.sh 2>/dev/null | wc -l) скриптов"
echo "  - init.d: $(ls -la /opt/etc/init.d/S* 2>/dev/null | wc -l) скриптов"

echo ""
echo "[3/8] Перезапуск dnsmasq..."
/opt/etc/init.d/S56dnsmasq restart
sleep 2
if pgrep -x dnsmasq >/dev/null; then
    echo "  dnsmasq запущен (PID: $(pgrep -x dnsmasq))"
else
    echo "  ОШИБКА: dnsmasq не запущен!"
fi

echo ""
echo "[4/8] Проверка конфигурационных файлов..."
echo "  - unblock.dnsmasq: $(wc -l < /opt/etc/unblock.dnsmasq 2>/dev/null || echo 0) строк"
echo "  - unblock-ai.dnsmasq: $(wc -l < /opt/etc/unblock-ai.dnsmasq 2>/dev/null || echo 0) строк"
echo "  - shadowsocks.txt: $(wc -l < /opt/etc/unblock/shadowsocks.txt 2>/dev/null || echo 0) строк"
echo "  - vless.txt: $(wc -l < /opt/etc/unblock/vless.txt 2>/dev/null || echo 0) строк"

echo ""
echo "[5/8] Запуск bypass (через shell скрипты)..."
echo "  - Запуск unblock_dnsmasq.sh..."
if [ -x "/opt/bin/unblock_dnsmasq.sh" ]; then
    /opt/bin/unblock_dnsmasq.sh
else
    echo "    Скрипт не найден или не исполняемый"
fi

echo "  - Запуск unblock_ipset.sh..."
if [ -x "/opt/bin/unblock_ipset.sh" ]; then
    /opt/bin/unblock_ipset.sh
else
    echo "    Скрипт не найден или не исполняемый"
fi
sleep 2

echo ""
echo "[6/8] Проверка ipsets после заполнения..."
for setname in unblocksh unblockvless unblocktroj; do
    if ipset list "$setname" -n >/dev/null 2>&1; then
        count=$(ipset list "$setname" 2>/dev/null | grep -c "^[0-9]" || echo 0)
        echo "  - $setname: $count записей"
    else
        echo "  - $setname: НЕ СУЩЕСТВУЕТ"
    fi
done

echo ""
echo "[7/8] Применение iptables правил..."
if [ -x "/opt/etc/ndm/netfilter.d/100-redirect.sh" ]; then
    /opt/etc/ndm/netfilter.d/100-redirect.sh
    echo "  100-redirect.sh выполнен"
else
    echo "  100-redirect.sh не найден"
fi

echo ""
echo "[8/8] Запуск веб-интерфейса..."
cd /opt/etc/web_ui
nohup /opt/bin/python3 app.py >/opt/var/log/web_ui.log 2>&1 &
sleep 3

if pgrep -f "python3.*app.py" >/dev/null; then
    echo "  Веб-интерфейс запущен (PID: $(pgrep -f 'python3.*app.py'))"
else
    echo "  ОШИБКА: Веб-интерфейс не запущен"
fi

echo ""
echo "========================================"
echo "ВОССТАНОВЛЕНИЕ ЗАВЕРШЕНО"
echo "========================================"
echo ""
echo "СТАТУС СЕРВИСОВ:"
echo "  - dnsmasq: $(pgrep -x dnsmasq >/dev/null && echo 'ЗАПУЩЕН' || echo 'ОСТАНОВЛЕН')"
echo "  - web_ui: $(pgrep -f 'python3.*app.py' >/dev/null && echo 'ЗАПУЩЕН' || echo 'ОСТАНОВЛЕН')"
echo "  - watchdog: $(pgrep -f 'dnsmasq_watchdog' >/dev/null && echo 'ЗАПУЩЕН' || echo 'ОСТАНОВЛЕН')"
echo ""
echo "IPSETS:"
for setname in unblocksh unblockvless unblocktroj; do
    if ipset list "$setname" -n >/dev/null 2>&1; then
        count=$(ipset list "$setname" 2>/dev/null | grep -c "^[0-9]" || echo 0)
        echo "  - $setname: $count записей"
    else
        echo "  - $setname: НЕ СУЩЕСТВУЕТ"
    fi
done
echo ""
echo "ЛОГИ:"
echo "  - Web UI: /opt/var/log/web_ui.log"
echo "  - S99unblock: /opt/var/log/S99unblock.log"
echo "  - unblock_dnsmasq: /opt/var/log/unblock_dnsmasq.log"
echo "  - unblock_ipset: /opt/var/log/unblock_ipset.log"
echo ""
echo "БЫСТРЫЕ КОМАНДЫ:"
echo "  Перезапуск bypass: /opt/etc/init.d/S99unblock restart"
echo "  Проверка ipsets: for i in unblocksh unblockvless unblocktroj; do echo \$i: \$(ipset list \$i 2>/dev/null | grep -c '^[0-9]'); done"
echo "  Тест DNS: nslookup google.com"
echo "  Ручной запуск unblock: /opt/bin/unblock_update.sh"