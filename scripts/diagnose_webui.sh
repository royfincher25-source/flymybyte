#!/bin/sh
# Диагностика веб-интерфейса flymybyte
# Использование: sh /opt/root/diagnose_webui.sh

echo "=========================================="
echo "  Диагностика Bypass Keenetic Web UI"
echo "=========================================="
echo ""

# 1. Проверка процесса
echo "1. Проверка процесса веб-интерфейса..."
ps | grep -E "python.*web_ui|waitress" | grep -v grep
if [ $? -ne 0 ]; then
    echo "   ❌ Процесс не найден"
else
    echo "   ✅ Процесс запущен"
fi
echo ""

# 2. Проверка порта 8080
echo "2. Проверка порта 8080..."
netstat -tlnp | grep :8080
if [ $? -ne 0 ]; then
    echo "   ❌ Порт 8080 не слушается"
else
    echo "   ✅ Порт 8080 открыт"
fi
echo ""

# 3. Проверка директории web_ui
echo "3. Проверка директории web_ui..."
if [ -d /opt/etc/web_ui ]; then
    echo "   ✅ Директория существует"
    ls -la /opt/etc/web_ui/ | head -10
else
    echo "   ❌ Директория не найдена"
fi
echo ""

# 4. Проверка .env файла
echo "4. Проверка .env файла..."
if [ -f /opt/etc/web_ui/.env ]; then
    echo "   ✅ .env существует"
    echo "   Содержимое (без пароля):"
    grep -v "WEB_PASSWORD" /opt/etc/web_ui/.env | sed 's/^/   /'
else
    echo "   ❌ .env не найден"
fi
echo ""

# 5. Проверка шаблонов
echo "5. Проверка шаблонов..."
TEMPLATE_DIR="/opt/etc/web_ui/templates"
if [ -d "$TEMPLATE_DIR" ]; then
    echo "   ✅ Директория templates существует"
    echo "   Шаблоны:"
    ls "$TEMPLATE_DIR" | sed 's/^/   - /'
    
    # Проверка ключевых шаблонов
    for tpl in base.html bypass.html bypass_catalog.html logs.html; do
        if [ -f "$TEMPLATE_DIR/$tpl" ]; then
            echo "   ✅ $tpl существует"
        else
            echo "   ❌ $tpl НЕ найден"
        fi
    done
else
    echo "   ❌ Директория templates не найдена"
fi
echo ""

# 6. Проверка директории unblock
echo "6. Проверка директории unblock..."
UNBLOCK_DIR="/opt/etc/unblock"
if [ -d "$UNBLOCK_DIR" ]; then
    echo "   ✅ Директория существует"
    ls -la "$UNBLOCK_DIR" | head -10
else
    echo "   ❌ Директория не найдена (это нормально для новой установки)"
fi
echo ""

# 7. Проверка логов
echo "7. Проверка логов..."
LOG_FILE="/opt/var/log/web_ui.log"
if [ -f "$LOG_FILE" ]; then
    echo "   ✅ Лог-файл существует"
    echo "   Размер: $(ls -lh "$LOG_FILE" | awk '{print $5}')"
    echo "   Последние 20 строк:"
    tail -20 "$LOG_FILE" | sed 's/^/   /'
    
    echo ""
    echo "   Последние ошибки (ERROR/CRITICAL):"
    grep -E "ERROR|CRITICAL" "$LOG_FILE" | tail -10 | sed 's/^/   /'
    if [ $? -ne 0 ]; then
        echo "   ✅ Ошибок не найдено"
    fi
else
    echo "   ❌ Лог-файл не найден"
fi
echo ""

# 8. Проверка зависимостей Python
echo "8. Проверка зависимостей Python..."
python3 -c "import flask; print('   ✅ Flask:', flask.__version__)" 2>&1
python3 -c "import jinja2; print('   ✅ Jinja2:', jinja2.__version__)" 2>&1
python3 -c "import werkzeug; print('   ✅ Werkzeug:', werkzeug.__version__)" 2>&1
python3 -c "import requests; print('   ✅ requests:', requests.__version__)" 2>&1
python3 -c "from waitress import serve; print('   ✅ waitress установлен')" 2>&1 || echo "   ⚠️ waitress не установлен (будет использоваться Flask dev server)"
echo ""

# 9. Тест импорта модулей
echo "9. Тест импорта модулей..."
cd /opt/etc/web_ui 2>/dev/null
python3 -c "from core.app_config import WebConfig; c = WebConfig(); print('   ✅ WebConfig:', c.to_dict())" 2>&1
if [ $? -ne 0 ]; then
    echo "   ❌ Ошибка импорта WebConfig"
fi

python3 -c "from core.list_catalog import get_catalog; c = get_catalog(); print('   ✅ get_catalog:', list(c.keys()) if c else 'пусто')" 2>&1
if [ $? -ne 0 ]; then
    echo "   ❌ Ошибка импорта get_catalog"
fi
echo ""

# 10. Проверка маршрутов Flask
echo "10. Тест маршрутов Flask..."
cd /opt/etc/web_ui 2>/dev/null
python3 -c "
from app import create_app
app = create_app()
with app.app_context():
    rules = [str(r) for r in app.url_map.iter_rules()]
    bypass_rules = [r for r in rules if 'bypass' in r]
    print('   ✅ Маршруты с bypass:')
    for r in bypass_rules:
        print('     -', r)
" 2>&1
if [ $? -ne 0 ]; then
    echo "   ❌ Ошибка проверки маршрутов"
fi
echo ""

# 11. curl тест
echo "11. Тест доступности HTTP..."
curl -I http://localhost:8080/ 2>&1 | head -5
if [ $? -eq 0 ]; then
    echo "   ✅ HTTP ответ получен"
else
    echo "   ❌ HTTP запрос не удался"
fi
echo ""

echo "=========================================="
echo "  Диагностика завершена"
echo "=========================================="
echo ""
echo "Рекомендации:"
echo "1. Если процесс не запущен: /opt/etc/init.d/S99web_ui start"
echo "2. Если порт не слушается: проверьте firewall"
echo "3. Если шаблоны не найдены: переустановите веб-интерфейс"
echo "4. Если ошибки в логах: отправьте логи на анализ"
