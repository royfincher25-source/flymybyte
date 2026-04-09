# Решение проблемы: Telegram Desktop и мобильная версия не работают

## Проблема
После обновления FlyMyByte Telegram работает только в веб-версии, но **не работает** в:
- Telegram Desktop (ПК)
- Telegram для iOS/Android

## Причина

Telegram использует **разные протоколы** для разных версий:

| Версия | Протокол | Что использует |
|--------|----------|----------------|
| **Веб-версия** | HTTPS/WebSocket | Домены (web.telegram.org, t.me) ✅ Работает |
| **Desktop** | MTProto + CDN | IP-диапазоны 149.154.x.x, 91.108.x.x + CDN ❌ Не было |
| **Mobile** | MTProto | IP-диапазоны 95.161.x.x, 185.76.x.x ❌ Не было |

**Проблема:** В обходе были только основные домены, но **НЕ БЫЛИ добавлены**:
1. CDN-серверы Telegram (cdn1-8.telegram-cdn.org)
2. API эндпоинты (pluto, venus, flame, vesta.telegram.org)
3. IP-диапазоны MTProto в ipset

## Решение (версия 2.6.0)

### 1. Добавлены критически важные домены

#### CDN-серверы (фото, видео, файлы)
```
cdn1.telegram-cdn.org
cdn2.telegram-cdn.org
cdn3.telegram-cdn.org
cdn4.telegram-cdn.org
cdn5.telegram-cdn.org
cdn6.telegram-cdn.org
cdn7.telegram-cdn.org
cdn8.telegram-cdn.org
```

#### API и MTProto эндпоинты
```
api.telegram.org
pluto.telegram.org
venus.telegram.org
flame.telegram.org
vesta.telegram.org
```

### 2. Расширены IP-диапазоны

| Диапазон | Назначение |
|----------|-----------|
| `149.154.160.0/20` | Основные серверы Telegram |
| `149.154.164.0/22` | Подсеть основных серверов |
| `149.154.168.0/21` | Подсеть основных серверов |
| `91.108.4.0/22` | Серверы для мобильных приложений |
| `95.161.64.0/19` | Новые серверы (2020+) |
| `5.255.255.0/24` | CDN серверы |
| `185.76.151.0/24` | Дополнительные CDN |

### 3. Создан скрипт автоматического добавления IP

**Файл:** `src/web_ui/resources/scripts/add_telegram_ipranges.sh`

Автоматически добавляет все IP-диапазоны в ipset:
```bash
sh /opt/etc/web_ui/resources/scripts/add_telegram_ipranges.sh
```

## Инструкция по применению

### Вариант 1: OTA обновление (рекомендуется)

1. Дождитесь обновления до версии **2.6.0** в веб-интерфейсе
2. Обновите через **Сервисы → Обновления**
3. После обновления выполните на роутере:
   ```bash
   sh /opt/etc/web_ui/resources/scripts/add_telegram_ipranges.sh
   ```

### Вариант 2: Ручное обновление файлов

1. Скопируйте обновлённые файлы на роутер:
   ```bash
   scp src/web_ui/resources/lists/unblockvless.txt root@192.168.1.1:/opt/etc/unblock/vless.txt
   scp src/web_ui/resources/scripts/add_telegram_ipranges.sh root@192.168.1.1:/opt/etc/web_ui/resources/scripts/
   ```

2. Перезапустите сервисы:
   ```bash
   ssh root@192.168.1.1
   sh /opt/etc/web_ui/resources/scripts/add_telegram_ipranges.sh
   /opt/etc/init.d/S99unblock restart
   /opt/etc/init.d/S56dnsmasq restart
   ```

### Вариант 3: Быстрое решение (если нужно срочно)

```bash
ssh root@192.168.1.1

# Добавьте IP-диапазоны вручную:
ipset add unblockvless 149.154.160.0/20
ipset add unblockvless 149.154.164.0/22
ipset add unblockvless 149.154.168.0/21
ipset add unblockvless 91.108.4.0/22
ipset add unblockvless 95.161.64.0/19
ipset add unblockvless 5.255.255.0/24
ipset add unblockvless 185.76.151.0/24

# Перезапустите dnsmasq:
/opt/etc/init.d/S56dnsmasq restart
```

