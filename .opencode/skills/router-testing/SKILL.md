---
name: router-testing
description: Используй перед тестированием изменений на Keenetic роутере. Включает workflow обновления, проверки и отладки.
---

<skill_content name="router-testing">

# Router Testing Skill

## Когда использовать

- После любого изменения кода, который нужно протестировать на роутере
- Перед мержем в master
- При отладке проблем на роутере

## Workflow

### 1. Обновление файлов на роутере

```bash
# Основные файлы
curl -o /opt/bin/unblock.py https://raw.githubusercontent.com/royfincher25-source/flymybyte/master/src/web_ui/resources/scripts/unblock.py

curl -o /opt/etc/init.d/S99unblock https://raw.githubusercontent.com/royfincher25-source/flymybyte/master/src/web_ui/resources/scripts/S99unblock

curl -o /opt/etc/ndm/netfilter.d/100-redirect.sh https://raw.githubusercontent.com/royfincher25-source/flymybyte/master/src/web_ui/resources/scripts/100-redirect.sh
```

### 2. Перезапуск сервисов

```bash
# Полный перезапуск (рекомендуется)
/opt/etc/init.d/S99unblock restart

# Или остановить + запустить
/opt/etc/init.d/S99unblock stop
sleep 2
/opt/etc/init.d/S99unblock start
```

### 3. Проверка watchdog процессов

```bash
# Должен быть ровно 1 процесс
for f in /proc/[0-9]*/cmdline; do 
    grep -q "dnsmasq_watchdog" "$f" 2>/dev/null && basename $(dirname "$f")
done | wc -l
```

### 4. Проверка логов

```bash
# S99unblock лог
tail -50 /opt/var/log/S99unblock.log

# Web UI лог
tail -50 /opt/var/log/web_ui.log
```

## Debug команды

### Проверить конкретный процесс
```bash
# watchdog
ls /proc/25048/cmdline 2>/dev/null && echo "Found" || echo "Not found"

# Проверить lockfile
cat /tmp/dnsmasq_watchdog.pid
```

### Проверить все watchdog
```bash
for f in /proc/[0-9]*/cmdline; do 
    if grep -q "dnsmasq_watchdog" "$f" 2>/dev/null; then 
        echo "PID: $(basename $(dirname "$f"))"
    fi
done
```

### Убить зависший процесс
```bash
# По PID
kill -9 <PID>

# Все watchdog
for f in /proc/[0-9]*/cmdline; do 
    if grep -q "dnsmasq_watchdog" "$f" 2>/dev/null; then 
        kill -9 $(basename $(dirname "$f"))
    fi
done
```

## BusyBox команды (работают)

- `/proc/[0-9]*` — итерация по процессам
- `tr '\0' '\n'` — чтение cmdline
- `[ "$pid_num" -eq "$pid_num" ]` — проверка числа
- `grep -q` — тихий grep

## BusyBox команды (НЕ работают)

- `pkill`, `pgrep`
- некоторые опции `head`, `tail`

## Всегда проверяй

1. ✅ Файл скачался (размер > 0)
2. ✅ Процесс запустился
3. ✅ Лог не содержит ошибок
4. ✅ Один watchdog (не больше)

## После каждого изменения

После каждого `git commit` выводи таблицу изменений с путями на роутере:

```
| Файл | Изменения | На роутере |
|------|----------|-----------|
| path/to/file.py | +X/-Y строк | /путь/на/роутере |
```

Пример:
```
| Файл | Изменения | На роутере |
|------|----------|-----------|
| README.md | +9 строк | - |
| src/web_ui/core/constants.py | +2 строки | @web_ui |
| src/web_ui/resources/scripts/S99unblock | +43 строки | /opt/etc/init.d/S99unblock |
| src/web_ui/resources/scripts/vpn_watchdog.sh | Новый (+147) | /opt/bin/vpn_watchdog.sh |
```

Команда для получения:
```bash
git diff master --stat
```

## Маппинг путей файлов

| Папка проекта | На роутере |
|---------------|-----------|
| src/web_ui/resources/scripts/ | /opt/bin/ или /opt/etc/init.d/ |
| src/web_ui/core/*.py | @web_ui (встроен) |
| src/web_ui/routes_*.py | @web_ui (встроен) |
| src/web_ui/templates/*.html | @web_ui/templates/ |
| README.md | - (не копируется) |

Основные скрипты:
- `S99unblock` -> `/opt/etc/init.d/S99unblock`
- `vpn_watchdog.sh` -> `/opt/bin/vpn_watchdog.sh`
- `dnsmasq_watchdog.sh` -> `/opt/bin/dnsmasq_watchdog.sh`
- `unblock.py` -> `/opt/bin/unblock.py`
- `100-redirect.sh` -> `/opt/etc/ndm/netfilter.d/100-redirect.sh`

## Notes (см. ROUTER_NOTES.md)

- Git на роутере НЕ установлен
- Timeout NDMS API — 5 секунд
- Lockfile: `/tmp/dnsmasq_watchdog.pid`

</skill_content>