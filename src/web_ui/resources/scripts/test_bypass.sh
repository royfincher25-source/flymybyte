#!/bin/sh
# test_bypass.sh - Автоматическое тестирование bypass системы после обновления
# Запуск: /opt/bin/test_bypass.sh
# Результат: /opt/var/log/test_bypass_result.log

mkdir -p /opt/var/log
RESULT_LOG="/opt/var/log/test_bypass_result.log"
PASS=0
FAIL=0
WARN=0

# Header
cat > "$RESULT_LOG" << 'HEADER'
============================================================
 FlyMyByte — Тест bypass системы после обновления
============================================================
HEADER
echo "Дата: $(date '+%Y-%m-%d %H:%M:%S')" >> "$RESULT_LOG"
echo "" >> "$RESULT_LOG"

# ============================================================
# ЭТАП 0: Очистка всех логов
# ============================================================
echo "=== ЭТАП 0: Очистка логов ===" >> "$RESULT_LOG"
for logfile in S99unblock.log unblock_ipset.log 100-redirect.log unblock_dnsmasq.log dnsmasq_watchdog.log web_ui.log emergency_restore.log rollback.log; do
    if [ -f "/opt/var/log/$logfile" ]; then
        > "/opt/var/log/$logfile"
        echo "  Очищен: $logfile" >> "$RESULT_LOG"
    else
        echo "  Не найден (пропущен): $logfile" >> "$RESULT_LOG"
    fi
done
echo "" >> "$RESULT_LOG"

# ============================================================
# ЭТАП 1: Запуск bypass системы
# ============================================================
echo "=== ЭТАП 1: Запуск S99unblock ===" >> "$RESULT_LOG"
echo "  Запуск..." >> "$RESULT_LOG"
/opt/etc/init.d/S99unblock start >> "$RESULT_LOG" 2>&1
echo "  Завершён" >> "$RESULT_LOG"
echo "" >> "$RESULT_LOG"

# ============================================================
# ЭТАП 2: Проверка логов на ошибки
# ============================================================
echo "=== ЭТАП 2: Проверка логов ===" >> "$RESULT_LOG"

# S99unblock.log — нет ERROR
if [ -f "/opt/var/log/S99unblock.log" ]; then
    errors=$(grep -c "ERROR" /opt/var/log/S99unblock.log 2>/dev/null)
    errors=${errors:-0}
    if [ "$errors" -eq 0 ]; then
        echo "  [PASS] S99unblock.log — нет ошибок" >> "$RESULT_LOG"
        PASS=$((PASS + 1))
    else
        echo "  [FAIL] S99unblock.log — $errors ошибок" >> "$RESULT_LOG"
        grep "ERROR" /opt/var/log/S99unblock.log >> "$RESULT_LOG" 2>/dev/null
        FAIL=$((FAIL + 1))
    fi
else
    echo "  [FAIL] S99unblock.log — файл отсутствует" >> "$RESULT_LOG"
    FAIL=$((FAIL + 1))
fi

# unblock_ipset.log — DNS OK, записи > 0
if [ -f "/opt/var/log/unblock_ipset.log" ]; then
    if grep -q "DNS is available" /opt/var/log/unblock_ipset.log 2>/dev/null; then
        echo "  [PASS] unblock_ipset.log — DNS доступен" >> "$RESULT_LOG"
        PASS=$((PASS + 1))
    else
        echo "  [FAIL] unblock_ipset.log — DNS недоступен" >> "$RESULT_LOG"
        FAIL=$((FAIL + 1))
    fi

    if grep -q "restore failed" /opt/var/log/unblock_ipset.log 2>/dev/null; then
        echo "  [FAIL] unblock_ipset.log — ipset restore errors" >> "$RESULT_LOG"
        grep "restore failed" /opt/var/log/unblock_ipset.log >> "$RESULT_LOG" 2>/dev/null
        FAIL=$((FAIL + 1))
    else
        echo "  [PASS] unblock_ipset.log — ipset restore без ошибок" >> "$RESULT_LOG"
        PASS=$((PASS + 1))
    fi
