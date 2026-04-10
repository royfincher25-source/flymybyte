#!/bin/sh
# update_to_refactoring.sh - Обновление до версии с рефакторингом (Этап 1)
# Включает: parsers.py, service_ops.py, services.py (сокращён)

LOG_FILE="/opt/var/log/update_to_refactoring.log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "========================================"
log "Обновление до refactoring-phase1"
log "========================================"

if [ ! -d "/opt/etc/web_ui" ]; then
    log "ОШИБКА: Не найдена директория /opt/etc/web_ui"
    exit 1
fi

log "[1/7] Создание резервной копии..."
BACKUP_DIR="/opt/var/backup_pre_refactoring_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"
cp -r /opt/etc/web_ui/core "$BACKUP_DIR/" 2>/dev/null || true
cp -r /opt/etc/web_ui/routes_*.py "$BACKUP_DIR/" 2>/dev/null || true
cp -r /opt/etc/web_ui/resources/scripts "$BACKUP_DIR/" 2>/dev/null || true
log "Резервная копия: $BACKUP_DIR"

log "[2/7] Остановка веб-интерфейса..."
killall -9 python3 2>/dev/null || true
killall -9 web_ui 2>/dev/null || true

log "[3/7] Определение URL репозитория..."
CURRENT_BRANCH=$(git -C /opt/etc/web_ui rev-parse --abbrev-ref HEAD 2>/dev/null || echo "master")
log "Текущая ветка: $CURRENT_BRANCH"

REPO_BASE="https://raw.githubusercontent.com/royfincher25-source/flymybyte/feature/refactoring-phase1-services/src/web_ui"
log "URL: $REPO_BASE"

log "[4/7] Загрузка новых файлов..."

download_file() {
    local src="$1"
    local dest="$2"
    log "  Загрузка: $src -> $dest"
    
    HTTP_CODE=$(curl -sL -w "%{http_code}" -o "$dest" "$REPO_BASE/$src" 2>&1)
    CURL_EXIT=$?
    
    if [ $CURL_EXIT -ne 0 ]; then
        log "    ОШИБКА: curl exit code = $CURL_EXIT"
        return 1
    fi
    
    if [ "$HTTP_CODE" != "200" ]; then
        log "    ОШИБКА: HTTP code = $HTTP_CODE"
        return 1
    fi
    
    if [ ! -s "$dest" ]; then
        log "    ОШИБКА: файл пустой или не создан"
        return 1
    fi
    
    SIZE=$(ls -l "$dest" | awk '{print $5}')
    log "    OK (${SIZE} bytes)"
    return 0
}

download_file "core/parsers.py" "/opt/etc/web_ui/core/parsers.py" || { log "ОШИБКА: parsers.py"; exit 1; }
download_file "core/service_ops.py" "/opt/etc/web_ui/core/service_ops.py" || { log "ОШИБКА: service_ops.py"; exit 1; }
download_file "core/services.py" "/opt/etc/web_ui/core/services.py" || { log "ОШИБКА: services.py"; exit 1; }
download_file "core/__init__.py" "/opt/etc/web_ui/core/__init__.py" || { log "ОШИБКА: __init__.py"; exit 1; }

log "[5/7] Очистка кэша..."
rm -rf /opt/etc/web_ui/__pycache__ 2>/dev/null || true
find /opt/etc/web_ui -name "*.pyc" -delete 2>/dev/null || true

log "[6/7] Тестирование Python модулей..."
if /opt/bin/python3 -c "import sys; sys.path.insert(0, '/opt/etc/web_ui'); from core.parsers import parse_vless_key; from core.service_ops import check_service_status; print('OK')" 2>&1 | tee -a "$LOG_FILE"; then
    log "  Python модули загружаются корректно"
else
    log "  ВНИМАНИЕ: Ошибка загрузки Python модулей"
fi

log "[7/7] Перезапуск сервисов..."

log "  - dnsmasq restart..."
/opt/etc/init.d/S56dnsmasq restart 2>/dev/null || true

log "  - S99unblock start..."
/opt/etc/init.d/S99unblock start 2>/dev/null || log "    (запуск через shell)"

log "  - web_ui start..."
cd /opt/etc/web_ui
python3 app.py > /opt/var/log/web_ui.log 2>&1 &
PID=$!
echo $PID > /var/run/web_ui.pid
log "    Started (PID=$PID)"
sleep 3

log "========================================"
log "Обновление до refactoring-phase1 ЗАВЕРШЕНО"
log "========================================"
log ""
log "Логи для отладки:"
log "  - tail -f /opt/var/log/web_ui.log"
log "  - tail -f /opt/var/log/S99unblock.log"
log ""
log "Для отката: sh $BACKUP_DIR/restore.sh"
log "Для стабильной версии: sh /opt/bin/update_to_stable.sh"