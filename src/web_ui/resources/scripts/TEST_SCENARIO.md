# FlyMyByte — Сценарий запуска и тестирования bypass системы

## 1. Процесс запуска (step-by-step)

### Запуск: `S99unblock start`

```
S99unblock start
  │
  ├── Step 1: dnsmasq restart + sleep 2
  │     └─ dnsmasq слушает порт 5353 (из dnsmasq.conf: port=5353)
  │
  ├── Step 2: /opt/bin/unblock_ipset.sh
  │     ├── Проверяет DNS через 8.8.8.8 (timeout 30 сек)
  │     │   └─ FAIL → exit 1 → IPSET_OK=false
  │     ├── Определяет память → кол-во потоков (1-4)
  │     ├── Параллельно резолвит домены из файлов:
  │     │     shadowsocks.txt → unblocksh
  │     │     hysteria2.txt   → unblockhysteria2
  │     │     tor.txt         → unblocktor
  │     │     vless.txt       → unblockvless
  │     │     trojan.txt      → unblocktroj
  │     │     vpn-*.txt       → unblockvpn_*
  │     └─ Summary: кол-во записей в каждом ipset
  │
  ├── Step 3: Проверка ipset entries
  │     └─ TOTAL_ENTRIES < 1 → IPSET_OK=false → SKIP Step 4
  │
  ├── Step 4: /opt/etc/ndm/netfilter.d/100-redirect.sh
  │     │     (ТОЛЬКО если IPSET_OK=true)
  │     ├── Создаёт пустые ipset (hash:net -exist)
  │     ├── Проверяет dnsmasq:5353 (netstat/ss)
  │     │   └─ Не слушает → restart + wait 3 сек
  │     │       └─ Всё ещё нет → DNS redirect SKIP
  │     ├── DNS DNAT: port 53 → local_ip:5353 (tcp+udp)
  │     ├── add_redirect unblocksh     → 1082
  │     ├── add_redirect unblocktor    → 9141
  │     ├── add_redirect unblockvless  → 10810
  │     ├── add_redirect unblocktroj   → 10829
  │     └─ VPN rules (mangle MARK/CONNMARK)
  │
  └── Step 5: dnsmasq_watchdog.sh &
        └─ Каждые 15 сек проверяет порт 5353
            ├─ Упал → убирает DNS DNAT → пробует restart (3 раза)
            └─ Поднялся → восстанавливает DNS DNAT
```

---

## 2. Лог-файлы для проверки

| Лог | Что смотреть |
|-----|-------------|
| `/opt/var/log/S99unblock.log` | Общая цепочка: dnsmasq → ipset → redirect → watchdog |
| `/opt/var/log/unblock_ipset.log` | DNS OK? Сколько записей в каждом ipset? |
| `/opt/var/log/100-redirect.log` | dnsmasq:5353 listening? DNAT добавлен? Правила для сервисов? |
| `/opt/var/log/unblock_dnsmasq.log` | Конфиг dnsmasq сгенерирован? Рестарт OK? |
| `/opt/var/log/dnsmasq_watchdog.log` | dnsmasq жив? DNAT активен? |
| `/opt/var/log/web_ui.log` | Python-side операции |
| `/opt/var/log/emergency_restore.log` | Результат экстренного восстановления |
| `/opt/var/log/rollback.log` | Результат отката к backup |

---

## 3. Сценарии отказа и что произойдёт

| Сценарий | Результат | Интернет |
|----------|-----------|----------|
| DNS недоступен | `unblock_ipset.sh` exit 1 → redirect rules НЕ применяются | **Работает** |
| dnsmasq:5353 не стартовал | DNS DNAT НЕ добавляется → обычный DNS через 8.8.8.8 | **Работает** |
| ipset пустой (файлы пустые) | Step 3 detect → redirect rules SKIP | **Работает** |
| dnsmasq упал после старта | Watchdog за 15 сек уберёт DNAT → DNS через 8.8.8.8 | **Работает** |
| Всё сломалось | `/opt/bin/emergency_restore.sh` — чистит всё | **Восстанавливает** |
| Нужен полный откат | `/opt/bin/rollback.sh` — из архива `/opt/root/backup/` | **Восстанавливает** |

