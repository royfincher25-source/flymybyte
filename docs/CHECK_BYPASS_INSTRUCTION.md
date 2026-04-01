# ✅ Проверка настройки обхода блокировок

**Дата:** 23 марта 2026 г.  
**Версия:** 1.2

---

## 🚀 Быстрая проверка (3 команды)

```bash
# 1. Подключение к роутеру
ssh root@192.168.1.1 -p 222

# 2. Запуск диагностики
sh /opt/root/check_bypass.sh

# 3. Проверка логов
tail -50 /opt/var/log/web_ui.log
```

---

## 🆕 Проверка DNS-обхода AI-доменов

### 1. Проверка конфигурации

```bash
# Проверка наличия конфига
ls -la /opt/etc/unblock-ai.dnsmasq

# Проверка содержимого
cat /opt/etc/unblock-ai.dnsmasq
```

**✅ Ожидается:**
```conf
# AI Domains DNS Spoofing
server=/aistudio.google.com/127.0.0.1#40500
server=/gemini.google.com/127.0.0.1#40500
...
```

### 2. Проверка списка доменов

```bash
# Проверка списка AI-доменов
ls -la /opt/etc/unblock/ai-domains.txt
cat /opt/etc/unblock/ai-domains.txt
```

**✅ Ожидается:**
```
aistudio.google.com
gemini.google.com
colab.research.google.com
kaggle.com
...
```

### 3. Тест разрешения доменов

```bash
# Тест через nslookup
nslookup aistudio.google.com 192.168.1.1

# Тест через dig
dig @192.168.1.1 aistudio.google.com
```

**✅ Ожидается:** IP адрес (не блокируемый)

### 4. Проверка через веб-интерфейс

```bash
# Проверка статуса
curl -s http://192.168.1.1:8080/dns-spoofing/status | python3 -m json.tool
```

**✅ Ожидается:**
```json
{
  "enabled": true,
  "domain_count": 20,
  "config_exists": true,
  "dnsmasq_running": true
}
```

### 5. Проверка доступности AI-сервисов

```bash
# Тест через curl с прокси
curl -x socks5h://127.0.0.1:1082 https://aistudio.google.com -I

# Ожидается: 200 OK или редирект
```

---

## 📋 Полный чек-лист

### 1. Проверка Entware

```bash
ls -la /opt
```

**✅ Ожидается:** Директория `/opt` существует, есть папки `bin`, `etc`, `lib`

---

### 2. Проверка dnsmasq

```bash
# Проверка скрипта
ls -la /opt/etc/init.d/S56dnsmasq

# Проверка процесса
ps | grep dnsmasq

# Проверка порта 53
netstat -tlnp | grep :53
```

**✅ Ожидается:**
- ✅ Скрипт существует
- ✅ Процесс запущен
- ✅ Порт 53 слушается на 192.168.1.1

---

### 3. Проверка Shadowsocks

```bash
# Проверка конфигурации
cat /opt/etc/shadowsocks.json

# Проверка процесса
ps | grep ss-redir

# Проверка порта 1082
netstat -tlnp | grep :1082
```

**✅ Ожидается:**
- ✅ Файл конфигурации существует
- ✅ Процесс запущен
- ✅ Порт 1082 слушается

---

### 4. Проверка DNS Override

```bash
ndmc -c 'show running' | include dns-override
```

**✅ Ожидается:** Вывод содержит строку с `dns-override`

**❌ Если пусто:** DNS Override выключен

```bash
# Включить через веб-интерфейс:
# http://192.168.1.1:8080/service → DNS Override → ВКЛ
```

---

### 5. Проверка списков обхода

```bash
# Проверка директории
ls -la /opt/etc/unblock/

# Проверка количества записей
wc -l /opt/etc/unblock/*.txt
```

**✅ Ожидается:**
- ✅ Директория существует
- ✅ Есть файлы `shadowsocks.txt`, `tor.txt`, `vless.txt`
- ✅ В файлах есть записи (не пустые)

---

### 6. Проверка веб-интерфейса

```bash
# Проверка процесса
ps | grep -E "waitress|python.*web_ui"

# Проверка порта 8080
netstat -tlnp | grep :8080
```

**✅ Ожидается:**
- ✅ Процесс запущен
- ✅ Порт 8080 слушается

