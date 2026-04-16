#!/bin/sh
# rollback_to_master.sh - Откат к стабильной версии (master)
# Используется если обновление из fix/keenetic-pgrep-compatibility сломано

LOG_FILE="/opt/var/log/rollback_to_master.log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "========================================"
log "Rollback to MASTER branch"
log "========================================"

if [ ! -d "/opt/etc/web_ui" ]; then
    log "ОШИБКА: Не найдена директория /opt/etc/web_ui"
    log "Этот скрипт нужно запускать на роутере Keenetic"
    exit 1
fi

CONSTANTS_FILE="/opt/etc/web_ui/core/constants.py"
if [ ! -f "$CONSTANTS_FILE" ]; then
    log "ОШИБКА: constants.py не найден"
    exit 1
fi

log "[1/5] Проверка текущей ветки..."
CURRENT_BRANCH=$(grep "GITHUB_BRANCH" "$CONSTANTS_FILE" | grep -oP "'[^']+'" | head -1 | tr -d "'")
log "Текущая ветка: $CURRENT_BRANCH"

if [ "$CURRENT_BRANCH" = "master" ]; then
    log "Уже на master, откат не требуется"
    exit 0
fi

log "[2/5] Создание резервной копии..."
BACKUP_DIR="/opt/var/backup_pre_rollback_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"
cp "$CONSTANTS_FILE" "$BACKUP_DIR/" 2>/dev/null || true
log "Резервная копия: $BACKUP_DIR"

log "[3/5] Остановка веб-интерфейса..."
killall -9 python3 2>/dev/null || true
killall -9 web_ui 2>/dev/null || true
log "Web UI остановлен"

log "[4/5] Изменение GITHUB_BRANCH на master..."

sed -i "s/GITHUB_BRANCH = '[^']*'/GITHUB_BRANCH = 'master'/" "$CONSTANTS_FILE"

NEW_BRANCH=$(grep "GITHUB_BRANCH" "$CONSTANTS_FILE" | grep -oP "'[^']+'" | head -1 | tr -d "'")
log "Новая ветка: $NEW_BRANCH"

if [ "$NEW_BRANCH" != "master" ]; then
    log "ОШИБКА: Не удалось изменить ветку"
    exit 1
fi

log "[5/5] Перезапуск сервисов..."

log "  - S99web_ui restart..."
/opt/etc/init.d/S99web_ui restart 2>/dev/null || true

sleep 2

log "  - Проверка статуса..."
if curl -sf http://127.0.0.1:8080 > /dev/null 2>&1; then
    log "  Web UI запущен"
else
    log "  ВНИМАНИЕ: Web UI может быть недоступен"
fi

log "========================================"
log "Rollback to MASTER ЗАВЕРШЕН"
log "========================================"
log ""
log "Обновления будут загружаться из:"
log "  https://raw.githubusercontent.com/royfincher25-source/flymybyte/master/"
log ""
log "Для восстановления из бэкапа:"
log "  cp $BACKUP_DIR/constants.py $CONSTANTS_FILE"
log "  /opt/etc/init.d/S99web_ui restart"