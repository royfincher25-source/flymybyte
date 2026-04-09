#!/bin/sh
# ============================================================
# FlyMyByte - Диагностика обхода блокировок ChatGPT/OpenAI
# Запуск: ssh root@192.168.1.1 -p 222 'sh /путь/к/скрипту.sh'
# ============================================================

echo "============================================"
echo "  FlyMyByte Diagnostic - ChatGPT/OpenAI"
echo "  Date: $(date)"
echo "============================================"

# 1. Проверка DNS-разрешения основных доменов
echo ""
echo "--- 1. DNS Resolution (через 8.8.8.8) ---"
for domain in chatgpt.com www.chatgpt.com chat.openai.com api.openai.com openai.com oaiusercontent.com; do
    echo -n "$domain -> "
    nslookup $domain 8.8.8.8 2>/dev/null | grep -oE '[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}' | head -1 || echo "FAILED"
done

# 2. Проверка DNS через локальный dnsmasq (порт 5353)
echo ""
echo "--- 2. DNS Resolution (через локальный dnsmasq :5353) ---"
for domain in chatgpt.com chat.openai.com api.openai.com; do
    echo -n "$domain -> "
    nslookup $domain 127.0.0.1 5353 2>/dev/null | grep -oE '[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}' | head -1 || echo "FAILED"
done

# 3. Проверка ipset unblockvless
echo ""
echo "--- 3. Ipset unblockvless ---"
if ipset list unblockvless -n >/dev/null 2>&1; then
    count=$(ipset list unblockvless 2>/dev/null | tail -n +7 | grep -c "^[0-9]")
    echo "Ipset существует: $count записей"
    echo "Содержимое (первые 10):"
    ipset list unblockvless 2>/dev/null | tail -n +7 | head -10
else
    echo "Ipset НЕ СУЩЕСТВУЕТ!"
fi

# 4. Проверка файлов bypass
echo ""
echo "--- 4. Bypass файлы ---"
for f in vless.txt shadowsocks.txt; do
    filepath="/opt/etc/unblock/$f"
    if [ -f "$filepath" ]; then
        count=$(wc -l < "$filepath")
        echo "✅ $filepath ($count строк)"
        # Проверка на наличие доменов OpenAI
        if grep -qi "openai\|chatgpt" "$filepath" 2>/dev/null; then
            echo "   Содержит OpenAI домены:"
            grep -i "openai\|chatgpt" "$filepath" | sed 's/^/   - /'
        else
            echo "   ⚠️ НЕ содержит доменов OpenAI/ChatGPT!"
        fi
    else
        echo "❌ $filepath НЕ НАЙДЕН!"
    fi
done

# 5. Проверка dnsmasq конфига
echo ""
echo "--- 5. dnsmasq unblock конфиг ---"
unblock_conf="/opt/etc/unblock.dnsmasq"
if [ -f "$unblock_conf" ]; then
    count=$(grep -c "openai\|chatgpt" "$unblock_conf" 2>/dev/null)
    echo "Файл существует: $count правил для OpenAI/ChatGPT"
    if [ "$count" -gt 0 ]; then
        echo "Правила:"
        grep "openai\|chatgpt" "$unblock_conf" | head -5
    fi
else
    echo "❌ $unblock_conf НЕ НАЙДЕН!"
fi

# 6. Проверка dnsmasq процесса
echo ""
echo "--- 6. dnsmasq процесс ---"
if pgrep dnsmasq >/dev/null 2>&1; then
    echo "✅ dnsmasq запущен (PID: $(pgrep dnsmasq | head -1))"
    # Проверка listening портов
    netstat -lnp 2>/dev/null | grep dnsmasq || ss -lnp | grep dnsmasq
else
    echo "❌ dnsmasq НЕ запущен!"
fi

# 7. Проверка VPN процесса (xray для VLESS)
echo ""
echo "--- 7. VLESS (xray) процесс ---"
if pgrep xray >/dev/null 2>&1; then
    echo "✅ xray запущен (PID: $(pgrep xray | head -1))"
else
    echo "⚠️ xray НЕ запущен (проверьте VPN ключ)"
fi

# 8. Проверка маршрутов (iptables)
echo ""
echo "--- 8. iptables правила для unblockvless ---"
iptables -t nat -L PREROUTING -n -v 2>/dev/null | grep unblockvless | head -5 || echo "Правила не найдены"

# 9. Проверка внешнего IP (через VPN DNS)
echo ""
echo "--- 9. Проверка IP (через 8.8.8.8 DNS) ---"
# Используем nslookup для проверки какой IP видит внешний DNS
echo "IP через nslookup (cosmote.gr):"
nslookup myip.opendns.com 8.8.8.8 2>/dev/null | grep "Address:" | tail -1

# 10. Логи dnsmasq
echo ""
echo "--- 10. Последние логи dnsmasq (ошибки) ---"
log_file="/opt/var/log/unblock_dnsmasq.log"
if [ -f "$log_file" ]; then
    tail -20 "$log_file" | grep -i "error\|fail\|warn" | tail -10 || echo "Ошибок не найдено"
else
    echo "Лог файл не найден"
fi

echo ""
echo "============================================"
echo "  Diagnostic Complete"
echo "============================================"
