# Скрипты для роутера Keenetic

Директория содержит скрипты для развёртывания на роутере.

---

## 📋 Список скриптов

| Скрипт | Назначение |
|--------|------------|
| [`full_check.sh`](#full_checksh) | Полная диагностика системы |
| [`check_bypass.sh`](#check_bypasssh) | Быстрая проверка обхода |
| [`check_routing.sh`](#check_routingsh) | Проверка маршрутизации |
| [`apply_routing.sh`](#apply_routingsh) | Применение правил маршрутизации |
| [`restart_web_ui.sh`](#restart_web_uish) | Перезапуск веб-интерфейса |

---

## 🔧 full_check.sh

**Назначение:** Полная диагностика системы после перезагрузки или при проблемах.

### Использование:

```bash
# 1. Копирование на роутер
scp full_check.sh root@192.168.1.1:/opt/root/

# 2. Запуск
ssh root@192.168.1.1 -p 222 "sh /opt/root/full_check.sh"
```

### Проверяет:

1. ✅ **Shadowsocks** — конфигурация и процесс
2. ✅ **dnsmasq** — процесс и порт 53
3. ✅ **DNS Override** — статус через ndmc
4. ✅ **ipset** — наличие и количество записей
5. ✅ **iptables (NAT)** — правила перенаправления трафика
6. ✅ **Веб-интерфейс** — процесс и порт 8080
7. ✅ **DNS** — тестовый запрос google.com
8. ✅ **Логи** — поиск ошибок

### Пример вывода:

```
============================================================
ПОЛНАЯ ДИАГНОСТИКА ПОСЛЕ ПЕРЕЗАГРУЗКИ
============================================================

[1/8] Проверка Shadowsocks...
✅ Конфигурация найдена
✅ Shadowsocks запущен (PID: 570)

[2/8] Проверка dnsmasq...
✅ dnsmasq запущен (PID: 1229)
✅ Порт 53 слушается

...

[5/8] Проверка iptables (NAT)...
❌ NAT правила НЕ найдены
   Трафик НЕ перенаправляется через Shadowsocks!

============================================================
ИТОГОВАЯ СВОДКА
============================================================
Ошибки: 3
Предупреждения: 2

❌ НАЙДЕНЫ ПРОБЛЕМЫ

БЫСТРЫЕ КОМАНДЫ ДЛЯ ИСПРАВЛЕНИЯ:
================================

# Применение правил маршрутизации:
sh /opt/bin/unblock_ipset.sh && sh /opt/etc/ndm/netfilter.d/100-redirect.sh
```

---

## 🔍 check_bypass.sh

**Назначение:** Быстрая проверка работы обхода блокировок.

### Использование:

```bash
# Копирование на роутер
scp check_bypass.sh root@192.168.1.1:/opt/root/

# Запуск
ssh root@192.168.1.1 -p 222 "sh /opt/root/check_bypass.sh"
```

### Проверяет:

1. Entware
2. dnsmasq (процесс + порт)
3. Shadowsocks (конфиг + процесс)
4. DNS Override (статус)
5. Списки обхода (файлы + записи)
6. Конфигурация dnsmasq
7. Веб-интерфейс
8. Логи
9. Тест DNS
10. ipset

---

## 🛣️ check_routing.sh

**Назначение:** Проверка маршрутизации трафика.

### Использование:

```bash
# Копирование на роутер
scp check_routing.sh root@192.168.1.1:/opt/root/

# Запуск
ssh root@192.168.1.1 -p 222 "sh /opt/root/check_routing.sh"
```

### Проверяет:

1. ipset (unblocksh, unblocktor, unblockvless, unblocktroj)
2. iptables (NAT правила)
3. Маршрутизация (ip rule)
4. Интеграция dnsmasq + ipset
5. Скрипт unblock_dnsmasq.sh

---

## 🔥 apply_routing.sh

**Назначение:** Применение правил маршрутизации трафика.

### Использование:

```bash
# Копирование на роутер
scp apply_routing.sh root@192.168.1.1:/opt/root/

# Запуск
ssh root@192.168.1.1 -p 222 "sh /opt/root/apply_routing.sh"
```

### Выполняет:

1. Создание ipset (unblocksh, unblocktor, unblockvless, unblocktroj)
2. Заполнение ipset из списков обхода
3. Применение правил iptables для всех сервисов

### После выполнения:

```bash
# Проверка правил
iptables-save -t nat | grep 1082

# Ожидается:
# -A PREROUTING -p tcp -m set --match-set unblocksh dst -j REDIRECT --to-ports 1082
# -A PREROUTING -p udp -m set --match-set unblocksh dst -j REDIRECT --to-ports 1082
```

---

## 🔄 restart_web_ui.sh

**Назначение:** Очистка кэша, логов и перезапуск веб-интерфейса.

### Использование:

```bash
# Копирование на роутер
scp restart_web_ui.sh root@192.168.1.1:/opt/root/

# Запуск
ssh root@192.168.1.1 -p 222 "sh /opt/root/restart_web_ui.sh"
```

### Выполняет:

1. Остановка веб-интерфейса
2. Очистка кэша Python (`__pycache__`)
3. Очистка логов (`web_ui.log`)
4. Запуск веб-интерфейса
5. Показ последних 10 строк лога

---

## 📥 Развёртывание всех скриптов

```powershell
# Из Windows (PowerShell)
$router = "root@192.168.1.1"
$port = "222"
$dest = "/opt/root/"

scp full_check.sh $router:$dest
scp check_bypass.sh $router:$dest
scp check_routing.sh $router:$dest
scp apply_routing.sh $router:$dest
scp restart_web_ui.sh $router:$dest

# Запуск диагностики
ssh -p $port $router "sh /opt/root/full_check.sh"
```

---

## 🐛 Быстрое исправление проблем

### Проблема: YouTube не работает

```bash
# 1. Диагностика
ssh root@192.168.1.1 -p 222 "sh /opt/root/full_check.sh"

# 2. Если iptables правила не найдены
ssh root@192.168.1.1 -p 222 "sh /opt/root/apply_routing.sh"

# 3. Проверка
ssh root@192.168.1.1 -p 222 "iptables-save -t nat | grep 1082"
```

### Проблема: Веб-интерфейс не доступен

```bash
# Перезапуск
ssh root@192.168.1.1 -p 222 "sh /opt/root/restart_web_ui.sh"
```

### Проблема: После перезагрузки не работает

```bash
# Полная диагностика
ssh root@192.168.1.1 -p 222 "sh /opt/root/full_check.sh"

# Применение правил
ssh root@192.168.1.1 -p 222 "sh /opt/root/apply_routing.sh"
```

---

## 📊 Сводная таблица

| Скрипт | Диагностика | Исправление | Перезапуск |
|--------|-------------|-------------|------------|
| `full_check.sh` | ✅ Полная | ✅ Рекомендации | ❌ |
| `check_bypass.sh` | ✅ Быстрая | ❌ | ❌ |
| `check_routing.sh` | ✅ Маршрутизация | ❌ | ❌ |
| `apply_routing.sh` | ❌ | ✅ Правила | ❌ |
| `restart_web_ui.sh` | ❌ | ❌ | ✅ Веб-интерфейс |

---

## 🔗 См. также

- [`docs/FIX_ROUTING.md`](../docs/FIX_ROUTING.md) — Исправление маршрутизации
- [`docs/CHECK_BYPASS_INSTRUCTION.md`](../docs/CHECK_BYPASS_INSTRUCTION.md) — Инструкция по проверке обхода
