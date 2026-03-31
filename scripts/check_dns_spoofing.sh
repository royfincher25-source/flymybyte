#!/bin/sh
# check_dns_spoofing.sh - Диагностика DNS-спуфинга AI-доменов
# Запускать на роутере: sh /opt/root/check_dns_spoofing.sh

echo "============================================================"
echo "ДИАГНОСТИКА DNS-СПУФИНГА AI-ДОМЕНОВ"
echo "============================================================"
echo ""

# Цвета (если поддерживаются)
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

check_result() {
    if [ $1 -eq 0 ]; then
        echo -e "${GREEN}✅ $2${NC}"
    else
        echo -e "${RED}❌ $2${NC}"
    fi
}

# =============================================================================
# 1. Проверка конфигурации DNS-спуфинга
# =============================================================================
echo "[1/8] Проверка конфигурации DNS-спуфинга..."
AI_DNSMASQ="/opt/etc/unblock-ai.dnsmasq"
if [ -f "$AI_DNSMASQ" ]; then
    echo "✅ Файл конфигурации найден: $AI_DNSMASQ"
    lines=$(wc -l < "$AI_DNSMASQ")
    echo "   Строк в конфиге: $lines"
    
    # Проверка на наличие правил server=
    server_rules=$(grep -c "^server=/" "$AI_DNSMASQ" 2>/dev/null)
    echo "   Правил server=/: $server_rules"
    
    # Проверка DNS порта
    if grep -q "127.0.0.1#[0-9]*" "$AI_DNSMASQ"; then
        dns_port=$(grep "127.0.0.1#" "$AI_DNSMASQ" | head -1 | sed 's/.*#//')
        echo "✅ DNS порт: $dns_port (VPN DNS-over-TLS)"
    elif grep -q "1.1.1.1" "$AI_DNSMASQ"; then
        echo "❌ Обнаружен Cloudflare DNS (1.1.1.1) - устаревшая конфигурация!"
    else
        echo "⚠️  Не удалось определить DNS порт"
    fi
else
    echo "❌ Файл конфигурации не найден"
fi
echo ""

# =============================================================================
# 2. Проверка списка AI-доменов
# =============================================================================
echo "[2/8] Проверка списка AI-доменов..."
AI_DOMAINS="/opt/etc/unblock/ai-domains.txt"
if [ -f "$AI_DOMAINS" ]; then
    echo "✅ Файл доменов найден: $AI_DOMAINS"
    domains=$(grep -v "^#" "$AI_DOMAINS" | grep -v "^$" | wc -l)
    echo "   Доменов в списке: $domains"
    
    # Показать первые 5 доменов
    echo "   Первые 5 доменов:"
    grep -v "^#" "$AI_DOMAINS" | grep -v "^$" | head -5 | sed 's/^/      /'
else
    echo "❌ Файл доменов не найден"
fi
echo ""

# =============================================================================
# 3. Проверка подключения к dnsmasq
# =============================================================================
echo "[3/8] Проверка dnsmasq..."
if pgrep -x dnsmasq > /dev/null; then
    echo "✅ dnsmasq запущен"
    pid=$(pgrep -x dnsmasq)
    echo "   PID: $pid"
    
    # Проверка порта 53
    if netstat -tlnp 2>/dev/null | grep -q ":53"; then
        echo "✅ Порт 53 слушается"
    else
        echo "❌ Порт 53 не слушается"
    fi
else
    echo "❌ dnsmasq не запущен"
fi
echo ""

# =============================================================================
# 4. Тест DNS-запроса через локальный DNS
# =============================================================================
echo "[4/8] Тест DNS-запроса AI-доменов..."

# Функция для теста домена
test_domain() {
    local domain=$1
    local dns_server=$2
    local port=$3
    
    echo "   Тест: $domain @ $dns_server#$port"
    
    if command -v nslookup > /dev/null; then
        result=$(nslookup "$domain" "$dns_server" -port="$port" 2>&1)
        if echo "$result" | grep -q "Address:"; then
            ips=$(echo "$result" | grep "Address:" | grep -v "^#" | head -3)
            echo "   ✅ resolved:"
            echo "$ips" | sed 's/^/      /'
            return 0
        else
            echo "   ❌ не резолвится"
            return 1
        fi
    else
        echo "   ⚠️  nslookup не найден"
        return 1
    fi
}

# Получить DNS порт из конфигурации
DNS_PORT="40500"
if [ -f "/opt/etc/web_ui/.env" ]; then
    DNS_PORT=$(grep "^dnsovertlsport=" /opt/etc/web_ui/.env 2>/dev/null | cut -d'=' -f2 | tr -d ' ')
    [ -z "$DNS_PORT" ] && DNS_PORT="40500"
fi

echo "   DNS порт: $DNS_PORT"
echo ""

# Тест популярных AI-доменов
echo "   Тест через VPN DNS (127.0.0.1:$DNS_PORT):"
test_domain "chatgpt.com" "127.0.0.1" "$DNS_PORT"
echo ""
test_domain "aistudio.google.com" "127.0.0.1" "$DNS_PORT"
echo ""
test_domain "gemini.google.com" "127.0.0.1" "$DNS_PORT"
echo ""

