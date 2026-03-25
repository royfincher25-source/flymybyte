#!/bin/sh
# Диагностика обхода блокировок
# Запускать на роутере: sh /opt/root/check_bypass.sh

echo "============================================================"
echo "ДИАГНОСТИКА ОБХОДА БЛОКИРОВОК"
echo "============================================================"
echo ""

# Цвета (если поддерживаются)
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

check_result() {
    if [ $1 -eq 0 ]; then
        echo "✅ $2"
    else
        echo "❌ $2"
    fi
}

# =============================================================================
# 1. Проверка Entware
# =============================================================================
echo "[1/12] Проверка Entware..."
if [ -d "/opt" ]; then
    echo "✅ Entware установлен: /opt"
else
    echo "❌ Entware не найден"
fi
echo ""

# =============================================================================
# 2. Проверка dnsmasq
# =============================================================================
echo "[2/12] Проверка dnsmasq..."
if [ -f "/opt/etc/init.d/S56dnsmasq" ]; then
    echo "✅ Скрипт dnsmasq найден"
    if pgrep -x dnsmasq > /dev/null; then
        echo "✅ dnsmasq запущен"
        pgrep -x dnsmasq
    else
        echo "❌ dnsmasq не запущен"
    fi
else
    echo "❌ Скрипт dnsmasq не найден"
fi
echo ""

# =============================================================================
# 3. Проверка порта 53 (DNS)
# =============================================================================
echo "[3/12] Проверка порта 53..."
if netstat -tlnp 2>/dev/null | grep -q ":53"; then
    echo "✅ Порт 53 слушается:"
    netstat -tlnp 2>/dev/null | grep ":53"
else
    echo "❌ Порт 53 не слушается"
fi
echo ""

# =============================================================================
# 4. Проверка Shadowsocks
# =============================================================================
echo "[4/12] Проверка Shadowsocks..."
if [ -f "/opt/etc/shadowsocks.json" ]; then
    echo "✅ Конфигурация Shadowsocks найдена"
    echo "   Файл: /opt/etc/shadowsocks.json"
    if [ -f "/opt/etc/init.d/S22shadowsocks" ]; then
        if pgrep -f ss-redir > /dev/null; then
            echo "✅ Shadowsocks запущен"
            pgrep -f ss-redir
        else
            echo "❌ Shadowsocks не запущен"
        fi
    fi
else
    echo "❌ Конфигурация Shadowsocks не найдена"
fi
echo ""

# =============================================================================
# 5. Проверка DNS Override
# =============================================================================
echo "[5/12] Проверка DNS Override..."
if ndmc -c 'show running' 2>/dev/null | grep -q 'dns-override'; then
    echo "✅ DNS Override включен"
else
    echo "❌ DNS Override выключен"
fi
echo ""

