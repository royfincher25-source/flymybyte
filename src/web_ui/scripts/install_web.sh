#!/bin/sh
# =============================================================================
# FLYMYBYTE WEB UI - MINIMAL INSTALLER
# =============================================================================
# Установка в одну команду:
#   curl -sL https://raw.githubusercontent.com/royfincher25-source/flymybyte/master/src/web_ui/install_web.sh | sh
# =============================================================================

set -e

WEB_DIR="/opt/etc/web_ui"
GITHUB_REPO="royfincher25-source/flymybyte"
GITHUB_BRANCH="master"
BASE_URL="https://raw.githubusercontent.com/${GITHUB_REPO}/${GITHUB_BRANCH}/src/web_ui"

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() {
    echo "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo "${RED}❌ $1${NC}"
}

# =============================================================================
# ПРОВЕРКА ТРЕБОВАНИЙ
# =============================================================================
log_info "=== Bypass Keenetic Web UI Installer ==="
echo ""

# Проверка Python
if ! command -v python3 >/dev/null 2>&1; then
    log_error "Python3 не найден"
    echo "Установите: opkg install python3"
    exit 1
fi
log_success "Python3 найден: $(python3 --version)"

# Проверка pip
if ! command -v pip3 >/dev/null 2>&1; then
    log_error "pip3 не найден"
    echo "Установите: opkg install python3-pip"
    exit 1
fi
log_success "pip3 найден: $(pip3 --version)"

# Проверка curl
if ! command -v curl >/dev/null 2>&1; then
    log_error "curl не найден"
    echo "Установите: opkg install curl"
    exit 1
fi
log_success "curl найден"

# Проверка свободного места
FREE_SPACE=$(df -m /opt 2>/dev/null | awk 'NR==2 {print $4}')
if [ -n "$FREE_SPACE" ] && [ "$FREE_SPACE" -lt 50 ]; then
    log_warning "Мало свободного места: ${FREE_SPACE}MB (рекомендуется 50MB+)"
else
    log_success "Свободное место: ${FREE_SPACE}MB"
fi

echo ""

# =============================================================================
# СОЗДАНИЕ ДИРЕКТОРИИ
# =============================================================================
log_info "📁 Создание директории: $WEB_DIR"
mkdir -p "$WEB_DIR"
cd "$WEB_DIR"

# =============================================================================
# ЗАГРУЗКА ФАЙЛОВ ВЕБ-ИНТЕРФЕЙСА
# =============================================================================
log_info "⏳ Загрузка файлов веб-интерфейса..."

# Основные файлы
FILES="app.py routes.py env_parser.py requirements.txt .env.example"
for file in $FILES; do
    printf "  → %-20s" "$file"
    if curl -sL -o "$file" "$BASE_URL/$file"; then
        echo " ✅"
    else
        echo " ❌"
    fi
done

# VERSION загружается из корня репозитория
printf "  → %-20s" "VERSION"
VERSION_URL="https://raw.githubusercontent.com/${GITHUB_REPO}/${GITHUB_BRANCH}/VERSION"
if curl -sL -o "VERSION" "$VERSION_URL"; then
    echo " ✅"
else
    echo " ❌"
fi

# =============================================================================
# ЗАГРУЗКА CORE МОДУЛЕЙ
# =============================================================================
log_info "⏳ Загрузка core модулей..."
mkdir -p core
cd core

# Загружаем все .py файлы из core/
for file in __init__.py app_config.py config.py utils.py services.py ipset_manager.py list_catalog.py dns_manager.py dns_monitor.py dns_resolver.py dns_spoofing.py web_config.py; do
    printf "  → %-20s" "$file"
    if curl -sL -o "$file" "$BASE_URL/core/$file"; then
        echo " ✅"
    else
        echo " ❌"
    fi
done
cd ..

# =============================================================================
# ЗАГРУЗКА ШАБЛОНОВ
# =============================================================================
log_info "⏳ Загрузка шаблонов..."
mkdir -p templates
cd templates

