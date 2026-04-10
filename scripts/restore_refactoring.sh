#!/bin/sh
# restore_refactoring.sh - Восстановление из резервной копии после refactoring

LOG_FILE="/opt/var/log/restore_refactoring.log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "========================================"
log "Восстановление из резервной копии"
log "========================================"

log "[1/4] Остановка сервисов..."
killall -9 python3 2>/dev/null || true

log "[2/4] Поиск резервной копии..."
LATEST_BACKUP=$(ls -td /opt/var/backup_pre_refactoring_* 2>/dev/null | head -1)

if [ -z "$LATEST_BACKUP" ]; then
    log "ОШИБКА: Резервная копия не найдена"
    log "Доступные backup:"
    ls -la /opt/var/ | grep backup || true
    exit 1
fi

log "Найдена резервная копия: $LATEST_BACKUP"

log "[3/4] Восстановление файлов..."
cp -f "$LATEST_BACKUP/core/"* /opt/etc/web_ui/core/ 2>/dev/null || true
cp -f "$LATEST_BACKUP/routes_"* /opt/etc/web_ui/ 2>/dev/null || true
cp -f "$LATEST_BACKUP/resources/scripts/"* /opt/etc/web_ui/resources/scripts/ 2>/dev/null || true

log "  - Восстановлено из $LATEST_BACKUP"

log "[4/4] Перезапуск сервисов..."
rm -rf /opt/etc/web_ui/__pycache__ 2>/dev/null || true

/opt/etc/init.d/S56dnsmasq restart 2>/dev/null || true
/opt/etc/init.d/S99unblock start 2>/dev/null || true

cd /opt/etc/web_ui
python3 app.py > /opt/var/log/web_ui.log 2>&1 &
PID=$!
echo $PID > /var/run/web_ui.pid
log "  Started (PID=$PID)"

log "========================================"
log "Восстановление завершено"
log "========================================"