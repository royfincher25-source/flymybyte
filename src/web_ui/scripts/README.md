# Scripts Directory

Эта директория содержит скрипты для установки и удаления flymybyte с веб-интерфейсом.

## Файлы

- `install_web.sh` — установщик веб-интерфейса в одну команду
- `script.sh` — основной скрипт установки/удаления flymybyte
- `script.sh.md5` — MD5 хэш для проверки целостности
- `.gitkeep` — файл для отслеживания директории в git
- `README.md` — эта документация

## Установка

### Быстрая установка (рекомендуется)

```bash
curl -sL https://raw.githubusercontent.com/royfincher25-source/flymybyte/master/src/web_ui/scripts/install_web.sh | sh
```

### Ручная установка

```bash
# Копирование на роутер
scp scripts/install_web.sh root@192.168.1.1:/opt/root/
scp scripts/script.sh root@192.168.1.1:/opt/root/

# Установка
/opt/root/install_web.sh
# или
/opt/root/script.sh -install
```

## Обновление скрипта

Для обновления script.sh:

```bash
# Отредактировать script_web.sh
# Скопировать в script.sh
copy script_web.sh script.sh

# Обновить MD5 хэш
certutil -hashfile script.sh MD5 > script.sh.md5
```

## Использование

### Установка

```bash
/opt/root/script.sh -install
```

**Что делает:**
1. Устанавливает пакеты (curl, python3, python3-pip)
2. Настраивает ipset для маршрутизации
3. Загружает шаблоны конфигураций VPN
4. Устанавливает скрипты unblock
5. **Устанавливает веб-интерфейс** в `/opt/etc/web_ui/`
6. Создаёт `web_config.py` с параметрами
7. Устанавливает `S99web_ui` для автозапуска
8. Запускает веб-интерфейс

### Удаление

```bash
/opt/root/script.sh -remove
```

**Что делает:**
1. Удаляет пакеты
2. Очищает ipset множества
3. Удаляет файлы и директории flymybyte
4. **Удаляет веб-интерфейс** из `/opt/etc/web_ui/`
5. Удаляет `S99web_ui`

### Обновление

```bash
/opt/root/script.sh -update
```

**Что делает:**
1. Обновляет пакеты
2. **Обновляет файлы веб-интерфейса**
3. Обновляет core модули
4. Перезапускает веб-интерфейс

### Диагностика

```bash
/opt/root/script.sh -var
```

Показывает все переменные конфигурации.

## Принцип работы

1. Веб-интерфейс копирует `script.sh` из локальной директории `scripts/`
2. Скрипт размещается в `/opt/root/script.sh` на роутере
3. Скрипт запускается с аргументом `-install`, `-remove` или `-update`
4. `script.sh` читает конфигурацию из `/opt/etc/web_ui/core/web_config.py`
5. Устанавливает/удаляет/обновляет компоненты flymybyte и веб-интерфейс

## URL для загрузки файлов

Скрипт использует `base_url` из конфигурации:

```python
base_url = "https://raw.githubusercontent.com/royfincher25-source/flymybyte/main"
```

**Важно:** Убедитесь, что `web_config.py` содержит правильный URL!

## Структура веб-интерфейса

После установки:

```
/opt/etc/web_ui/
├── app.py              # Flask приложение
├── routes_service.py   # Blueprint: система, логи, обновления
├── routes_keys.py      # Blueprint: VPN-ключи
├── routes_bypass.py    # Blueprint: списки обхода
├── env_parser.py       # Парсер .env
├── requirements.txt    # Зависимости Python
├── .env.example        # Шаблон конфигурации
├── VERSION             # Версия
├── core/
│   ├── config.py
│   ├── utils.py
│   ├── services.py
│   ├── ipset_manager.py
│   ├── list_catalog.py
│   ├── dns_manager.py
│   ├── app_config.py
│   ├── web_config.py   # Конфигурация (генерируется)
│   └── __init__.py
└── templates/          # HTML шаблоны
```

## Автозапуск

Скрипт `S99web_ui`:

```bash
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
```

**Проверка статуса:**

```bash
# Проверить процесс
ps | grep python

# Проверить порт
netstat -tlnp | grep 8080

# Проверить логи
tail -f /opt/var/log/web_ui.log
```