TEMPLATES="base.html login.html index.html keys.html bypass.html install.html stats.html service.html updates.html bypass_view.html bypass_add.html bypass_remove.html bypass_catalog.html key_generic.html backup.html dns_monitor.html logs.html dns_spoofing.html"
for file in $TEMPLATES; do
    printf "  → %-20s" "$file"
    if curl -sL -o "$file" "$BASE_URL/templates/$file"; then
        echo " ✅"
    else
        echo " ❌"
    fi
done
cd ..

# =============================================================================
# ЗАГРУЗКА СТАТИКИ
# =============================================================================
log_info "⏳ Загрузка статических файлов..."
mkdir -p static
cd static

printf "  → %-20s" "style.css"
if curl -sL -o "style.css" "$BASE_URL/static/style.css"; then
    echo " ✅"
else
    echo " ❌"
fi
cd ..

# =============================================================================
# ЗАГРУЗКА СКРИПТА УСТАНОВКИ
# =============================================================================
log_info "⏳ Загрузка скрипта установки bypass_keenetic..."
mkdir -p scripts
cd scripts

    printf "  → %-20s" "script.sh"
    if curl -sL -o "script.sh" "$BASE_URL/scripts/script.sh"; then
        chmod 755 "script.sh"
        echo " ✅"
    else
        echo " ❌"
    fi
cd ..

# =============================================================================
# ЗАГРУЗКА РЕСУРСОВ (СПИСКИ, КОНФИГИ, СКРИПТЫ)
# =============================================================================
log_info "⏳ Загрузка ресурсов..."
mkdir -p resources/lists resources/config resources/scripts
cd resources

# Списки доменов
printf "  → %-20s" "lists/unblock-ai-domains.txt"
if curl -sL -o "lists/unblock-ai-domains.txt" "$BASE_URL/resources/lists/unblock-ai-domains.txt"; then
    echo " ✅"
else
    echo " ❌"
fi

# Конфигурации
printf "  → %-20s" "config/unblock-ai.dnsmasq.template"
if curl -sL -o "config/unblock-ai.dnsmasq.template" "$BASE_URL/resources/config/unblock-ai.dnsmasq.template"; then
    echo " ✅"
else
    echo " ❌"
fi

# Скрипты
printf "  → %-20s" "scripts/unblock_dnsmasq.sh"
if curl -sL -o "scripts/unblock_dnsmasq.sh" "$BASE_URL/resources/scripts/unblock_dnsmasq.sh"; then
    chmod 755 "scripts/unblock_dnsmasq.sh"
    echo " ✅"
else
    echo " ❌"
fi
cd ..

# =============================================================================
# СОЗДАНИЕ .ENV
# =============================================================================
log_info "⏳ Создание конфигурации..."
if [ ! -f .env ]; then
    cat > .env << 'EOF'
# Bypass Keenetic Web UI Configuration
WEB_HOST=0.0.0.0
WEB_PORT=8080
WEB_PASSWORD=changeme
ROUTER_IP=192.168.1.1
UNBLOCK_DIR=/opt/etc/unblock/
LOG_FILE=/opt/var/log/web_ui.log
EOF
    log_warning "Пароль по умолчанию: changeme"
    log_info "Измените пароль в .env после первого входа!"
else
    log_success ".env уже существует"
fi

# =============================================================================
# УСТАНОВКА ЗАВИСИМОСТЕЙ
# =============================================================================
log_info "⏳ Установка зависимостей (это может занять несколько минут)..."
if pip3 install -r requirements.txt >/dev/null 2>&1; then
    log_success "Зависимости установлены"
else
    log_error "Не удалось установить зависимости"
    echo "Попробуйте вручную: pip3 install -r requirements.txt"
    exit 1
fi

