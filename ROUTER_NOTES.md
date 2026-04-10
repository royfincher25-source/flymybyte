# FlyMyByte Router Notes — Keenetic Specific Knowledge Base

## Версия
- Текущая: 2.9.6

## BusyBoxshell ограничения

### Недоступные команды
- `pkill`, `pgrep` — нет в BusyBox
- `head`, `tail` — ограничены (нет некоторых опций)
- `grep` — базовый, без -E в некоторых случаях
- `xargs` — работает, но с предупреждениями о NUL characters

### Работающие подходы
- `/proc/[0-9]*` — итерация по процессам вместо `ps`
- `grep -q` внутри цикла for по /proc
- `tr '\0' '\n'` для чтения cmdline
- Проверка PID через `[ "$pid_num" -eq "$pid_num" ]` (is numeric)
- Удаление stale lockfiles вручную

## NDMS API ( Keenetic)

- API доступен через `localhost:79/rci/...`
- Timeout по умолчанию 5 секунд (нужно учитывать)
- JSON формат ответа
- Пример: `curl -s localhost:79/rci/show/interface`

## IPTables на Keenetic

- Работает стандартно
- Особенность: `iptables -C` (check) может возвращать ошибку даже если правило существует
- Решение: использовать `-D` (delete) в цикле для удаления дубликатов

## Git на роутере

- **НЕТ** — git не установлен
- Решение: обновлять файлы через `curl` с GitHub

## Python на роутере

- `/opt/bin/python3` — доступен
- Кэширование байт-кода: нужно удалять `__pycache__` при обновлении
- sys.path нужно настраивать для импортов

## Структура директорий

```
/opt/bin/              # Скрипты
/opt/etc/web_ui/      # Основной код
/opt/etc/ndm/netfilter.d/  # iptables скрипты
/opt/etc/ndm/ifstatechanged.d/ # VPN скрипты
/opt/etc/init.d/      # Init скрипты
/opt/var/log/        # Логи
/tmp/                # Временные файлы (в т.ч. lockfiles)
```

## Полезные команды для debug

```bash
# Проверить процессы watchdog
for f in /proc/[0-9]*/cmdline; do 
    grep -q "dnsmasq_watchdog" "$f" 2>/dev/null && basename $(dirname "$f")
done

# Проверить lockfile
cat /tmp/dnsmasq_watchdog.pid

# Лог S99unblock
tail -50 /opt/var/log/S99unblock.log

# Лог web_ui
tail -50 /opt/var/log/web_ui.log
```

## Git Workflow

1. Все изменения в feature branch
2. Тест на роутере через curl обновление файлов
3. Код-ревью
4. Merge в master
5. На роутере: `cd /opt/etc/web_ui && git pull` (если есть git) или `curl` обновление

## VPN интерфейсы Keenetic

- Типы: IKE, SSTP, OpenVPN, Wireguard, VPNL2TP
- Определяются через NDMS API
- Настройка маршрутизации через ip rule / ip route
- RT tables: `/opt/etc/iproute2/rt_tables`

## Обновление файлов на роутере

```bash
# Скрипты
curl -o /opt/bin/unblock.py https://raw.githubusercontent.com/.../unblock.py

# Init скрипты
curl -o /opt/etc/init.d/S99unblock https://raw.githubusercontent.com/.../S99unblock

# Обновить все при загрузке
/opt/etc/init.d/S99unblock restart
```

## Известные баги и решения

1. **Множественные watchdog** — убивать через /proc, удалять lockfile
2. **pkill не работает** — использовать цикл по /proc
3. **iptables -C ошибка** — использовать цикл с -D
4. **API timeout** — увеличить timeout до 10+ сек

## TODO

- [ ] Заменить refresh_ipset.sh → Python
- [ ] Объединить DNS-обход AI (отложено)
- [ ] Использовать core/handlers.py в routes