## Диагностика

**Команды сохранены в H:\disk_e\dell\FlyMyByte\test.txt**

### Быстрая проверка

```bash
# 1. Проверьте IP-диапазоны в ipset
ipset list unblockvless | grep -E "^(149\.154|91\.108|95\.161)"

# 2. Проверьте резолвинг доменов
nslookup cdn1.telegram-cdn.org 127.0.0.1
nslookup api.telegram.org 127.0.0.1

# 3. Полная диагностика
sh /opt/etc/unblock/telegram_diagnosis.sh
```

### Полная диагностика

Выполните на роутере:
```bash
scp H:\disk_e\dell\FlyMyByte\test.txt root@192.168.1.1:/opt/tmp/telegram_diagnosis.sh
ssh root@192.168.1.1 "sh /opt/tmp/telegram_diagnosis.sh"
```

## Проверка результата

После применения обновлений:

1. **Перезагрузите роутер** (не обязательно, но рекомендуется):
   ```bash
   reboot
   ```

2. **Проверьте веб-версию:**
   - Откройте https://web.telegram.org
   - Должна работать ✅

3. **Проверьте Desktop:**
   - Откройте Telegram Desktop
   - Должен подключиться ✅

4. **Проверьте мобильную версию:**
   - Откройте Telegram на телефоне
   - Должен подключиться ✅

## Если проблема сохраняется

### 1. Проверьте логи:
```bash
tail -50 /opt/var/log/web_ui.log
logread | grep -i telegram
```

### 2. Проверьте iptables:
```bash
iptables -L -n -v | grep unblockvless
```
Должны быть правила для редиректа трафика на VPN

### 3. Проверьте статус VPN:
```bash
ps | grep -E "(xray|shadowsocks)" | grep -v grep
```

### 4. Включите отладку в Telegram:
- **Desktop:** Settings → Advanced → Connection Type → Use TCP
- **Mobile:** Settings → Data and Storage → Use Proxy → MTProto

### 5. Временное решение - используйте прокси:
Если обход всё ещё не работает, настройте встроенный прокси в Telegram:
- Settings → Privacy and Security → Proxy
- Добавьте MTProxy с вашего роутера

## Изменённые файлы

| Файл | Изменения |
|------|-----------|
| `src/web_ui/resources/lists/unblockvless.txt` | Добавлены все домены Telegram (CDN, API, MTProto) |
| `bypass_list/telegram.txt` | Полный список доменов + IP-диапазоны с документацией |
| `src/web_ui/resources/scripts/add_telegram_ipranges.sh` | **НОВЫЙ** скрипт автоматического добавления IP |
| `VERSION` | 2.6.0 |
| `CHANGELOG.md` | Запись об изменениях |

## Технические детали

### Архитектура обхода Telegram

```
Telegram Client (Desktop/Mobile)
  │
  ├─ DNS запрос → dnsmasq → резолвит в IP
  │   └─ Домены из /opt/etc/unblock/vless.txt
  │
  ├─ Подключение к IP → iptables проверяет ipset
  │   └─ IP из диапазонов Telegram → редирект на VPN
  │
  └─ VPN туннель (VLESS/Shadowsocks)
      └─ Трафик идёт через внешний сервер
```

### Почему веб-версия работала, а Desktop нет?

**Веб-версия:**
- Использует только HTTPS (порт 443)
- Обходится через dnsmasq + ipset (домены → IP → редирект)

**Desktop/Mobile:**
- Использует **MTProto протокол** на прямых IP
- Подключается к `149.154.x.x`, `91.108.x.x` напрямую
- **БЕЗ добавления IP в ipset — редиректа нет!**

### Источник IP-диапазонов

Официальный список: https://core.telegram.org/resources/cidr.txt

Актуальные диапазоны на 2026-04-09:
- 149.154.160.0/20
- 149.154.164.0/22
- 149.154.168.0/21
- 91.108.4.0/22
- 95.161.64.0/19

Дополнительно добавлены (из практики):
- 5.255.255.0/24 (CDN)
- 185.76.151.0/24 (CDN)

---

**Дата создания:** 2026-04-09  
**Версия:** 2.6.0  
**Статус:** ✅ Готово к применению  
**Коммит:** `8b3bd73`