# =============================================================================
# СОЗДАНИЕ WEB_CONFIG.PY
# =============================================================================
log_info "⏳ Создание web_config.py..."
cat > core/web_config.py << 'EOF'
# =============================================================================
# WEB CONFIGURATION
# Auto-generated by install_web.sh
# =============================================================================

base_url = "https://raw.githubusercontent.com/royfincher25-source/flymybyte/master"
routerip = "192.168.1.1"

localportsh = 8388
dnsporttor = 5300
localporttor = 9080
localportvless = 10000
localporttrojan = 10001
dnsovertlsport = 10002
dnsoverhttpsport = 10003

unblock_dir = "/opt/etc/unblock/"
tor_config = "/opt/etc/tor/torrc"
shadowsocks_config = "/opt/etc/shadowsocks.json"
trojan_config = "/opt/etc/trojan/config.json"
vless_config = "/opt/etc/xray/config.json"
templates_dir = "/opt/etc/web_ui/templates/"
dnsmasq_conf = "/opt/etc/dnsmasq.conf"
crontab = "/opt/etc/crontab"
redirect_script = "/opt/etc/ndm/netfilter.d/100-redirect.sh"
vpn_script = "/opt/etc/ndm/ifstatechanged.d/100-unblock-vpn.sh"
ipset_script = "/opt/etc/ndm/fs.d/100-ipset.sh"
unblock_ipset = "/opt/bin/unblock_ipset.sh"
unblock_dnsmasq = "/opt/bin/unblock_dnsmasq.sh"
unblock_update = "/opt/bin/unblock_update.sh"
script_sh = "/opt/root/script.sh"
web_dir = "/opt/etc/web_ui"
tor_tmp_dir = "/opt/tmp/tor"
tor_dir = "/opt/etc/tor"
xray_dir = "/opt/etc/xray"
trojan_dir = "/opt/etc/trojan"
init_shadowsocks = "/opt/etc/init.d/S22shadowsocks"
init_trojan = "/opt/etc/init.d/S22trojan"
init_xray = "/opt/etc/init.d/S24xray"
init_tor = "/opt/etc/init.d/S35tor"
init_dnsmasq = "/opt/etc/init.d/S56dnsmasq"
init_unblock = "/opt/etc/init.d/S99unblock"
init_web = "/opt/etc/init.d/S99web_ui"
hosts_file = "/opt/etc/hosts"
EOF
log_success "web_config.py создан"

# =============================================================================
# ЗАПУСК ВЕБ-ИНТЕРФЕЙСА
# =============================================================================
log_info "🚀 Запуск веб-интерфейса..."

# Остановить предыдущий процесс если есть
pkill -f "python.*app.py" 2>/dev/null || true
sleep 1

# Запустить в фоне (без nohup для совместимости)
cd "$WEB_DIR"
python3 app.py > /opt/var/log/web_ui.log 2>&1 &
sleep 2

# Проверка запуска
if pgrep -f "python.*app.py" >/dev/null; then
    log_success "Веб-интерфейс запущен"
else
    log_error "Не удалось запустить веб-интерфейс"
    echo "Проверьте логи: tail /opt/var/log/web_ui.log"
    exit 1
fi

# =============================================================================
# ИТОГОВАЯ ИНФОРМАЦИЯ
# =============================================================================
echo ""
log_success "=== Установка завершена! ==="
echo ""
echo "🌐 Веб-интерфейс доступен по адресу:"
echo "   http://192.168.1.1:8080"
echo ""
echo "🔑 Пароль по умолчанию:"
echo "   changeme"
echo ""
echo "⚠️  Измените пароль в .env после первого входа!"
echo ""
echo "📋 Дальнейшие шаги:"
echo "   1. Откройте http://192.168.1.1:8080 в браузере"
echo "   2. Войдите с паролем из .env"
echo "   3. Перейдите в '📲 Установка и удаление'"
echo "   4. Нажмите 'Установить' для загрузки bypass_keenetic"
echo ""
log_info "Логи: tail -f /opt/var/log/web_ui.log"
