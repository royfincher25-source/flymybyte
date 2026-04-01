# flymybyte

Web-интерфейс для управления flymybyte на роутерах Keenetic.

## Описание

Веб-интерфейс для управления flymybyte на роутерах Keenetic через браузер.

## ⚡ Быстрая установка (2 шага!)

### Шаг 1: Установка веб-интерфейса (5 минут)

```bash
curl -sL https://raw.githubusercontent.com/royfincher25-source/flymybyte/master/src/web_ui/scripts/install_web.sh | sh
```

**Что делает скрипт:**
- ✅ Проверяет требования (Python 3.8+, pip3, curl)
- ✅ Загружает файлы веб-интерфейса с GitHub
- ✅ Устанавливает зависимости (Flask и др.)
- ✅ Создаёт конфигурацию (.env, web_config.py)
- ✅ Запускает веб-интерфейс

### Шаг 2: Установка flymybyte

1. Откройте http://192.168.1.1:8080 в браузере
2. Войдите с паролем из `/opt/etc/web_ui/.env` (по умолчанию: `changeme`)
3. Перейдите в **📲 Установка и удаление**
4. Нажмите **Установить**

**Что делает кнопка:**
- ✅ Загружает все ресурсы с GitHub (скрипты, шаблоны, конфиги, списки)
- ✅ Устанавливает пакеты (curl, python3-pip, dnsmasq и др.)
- ✅ Настраивает ipset, VPN, dnsmasq
- ✅ Запускает веб-интерфейс

**Готово!** 🎉

---

## Требования

- Python 3.8+
- Flask 3.0.0
- Jinja2 3.1.2
- Werkzeug 3.0.0
- requests >= 2.31.0
- waitress==2.1.2 (production server, опционально)

## Зависимости

### Основные зависимости

| Пакет | Версия | Размер | Назначение |
|-------|--------|--------|------------|
| **Flask** | 3.0.0 | ~2.5MB | Веб-фреймворк |
| **Jinja2** | 3.1.2 | ~1MB | Шаблонизатор |
| **Werkzeug** | 3.0.0 | ~1MB | WSGI-утилиты |
| **requests** | >=2.31.0 | ~500KB | HTTP-клиент |
| **waitress** | 2.1.2 | ~200KB | Production server |

**Итого:** ~7MB (с waitress), ~5MB (без waitress)

### Production server (waitress)

> [!tip] Рекомендуется для production
> Waitress легче чем gunicorn (~2MB vs ~5MB) и оптимизирован для embedded-устройств

**Настройки по умолчанию:**
- `threads=2` — минимум воркеров для 128MB RAM
- `connection_limit=10` — защита от перегрузки
- `cleanup_interval=30` — очистка каждые 30 секунд

**Если waitress не установлен:**
- Автоматический fallback на Flask development server
- Режим `threaded=True` для многопоточности

## Ручная установка

Если curl недоступен — установите вручную:

### Шаг 1: Копирование файлов

```bash
scp -r src/web_ui/ root@192.168.1.1:/opt/etc/web_ui/
```

### Шаг 2: Установка зависимостей

```bash
pip3 install -r /opt/etc/web_ui/requirements.txt
```

### Шаг 3: Настройка

```bash
cp /opt/etc/web_ui/.env.example /opt/etc/web_ui/.env
nano /opt/etc/web_ui/.env
```

### Шаг 4: Запуск

```bash
cd /opt/etc/web_ui
nohup python3 app.py > /opt/var/log/web_ui.log 2>&1 &
```

> [!important] Оптимизация для 128MB RAM
> Проект оптимизирован: ротация логов (100KB×3), LRU-кэш 50 записей, кэш статусов 30с TTL, ThreadPool 2 воркера.

### Установка dnsmasq (опционально)

> [!tip]
> **dnsmasq** обеспечивает автоматическое переключение DNS при отказе и кэширование запросов.
> Без dnsmasq DNS мониторинг работает, но не может автоматически обновлять конфигурацию.

**Базовая установка:**

```bash
# 1. Установить dnsmasq
opkg update
opkg install dnsmasq

# 2. Создать базовую конфигурацию
cat > /opt/etc/dnsmasq.conf << 'EOF'
# Базовая конфигурация dnsmasq
no-resolv
server=8.8.8.8
server=1.1.1.1
listen-address=127.0.0.1
cache-size=150
EOF

# 3. Запустить dnsmasq
/etc/init.d/S56dnsmasq start

# 4. Проверить статус
ps | grep dnsmasq
# Ожидается: dnsmasq запущен

# 5. Проверить логи
tail -f /opt/var/log/messages | grep dnsmasq
```

