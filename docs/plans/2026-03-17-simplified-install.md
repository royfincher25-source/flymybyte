# Simplified Installation Plan

> **Goal:** Максимально упростить установку — загружаем только web_ui, остальное по кнопке

**Architecture:** 
1. **Step 1:** Минимальный скрипт установки (1 файл) → загружает web_ui + dependencies
2. **Step 2:** Через веб-интерфейс кнопка "Установить" → загружает все ресурсы и настраивает bypass_keenetic

**Tech Stack:** Bash, Python Flask, requests

---

## Current Problems

1. ❌ 21 файл ресурсов нужно копировать вручную
2. ❌ Сложная настройка web_config.py перед установкой
3. ❌ Много шагов для начала работы

## Solution

### Phase 1: Minimal Installer (5 минут)

**Создать:** `install_web.sh` — один скрипт который:
- ✅ Проверяет Python, pip
- ✅ Создаёт директорию `/opt/etc/web_ui/`
- ✅ Загружает web_ui с GitHub
- ✅ Устанавливает зависимости (Flask и др.)
- ✅ Создаёт минимальный .env
- ✅ Запускает веб-интерфейс

**Команда:**
```bash
curl -s https://raw.githubusercontent.com/.../install_web.sh | sh
```

### Phase 2: Web UI Installer

**Веб-интерфейс** после запуска:
- ✅ Кнопка "Установить bypass_keenetic"
- ✅ Загружает все ресурсы (scripts, templates, configs, lists)
- ✅ Создаёт web_config.py
- ✅ Запускает script.sh -install
- ✅ Показывает прогресс

---

## Tasks

### Task 1: Создать install_web.sh

**Files:**
- Create: `src/web_ui/install_web.sh`

**Content:**
```bash
#!/bin/sh
# Minimal web UI installer

echo "=== Bypass Keenetic Web UI Installer ==="

# Check Python
if ! command -v python3 >/dev/null 2>&1; then
    echo "❌ Python3 не найден. Установите: opkg install python3"
    exit 1
fi

# Check pip
if ! command -v pip3 >/dev/null 2>&1; then
    echo "❌ pip3 не найден. Установите: opkg install python3-pip"
    exit 1
fi

# Create directory
WEB_DIR="/opt/etc/web_ui"
echo "📁 Создание директории: $WEB_DIR"
mkdir -p "$WEB_DIR"

# Download web UI
echo "⏳ Загрузка файлов веб-интерфейса..."
cd "$WEB_DIR"

FILES="app.py routes.py env_parser.py requirements.txt .env.example version.md"
BASE_URL="https://raw.githubusercontent.com/royfincher25-source/bypass_keenetic-web/main/src/web_ui"

for file in $FILES; do
    echo "  → $file"
    curl -sLO "$BASE_URL/$file" || echo "⚠️ Не удалось загрузить $file"
done

# Download core modules
echo "⏳ Загрузка core модулей..."
mkdir -p core
cd core
CORE_FILES="config.py utils.py services.py ipset_manager.py list_catalog.py dns_manager.py app_config.py web_config.py __init__.py"
for file in $CORE_FILES; do
    echo "  → $file"
    curl -sLO "$BASE_URL/core/$file" || echo "⚠️ Не удалось загрузить $file"
done
cd ..

# Download templates
echo "⏳ Загрузка шаблонов..."
mkdir -p templates
cd templates
for file in base.html login.html index.html keys.html bypass.html install.html stats.html service.html updates.html; do
    echo "  → $file"
    curl -sLO "$BASE_URL/templates/$file" || echo "⚠️ Не удалось загрузить $file"
done
cd ..

# Download static
echo "⏳ Загрузка стилей..."
mkdir -p static
curl -sLO "$BASE_URL/static/style.css" || echo "⚠️ Не удалось загрузить style.css"

# Create .env
echo "⏳ Создание конфигурации..."
if [ ! -f .env ]; then
    cat > .env << 'EOF'
WEB_HOST=0.0.0.0
WEB_PORT=8080
WEB_PASSWORD=changeme
ROUTER_IP=192.168.1.1
UNBLOCK_DIR=/opt/etc/unblock/
LOG_FILE=/opt/var/log/web_ui.log
EOF
    echo "⚠️ Пароль по умолчанию: changeme (измените в .env!)"
fi

# Install dependencies
echo "⏳ Установка зависимостей..."
pip3 install -r requirements.txt

# Create minimal web_config.py
echo "⏳ Создание web_config.py..."
cat > core/web_config.py << 'EOF'
base_url = "https://raw.githubusercontent.com/royfincher25-source/bypass_keenetic/main"
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
templates_dir = "/opt/etc/bot/templates/"
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

# Start web UI
echo "🚀 Запуск веб-интерфейса..."
python3 app.py &

echo ""
echo "✅ Установка завершена!"
echo "🌐 Откройте: http://192.168.1.1:8080"
echo "🔑 Пароль: changeme (измените в .env!)"
```

### Task 2: Создать installer.py для веб-интерфейса

**Files:**
- Create: `src/web_ui/core/installer.py`

**Content:**
- Класс `WebUIInstaller`
- Метод `download_resources()` — загружает все ресурсы с GitHub
- Метод `create_config()` — создаёт web_config.py
- Метод `install_bypass()` — запускает script.sh -install
- Метод `get_progress()` — возвращает прогресс установки

### Task 3: Создать страницу установки

**Files:**
- Create: `src/web_ui/templates/install_wizard.html`
- Modify: `src/web_ui/routes.py`

**Content:**
- Пошаговый мастер установки
- Прогресс бар
- Лог установки в реальном времени
- Кнопка "Установить"

### Task 4: Обновить routes.py

**Files:**
- Modify: `src/web_ui/routes.py`

**Routes:**
- `POST /api/install/start` — начать установку
- `GET /api/install/status` — получить статус
- `GET /api/install/logs` — получить логи

### Task 5: Удалить resources/ из репозитория

**Files:**
- Remove: `src/web_ui/resources/`

**Reason:** Файлы будут загружаться динамически

### Task 6: Обновить документацию

**Files:**
- Modify: `README.md`
- Create: `INSTALL.md`

---

## Result

**Было (7 шагов):**
1. Скопировать web_ui (scp/git)
2. Скопировать resources/
3. Создать web_config.py
4. Создать .env
5. Установить зависимости
6. Запустить веб-интерфейс
7. Нажать "Установить" в веб-интерфейсе

**Стало (2 шага):**
1. Выполнить `curl ... | sh`
2. Нажать "Установить" в веб-интерфейсе

---

## Verification

- [ ] install_web.sh работает
- [ ] Веб-интерфейс запускается
- [ ] Кнопка "Установить" загружает ресурсы
- [ ] script.sh -install работает
- [ ] Все файлы на месте
