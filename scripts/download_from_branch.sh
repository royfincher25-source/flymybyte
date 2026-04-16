#!/bin/sh
# download_from_branch.sh - Загрузка и применение обновления из指定ной ветки
# Использование: ./download_from_branch.sh [branch_name]
# По умолчанию: fix/keenetic-pgrep-compatibility

BRANCH="${1:-fix/keenetic-pgrep-compatibility}"
REPO="royfincher25-source/flymybyte"
LOG_FILE="/opt/var/log/download_from_branch.log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "========================================"
log "Download from branch: $BRANCH"
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

log "[1/7] Проверка доступности ветки..."
REPO_BASE="https://raw.githubusercontent.com/${REPO}/${BRANCH}"

HTTP_CODE=$(curl -sL -w "%{http_code}" -o /dev/null "${REPO_BASE}/VERSION" 2>&1)
if [ "$HTTP_CODE" != "200" ]; then
    log "ОШИБКА: Ветка $BRANCH недоступна (HTTP $HTTP_CODE)"
    exit 1
fi

log "Ветка доступна: $REPO_BASE"
log "VERSION: $(curl -sL "${REPO_BASE}/VERSION")"

log "[2/7] Создание резервной копии..."
BACKUP_DIR="/opt/var/backup_pre_branch_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"
cp "$CONSTANTS_FILE" "$BACKUP_DIR/" 2>/dev/null || true
log "Резервная копия: $BACKUP_DIR"

log "[3/7] Текущая ветка..."
CURRENT_BRANCH=$(grep "GITHUB_BRANCH" "$CONSTANTS_FILE" | grep -oP "'[^']+'" | head -1 | tr -d "'")
log "Текущая ветка: $CURRENT_BRANCH"

log "[4/7] Остановка веб-интерфейса..."
killall -9 python3 2>/dev/null || true
killall -9 web_ui 2>/dev/null || true
log "Web UI остановлен"

log "[5/7] Изменение GITHUB_BRANCH на $BRANCH..."

# BusyBox sed -i не работает, используем временный файл
sed "s/GITHUB_BRANCH = '[^']*'/GITHUB_BRANCH = '$BRANCH'/" "$CONSTANTS_FILE" > "$CONSTANTS_FILE.tmp"
mv "$CONSTANTS_FILE.tmp" "$CONSTANTS_FILE"

NEW_BRANCH=$(grep "GITHUB_BRANCH" "$CONSTANTS_FILE" | grep -oP "'[^']+'" | head -1 | tr -d "'")
log "Новая ветка: $NEW_BRANCH"

if [ "$NEW_BRANCH" != "$BRANCH" ]; then
    log "ОШИБКА: Не удалось изменить ветку"
    exit 1
fi

log "[6/7] Очистка кэша..."
rm -rf /opt/etc/web_ui/__pycache__ 2>/dev/null || true
find /opt/etc/web_ui -name "*.pyc" -delete 2>/dev/null || true

log "[7/7] Перезапуск сервисов..."

log "  - S99web_ui start..."
/opt/etc/init.d/S99web_ui restart 2>/dev/null || true

sleep 3

log "  - Проверка статуса..."
if curl -sf http://127.0.0.1:8080 > /dev/null 2>&1; then
    log "  Web UI запущен"
else
    log "  ВНИМАНИЕ: Web UI может быть недоступен"
fi

log "========================================"
log "Download from $BRANCH ЗАВЕРШЕН"
log "========================================"
log ""
log "Обновления будут загружаться из:"
log "  $REPO_BASE/"
log ""
log "Логи для отладки:"
log "  - tail -f /opt/var/log/web_ui.log"
log ""
log "Для отката к master:"
log "  sh rollback_to_master.sh"
log "Для восстановления из бэкапа:"
log "  cp $BACKUP_DIR/constants.py $CONSTANTS_FILE"
log "  /opt/etc/init.d/S99web_ui restart"