# =============================================================================
# 6. Проверка списков обхода
# =============================================================================
echo "[6/12] Проверка списков обхода..."
UNBLOCK_DIR="/opt/etc/unblock"
if [ -d "$UNBLOCK_DIR" ]; then
    echo "✅ Директория списков обхода найдена: $UNBLOCK_DIR"
    echo "   Файлы:"
    ls -la "$UNBLOCK_DIR"/*.txt 2>/dev/null | while read line; do
        echo "   $line"
    done
    
    # Подсчёт записей
    total=0
    for f in "$UNBLOCK_DIR"/*.txt; do
        if [ -f "$f" ]; then
            count=$(grep -v '^#' "$f" | grep -v '^$' | wc -l)
            total=$((total + count))
            fname=$(basename "$f")
            echo "   → $fname: $count записей"
        fi
    done
    echo "   Всего записей: $total"
else
    echo "❌ Директория списков обхода не найдена"
fi
echo ""

# =============================================================================
# 7. Проверка dnsmasq.conf
# =============================================================================
echo "[7/12] Проверка конфигурации dnsmasq..."
DNSMASQ_CONF="/opt/etc/dnsmasq.conf"
if [ -f "$DNSMASQ_CONF" ]; then
    echo "✅ Файл конфигурации найден"
    echo "   Содержимое:"
    cat "$DNSMASQ_CONF" | sed 's/^/   /'
else
    echo "❌ Файл конфигурации не найден"
fi
echo ""

# =============================================================================
# 8. Проверка веб-интерфейса
# =============================================================================
echo "[8/12] Проверка веб-интерфейса..."
if pgrep -f "waitress" > /dev/null || pgrep -f "python.*web_ui" > /dev/null; then
    echo "✅ Веб-интерфейс запущен"
    pgrep -af "waitress\|web_ui" 2>/dev/null
else
    echo "❌ Веб-интерфейс не запущен"
fi
echo ""

# =============================================================================
# 9. Проверка логов
# =============================================================================
echo "[9/12] Последние ошибки в логах..."
LOG_FILE="/opt/var/log/web_ui.log"
if [ -f "$LOG_FILE" ]; then
    echo "✅ Лог файл найден: $LOG_FILE"
    echo "   Последние 10 строк:"
    tail -10 "$LOG_FILE" | sed 's/^/   /'
else
    echo "❌ Лог файл не найден"
fi
echo ""

# =============================================================================
# 10. Проверка DNS (тестовый запрос)
# =============================================================================
echo "[10/12] Тест DNS (запрос google.com)..."
if command -v dig > /dev/null; then
    echo "   Запрос через локальный DNS (192.168.1.1):"
    dig +short google.com @192.168.1.1 -p 53 | head -3 | sed 's/^/   /'
    
    echo "   Запрос через внешний DNS (8.8.8.8):"
    dig +short google.com @8.8.8.8 | head -3 | sed 's/^/   /'
elif command -v nslookup > /dev/null; then
    echo "   Запрос через локальный DNS:"
    nslookup google.com 192.168.1.1 2>&1 | grep -A2 "Name:" | sed 's/^/   /'
else
    echo "❌ dig/nslookup не найдены"
fi
echo ""

# =============================================================================
# 11. Проверка маршрутизации (если есть ipset)
# =============================================================================
echo "[11/12] Проверка ipset..."
if command -v ipset > /dev/null; then
    if ipset list unblock 2>/dev/null; then
        echo "✅ ipset 'unblock' существует"
        ipset list unblock | head -10 | sed 's/^/   /'
        echo "   ..."
    else
        echo "⚠️  ipset 'unblock' не найден"
    fi
else
    echo "⚠️  ipset не доступен (требуется модуль ядра)"
fi
echo ""

# =============================================================================
# 12. Итоговая сводка
# =============================================================================
echo "============================================================"
echo "ИТОГОВАЯ СВОДКА"
echo "============================================================"

errors=0

# Проверка ключевых компонентов
[ ! -f "/opt/etc/shadowsocks.json" ] && errors=$((errors + 1))
[ ! -f "/opt/etc/dnsmasq.conf" ] && errors=$((errors + 1))
! pgrep -x dnsmasq > /dev/null && errors=$((errors + 1))
! ndmc -c 'show running' 2>/dev/null | grep -q 'dns-override' && errors=$((errors + 1))

if [ $errors -eq 0 ]; then
    echo "✅ ВСЕ КОМПОНЕНТЫ НАСТРОЕНЫ КОРРЕКТНО"
    echo ""
    echo "Рекомендуемые действия:"
    echo "1. Откройте http://192.168.1.1:8080"
    echo "2. Проверьте статус сервисов на странице /service"
    echo "3. Протестируйте обход на заблокированном ресурсе"
else
    echo "❌ НАЙДЕНО ОШИБОК: $errors"
    echo ""
    echo "Рекомендуется:"
    echo "1. Проверить логи: tail -50 /opt/var/log/web_ui.log"
    echo "2. Перезапустить сервисы: sh /opt/root/restart_web_ui.sh"
    echo "3. Включить DNS Override через веб-интерфейс"
fi

echo ""
echo "============================================================"