else
    echo "  [FAIL] unblock_ipset.log — файл отсутствует" >> "$RESULT_LOG"
    FAIL=$((FAIL + 1))
fi

# 100-redirect.log
if [ -f "/opt/var/log/100-redirect.log" ]; then
    if grep -q "DNS redirect NOT applied" /opt/var/log/100-redirect.log 2>/dev/null; then
        echo "  [WARN] 100-redirect.log — DNS redirect не применён (dnsmasq:5353 недоступен)" >> "$RESULT_LOG"
        WARN=$((WARN + 1))
    else
        echo "  [PASS] 100-redirect.log — DNS redirect применён" >> "$RESULT_LOG"
        PASS=$((PASS + 1))
    fi
else
    echo "  [FAIL] 100-redirect.log — файл отсутствует" >> "$RESULT_LOG"
    FAIL=$((FAIL + 1))
fi

echo "" >> "$RESULT_LOG"

# ============================================================
# ЭТАП 3: Проверка ipset
# ============================================================
echo "=== ЭТАП 3: Проверка ipset ===" >> "$RESULT_LOG"
TOTAL_IPSET=0
for setname in unblocksh unblockhysteria2 unblocktor unblockvless unblocktroj; do
    if ipset list "$setname" -n >/dev/null 2>&1; then
        count=$(ipset list "$setname" 2>/dev/null | tail -n +7 | grep -c "^[0-9]")
        count=${count:-0}
        TOTAL_IPSET=$((TOTAL_IPSET + count))
        if [ "$count" -gt 0 ]; then
            echo "  [PASS] $setname: $count entries" >> "$RESULT_LOG"
            PASS=$((PASS + 1))
        else
            echo "  [WARN] $setname: 0 entries (пустой список)" >> "$RESULT_LOG"
            WARN=$((WARN + 1))
        fi
    else
        echo "  [FAIL] $setname: не создан" >> "$RESULT_LOG"
        FAIL=$((FAIL + 1))
    fi
done
echo "  TOTAL ipset entries: $TOTAL_IPSET" >> "$RESULT_LOG"
echo "" >> "$RESULT_LOG"

# ============================================================
# ЭТАП 4: Проверка iptables
# ============================================================
echo "=== ЭТАП 4: Проверка iptables ===" >> "$RESULT_LOG"

# NAT PREROUTING — DNAT и REDIRECT правила
nat_rules=$(iptables -t nat -L PREROUTING -n 2>/dev/null | grep -c "REDIRECT\|DNAT")
nat_rules=${nat_rules:-0}
if [ "$nat_rules" -gt 0 ]; then
    echo "  [PASS] iptables nat PREROUTING: $nat_rules rules" >> "$RESULT_LOG"
    PASS=$((PASS + 1))
else
    echo "  [FAIL] iptables nat PREROUTING: нет правил" >> "$RESULT_LOG"
    FAIL=$((FAIL + 1))
fi

# Mangle PREROUTING — VPN mark rules
mangle_rules=$(iptables -t mangle -L PREROUTING -n 2>/dev/null | grep -c "MARK\|CONNMARK")
mangle_rules=${mangle_rules:-0}
if [ "$mangle_rules" -gt 0 ]; then
    echo "  [PASS] iptables mangle PREROUTING: $mangle_rules rules" >> "$RESULT_LOG"
    PASS=$((PASS + 1))
else
    echo "  [WARN] iptables mangle PREROUTING: нет VPN mark rules" >> "$RESULT_LOG"
    WARN=$((WARN + 1))
fi

echo "" >> "$RESULT_LOG"

# ============================================================
# ЭТАП 5: Проверка dnsmasq
# ============================================================
echo "=== ЭТАП 5: Проверка dnsmasq ===" >> "$RESULT_LOG"

if netstat -tlnp 2>/dev/null | grep -q ":5353 " || ss -tlnp 2>/dev/null | grep -q ":5353 "; then
    echo "  [PASS] dnsmasq слушает порт 5353" >> "$RESULT_LOG"
    PASS=$((PASS + 1))
