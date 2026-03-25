# Инструкция по переходу с Telegram-бота на Web-интерфейс

> **Версия:** 1.0  
> **Дата:** 16.03.2026  
> **Откуда:** `test/` (Telegram-бот)  
> **Куда:** `src/web_ui/` (Web-интерфейс)

---

## 📋 Обзор изменений

| Параметр | Старый проект (test/) | Новый проект (src/web_ui/) |
|----------|----------------------|----------------------------|
| **Тип интерфейса** | Telegram-бот | Web-интерфейс (Flask) |
| **Директория на роутере** | `/opt/etc/bot/` | `/opt/etc/web_ui/` |
| **Порт** | Не требуется | 8080 |
| **Зависимости** | aiogram, asyncio | Flask, Jinja2, Werkzeug |
| **Потребление RAM** | ~5MB | ~15MB |
| **Авторизация** | Telegram ID | Пароль из .env |

---

## ⚠️ Что нужно удалить на роутере

### 1. Остановить Telegram-бота

```bash
# Найти процесс бота
ps | grep python

# Остановить бота
pkill -f "python.*bot"
# или
pkill -f "python.*main.py"
```

### 2. Удалить старую директорию бота

```bash
# Удалить директорию с ботом
rm -rf /opt/etc/bot/

# Удалить скрипт автозапуска (если есть)
rm -f /opt/etc/init.d/S99bypass_bot

# Проверить что удалено
ls -la /opt/etc/ | grep bot
```

### 3. Сохранить конфигурацию (опционально)

```bash
# Создать бэкап перед удалением
mkdir -p /opt/backup/bot_$(date +%Y%m%d_%H%M%S)
cp -r /opt/etc/bot/ /opt/backup/bot_YYYYMMDD_HHMMSS/

# Сохранить .env если есть
cp /opt/etc/bot/.env /opt/backup/bot_env.backup 2>/dev/null
```

---

## 🔄 Пошаговый переход

### Шаг 1: Подготовка

```bash
# 1. Проверить свободное место
df -h /opt
# Требуется: минимум 20MB

# 2. Проверить версию Python
python3 --version
# Требуется: Python 3.8+

# 3. Остановить старого бота
pkill -f "python.*bot"
```

### Шаг 2: Копирование нового проекта

**С локального компьютера (Windows PowerShell):**

```powershell
# Копирование файлов на роутер
scp -r "H:\disk_e\dell\flymybyte\src\web_ui" root@192.168.1.1:/opt/etc/web_ui/
```

**Или через git (на роутере):**

```bash
# Клонировать репозиторий
cd /opt/etc
git clone https://github.com/royfincher25-source/flymybyte.git

# Скопировать web_ui
cp -r FlyMyByte/src/web_ui/* /opt/etc/web_ui/
rm -rf FlyMyByte
```

### Шаг 3: Настройка конфигурации

```bash
# Перейти в директорию
cd /opt/etc/web_ui

# Создать .env из примера
cp .env.example .env

# Отредактировать конфигурацию
nano .env
```

**Минимальная конфигурация:**

```bash
# Web Interface Configuration
WEB_HOST=0.0.0.0
WEB_PORT=8080
WEB_PASSWORD=your_secure_password_here

# Router Configuration
ROUTER_IP=192.168.1.1
UNBLOCK_DIR=/opt/etc/unblock/

# Logging
LOG_FILE=/opt/var/log/web_ui.log
```

> [!WARNING]
> Обязательно измените `WEB_PASSWORD` на сложный пароль!

### Шаг 4: Установка зависимостей

```bash
# Установить зависимости
pip3 install -r /opt/etc/web_ui/requirements.txt

# Проверить установку
pip3 list | grep -E "Flask|Jinja2|Werkzeug"
```

**Зависимости:**
```
Flask==3.0.0
Jinja2==3.1.2
Werkzeug==3.0.0
requests>=2.31.0
waitress==2.1.2 (опционально, production server)
```

### Шаг 4.1: Установка dnsmasq (опционально, рекомендуется)

