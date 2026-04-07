# FlyMyByte — Проект

## Обзор проекта

**FlyMyByte** — веб-интерфейс для управления обходом блокировок на роутерах Keenetic через браузер. Предоставляет GUI для настройки VPN-ключей (Tor, VLESS, Trojan, Shadowsocks), управления списками доменов для обхода блокировок, мониторинга DNS и сервисных функций.

**Текущая версия:** 2.0.4

**Основное назначение:**
- 📲 Установка и настройка flymybyte на роутерах Keenetic (Entware)
- 🔑 Управление VPN-ключами и мостами
- 📑 Управление списками обхода (ipset + dnsmasq)
- 🌐 DNS-обход AI-доменов (Google AI Studio, Gemini, Colab)
- 📊 Статистика трафика
- ⚙️ Сервисные функции (перезапуск, бэкап, DNS Override)

---

## Технологии и стек

### Backend
- **Python 3.8+** — основной язык
- **Flask 3.0.0** — веб-фреймворк
- **Jinja2 3.1.2** — шаблонизатор
- **Werkzeug 3.0.0** — WSGI-утилиты
- **requests >= 2.31.0** — HTTP-клиент
- **waitress 2.1.2** — production server (оптимизирован для embedded)

### Frontend
- **Bootstrap 5.3** — UI framework (dark theme)
- **HTML5/CSS3** — шаблоны

### Router Integration
- **Entware** — пакетный менеджер
- **dnsmasq** — DNS server и кэширование
- **ipset** — управление списками IP для маршрутизации
- **iptables** — NAT правила для перенаправления трафика
- **Shadowsocks/Xray/Tor** — VPN сервисы

---

## Структура проекта

```
FlyMyByte/
├── src/web_ui/                    # Основная директория веб-интерфейса
│   ├── app.py                     # Flask приложение (factory function)
│   ├── routes_service.py          # Blueprint: система, логи, обновления, DNS-spoofing
│   ├── routes_keys.py             # Blueprint: VLESS, SS, Trojan, Tor, Hysteria2
│   ├── routes_bypass.py           # Blueprint: списки обхода, каталог, ipset
│   ├── env_parser.py              # Лёгкий парсер .env
│   ├── requirements.txt           # Python зависимости
│   ├── .env.example               # Пример конфигурации
│   │
│   ├── core/                      # Ядро приложения
│   │   ├── app_config.py          # WebConfig singleton
│   │   ├── utils.py               # Утилиты, LRU-кэш, логирование
│   │   ├── services.py            # Парсеры VPN-ключей
│   │   ├── dns_spoofing.py        # DNS-обход AI-доменов
│   │   ├── dns_manager.py         # Управление dnsmasq
│   │   ├── dns_monitor.py         # DNS мониторинг (автопереключение)
│   │   ├── dns_resolver.py        # Параллельный DNS-резолв (ThreadPool)
│   │   ├── ipset_manager.py       # Bulk-операции с ipset
│   │   ├── list_catalog.py        # Каталог готовых списков
│   │   ├── update_progress.py     # Прогресс обновлений
│   │   └── constants.py           # Константы
│   │
│   ├── templates/                 # HTML шаблоны
│   │   ├── base.html              # Базовый шаблон (Bootstrap 5.3 dark)
│   │   ├── login.html             # Страница авторизации
│   │   ├── index.html             # Главное меню (плитки)
│   │   ├── keys.html              # Ключи и мосты
│   │   ├── bypass.html            # Списки обхода
│   │   ├── install.html           # Установка/удаление
│   │   ├── stats.html             # Статистика
│   │   ├── service.html           # Сервисное меню
│   │   ├── updates.html           # Обновления
│   │   └── dns_spoofing.html      # DNS-обход AI-доменов
│   │
│   ├── resources/                 # Ресурсы
│   │   ├── lists/
│   │   │   └── unblock-ai-domains.txt  # Список AI-доменов
│   │   ├── scripts/
│   │   │   └── unblock_dnsmasq.sh      # Генерация dnsmasq конфига
│   │   └── config/
│   │       └── unblock-ai.dnsmasq.template
│   │
│   ├── static/                    # Статические файлы
│   │   └── style.css              # Custom стили
│   │
│   └── scripts/                   # Скрипты установки
│       ├── script.sh              # Установка/удаление flymybyte
│       ├── script.sh.md5          # MD5 хэш для проверки целостности
│       └── README.md              # Документация scripts/
│
├── scripts/                       # Скрипты для роутера (диагностика)
│   ├── full_check.sh              # Полная диагностика системы
│   ├── check_bypass.sh            # Быстрая проверка обхода
│   ├── check_routing.sh           # Проверка маршрутизации
│   ├── apply_routing.sh           # Применение правил маршрутизации
│   ├── restart_web_ui.sh          # Перезапуск веб-интерфейса
│   └── README.md                  # Документация скриптов
│
├── docs/                          # Документация
│   ├── DNS_SPOOFING_DESIGN.md     # Дизайн-документ DNS-обхода
│   ├── DNS_SPOOFING_INSTRUCTION.md # Инструкция пользователя
│   ├── CHECK_BYPASS_INSTRUCTION.md # Проверка обхода
│   ├── INSTALL-manual.md          # Ручная установка
│   ├── OBSIDIAN_INSTRUCTION.md    # Полная документация Obsidian
│   ├── OPTIMIZATION_ANALYSIS.md   # Анализ оптимизаций
│   ├── MIGRATION_FROM_TELEGRAM_BOT.md
│   └── plans/                     # Планы разработки
│
├── tests/                         # Тесты (pytest)
│   └── test_dns_spoofing.py       # Unit-тесты DNS-обхода
│
├── CHANGELOG.md                   # История изменений
├── VERSION                        # Текущая версия (2.0.4)
└── README.md                      # Основная документация
```

