---
type: documentation
project: flymybyte
platform: Keenetic Router + Python Flask
version: 1.2.0
date: 23.03.2026
tags:
  - FlyMyByte
  - keenetic
  - router
  - flask
  - web-interface
  - vpn
  - installation
  - troubleshooting
  - manual
  - support
  - dns-spoofing
  - ai-bypass
category:
  - router
  - bypass
  - documentation
related:
  - "[[README]]"
  - "[[MIGRATION_FROM_TELEGRAM_BOT]]"
  - "[[DNS_SPOOFING_DESIGN]]"
  - "[[DNS_SPOOFING_INSTRUCTION]]"
  - "[[src/web_ui/app.py]]"
  - "[[src/web_ui/.env.example]]"
  - "[[VERSION]]"
---

# FlyMyByte — Полное руководство

> **Версия документа:** 1.2.0
> **Дата:** 23.03.2026
> **Проект:** FlyMyByte
> **Платформа:** Keenetic Router + Python Flask

---

## Содержание

1. [[#1-обзор-проекта|Обзор проекта]]
2. [[#2-установка|Установка]]
3. [[#3-обновление|Обновление]]
4. [[#4-функционал-web-интерфейса|Функционал веб-интерфейса]]
5. [[#5-команды-терминала|Команды терминала]]
6. [[#6-администрирование|Администрирование]]
7. [[#7-диагностика|Диагностика и устранение неполадок]]
8. [[#8-поддержка-Поддержка]]
9. [[#приложения|Приложения]]

---

## 1. Обзор проекта

### 1.1 Что это такое

**FlyMyByte** — веб-интерфейс для управления системой обхода блокировок `FlyMyByte` на роутерах Keenetic. Веб-интерфейс заменяет Telegram-бота и предоставляет тот же функционал через браузер.

```
┌─────────────────────────────────────────────────────────────────┐
│                        Пользователь                             │
│                    (Браузер на ПК/телефоне)                     │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             │ HTTP :8080
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    FlyMyByte                          │
│                    (Flask приложение, v1.2.0)                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │   Routes     │  │   Services   │  │ DNS Monitor  │         │
│  │  (API v1)    │  │  (VPN keys)  │  │ (Cloudflored)│         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
│  ┌──────────────┐                                              │
│  │DNS Spoofing  │  (AI domains bypass)                         │
│  └──────────────┘                                              │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             │ Конфигурация, скрипты
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Keenetic Router                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │   Unblock   │  │  VPN Keys    │  │  Memory Mgr  │         │
│  │  (ipset)    │  │ (xray/tor)   │  │ (Auto-opt)   │         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
│  ┌──────────────┐  ┌──────────────┐                            │
│  │ dnsmasq AI   │  │  DNSPort     │                            │
│  │  (spoofing) │  │  (40500)     │                            │
│  └──────────────┘  └──────────────┘                            │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 Основные возможности v1.2.0

| Раздел | Описание |
|--------|----------|
| 🔑 **Ключи и мосты** | Управление VPN-ключами (Tor, VLESS, Trojan, Shadowsocks, VLESS+REALITY) |
| 📑 **Списки обхода** | Управление списками доменов, каталог готовых списков |
| 📲 **Установка/удаление** | One-click установка/удаление FlyMyByte |
| 📊 **Статистика** | Просмотр статистики трафика |
| 🔄 **Обновления** | Smart update с сохранением пользовательских данных |
| 💾 **Бэкап** | Создание и управление резервными копиями |
| ⚙️ **Сервис** | Перезапуск, DNS Override, Memory Manager, DNS-обход AI |
| 📡 **DNS Мониторинг** | Автопереключение DNS при отказе (cloudflored) |
| 🌐 **DNS-обход AI-доменов** | Обход блокировок AI-сервисов через подмену DNS |

### 1.3 Новые функции v1.2.0

> [!success] Ключевые улучшения v1.2.0

**DNS-обход AI-доменов (новое!)**
- Обход региональных блокировок Google AI, Gemini, Colab, Kaggle
- Маршрутизация DNS-запросов через VPN DNSPort (40500)
- Готовый список AI-доменов
- Веб-интерфейс управления
- Тестирование разрешения доменов

### 1.4 Новые функции v1.1.0

> [!success] Ключевые улучшения v1.1.0

**Smart Update (сохранение данных)**
- При обновлении сохраняются: ключи, списки bypass, конфигурации
- Перезаписываются только системные файлы
- Автоматический перезапуск сервисов после обновления

**Memory Manager (оптимизация RAM)**
- Автоматическая оптимизация при низкой памяти
- Ручная кнопка "Оптимизировать память"
- Отображение занятой/свободной памяти в реальном времени
- Настройка порогов для автоматической оптимизации

**DNS Мониторинг (Соломка)**
- Проверка DNS каждые 60 секунд (was 30)
- Автопереключение на резервный DNS при 3 неудачах
- Интеграция с cloudflored (primary DNS)
- Fallback на 8.8.8.8, 1.1.1.1

**Backup System**
- Создание полной резервной копии (tar.gz)
- Сохранение: web_ui, xray, tor, unblock, dnsmasq, scripts
- Список резервных копий с датой и размером
- Удаление старых копий

**Глобальный loading overlay**
- Визуальная обратная связь при длительных операциях
- Кнопки блокируются на время выполнения
- Не блокирует браузер

### 1.4 Оптимизации для KN-1212 (128MB RAM)

> [!important] Критические оптимизации
> Проект оптимизирован для роутеров Keenetic KN-1212 с 128MB RAM:

| Параметр | Значение | Описание |
|----------|----------|----------|
| **DNS interval** | 60s | Проверка DNS каждые 60 сек |
| **DNS timeout** | 3s | Таймаут запроса |
| **RAM (web_ui)** | ~15MB | Потребление памяти |
| **Log rotation** | 100KB × 3 | Максимум 300KB логов |
| **LRU cache** | 50 записей | Кэширование статусов |
| **Waitress threads** | 2 | Ограничение потоков |
| **Connection limit** | 10 | Защита от перегрузки |

### 1.5 Требования

#### Аппаратные требования

| Параметр | Минимум | Рекомендуется |
|----------|---------|---------------|
| Модель | KN-1210, KN-1211, KN-1212 | KN-1810, KN-1910 |
| RAM | 128 MB | 256 MB+ |
| Flash | 16 MB | 32 MB+ |
| Свободное место | 20 MB | 50 MB+ |

#### Программные требования

| Компонент | Версия | Размер | Назначение |
|-----------|--------|--------|------------|
| Python | 3.8+ | ~10MB | Интерпретатор |
| Flask | 3.0.0 | ~2.5MB | Веб-фреймворк |
| Jinja2 | 3.1.2 | ~1MB | Шаблонизатор |
| Werkzeug | 3.0.0 | ~1MB | WSGI-утилиты |
| requests | >=2.31.0 | ~500KB | HTTP-клиент |
| waitress | 2.1.2 | ~200KB | Production server |

---

## 2. Установка

### 2.1 Быстрая установка (2 шага)

> [!success] Рекомендуемый способ
> Установка через скрипт — самый простой способ

```bash
# Шаг 1: Установка веб-интерфейса
curl -sL https://raw.githubusercontent.com/royfincher25-source/flymybyte/master/src/web_ui/scripts/install_web.sh | sh
```

**Скрипт выполняет:**
- ✅ Проверка требований (Python 3.8+, pip3, curl)
- ✅ Загрузка файлов с GitHub
- ✅ Установка зависимостей (Flask, Jinja2, Werkzeug, requests)
- ✅ Создание конфигурации (.env, web_config.py)
- ✅ Запуск веб-интерфейса

```bash
# Шаг 2: Установка FlyMyByte
# 1. Откройте http://192.168.1.1:8080
# 2. Войдите с паролем из /opt/etc/web_ui/.env
# 3. Перейдите в 📲 Установка и удаление
# 4. Нажмите Установить
```

### 2.2 Ручная установка

```bash
# 1. Подключение к роутеру
ssh root@192.168.1.1

# 2. Создание директории
mkdir -p /opt/etc/web_ui
cd /opt/etc/web_ui

# 3. Копирование файлов (с локального ПК)
# PowerShell:
scp -r "H:\path\to\FlyMyByte\src\web_ui\*" root@192.168.1.1:/opt/etc/web_ui/

# 4. Установка зависимостей
pip3 install -r requirements.txt

# 5. Создание конфигурации
cp .env.example .env
nano .env

# 6. Запуск
python3 app.py
```

### 2.3 Конфигурация (.env)

> [!warning] Важно
> Измените пароль по умолчанию!

```bash
nano /opt/etc/web_ui/.env
```

```bash
# ===========================================
# БАЗОВАЯ КОНФИГУРАЦИЯ
# ===========================================

# Веб-интерфейс
WEB_HOST=0.0.0.0          # Слушать на всех интерфейсах
WEB_PORT=8080             # Порт веб-интерфейса
WEB_PASSWORD=changeme     # ⚠️ ИЗМЕНИТЕ ПАРОЛЬ!

# Роутер
ROUTER_IP=192.168.1.1     # IP роутера
UNBLOCK_DIR=/opt/etc/unblock/  # Директория bypass

# Логирование
LOG_LEVEL=INFO            # DEBUG, INFO, WARNING, ERROR
LOG_FILE=/opt/var/log/web_ui.log
```

| Параметр | Обязательно | По умолчанию | Описание |
|----------|-------------|--------------|----------|
| WEB_PASSWORD | ✅ Да | changeme | Пароль для входа |
| WEB_PORT | Нет | 8080 | Порт приложения |
| ROUTER_IP | Нет | 192.168.1.1 | IP роутера |
| UNBLOCK_DIR | Нет | /opt/etc/unblock/ | Директория bypass |

### 2.4 Проверка установки

```bash
# Проверка процесса
ps | grep python

# Проверка порта
netstat -tlnp | grep 8080

# Проверка логов
tail -f /opt/var/log/web_ui.log

# Проверка доступности
curl -I http://192.168.1.1:8080
# Ожидается: HTTP/1.1 302 Redirect (на /login)
```

### 2.5 Автозапуск

```bash
# Создание скрипта автозапуска
cat > /opt/etc/init.d/S99web_ui << 'EOF'
#!/bin/sh
case "$1" in
  start)
    cd /opt/etc/web_ui
    python3 app.py > /dev/null 2>&1 &
    ;;
  stop)
    pkill -f "python.*app.py"
    ;;
  restart)
    $0 stop
    sleep 2
    $0 start
    ;;
esac
EOF

chmod +x /opt/etc/init.d/S99web_ui

# Запуск
/opt/etc/init.d/S99web_ui start
```

---

## 3. Обновление

### 3.1 Smart Update (рекомендуется)

> [!success] Сохраняет пользовательские данные
> При обновлении сохраняются: ключи, списки bypass, конфигурации VPN

```bash
# Через веб-интерфейс:
# 1. Откройте http://192.168.1.1:8080
# 2. Перейдите в 🔄 Обновления
# 3. Нажмите "Обновить"
```

**Что происходит:**
1. Скачиваются новые файлы с GitHub
2. Выполняются скрипты обновления (unblock_update.sh, unblock_dnsmasq.sh)
3. Перезапускаются сервисы: S99unblock, S56dnsmasq, S99web_ui
4. Пользовательские данные сохраняются

### 3.2 Ручное обновление

```bash
# На локальном компьютере
scp -r "H:\path\to\FlyMyByte\src\web_ui" root@192.168.1.1:/opt/etc/

# На роутере: перезапуск
/opt/etc/init.d/S99web_ui restart
```

### 3.3 Откат

```bash
# Откат через git
cd /opt/etc/web_ui
git log --oneline -5
git checkout <commit_hash>

# Или из резервной копии
/opt/etc/init.d/S99web_ui stop
rm -rf /opt/etc/web_ui
tar -xzf /opt/backup/web_ui_backup.tar.gz -C /opt/etc/
/opt/etc/init.d/S99web_ui start
```

---

## 4. Функционал веб-интерфейса

### 4.1 Главное меню

После авторизации доступны разделы:

| Иконка | Раздел | Описание |
|--------|--------|----------|
| 🔑 | Ключи и мосты | Управление VPN-ключами |
| 📑 | Списки обхода | Управление списками доменов |
| 📲 | Установка | Установка/удаление FlyMyByte |
| 🔄 | Обновления | Проверка и установка обновлений |
| 💾 | Бэкап | Резервное копирование |
| ⚙️ | Сервис | Системные функции |
| 📡 | DNS Мониторинг | Статус и управление DNS |

### 4.2 Ключи и мосты

Поддерживаемые типы VPN:

| Тип | Описание | Файл конфига |
|-----|---------|--------------|
| **Tor** | Tor с obfs4 | tor.json |
| **VLESS** | Протокол VLESS | vless.json |
| **Trojan** | Trojan-Go | trojan.json |
| **Shadowsocks** | Shadowsocks | shadowsocks.json |
| **VLESS+REALITY** | VLESS с REALITY | vless_reality.json |

**Управление:**
- Добавление/редактирование ключей
- Валидация формата
- Тестирование подключения

### 4.3 Списки обхода

**Категории списков:**

| Категория | Описание |
|-----------|---------|
| anticensor | Списки для обхода блокировок |
| reestr | Реестр заблокированных доменов |
| social | Социальные сети |
| streaming | Streaming сервисы |
| torrents | Torrent-трекеры |

**Функции:**
- Ручное добавление доменов
- Каталог готовых списков
- Параллельная загрузка (10 workers)
- Bulk-добавление в ipset

### 4.4 Установка и удаление

**Установка (Install):**
> [!warning] Перезаписывает данные!
> При установке сохраняются пользовательские данные (ключи, списки)

- Загрузка ресурсов с GitHub
- Установка пакетов (curl, python3-pip, dnsmasq)
- Настройка ipset, VPN, dnsmasq
- Запуск сервисов

**Удаление (Remove):**
- Остановка сервисов
- Удаление файлов FlyMyByte
- Очистка конфигурации

### 4.5 DNS Мониторинг

> [!tip] Автоматическое переключение DNS
> При отказе основного DNS автоматически переключает на резервный

**Настройки:**
- Primary DNS: cloudflored (127.0.0.1:5053)
- Backup DNS: 8.8.8.8, 1.1.1.1
- Check interval: 60 секунд
- Fail threshold: 3 неудачи

**Управление:**
- Start/Stop мониторинга
- Ручная проверка DNS
- Просмотр текущего активного DNS

### 4.6 Memory Manager

> [!success] Автоматическая оптимизация RAM

**Функции:**
- Отображение занятой/свободной памяти
- Автоматическая оптимизация при низкой памяти
- Ручная кнопка оптимизации
- Настройка порогов срабатывания

**Пороги по умолчанию:**
- Warning: < 30MB свободно
- Critical: < 15MB свободно

### 4.7 Бэкап

**Создание резервной копии:**
```bash
# Автоматически через веб-интерфейс
# Сохраняет: web_ui, xray, tor, unblock, dnsmasq, scripts
```

**Список бэкапов:**
- Дата и время создания
- Размер файла
- Количество объектов
- Кнопка удаления

---

## 5. Команды терминала

### 5.1 Подключение к роутеру

```bash
# SSH подключение
ssh root@192.168.1.1

# С указанием порта
ssh -p 2222 root@192.168.1.1

# С использованием ключа
ssh -i ~/.ssh/id_rsa root@192.168.1.1
```

### 5.2 Копирование файлов

```bash
# С локального ПК на роутер (PowerShell)
scp -r "H:\path\to\project\src\web_ui" root@192.168.1.1:/opt/etc/

# Отдельный файл
scp app.py root@192.168.1.1:/opt/etc/web_ui/

# С роутера на локальный ПК
scp root@192.168.1.1:/opt/etc/web_ui/backup.tar.gz "H:\backup\"
```

### 5.3 Управление приложением

```bash
# ===========================================
# ЗАПУСК
# ===========================================

# Ручной запуск
cd /opt/etc/web_ui
python3 app.py

# Фоновый запуск
cd /opt/etc/web_ui
nohup python3 app.py > /opt/var/log/web_ui.log 2>&1 &

# Через init.d
/opt/etc/init.d/S99web_ui start

# ===========================================
# ОСТАНОВКА
# ===========================================

# По процессу
pkill -f "python.*app.py"

# Через init.d
/opt/etc/init.d/S99web_ui stop

# ===========================================
# ПЕРЕЗАПУСК
# ===========================================

/opt/etc/init.d/S99web_ui restart
```

### 5.4 Проверка статуса

```bash
# Процесс запущен?
ps | grep app.py

# Порт занят?
netstat -tlnp | grep 8080

# Приложение отвечает?
curl -I http://localhost:8080

# Проверка всех сервисов
ps aux | grep -E "(python|3proxy|tor)" | grep -v grep
```

### 5.5 Логи

```bash
# Просмотр логов
cat /opt/var/log/web_ui.log

# В реальном времени
tail -f /opt/var/log/web_ui.log

# Последние 50 строк
tail -n 50 /opt/var/log/web_ui.log

# Поиск ошибок
grep -i error /opt/var/log/web_ui.log

# Системный лог
logread | grep -i bypass
```

### 5.6 Управление FlyMyByte

```bash
# Перезапуск всех сервисов bypass
/opt/etc/init.d/S99unblock restart

# Перезапуск dnsmasq
/opt/etc/init.d/S56dnsmasq restart

# Перезагрузка ipset
/opt/etc/web_ui/scripts/unblock_ipset.sh

# Обновление конфигурации DNS
/opt/etc/web_ui/scripts/unblock_dnsmasq.sh
```

### 5.7 DNS и сеть

```bash
# Проверка DNS
nslookup google.com 127.0.0.1

# Тест cloudflored
curl -I https://www.google.com --doh-url https://cloudflare-dns.com/dns-query

# Проверка cloudflored
ps | grep cloudflored

# Перезапуск cloudflored
pkill -f cloudflored
/opt/bin/cloudflored -config /opt/etc/cloudflored/config.yml &
```

### 5.8 Резервное копирование

```bash
# Создание бэкапа вручную
cd /opt/etc
tar -czf /opt/root/backup/backup_$(date +%Y%m%d_%H%M%S).tar.gz \
    web_ui xray tor unblock dnsmasq.conf crontab

# Просмотр бэкапов
ls -lh /opt/root/backup/

# Восстановление
tar -xzf /opt/root/backup/backup_FILE.tar.gz -C /opt/etc/
```

---

## 6. Администрирование

### 6.1 Мониторинг

```bash
# ===========================================
# ПРОВЕРКА РАБОТЫ
# ===========================================

# Все процессы bypass
ps aux | grep -E "(python|3proxy|tor|cloudflored)" | grep -v grep

# Использование памяти
free -m

# Процесс web_ui
ps -o pid,vsz,rss,pmem,comm -p $(pgrep -f "python.*app.py")

# Место на диске
df -h /opt

# ===========================================
# АВТОМОНИТОРИНГ
# ===========================================

# Создание скрипта мониторинга
cat > /opt/bin/check_bypass.sh << 'EOF'
#!/bin/sh
LOG="/opt/var/log/bypass_check.log"

if ! pgrep -f "python.*app.py" > /dev/null; then
    echo "$(date): web_ui not running, restarting..." >> $LOG
    cd /opt/etc/web_ui
    python3 app.py > /dev/null 2>&1 &
fi
EOF

chmod +x /opt/bin/check_bypass.sh

# Добавление в cron (каждые 5 минут)
echo "*/5 * * * * /opt/bin/check_bypass.sh" >> /opt/etc/crontabs/root
```

### 6.2 Безопасность

> [!warning] Рекомендации
> Соблюдайте меры безопасности для защиты роутера

```bash
# 1. Надёжный пароль
# Измените в .env:
WEB_PASSWORD=your_very_strong_password_here

# 2. Ограничение SSH
# В настройках роутера: SSH только для локальной сети

# 3. Регулярные обновления
# Используйте Smart Update в веб-интерфейсе

# 4. Резервные копии
# Создавайте бэкап перед обновлением
```

### 6.3 Оптимизация памяти (Memory Manager)

```bash
# Ручная оптимизация
cd /opt/etc/web_ui
python3 -c "from core.utils import MemoryManager; MemoryManager.optimize()"

# Автоматическая проверка
# Встроена в веб-интерфейс
# Пороги: warning <30MB, critical <15MB

# Очистка кэша Python
python3 -c "import gc; gc.collect()"
```

### 6.4 Управление сервисами

```bash
# Статус всех сервисов
/etc/init.d/S99unblock status
/etc/init.d/S56dnsmasq status
/etc/init.d/S99web_ui status

# Перезапуск всех
/etc/init.d/S99unblock restart
/etc/init.d/S56dnsmasq restart
/etc/init.d/S99web_ui restart

# Логи сервисов
tail -f /opt/var/log/messages | grep -E "(unblock|dnsmasq)"
```

---

## 7. Диагностика

### 7.1 Checklist Troubleshooting

> [!checklist] Быстрая диагностика

- [ ] 1. Роутер доступен (`ping 192.168.1.1`)
- [ ] 2. Python 3 установлен (`python3 --version`)
- [ ] 3. Процесс запущен (`ps | grep app.py`)
- [ ] 4. Порт прослушивается (`netstat -tlnp | grep 8080`)
- [ ] 5. Веб-интерфейс открывается (`curl http://192.168.1.1:8080`)
- [ ] 6. Нет ошибок в логах (`tail /opt/var/log/web_ui.log`)
- [ ] 7. Зависимости установлены (`pip3 list | grep Flask`)
- [ ] 8. Конфигурация корректна (`cat /opt/etc/web_ui/.env`)

### 7.2 Типичные проблемы

| Проблема | Причина | Решение |
|----------|---------|---------|
| Не открывается страница | Приложение не запущено | `python3 app.py` |
| Ошибка 500 | Ошибка в коде | Проверить логи |
| Неверный пароль | Неправильный .env | Проверить WEB_PASSWORD |
| Port already in use | Порт занят | `pkill -f app.py; python3 app.py` |
| ModuleNotFoundError | Зависимости не установлены | `pip3 install -r requirements.txt` |

### 7.3 Диагностика по шагам

```bash
# ===========================================
# ШАГ 1: ПРОВЕРЬТЕ ПРОЦЕСС
# ===========================================
ps aux | grep python

# Должен быть: python3 app.py

# ===========================================
# ШАГ 2: ПРОВЕРЬТЕ ПОРТ
# ===========================================
netstat -tlnp | grep 8080

# Должен быть: tcp 0.0.0.0:8080 LISTEN

# ===========================================
# ШАГ 3: ПРОВЕРЬТЕ ЛОГИ
# ===========================================
tail -100 /opt/var/log/web_ui.log

# Ищите: ERROR, Exception, Traceback

# ===========================================
# ШАГ 4: ПРОВЕРЬТЕ ЗАВИСИМОСТИ
# ===========================================
python3 -c "import flask; print(flask.__version__)"

# Должна вывести версию Flask

# ===========================================
# ШАГ 5: ПРОВЕРЬТЕ КОНФИГУРАЦИЮ
# ===========================================
cat /opt/etc/web_ui/.env

# ===========================================
# ШАГ 6: ТЕСТИРОВАНИЕ
# ===========================================
cd /opt/etc/web_ui
python3 -c "from app import app; print('OK')"
```

### 7.4 Восстановление после сбоев

```bash
# Полное восстановление
# 1. Остановите всё
pkill -f python

# 2. Проверьте файлы
ls -la /opt/etc/web_ui/

# 3. Восстановите из бэкапа
tar -xzf /opt/root/backup/backup_latest.tar.gz -C /opt/etc/

# 4. Переустановите зависимости
pip3 install --force-reinstall -r /opt/etc/web_ui/requirements.txt

# 5. Запустите
/opt/etc/init.d/S99web_ui start
```

---

## 8. Поддержка

### 8.1 Сообщение о проблемах

При возникновении проблем предоставьте:

```bash
# 1. Версия приложения
cat /opt/etc/web_ui/VERSION

# 2. Статус процессов
ps aux | grep -E "(python|3proxy|tor|cloudflored)" | grep -v grep

# 3. Последние 100 строк лога
tail -100 /opt/var/log/web_ui.log

# 4. Конфигурация (без пароля)
grep -v PASSWORD /opt/etc/web_ui/.env

# 5. Версия Python
python3 --version

# 6. Установленные пакеты
pip3 list
```

### 8.2 Полезные команды диагностики

```bash
# Системная информация
uname -a
cat /proc/version
free -m
df -h /opt

# Сетевые настройки
cat /opt/etc/dnsmasq.conf
ps | grep cloudflored
netstat -tlnp | grep -E "(53|8080)"

# Версии компонентов
python3 --version
pip3 show flask
```

### 8.3 Ресурсы

| Ресурс | Ссылка |
|--------|--------|
| Репозиторий | https://github.com/royfincher25-source/flymybyte |
| Issues | https://github.com/royfincher25-source/flymybyte/issues |
| Entware | https://help.keenetic.com/hc/ru/articles/360000409409 |
| Flask Docs | https://flask.palletsprojects.com/ |
| Keenetic Forum | https://forum.keenetic.com/ |

---

## Приложения

### Приложение А: Быстрые команды

```bash
# ╔══════════════════════════════════════════════════════════╗
# ║             БЫСТРЫЙ СПРАВОЧНИК                          ║
# ╚══════════════════════════════════════════════════════════╝

# ПОДКЛЮЧЕНИЕ
ssh root@192.168.1.1                    # SSH доступ

# ЗАПУСК
/opt/etc/init.d/S99web_ui start       # Через init.d
cd /opt/etc/web_ui && python3 app.py   # Ручной

# ОСТАНОВКА
/opt/etc/init.d/S99web_ui stop        # Через init.d
pkill -f "python.*app.py"             # По процессу

# ПРОВЕРКА
ps | grep app.py                       # Процесс
netstat -tlnp | grep 8080             # Порт
curl http://192.168.1.1:8080           # Доступ

# ЛОГИ
tail -f /opt/var/log/web_ui.log       # В реальном времени

# ОБНОВЛЕНИЕ
scp -r src/web_ui/* root@192.168.1.1:/opt/etc/web_ui/
/opt/etc/init.d/S99web_ui restart

# БЭКАП
tar -czf backup.tar.gz -C /opt/etc web_ui

# ВЕРСИЯ
cat /opt/etc/web_ui/VERSION
```

### Приложение Б: Структура проекта

```
flymybyte/              # Корень репозитория
├── VERSION                       # Версия (1.2.0)
├── README.md                     # Документация
├── docs/                         # Планы и документация
│   ├── plans/                    # Планы реализации
│   ├── DNS_SPOOFING_DESIGN.md   # Дизайн DNS-обхода
│   ├── DNS_SPOOFING_INSTRUCTION.md # Инструкция DNS-обхода
│   └── OBSIDIAN_INSTRUCTION.md  # Obsidian документация
├── scripts/                      # Скрипты развёртывания
├── src/
│   └── web_ui/                  # Пакет для роутера
│       ├── app.py               # Flask приложение
│       ├── routes.py            # API endpoints (вкл. DNS spoofing)
│       ├── VERSION              # Версия (1.2.0)
│       ├── .env.example         # Пример конфигурации
│       ├── requirements.txt     # Python зависимости
│       ├── core/                # Core модули
│       │   ├── app_config.py   # Конфигурация приложения
│       │   ├── dns_manager.py  # DNS менеджер
│       │   ├── dns_monitor.py  # DNS мониторинг
│       │   ├── dns_resolver.py # DNS резолвер
│       │   ├── dns_spoofing.py # DNS-обход AI-доменов ⭐ NEW
│       │   ├── ipset_manager.py # ipset оптимизации
│       │   ├── list_catalog.py # Каталог списков
│       │   ├── services.py     # VPN парсеры
│       │   ├── utils.py        # Утилиты
│       │   └── web_config.py   # Web конфиг
│       ├── templates/           # HTML шаблоны
│       │   ├── dns_spoofing.html # DNS-обход AI ⭐ NEW
│       │   ├── base.html
│       │   ├── login.html
│       │   ├── index.html
│       │   ├── keys.html
│       │   ├── bypass.html
│       │   ├── install.html
│       │   ├── stats.html
│       │   ├── service.html
│       │   └── updates.html
│       ├── static/              # CSS
│       ├── scripts/             # Установочные скрипты
│       │   ├── install_web.sh  # Установка веб-интерфейса
│       │   └── script.sh       # FlyMyByte
│       └── resources/          # Конфиги, списки
│           ├── config/          # Шаблоны конфигов
│           │   ├── dnsmasq.conf
│           │   └── unblock-ai.dnsmasq.template ⭐ NEW
│           ├── lists/           # Списки доменов
│           │   ├── unblock-ai-domains.txt ⭐ NEW
│           │   ├── unblock-shadowsocks-optimal.txt
│           │   └── ...
│           └── scripts/         # Системные скрипты
│               ├── unblock_ipset.sh
│               ├── unblock_dnsmasq.sh ⭐ UPDATED
│               └── unblock_update.sh
```

### Приложение В: Changelog v1.2.0

> [!success] Изменения в версии 1.2.0

**Новые функции:**
- 🌐 **DNS-обход AI-доменов** — обход региональных блокировок AI-сервисов
  - Модуль `core/dns_spoofing.py`
  - Веб-интерфейс `/dns-spoofing`
  - Готовый список AI-доменов
  - Тестирование разрешения доменов
  - Интеграция с dnsmasq и VPN DNSPort

**Новые файлы:**
- `core/dns_spoofing.py` — модуль DNS-обхода
- `templates/dns_spoofing.html` — веб-интерфейс
- `resources/lists/unblock-ai-domains.txt` — список AI-доменов
- `resources/config/unblock-ai.dnsmasq.template` — шаблон dnsmasq
- `docs/DNS_SPOOFING_DESIGN.md` — дизайн-документ
- `docs/DNS_SPOOFING_INSTRUCTION.md` — инструкция пользователя
- `tests/test_dns_spoofing.py` — unit-тесты

**Обновлённые файлы:**
- `routes.py` — 8 новых endpoints для DNS-обхода
- `unblock_dnsmasq.sh` — генерация AI-конфигурации
- `service.html` — карточка DNS-обход AI
- `README.md` — документация DNS-обхода
- `OBSIDIAN_INSTRUCTION.md` — полная документация

### Приложение Г: Changelog v1.1.0

> [!success] Изменения в версии 1.1.0

**Исправления:**
- ✅ DNS bug: dnsmasq.conf использовал server=8.8.8.8, cloudflored использовал port 50500
- ✅ script.sh: перезаписывал пользовательские данные при каждой установке
- ✅ Backup format mismatch: создовался .tar.gz, искался как директория
- ✅ Outdated paths: /opt/etc/bot/ → /opt/etc/web_ui/

**Новые функции:**
- 🔄 Smart Update с сохранением пользовательских данных
- 💾 Memory Manager с автооптимизацией
- 📡 DNS Monitoring с cloudflored
- 💾 Backup System с списком и удалением
- ⏳ Global loading overlay

**Оптимизации:**
- ⚡ DNS interval: 30s → 60s
- ⚡ DNS timeout: 5s → 3s
- ⚡ KN-1212 RAM: ~25MB → ~15MB

---

## Ссылки

- [[README]] — Основной README проекта
- [[VERSION]] — Версия проекта (1.2.0)
- [[MIGRATION_FROM_TELEGRAM_BOT]] — Миграция с Telegram-бота
- [[DNS_SPOOFING_DESIGN]] — Дизайн DNS-обхода AI-доменов
- [[DNS_SPOOFING_INSTRUCTION]] — Инструкция по DNS-обходу
- [GitHub Repository](https://github.com/royfincher25-source/flymybyte)
- [Issues](https://github.com/royfincher25-source/flymybyte/issues)

---

> **Автор документа:** AI Assistant
> **Дата создания:** 15.03.2026
> **Последнее обновление:** 23.03.2026
> **Версия:** 1.2.0
