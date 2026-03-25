# Script.sh Adaptation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Адаптировать script.sh для текущего веб-проекта — заменить зависимости от Telegram-бота на веб-интерфейс.

**Architecture:** Script.sh должен устанавливать bypass_keenetic компоненты (Unblock, VPN сервисы, списки обхода), но НЕ устанавливать Telegram-бот. Вместо этого скрипт должен создавать конфигурацию для веб-интерфейса.

**Tech Stack:** Bash shell script, Python Flask

---

## Анализ различий

### Telegram-бот (test/) vs Веб-интерфейс (src/web_ui/)

| Компонент | Telegram-бот | Веб-интерфейс |
|-----------|--------------|---------------|
| **Директория** | `/opt/etc/bot/` | `/opt/etc/web_ui/` |
| **Конфигурация** | `bot_config.py` | `web_config.py` (генерируется) |
| **Init скрипт** | `S99telegram_bot` | `S99web_ui` |
| **Core модули** | `src/core/` | `core/` (в той же директории) |
| **Порт** | Не требуется | 8080 |

### Что НЕ нужно устанавливать

**Telegram-бот файлы:**
- ❌ `main.py` (aiogram бот)
- ❌ `handlers.py` (обработчики сообщений)
- ❌ `menu.py` (inline клавиатуры)
- ❌ `utils.py` (утилиты бота)
- ❌ `S99telegram_bot` (автозапуск бота)
- ❌ Core модули для бота

### Что НУЖНО установить

**Базовые компоненты bypass_keenetic:**
- ✅ Пакеты: curl, python3, python3-pip
- ✅ ipset скрипты для маршрутизации
- ✅ Шаблоны конфигураций (Tor, VLESS, Trojan, Shadowsocks)
- ✅ Списки обхода (unblocktor.txt, unblockvless.txt)
- ✅ Скрипты: unblock_ipset.sh, unblock_dnsmasq.sh, unblock_update.sh
- ✅ dnsmasq конфигурация
- ✅ crontab задачи
- ✅ Скрипты инициализации: S99unblock
- ✅ 100-redirect.sh, 100-unblock-vpn.sh
- ✅ keensnap.sh для бэкапов

**Веб-интерфейс:**
- ✅ Директория `/opt/etc/web_ui/`
- ✅ `web_config.py` (конфигурация)
- ✅ `S99web_ui` (автозапуск)
- ✅ requirements.txt и зависимости

---

## Необходимые изменения в script.sh

### 1. Изменить путь к конфигурации

**Было:**
```bash
BOT_CONFIG="/opt/etc/bot/bot_config.py"
BASE_URL=$(grep "^base_url" "$BOT_CONFIG" | awk -F'"' '{print $2}')
BOT_URL="$BASE_URL/src/bot3"
```

**Стало:**
```bash
WEB_CONFIG="/opt/etc/web_ui/core/web_config.py"
if [ ! -f "$WEB_CONFIG" ]; then
    echo "❌ Ошибка: Файл конфигурации $WEB_CONFIG не найден!" >&2
    exit 1
fi

BASE_URL=$(grep "^base_url" "$WEB_CONFIG" | awk -F'"' '{print $2}')
WEB_URL="$BASE_URL/src/web_ui"
```

### 2. Изменить пути из paths

**Заменить:**
- `BOT_DIR` → `WEB_DIR="/opt/etc/web_ui"`
- `INIT_BOT` → `INIT_WEB="/opt/etc/init.d/S99web_ui"`
- Убрать зависимости от `BOT_DIR/core`

### 3. Удалить установку файлов бота

**Удалить секции:**
- Загрузка `main.py`, `handlers.py`, `menu.py`, `utils.py`
- Загрузка core модулей (`config.py`, `env_parser.py`, и т.д.)
- Установка `S99telegram_bot`

### 4. Добавить установку веб-интерфейса

**Добавить:**
```bash
# Установка веб-интерфейса
echo "Загрузка файлов веб-интерфейса..."
mkdir -p "$WEB_DIR"
curl -s -o "$WEB_DIR/app.py" "$WEB_URL/app.py" || exit 1
curl -s -o "$WEB_DIR/routes.py" "$WEB_URL/routes.py" || exit 1
curl -s -o "$WEB_DIR/env_parser.py" "$WEB_URL/env_parser.py" || exit 1
curl -s -o "$WEB_DIR/requirements.txt" "$WEB_URL/requirements.txt" || exit 1
curl -s -o "$WEB_DIR/version.md" "$WEB_URL/version.md" || exit 1
curl -s -o "$WEB_DIR/.env.example" "$WEB_URL/.env.example" || echo "⚠️ Не удалось загрузить .env.example"

# Создание web_config.py
cat > "$WEB_DIR/core/web_config.py" << EOF
# Web Configuration
base_url = "$BASE_URL"
routerip = "$lanip"
# ... остальные параметры
EOF

echo "✅ Файлы веб-интерфейса загружены"
```

### 5. Обновить сообщения для пользователя

**Заменить:**
- "Через меню \"🔑 Ключи и мосты\"" → "Откройте http://192.168.1.1:8080"
- "бот будет перезапущен" → "веб-интерфейс будет перезапущен"

### 6. Обновить -update секцию

**Изменить логику обновления:**
- Обновлять файлы веб-интерфейса вместо файлов бота
- Перезапускать `S99web_ui` вместо `S99telegram_bot`

---

## План выполнения

### Task 1: Создать копию script.sh для веб-проекта

**Files:**
- Copy: `src/web_ui/scripts/script.sh` → `src/web_ui/scripts/script_web.sh`

### Task 2: Изменить пути к конфигурации

**Modify:** `src/web_ui/scripts/script_web.sh:1-30`

### Task 3: Удалить установку файлов бота

**Modify:** `src/web_ui/scripts/script_web.sh:230-280`

### Task 4: Добавить установку веб-интерфейса

**Modify:** `src/web_ui/scripts/script_web.sh:230-280` (заменить)

### Task 5: Обновить сообщения

**Modify:** `src/web_ui/scripts/script_web.sh` (все сообщения)

### Task 6: Обновить -update секцию

**Modify:** `src/web_ui/scripts/script_web.sh:320-380`

### Task 7: Переименовать в script.sh

**Replace:** `src/web_ui/scripts/script.sh`

### Task 8: Проверка и тестирование

**Test:** Синтаксис bash, логика установки

---

## Verification Checklist

- [ ] `base_url` читается из `web_config.py`
- [ ] Пути указывают на `/opt/etc/web_ui/`
- [ ] Файлы бота НЕ загружаются
- [ ] Файлы веб-интерфейса загружаются
- [ ] `S99web_ui` устанавливается
- [ ] Сообщения обновлены
- [ ] `-update` работает для веб-интерфейса
- [ ] Синтаксис bash валиден