**Если скрипт не найден:**

```bash
# 1. Найти скрипт инициализации
find /opt/etc/init.d -name "*dnsmasq*"
ls -la /opt/etc/init.d/ | grep dns

# 2. Возможные альтернативы:
# /opt/etc/init.d/S61dnsmasq
# /opt/etc/init.d/dnsmasq

# 3. Запустить напрямую (если скрипт не найден)
dnsmasq --conf-file=/opt/etc/dnsmasq.conf &

# 4. Проверить процесс
ps | grep dnsmasq

# 5. Проверить порт 53
netstat -lnp | grep 53
# Ожидается: 127.0.0.1:53
```

**Создание скрипта инициализации (если не установлен):**

```bash
# 1. Создать скрипт
cat > /opt/etc/init.d/S56dnsmasq << 'EOF'
#!/bin/sh
case "$1" in
  start)
    echo "Starting dnsmasq..."
    /opt/bin/dnsmasq --conf-file=/opt/etc/dnsmasq.conf
    ;;
  stop)
    echo "Stopping dnsmasq..."
    pkill dnsmasq
    ;;
  restart)
    $0 stop
    sleep 1
    $0 start
    ;;
  *)
    echo "Usage: /opt/etc/init.d/S56dnsmasq {start|stop|restart}"
    exit 1
    ;;
esac
EOF

# 2. Сделать исполняемым
chmod +x /opt/etc/init.d/S56dnsmasq

# 3. Запустить
/opt/etc/init.d/S56dnsmasq start
```

**Проверка работы:**

```bash
# 1. Проверить процесс
ps | grep dnsmasq
# Ожидается: dnsmasq --conf-file=/opt/etc/dnsmasq.conf

# 2. Проверить порт 53
netstat -lnp | grep 53
# Ожидается: 127.0.0.1:53

# 3. Протестировать DNS
nslookup google.com 127.0.0.1
# Должен вернуть IP адрес

# 4. Проверить логи
logread | grep dnsmasq
```

**Что даёт dnsmasq:**

| Функция | Описание |
|---------|----------|
| **Автопереключение DNS** | При отказе основного DNS автоматически переключает на резервный |
| **Кэширование** | Ускоряет повторные DNS запросы (кэш в RAM) |
| **Централизация** | Все устройства используют роутер как DNS, переключение только на роутере |

**Без dnsmasq:**
- ✅ DNS мониторинг работает
- ✅ Проверка доступности DNS
- ❌ Нет автопереключения (только логирование)
- ❌ Нет кэширования

**Важно:** dnsmasq не критичен для работы приложения. Если не установлен — DNS мониторинг продолжает работать, просто логируется предупреждение.

## Чек-лист проверки

### После установки

```bash
# 1. Проверка процесса
ps | grep python
# Ожидается: python3 app.py запущен

# 2. Проверка порта
netstat -tlnp | grep 8080
# Ожидается: порт 8080 открыт

# 3. Проверка логов
tail -f /opt/var/log/web_ui.log
# Ожидается: нет ошибок ERROR/CRITICAL

# 4. Проверка доступности
curl -I http://localhost:8080
# Ожидается: HTTP/1.0 302 Found (редирект на /login)

# 5. Проверка размера логов
ls -lh /opt/var/log/web_ui.log*
# Ожидается: <300KB (3 файла по 100KB)
```

### После оптимизаций

```bash
# 1. Потребление памяти
ps | grep python | awk '{print $2}'
# Ожидается: ~10-15MB (was ~25MB)

# 2. Проверка кэширования
time curl http://localhost:8080/keys
# 2-й запрос должен быть быстрее (кэш статусов 30с)

# 3. Проверка ротации логов
ls -lh /opt/var/log/web_ui.log*
# Ожидается: 3 файла по ~100KB

# 4. Проверка ThreadPoolExecutor
curl http://localhost:8080/keys &
curl http://localhost:8080/service &
wait
# Оба запроса выполнятся параллельно
```

### Диагностика проблем

```bash
# Если не запускается:

# 1. Проверить логи
tail -n 50 /opt/var/log/web_ui.log

# 2. Проверить зависимости
pip3 show flask

# 3. Проверить .env
cat /opt/etc/web_ui/.env

# 4. Запустить в режиме отладки
cd /opt/etc/web_ui
python3 app.py
# Смотреть вывод в консоль
```

## Доступ

- **URL:** http://192.168.1.1:8080
- **Пароль:** из `.env` (WEB_PASSWORD)

## Конфигурация

Файл `.env`:

```bash
# Web Interface Configuration
WEB_HOST=0.0.0.0
WEB_PORT=8080
WEB_PASSWORD=your_secure_password

# Router Configuration
ROUTER_IP=192.168.1.1
UNBLOCK_DIR=/opt/etc/unblock/

# Logging
LOG_FILE=/opt/var/log/web_ui.log
```

| Параметр | Описание | По умолчанию |
|----------|----------|--------------|
| WEB_HOST | Адрес прослушивания | 0.0.0.0 |
| WEB_PORT | Порт web-интерфейса | 8080 |
| WEB_PASSWORD | Пароль для авторизации | changeme |
| ROUTER_IP | IP-адрес роутера | 192.168.1.1 |
| UNBLOCK_DIR | Директория bypass | /opt/etc/unblock/ |
| LOG_FILE | Путь к лог-файлу | /opt/var/log/web_ui.log |

## Функционал

### Главное меню

5 основных разделов:

- 🔑 **Ключи и мосты** — настройка VPN ключей (Tor, Vless, Trojan, Shadowsocks, VLESS+REALITY)
- 📑 **Списки обхода** — управление списками доменов для обхода блокировок
- 📲 **Установка и удаление** — установка и удаление flymybyte с GitHub
- 📊 **Статистика** — статистика трафика
- ⚙️ **Сервис** — сервисные функции:
  - Перезапуск роутера
  - Перезапуск всех сервисов
  - DNS Override
  - **DNS-обход AI-доменов** — обход региональных блокировок AI-сервисов
  - Бэкап конфигурации
  - Обновление flymybyte

### 🚀 Оптимизации производительности (v1.12)

**Рефакторинг кодовой базы:**
- Централизация всех путей и констант в `core/constants.py`
- Единый источник декораторов в `core/decorators.py`
- Выделены сервисные модули: `backup_service.py`, `update_service.py`
- Устранено дублирование парсеров .env (430 → 208 строк в `app_config.py`)
- Логирование без side-effects при импорте
- Экономия ~500 строк кода

**Все функции из test.txt реализованы:**

| Функция | Описание | Улучшение |
|---------|----------|-----------|
| **ipset restore** | Bulk-добавление правил в ipset | 60x быстрее (1000 записей за 5-10 сек) |
| **Параллельный DNS-резолв** | ThreadPoolExecutor для резолва доменов | 20x быстрее (100 доменов за 5 сек) |
| **Каталог списков** | Готовые списки (anticensor, social, streaming, torrents) | One-click загрузка |
| **DNS мониторинг (Соломка)** | Автопереключение на резервный DNS при отказе | <90 сек downtime |
| **DNS-обход AI-доменов** | Подмена DNS для обхода блокировок AI-сервисов | Скрытие региона от AI |

**Детали оптимизаций:**

```
ipset restore:
- Было: 5-10 минут на 1000 записей (построчное добавление)
- Стало: 5-10 секунд (bulk-операции через ipset restore)
- MAX_BULK_ENTRIES = 5000 (защита от OOM)

DNS Resolver:
- Было: 100 секунд на 100 доменов (последовательно)
- Стало: 5 секунд (параллельно, 10 workers)
- Batch processing для больших списков

DNS Monitor:
- Проверка DNS каждые 30 секунд
- Автопереключение после 3 неудач
- Интеграция с dnsmasq (автообновление конфига)
- Graceful shutdown при выходе

Catalog:
- 5 категорий: anticensor, reestr, social, streaming, torrents
- Загрузка из GitHub или predefined domains
- Atomic file writes
```

**Технические детали:**

- **Memory protection:** MAX_BULK_ENTRIES, BATCH_SIZE, max_workers=10
- **Thread safety:** Singleton pattern с _lock
- **Error handling:** Детализация failed entries, санитизация input
- **Security:** Валидация setname, санитизация entry, rate limiting

### 🌐 DNS-обход AI-доменов (новое!)

**Назначение:** Обход региональных блокировок AI-сервисов Google через подмену DNS.

**Поддерживаемые сервисы:**
- Google AI Studio (aistudio.google.com)
- Gemini (gemini.google.com)
- Google Colab (colab.research.google.com)
- Kaggle (kaggle.com)
- Google DeepMind
- TensorFlow
- и другие

**Принцип работы:**
1. DNS-запросы к AI-доменам направляются через VPN DNS (порт 40500)
2. VPN резолвит домены через внешний DNS (8.8.8.8)
3. Сервис видит IP VPN, а не реальный регион пользователя