---

## Сборка и запуск

### Требования для разработки
- Python 3.8+
- pip3
- Git

### Установка зависимостей

```bash
cd src/web_ui
pip3 install -r requirements.txt
```

### Запуск веб-интерфейса

```bash
cd src/web_ui
python3 app.py
```

**По умолчанию:** http://localhost:8080

### Конфигурация (.env)

```bash
# Web Interface Configuration
WEB_HOST=0.0.0.0
WEB_PORT=8080
WEB_PASSWORD=changeme

# Router Configuration
ROUTER_IP=192.168.1.1
UNBLOCK_DIR=/opt/etc/unblock/

# Logging
LOG_FILE=/opt/var/log/web_ui.log
```

### Production server (waitress)

Приложение автоматически использует waitress при установке:

```python
from waitress import serve
serve(
    app,
    host=host,
    port=port,
    threads=4,              # Для KN-1212 (128MB RAM)
    connection_limit=10,    # Защита от перегрузки
    cleanup_interval=30,    # Очистка каждые 30 секунд
)
```

**Fallback:** Flask development server с `threaded=True`

---

## Тестирование

```bash
pytest tests/ -v
```

**Категории тестов:**
- DomainValidation — валидация доменов
- ConfigGeneration — генерация конфигурации dnsmasq
- ConfigWrite — запись конфигурации
- Status — статус DNS-обхода
- DomainLoading — загрузка списка доменов
- ModuleFunctions — тестирование функций модуля

---

## Разработка

### Git worktrees

Для изоляции фич используйте worktrees:

```bash
# Создать новую фичу в изолированном worktree
git worktree add -f ../feature-branch feature-branch

# Перейти в worktree
cd ../feature-branch

# Удалить worktree после завершения
git worktree remove feature-branch
```

### Методология разработки

1. **Brainstorming** — перед написанием кода:
   - Задавать уточняющие вопросы
   - Предлагать альтернативы
   - Сохранять дизайн-документ

2. **Test-Driven Development (TDD):**
   - RED: Сначала написать тест
   - GREEN: Минимальный код для прохождения
   - REFACTOR: Рефакторинг

3. **Планирование:**
   - Разбивать задачи на шаги (2-5 минут)
   - Чёткие критерии завершения

4. **Code Review** — перед завершением работы

### Код-стайл

- **Именование:** snake_case для функций/переменных, PascalCase для классов
- **Типизация:** Python type hints для функций
- **Логирование:** logging module с уровнями DEBUG/INFO/WARNING/ERROR
- **Комментарии:** Только "почему", не "что"