echo "   Тест через внешний DNS (8.8.8.8:53) для сравнения:"
test_domain "chatgpt.com" "8.8.8.8" "53"
echo ""

# =============================================================================
# 5. Проверка через роутер (как клиент)
# =============================================================================
echo "[5/8] Тест DNS-запроса через роутер (192.168.1.1:53)..."
if command -v nslookup > /dev/null; then
    echo "   Запрос: chatgpt.com @ 192.168.1.1"
    result=$(nslookup chatgpt.com 192.168.1.1 2>&1)
    
    # Проверка на "Не заслуживающий доверия ответ"
    if echo "$result" | grep -q "Не заслуживающий доверия ответ\|Non-authoritative"; then
        echo "   ⚠️  Ответ не авторитетный (это нормально)"
    fi
    
    # Извлечь IP адреса
    if echo "$result" | grep -q "Address:"; then
        echo "   ✅ resolved:"
        echo "$result" | grep "Address:" | grep -v "^#" | head -5 | sed 's/^/      /'
        
        # Проверка на IPv6
        if echo "$result" | grep -q "2a0"; then
            echo "   ⚠️  Обнаружен IPv6 (возможно, нужен filter-aaaa)"
        fi
    else
        echo "   ❌ не резолвится"
    fi
else
    echo "   ⚠️  nslookup не найден"
fi
echo ""

# =============================================================================
# 6. Проверка dnsmasq.conf
# =============================================================================
echo "[6/8] Проверка подключения unblock-ai.dnsmasq..."
DNSMASQ_CONF="/opt/etc/dnsmasq.conf"
if [ -f "$DNSMASQ_CONF" ]; then
    if grep -q "unblock-ai.dnsmasq" "$DNSMASQ_CONF"; then
        echo "✅ unblock-ai.dnsmasq подключен в dnsmasq.conf"
    else
        echo "❌ unblock-ai.dnsmasq не подключен в dnsmasq.conf"
        echo "   Добавьте: conf-file=/opt/etc/unblock-ai.dnsmasq"
    fi
    
    # Проверка filter-aaaa для IPv6
    if grep -q "filter-aaaa" "$DNSMASQ_CONF"; then
        echo "✅ IPv6 filtering включен (filter-aaaa)"
    else
        echo "⚠️  IPv6 filtering выключен (возможны утечки)"
    fi
else
    echo "❌ dnsmasq.conf не найден"
fi
echo ""

# =============================================================================
# 7. Проверка логов
# =============================================================================
echo "[7/8] Проверка логов DNS-спуфинга..."
WEB_UI_LOG="/opt/var/log/web_ui.log"
if [ -f "$WEB_UI_LOG" ]; then
    echo "✅ Лог найден: $WEB_UI_LOG"
    
    # Поиск ошибок DNS-спуфинга
    dns_errors=$(grep -i "dns.*spoof\|ai.*domain" "$WEB_UI_LOG" | tail -10)
    if [ -n "$dns_errors" ]; then
        echo "   Последние записи:"
        echo "$dns_errors" | sed 's/^/      /'
    else
        echo "   Нет записей о DNS-спуфинге"
    fi
else
    echo "❌ Лог не найден"
fi
echo ""

# =============================================================================
# 8. Итоговая сводка
# =============================================================================
echo "============================================================"
echo "ИТОГОВАЯ СВОДКА"
echo "============================================================"

errors=0

# Проверка ключевых компонентов
[ ! -f "$AI_DNSMASQ" ] && errors=$((errors + 1))
[ ! -f "$AI_DOMAINS" ] && errors=$((errors + 1))
! pgrep -x dnsmasq > /dev/null && errors=$((errors + 1))
! grep -q "unblock-ai.dnsmasq" "$DNSMASQ_CONF" 2>/dev/null && errors=$((errors + 1))

# Проверка на устаревшую конфигурацию
if [ -f "$AI_DNSMASQ" ] && grep -q "1.1.1.1" "$AI_DNSMASQ"; then
    echo "⚠️  ВНИМАНИЕ: Обнаружена устаревшая конфигурация с Cloudflare DNS!"
    echo "   Рекомендуется обновить DNS-спуфинг через веб-интерфейс"
    echo "   или выполнить: Сервис → DNS-обход AI → Применить"
    errors=$((errors + 1))
fi

if [ $errors -eq 0 ]; then
    echo "✅ ВСЕ КОМПОНЕНТЫ НАСТРОЕНЫ КОРРЕКТНО"
    echo ""
    echo "Рекомендуемые действия:"
    echo "1. Протестируйте доступ к AI-сервисам:"
    echo "   - chatgpt.com"
    echo "   - aistudio.google.com"
    echo "   - gemini.google.com"
    echo ""
    echo "2. Если не работает, проверьте логи:"
    echo "   tail -50 /opt/var/log/web_ui.log"
else
    echo "❌ НАЙДЕНО ОШИБОК: $errors"
    echo ""
    echo "Рекомендуется:"
    echo "1. Откройте http://192.168.1.1:8080/dns-spoofing"
    echo "2. Загрузите список AI-доменов"
    echo "3. Нажмите 'Применить конфигурацию'"
    echo "4. Перезапустите dnsmasq:"
    echo "   /opt/etc/init.d/S56dnsmasq restart"
fi

echo ""
echo "============================================================"