else
    echo "  [WARN] dnsmasq НЕ слушает порт 5353" >> "$RESULT_LOG"
    WARN=$((WARN + 1))
fi

if ps | grep -v grep | grep -q dnsmasq; then
    echo "  [PASS] dnsmasq процесс запущен" >> "$RESULT_LOG"
    PASS=$((PASS + 1))
else
    echo "  [FAIL] dnsmasq процесс НЕ запущен" >> "$RESULT_LOG"
    FAIL=$((FAIL + 1))
fi

echo "" >> "$RESULT_LOG"

# ============================================================
# ЭТАП 6: Проверка watchdog
# ============================================================
echo "=== ЭТАП 6: Проверка watchdog ===" >> "$RESULT_LOG"

if [ -x "/opt/bin/dnsmasq_watchdog.sh" ]; then
    if ps | grep -v grep | grep -q dnsmasq_watchdog; then
        echo "  [PASS] dnsmasq_watchdog запущен" >> "$RESULT_LOG"
        PASS=$((PASS + 1))
    else
        echo "  [WARN] dnsmasq_watchdog не запущен (скрипт есть, процесс нет)" >> "$RESULT_LOG"
        WARN=$((WARN + 1))
    fi
else
    echo "  [WARN] dnsmasq_watchdog.sh не найден" >> "$RESULT_LOG"
    WARN=$((WARN + 1))
fi

echo "" >> "$RESULT_LOG"

# ============================================================
# ЭТАП 7: Проверка DNS и интернета
# ============================================================
echo "=== ЭТАП 7: Проверка DNS и интернета ===" >> "$RESULT_LOG"

if nslookup google.com 8.8.8.8 >/dev/null 2>&1; then
    echo "  [PASS] DNS через 8.8.8.8" >> "$RESULT_LOG"
    PASS=$((PASS + 1))
else
    echo "  [FAIL] DNS через 8.8.8.8 — недоступен" >> "$RESULT_LOG"
    FAIL=$((FAIL + 1))
fi

if nslookup google.com 127.0.0.1 >/dev/null 2>&1; then
    echo "  [PASS] DNS через 127.0.0.1" >> "$RESULT_LOG"
    PASS=$((PASS + 1))
else
    echo "  [WARN] DNS через 127.0.0.1 — недоступен" >> "$RESULT_LOG"
    WARN=$((WARN + 1))
fi

if curl -s --max-time 5 http://google.com >/dev/null 2>&1; then
    echo "  [PASS] Интернет доступен" >> "$RESULT_LOG"
    PASS=$((PASS + 1))
else
    echo "  [FAIL] Интернет недоступен" >> "$RESULT_LOG"
    FAIL=$((FAIL + 1))
fi

echo "" >> "$RESULT_LOG"

# ============================================================
# ИТОГО
# ============================================================
echo "============================================================" >> "$RESULT_LOG"
echo " РЕЗУЛЬТАТ" >> "$RESULT_LOG"
echo "============================================================" >> "$RESULT_LOG"
echo "  PASS: $PASS" >> "$RESULT_LOG"
echo "  WARN: $WARN" >> "$RESULT_LOG"
echo "  FAIL: $FAIL" >> "$RESULT_LOG"
TOTAL=$((PASS + WARN + FAIL))
echo "  Всего: $TOTAL проверок" >> "$RESULT_LOG"
echo "" >> "$RESULT_LOG"

if [ "$FAIL" -eq 0 ]; then
    echo "  СТАТУС: OK (есть предупреждения)" >> "$RESULT_LOG"
else
    echo "  СТАТУС: FAIL (требуется исправление)" >> "$RESULT_LOG"
fi

echo "============================================================" >> "$RESULT_LOG"
echo "" >> "$RESULT_LOG"
echo "Полный лог: /opt/var/log/test_bypass_result.log" >> "$RESULT_LOG"

# Вывод на экран
cat "$RESULT_LOG"
