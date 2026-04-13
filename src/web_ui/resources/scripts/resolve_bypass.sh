#!/bin/sh
# resolve_bypass.sh - Параллельный DNS resolve для bypass списков
# Использует xargs для параллельного запуска nslookup
# Скорость: ~10-15 секунд для 240 доменов

FILE=$1
SETNAME=${2:-unblockvless}
DNS=${3:-8.8.8.8}
MAX_WORKERS=${4:-10}

if [ -z "$FILE" ]; then
    echo "Usage: $0 <bypass_file> [ipset_name] [dns_server] [max_workers]"
    exit 1
fi

ipset create $SETNAME hash:ip timeout 300 maxelem 1048576 -exist 2>/dev/null

TEMP=$(mktemp)
> $TEMP

grep -v '^#' "$FILE" | grep -v '^[0-9]' | grep -v '^$' | xargs -P $MAX_WORKERS -I{} sh -c "nslookup {} $DNS 2>/dev/null | grep '^Address:' | grep -v '$DNS\$' | awk '{print \$2}'" >> $TEMP 2>/dev/null

sort -u $TEMP | while read ip; do
    [ -n "$ip" ] && ipset add -exist $SETNAME $ip 2>/dev/null
done

rm -f $TEMP

COUNT=$(ipset list $SETNAME 2>/dev/null | tail -n +7 | wc -l)
echo "Done: $COUNT entries in $SETNAME"