---

### 7. Проверка логов

```bash
# Последние ошибки
tail -50 /opt/var/log/web_ui.log

# Логи в реальном времени
tail -f /opt/var/log/web_ui.log
```

**✅ Ожидается:**
- ✅ Нет ошибок `ERROR`
- ✅ Есть сообщения об успешном старте

---

### 8. Тест DNS

```bash
# Запрос через локальный DNS
dig +short google.com @192.168.1.1 -p 53

# Или через nslookup
nslookup google.com 192.168.1.1
```

**✅ Ожидается:** Возвращается IP адрес (например, `142.250.185.78`)

---

### 9. Тест обхода блокировок

```bash
# Запрос через Shadowsocks (если есть curl)
curl -x socks5h://127.0.0.1:1082 https://example.com

# Или проверка разрешения домена
nslookup rutracker.org 192.168.1.1
```

**✅ Ожидается:** Домен разрешается, возвращается IP

---

## 🔧 Автоматическая диагностика

Скопируйте скрипт диагностики на роутер:

```bash
# Копирование
scp H:\disk_e\dell\flymybyte\scripts\check_bypass.sh root@192.168.1.1:/opt/root/

# Запуск
ssh root@192.168.1.1 -p 222 "sh /opt/root/check_bypass.sh"
```

**Скрипт проверит:**
1. ✅ Entware
2. ✅ dnsmasq (процесс + порт)
3. ✅ Shadowsocks (конфиг + процесс)
4. ✅ DNS Override (статус)
5. ✅ Списки обхода (файлы + записи)
6. ✅ Конфигурация dnsmasq
7. ✅ Веб-интерфейс
8. ✅ Логи
9. ✅ Тест DNS
10. ✅ ipset

---

## 📊 Интерпретация результатов

| Компонент | Статус | Действие |
|-----------|--------|----------|
| **Entware** | ❌ | Установить Entware |
| **dnsmasq** | ❌ | Запустить: `/opt/etc/init.d/S56dnsmasq start` |
| **Shadowsocks** | ❌ | Настроить ключ через веб-интерфейс |
| **DNS Override** | ❌ | Включить через `/service` |
| **Списки обхода** | ❌ | Добавить списки через `/bypass/catalog` |
| **Веб-интерфейс** | ❌ | Перезапустить: `S99web_ui restart` |

---

## 🎯 Минимальный набор для работы

Для работы обхода блокировок **необходимо**:

1. ✅ **Entware** установлен
2. ✅ **dnsmasq** запущен (порт 53)
3. ✅ **Shadowsocks** настроен (ключ валиден)
4. ✅ **DNS Override** включен
5. ✅ **Списки обхода** содержат домены

---

## 📝 Примеры команд

### Перезапуск всех сервисов:
```bash
sh /opt/root/restart_web_ui.sh
```

### Проверка логов в реальном времени:
```bash
tail -f /opt/var/log/web_ui.log
```

### Тестовый запрос DNS:
```bash
dig +short google.com @192.168.1.1 -p 53
```

### Проверка статуса Shadowsocks:
```bash
/opt/etc/init.d/S22shadowsocks status
```

---

## 🐛 Частые проблемы

| Проблема | Решение |
|----------|---------|
| **DNS Override выключен** | Веб-интерфейс → /service → DNS Override → ВКЛ |
| **dnsmasq не запущен** | `/opt/etc/init.d/S56dnsmasq start` |
| **Shadowsocks не запускается** | Проверить ключ в `/opt/etc/shadowsocks.json` |
| **Порт 53 не слушается** | Проверить конфиг dnsmasq: `cat /opt/etc/dnsmasq.conf` |
| **Веб-интерфейс недоступен** | Перезапустить: `/opt/etc/init.d/S99web_ui restart` |

---

## 📞 Поддержка

Если все проверки пройдены, но обход не работает:

1. Сохраните вывод диагностики:
   ```bash
   sh /opt/root/check_bypass.sh > /tmp/diag.txt 2>&1
   ```

2. Сохраните логи:
   ```bash
   cp /opt/var/log/web_ui.log /tmp/web_ui.log
   ```

3. Проанализируйте логи на наличие ошибок `ERROR`