### Оптимизации для embedded (128MB RAM)

- **LRU-кэш:** 50 записей максимум
- **Кэш статусов:** 30 секунд TTL
- **ThreadPoolExecutor:** max_workers=2 (оптимизировано для KN-1212)
- **Ротация логов:** 100KB × 3 файла
- **ipset restore:** Bulk-операции (5000 записей максимум)
- **DNS Resolver:** Параллельный резолв (10 workers)

---

## Архитектура

### Основные компоненты

#### 1. Flask Application (app.py)

Factory function `create_app()`:
- Генерация SECRET_KEY
- Загрузка WebConfig
- Регистрация маршрутов (3 Blueprint'а)
- Запуск DNS монитора
- Graceful shutdown (atexit)

#### 2. Blueprints (3 модуля, ~1500 строк)

**routes_service.py** (Blueprint `main`):
- `/` — Главное меню
- `/login` — Авторизация
- `/logout` — Выход
- `/status`, `/stats` — Статус и статистика
- `/service` — Сервисное меню
- `/install`, `/remove` — Установка/удаление
- `/dns-spoofing` — DNS-обход AI (8 API endpoints)
- `/logs` — Просмотр логов
- `/api/*` — API endpoints

**routes_keys.py** (Blueprint `keys`):
- `/keys` — Ключи и мосты
- `/keys/<service>` — Настройка VPN-сервисов

**routes_bypass.py** (Blueprint `bypass`):
- `/bypass` — Списки обхода
- `/bypass/catalog` — Каталог готовых списков

#### 3. Core Modules

| Модуль | Назначение |
|--------|------------|
| `app_config.py` | WebConfig singleton (загрузка .env) |
| `utils.py` | Утилиты, LRU-кэш, валидация, логирование |
| `services.py` | Парсеры VPN-ключей (VLESS, Hysteria2, Shadowsocks, Trojan, Tor) |
| `dns_spoofing.py` | DNS-обход AI-доменов (singleton, валидация, atomic write) |
| `dns_manager.py` | Управление dnsmasq (перезапуск, статус) |
| `dns_monitor.py` | DNS мониторинг (проверка каждые 30с, автопереключение) |
| `dns_resolver.py` | Параллельный DNS-резолв (ThreadPoolExecutor) |
| `ipset_manager.py` | Bulk-операции с ipset (restore, MAX_BULK_ENTRIES=5000) |
| `list_catalog.py` | Каталог готовых списков (5 категорий) |

#### 4. DNS Spoofing Architecture

```
Пользователь → dnsmasq → VPN DNSPort (40500) → Внешний DNS (8.8.8.8)
                      ↓
              /opt/etc/unblock-ai.dnsmasq
              server=/aistudio.google.com/127.0.0.1#40500
```

**Файлы:**
- `core/dns_spoofing.py` — модуль генерации конфигурации
- `resources/lists/unblock-ai-domains.txt` — список AI-доменов
- `/opt/etc/unblock-ai.dnsmasq` — конфигурация dnsmasq

---

## API Endpoints

### DNS-обход AI-доменов

| Endpoint | Method | Описание |
|----------|--------|----------|
| `/dns-spoofing` | GET | Страница управления |
| `/dns-spoofing/status` | GET | Статус DNS-обхода |
| `/dns-spoofing/apply` | POST | Применить конфигурацию |
| `/dns-spoofing/disable` | POST | Выключить DNS-обход |
| `/dns-spoofing/domains` | GET | Получить список доменов |
| `/dns-spoofing/domains` | POST | Сохранить список доменов |
| `/dns-spoofing/preset` | GET | Загрузить готовый список |
| `/dns-spoofing/test` | POST | Тестировать разрешение домена |
| `/dns-spoofing/logs` | GET | Получить логи |

---

## Безопасность

### Авторизация

- Session-based с cookie
- Сессия действует 24 часа
- CSRF token для всех форм
- Password hashing (планируется)

### Важные замечания

⚠️ **Измените пароль по умолчанию перед использованием!**

```bash
WEB_PASSWORD=your_secure_password_here
```

---

## Потребление ресурсов

| Ресурс | Значение |
|--------|----------|
| **Память** | ~15MB (веб-интерфейс) |
| **Дисковое пространство** | ~7MB (с waitress) |
| **Порт** | 8080 (локально) |
| **CPU** | Минимальное в простое |
| **Логи** | 300KB максимум (ротация) |

---

## Диагностика и отладка

### Проверка логов

```bash
tail -f /opt/var/log/web_ui.log
grep -i error /opt/var/log/web_ui.log
```

### Скрипты диагностики

| Скрипт | Назначение |
|--------|------------|
| `scripts/full_check.sh` | Полная диагностика системы |
| `scripts/check_bypass.sh` | Быстрая проверка обхода |
| `scripts/check_routing.sh` | Проверка маршрутизации |
| `scripts/apply_routing.sh` | Применение правил маршрутизации |
| `scripts/restart_web_ui.sh` | Перезапуск веб-интерфейса |

### Использование

```bash
# Копирование на роутер
scp scripts/full_check.sh root@192.168.1.1:/opt/root/

# Запуск
ssh root@192.168.1.1 -p 222 "sh /opt/root/full_check.sh"
```

---

## Установка на роутер

### Быстрая установка (2 шага)

```bash
# Шаг 1: Установка веб-интерфейса
curl -sL https://raw.githubusercontent.com/royfincher25-source/flymybyte/master/src/web_ui/scripts/install_web.sh | sh

# Шаг 2: Открыть http://192.168.1.1:8080 и нажать "Установить"
```

### Ручная установка

```bash
# 1. Копирование файлов
scp -r src/web_ui/ root@192.168.1.1:/opt/etc/web_ui/

# 2. Установка зависимостей
pip3 install -r /opt/etc/web_ui/requirements.txt

# 3. Настройка
cp /opt/etc/web_ui/.env.example /opt/etc/web_ui/.env
nano /opt/etc/web_ui/.env

# 4. Запуск
cd /opt/etc/web_ui
nohup python3 app.py > /opt/var/log/web_ui.log 2>&1 &
```

---

## Лицензия

Лицензия аналогична основному проекту flymybyte.

---

## Поддержка

- **GitHub:** https://github.com/royfincher25-source/flymybyte
- **Issues:** https://github.com/royfincher25-source/flymybyte/issues
- **Документация:** `docs/` директория

---

## Ключевые файлы для разработки

| Файл | Описание | Строк |
|------|----------|-------|
| `src/web_ui/app.py` | Flask приложение (factory) | ~100 |
| `src/web_ui/routes_service.py` | Blueprint: система, логи, обновления | ~984 |
| `src/web_ui/routes_keys.py` | Blueprint: VPN-ключи | ~329 |
| `src/web_ui/routes_bypass.py` | Blueprint: списки обхода | ~314 |
| `src/web_ui/core/dns_spoofing.py` | DNS-обход AI-доменов | ~200 |
| `src/web_ui/core/dns_monitor.py` | DNS мониторинг | ~150 |
| `src/web_ui/core/ipset_manager.py` | Bulk-операции ipset | ~100 |
| `src/web_ui/templates/dns_spoofing.html` | UI DNS-обхода | ~200 |
| `tests/test_dns_spoofing.py` | Unit-тесты | ~150 |

---

## Чек-лист перед коммитом

1. ✅ Запустить тесты: `pytest tests/ -v`
2. ✅ Проверить линтер (если настроен)
3. ✅ Обновить CHANGELOG.md (если есть изменения)
4. ✅ Обновить VERSION (если новая версия)
5. ✅ Code review (проверить изменения)
6. ✅ Создать commit с понятным сообщением

---

## Ссылки

- [README.md](README.md) — Основная документация
- [CHANGELOG.md](CHANGELOG.md) — История изменений
- [docs/DNS_SPOOFING_DESIGN.md](docs/DNS_SPOOFING_DESIGN.md) — Дизайн DNS-обхода
- [docs/DNS_SPOOFING_INSTRUCTION.md](docs/DNS_SPOOFING_INSTRUCTION.md) — Инструкция пользователя
- [scripts/README.md](scripts/README.md) — Документация скриптов