---

## 4. Команды для тестирования на роутере

### 4.1. Запуск bypass системы

```sh
# Запуск
/opt/etc/init.d/S99unblock start

# Перезапуск
/opt/etc/init.d/S99unblock restart

# Остановка
/opt/etc/init.d/S99unblock stop
```

### 4.2. Проверка логов

```sh
# Порядок просмотра — от общего к частному
cat /opt/var/log/S99unblock.log
cat /opt/var/log/unblock_ipset.log
cat /opt/var/log/100-redirect.log
cat /opt/var/log/unblock_dnsmasq.log
cat /opt/var/log/dnsmasq_watchdog.log
```

### 4.3. Проверка ipset

```sh
# Список всех ipset
ipset list -n

# Содержимое конкретного (первые 20 записей)
ipset list unblocksh | head -20
ipset list unblocktor | head -20
ipset list unblockvless | head -20
ipset list unblocktroj | head -20
ipset list unblockhysteria2 | head -20

# Кол-во записей
ipset list unblocksh | grep -c "^[0-9]"
ipset list unblocktor | grep -c "^[0-9]"
```

### 4.4. Проверка iptables

```sh
# NAT PREROUTING (DNS redirect + service redirect)
iptables -t nat -L PREROUTING -n -v

# Mangle PREROUTING (VPN mark rules)
iptables -t mangle -L PREROUTING -n -v

# Полная картина
iptables-save | head -50
```

### 4.5. Проверка dnsmasq

```sh
# Слушает ли порт 5353
netstat -tlnp | grep 5353
# или
ss -tlnp | grep 5353

# Процесс dnsmasq
ps | grep dnsmasq

# Проверка DNS через dnsmasq
nslookup google.com 127.0.0.1 -p 5353

# Проверка обычного DNS
nslookup google.com 8.8.8.8
```

### 4.6. Проверка watchdog

```sh
# Процесс watchdog
ps | grep dnsmasq_watchdog

# Лог watchdog
cat /opt/var/log/dnsmasq_watchdog.log
```

---

## 5. Аварийные команды

### 5.1. Экстренное восстановление интернета

```sh
# Убирает DNAT, чистит iptables/ipset, рестартует dnsmasq
/opt/bin/emergency_restore.sh

# Лог результата
cat /opt/var/log/emergency_restore.log
```

### 5.2. Полный откат к backup

```sh
# Использует последний архив из /opt/root/backup/
/opt/bin/rollback.sh

# Или указать конкретный архив
/opt/bin/rollback.sh /opt/root/backup/update_backup_20260401_161354.tar.gz

# Лог результата
cat /opt/var/log/rollback.log
```

### 5.3. Ручная чистка (если скрипты недоступны)

```sh
# Убрать DNS DNAT
iptables -t nat -F PREROUTING

# Очистить ipset
for s in unblocksh unblockhysteria2 unblocktor unblockvless unblocktroj; do ipset flush $s; done

# Рестарт dnsmasq
/opt/etc/init.d/S56dnsmasq restart
```

---

## 6. Чек-лист успешного запуска

- [ ] `S99unblock.log` — нет ERROR, все шаги выполнены
- [ ] `unblock_ipset.log` — DNS OK, записи в ipset > 0
- [ ] `100-redirect.log` — dnsmasq:5353 listening, DNAT добавлен, redirect rules добавлены
- [ ] `ipset list unblocksh` — записи > 0
- [ ] `iptables -t nat -L PREROUTING -n -v` — есть правила DNAT и REDIRECT
- [ ] `netstat -tlnp | grep 5353` — dnsmasq слушает
- [ ] `nslookup google.com 127.0.0.1` — DNS работает
- [ ] `curl http://google.com` — интернет работает
- [ ] `ps | grep dnsmasq_watchdog` — watchdog запущен
