#!/bin/sh
# resolve_bypass.sh - DNS resolve для bypass списков
# Резолвит домены из файла и добавляет IP в ipset
#
# Usage: resolve_bypass.sh <bypass_file> [ipset_name] [dns_server]

FILE="$1"
SETNAME="${2:-unblockvless}"
DNS="${3:-8.8.8.8}"

if [ -z "$FILE" ] || [ ! -f "$FILE" ]; then
    echo "Usage: $0 <bypass_file> [ipset_name] [dns_server]"
    exit 1
fi

# Создать ipset если не существует (hash:ip, timeout 300)
ipset create "$SETNAME" hash:ip timeout 300 maxelem 1048576 -exist 2>/dev/null

TEMP_IPS=$(mktemp)
> "$TEMP_IPS"

COUNT_RESOLVED=0
COUNT_FAILED=0

# Читаем файл построчно, пропускаем комментарии, IP/CIDR, пустые строки
while IFS= read -r line; do
    # Убираем пробелы
    line=$(echo "$line" | tr -d '\r' | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')

    # Пропускаем пустые строки
    [ -z "$line" ] && continue

    # Пропускаем комментарии
    case "$line" in
        \#*) continue ;;
    esac

    # Пропускаем IP-адреса и CIDR (начинаются с цифры)
    case "$line" in
        [0-9]*) continue ;;
    esac

    # Пропускаем wildcard (начинаются с *) — они резолвятся через nslookup
    # но nslookup не понимает *.domain — убираем *
    domain="$line"
    case "$domain" in
        \*.*) domain=$(echo "$domain" | sed 's/^\*\.//') ;;
    esac

    # Пропускаем строки с @ (метки типа @ads)
    case "$domain" in
        *@*) continue ;;
    esac

    # Резолвим домен через nslookup
    if [ -n "$domain" ]; then
        result=$(nslookup "$domain" "$DNS" 2>/dev/null)
        if [ $? -eq 0 ]; then
            # Извлекаем IPv4 адреса (исключая DNS сервер)
            echo "$result" | grep '^Address:' | grep -v "$DNS" | while read -r _ addr; do
                # Только IPv4 (пропускаем IPv6)
                case "$addr" in
                    *:*) ;;  # skip IPv6
                    *) echo "$addr" >> "$TEMP_IPS" ;;
                esac
            done
            COUNT_RESOLVED=$((COUNT_RESOLVED + 1))
        else
            COUNT_FAILED=$((COUNT_FAILED + 1))
        fi
    fi
done < "$FILE"

# Добавляем уникальные IP в ipset
if [ -s "$TEMP_IPS" ]; then
    echo "DEBUG: Adding IPs from $TEMP_IPS:" >&2
    cat "$TEMP_IPS" >&2
    sort -u "$TEMP_IPS" | while read -r ip; do
        if [ -n "$ip" ]; then
            echo "DEBUG: Adding $ip to $SETNAME" >&2
            ipset add -exist "$SETNAME" "$ip" 2>&1 || echo "DEBUG: FAILED to add $ip: $?" >&2
        fi
    done
fi

FINAL_COUNT=$(ipset list "$SETNAME" 2>/dev/null | tail -n +7 | grep -c '^[0-9]')

rm -f "$TEMP_IPS"

echo "Resolved: $COUNT_RESOLVED domains, Failed: $COUNT_FAILED, IP in $SETNAME: $FINAL_COUNT"