> [!tip]
> **dnsmasq** обеспечивает автоматическое переключение DNS при отказе.
> Без dnsmasq DNS мониторинг работает, но не может автоматически обновлять конфигурацию.

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
```

**Что даёт dnsmasq:**

| Функция | С dnsmasq | Без dnsmasq |
|---------|-----------|-------------|
| Автопереключение DNS | ✅ Автоматически | ❌ Только логирование |
| Кэширование DNS | ✅ Быстрее | ❌ Нет |
| Централизация | ✅ Все через роутер | ❌ На каждом устройстве |

### Шаг 5: Первый запуск

```bash
# Перейти в директорию
cd /opt/etc/web_ui

# Запустить приложение
python3 app.py &

# Проверить процесс
ps | grep python

# Проверить порт
netstat -tlnp | grep 8080
```

### Шаг 6: Проверка работы

**Открыть в браузере:**
```
http://192.168.1.1:8080
```

**Ввести пароль из .env**

**Проверить разделы:**
- 🔑 Ключи и мосты
- 📑 Списки обхода
- 📲 Установка и удаление
- 📊 Статистика
- ⚙️ Сервис

### Шаг 7: Настройка автозапуска

**Создать скрипт автозапуска:**

```bash
cat > /opt/etc/init.d/S99web_ui << 'EOF'
#!/bin/sh
case "$1" in
  start)
    cd /opt/etc/web_ui
    nohup python3 app.py > /opt/var/log/web_ui.log 2>&1 &
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
```

**Проверка автозапуска:**

```bash
# Перезапустить сервис
/opt/etc/init.d/S99web_ui restart