**Быстрый старт:**
```bash
# 1. Через веб-интерфейс
Сервис → DNS-обход AI → Загрузить готовый список → Применить

# 2. Через SSH
curl -sL -o /opt/etc/unblock/ai-domains.txt \
  https://raw.githubusercontent.com/royfincher25-source/flymybyte/master/src/web_ui/resources/lists/unblock-ai-domains.txt
sh /opt/etc/web_ui/resources/scripts/unblock_dnsmasq.sh
```

**Документация:**
- Инструкция: `docs/DNS_SPOOFING_INSTRUCTION.md`
- Дизайн: `docs/DNS_SPOOFING_DESIGN.md`

### Авторизация

Session-based авторизация с cookie:

- При первом входе требуется пароль
- Сессия действует 24 часа
- При выходе сессия очищается

## Безопасность

⚠️ **Важно:** Измените пароль по умолчанию перед использованием!

```bash
WEB_PASSWORD=your_secure_password_here
```

## Архитектура

```
flymybyte/
├── src/
│   └── web_ui/            # Папка для копирования на роутер
│       ├── app.py              # Flask приложение (factory function)
│       ├── routes_service.py   # Blueprint: система, логи, обновления, DNS-spoofing
│       ├── routes_keys.py      # Blueprint: VLESS, SS, Trojan, Tor, Hysteria2
│       ├── routes_bypass.py    # Blueprint: списки обхода, каталог, ipset
│       ├── env_parser.py       # Лёгкий парсер .env
│       ├── scripts/
│       │   ├── script.sh       # Скрипт установки/удаления flymybyte
│       │   ├── script.sh.md5   # MD5 хэш для проверки целостности
│       │   └── README.md       # Документация scripts/
│       ├── core/
│       │   ├── __init__.py
│       │   ├── constants.py    # Централизованные константы и пути
│       │   ├── decorators.py   # Декораторы авторизации и CSRF
│       │   ├── app_config.py   # WebConfig singleton
│       │   ├── backup_service.py # Логика бэкапов
│       │   ├── update_service.py # Логика обновлений
│       │   ├── utils.py        # Утилиты, LRU-кэш, setup_logging()
│       │   ├── services.py     # Парсеры VPN-ключей
│       │   ├── dns_spoofing.py # DNS-обход AI-доменов
│       │   ├── dns_manager.py  # Управление dnsmasq
│       │   ├── dns_monitor.py  # DNS мониторинг
│       │   └── dns_resolver.py # Параллельный DNS-резолв
│       ├── templates/
│       │   ├── base.html       # Базовый шаблон (Bootstrap 5.3 dark)
│       │   ├── login.html      # Страница авторизации
│       │   ├── index.html      # Главное меню (плитки)
│       │   ├── keys.html       # Ключи и мосты
│       │   ├── bypass.html     # Списки обхода
│       │   ├── install.html    # Установка/удаление
│       │   ├── stats.html      # Статистика
│       │   ├── service.html    # Сервисное меню
│       │   ├── updates.html    # Обновления
│       │   └── dns_spoofing.html # DNS-обход AI-доменов
│       ├── resources/
│       │   ├── lists/
│       │   │   └── unblock-ai-domains.txt # Список AI-доменов
│       │   ├── scripts/
│       │   │   └── unblock_dnsmasq.sh # Генерация dnsmasq
│       │   └── config/
│       │       └── unblock-ai.dnsmasq.template # Шаблон dnsmasq
│       ├── static/
│       │   ├── fonts/        # Иконочный шрифт (flymybyte-icons.*)
│       │   └── style.css     # Custom стили
│       ├── requirements.txt    # Зависимости Python
│       ├── .env.example       # Пример конфигурации
│       └── VERSION            # Версия приложения
└── README.md
```

## Логирование

Логи пишутся в файл, указанный в `LOG_FILE` (по умолчанию `/opt/var/log/web_ui.log`):

```bash
# Просмотр логов
tail -f /opt/var/log/web_ui.log

# Поиск ошибок
grep -i error /opt/var/log/web_ui.log
```

## Тестирование

Запуск тестов:

```bash
pytest tests/web/ -v
```

Тесты покрывают:

- Конфигурацию (WebConfig singleton, загрузка .env)
- Flask приложение (создание, маршруты)
- Шаблоны (существование, рендеринг, стили)

## Потребление ресурсов

- **Память:** ~15MB
- **Порт:** 8080 (локально)
- **CPU:** минимальное в простое

## Лицензия

Лицензия аналогична основному проекту flymybyte.

## Поддержка

Вопросы и предложения: https://github.com/royfincher25-source/flymybyte/issues