# Проверить статус
ps | grep python
```

---

## 🔧 Перенос данных

### Ключи и конфигурации

```bash
# Если ключи были в /opt/etc/bot/
# Скопировать в unblock_dir
cp /opt/etc/bot/*.json /opt/etc/unblock/ 2>/dev/null

# Или восстановить из бэкапа
cp /opt/backup/bot_YYYYMMDD/*.json /opt/etc/web_ui/ 2>/dev/null
```

### Списки обхода

```bash
# Списки обхода обычно в /opt/etc/unblock/
# Они остаются на месте, копировать не нужно

# Проверить
ls -la /opt/etc/unblock/
```

### Логи и статистика

```bash
# Логи бота можно сохранить
cp /opt/var/log/bot.log /opt/backup/bot_log.backup 2>/dev/null
```

---

## ✅ Чек-лист проверки

### После установки

```bash
# 1. Проверка процесса
ps | grep python
# ✅ Ожидается: python3 app.py запущен

# 2. Проверка порта
netstat -tlnp | grep 8080
# ✅ Ожидается: порт 8080 открыт

# 3. Проверка логов
tail -f /opt/var/log/web_ui.log
# ✅ Ожидается: нет ошибок ERROR/CRITICAL

# 4. Проверка доступности
curl -I http://localhost:8080
# ✅ Ожидается: HTTP/1.0 302 Found

# 5. Проверка размера логов
ls -lh /opt/var/log/web_ui.log*
# ✅ Ожидается: <300KB
```

### После оптимизаций

```bash
# 1. Потребление памяти
ps | grep python | awk '{print $2}'
# ✅ Ожидается: ~10-15MB

# 2. Проверка кэширования
time curl http://localhost:8080/keys
# ✅ 2-й запрос должен быть быстрее

# 3. Проверка ротации логов
ls -lh /opt/var/log/web_ui.log*
# ✅ Ожидается: 3 файла по ~100KB
```

---

## 🔍 Диагностика проблем

### Бот не останавливается

```bash
# Найти все процессы python
ps | grep python

# Принудительно остановить
pkill -9 -f "python.*bot"

# Проверить что остановлен
ps | grep python
```

### Порт 8080 занят

```bash
# Проверить кто использует порт
netstat -tlnp | grep 8080

# Изменить порт в .env
nano /opt/etc/web_ui/.env
# WEB_PORT=8081

# Перезапустить
pkill -f "python.*app.py"
cd /opt/etc/web_ui
python3 app.py &
```

### Ошибки при запуске

```bash
# Проверить логи
tail -n 50 /opt/var/log/web_ui.log

# Запустить в режиме отладки
cd /opt/etc/web_ui
python3 app.py
# Смотреть вывод в консоль

# Проверить зависимости
pip3 list | grep -E "Flask|Jinja2|Werkzeug"

# Переустановить
pip3 install --force-reinstall -r requirements.txt
```

### Недостаточно памяти

```bash
# Проверить свободную память
free -m

# Остановить лишние процессы
pkill -f "python.*bot"

# Очистить кэш
sync && echo 3 > /proc/sys/vm/drop_caches
```

---

## 📊 Сравнение функционала

| Функция | Telegram-бот | Web-интерфейс |
|---------|--------------|---------------|
| Ключи (VLESS, SS, Trojan, Tor) | ✅ | ✅ |
| Списки обхода | ✅ | ✅ |
| Установка/удаление | ✅ | ✅ |
| Статистика | ✅ | ✅ |
| Перезапуск Unblock | ✅ | ✅ |
| Перезапуск роутера | ✅ | ✅ |
| Перезапуск всех сервисов | ✅ | ✅ |
| DNS Override | ✅ | ✅ |
| Обновления | ✅ | ✅ |
| Бэкап | ✅ | ✅ |
| **Каталог списков** | ❌ | ✅ **НОВОЕ** |
| **DNS мониторинг** | ❌ | ✅ **НОВОЕ** |
| **ipset restore** | ❌ | ✅ **НОВОЕ** |
| **Параллельный DNS** | ❌ | ✅ **НОВОЕ** |

---

## 🎯 Преимущества перехода

### Web-интерфейс

**Преимущества:**
- ✅ Не зависит от Telegram API
- ✅ Работает в локальной сети
- ✅ Наглядный UI с плитками
- ✅ Мобильная адаптация
- ✅ Оптимизации производительности (60x быстрее!)
- ✅ Новые функции (каталог, DNS мониторинг)

**Требования:**
- Порт 8080 открыт локально
- ~15MB RAM
- Python 3.8+

### Telegram-бот

**Преимущества:**
- ✅ Доступ из любой точки мира
- ✅ Меньше потребление RAM (~5MB)

**Недостатки:**
- ❌ Зависит от Telegram API
- ❌ Нет новых оптимизаций
- ❌ Нет каталога списков
- ❌ Нет DNS мониторинга

---

## 🔒 Безопасность

### После установки

```bash
# 1. Изменить пароль по умолчанию
nano /opt/etc/web_ui/.env
# WEB_PASSWORD=your_strong_password_here

# 2. Настроить firewall (опционально)
# Разрешить доступ только из локальной сети

# 3. Включить HTTPS (опционально)
# Использовать reverse proxy (nginx)
```

### Рекомендации

- Используйте сложный пароль (минимум 12 символов)
- Регулярно обновляйте проект
- Делайте бэкапы конфигурации
- Мониторьте логи на предмет ошибок

---

## 📞 Поддержка

**Вопросы и предложения:**
- GitHub Issues: https://github.com/royfincher25-source/flymybyte/issues
- Discussions: https://github.com/royfincher25-source/flymybyte/discussions

**Документация:**
- README.md: Основная документация
- OBSIDIAN_INSTRUCTION.md: Полное руководство
- MIGRATION_TEST_TO_WEB.md: Детали миграции

---

## ✅ Итоговый чек-лист

- [ ] Остановлен Telegram-бот
- [ ] Удалена директория `/opt/etc/bot/`
- [ ] Скопирован новый проект в `/opt/etc/web_ui/`
- [ ] Настроен `.env` с паролем
- [ ] Установлены зависимости
- [ ] Запущено приложение
- [ ] Проверен доступ через браузер
- [ ] Настроен автозапуск
- [ ] Сохранён бэкап конфигурации

**Переход завершён!** 🎉
