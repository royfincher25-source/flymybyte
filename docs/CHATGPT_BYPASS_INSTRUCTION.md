# Инструкция: Решение проблемы с блокировкой ChatGPT по региону

## Проблема
ChatGPT (chatgpt.com) показывает сообщение о региональной блокировке, даже когда IP определяется как VPS.

## Причины
OpenAI использует несколько методов определения геолокации:
1. **IP-адрес** — проверяется по GeoIP базам
2. **DNS-утечка** — если DNS-запросы идут через провайдера, виден реальный регион
3. **IPv6-утечка** — если IPv6 включён, запрос может идти напрямую
4. **CDN-домены** — контент загружается через CDN, который может не попадать в bypass
5. **Cookies/Session** — сохранённые данные сессии с реальным IP

---

## Шаг 1: Обновить список доменов

Скопируйте обновлённый файл `unblockvless.txt` на роутер:

```bash
# Через SCP
scp -P 222 unblockvless.txt root@192.168.1.1:/opt/etc/unblock/vless.txt

# Или через SSH
ssh root@192.168.1.1 -p 222
cd /opt/etc/unblock
curl -sL -o vless.txt https://raw.githubusercontent.com/royfincher25-source/flymybyte/master/src/web_ui/resources/lists/unblockvless.txt
```

**Новые домены добавлены:**
- `chatgpt.com`, `www.chatgpt.com`
- `chat.openai.com`, `ios.chat.openai.com`
- `api.openai.com`, `platform.openai.com`
- `oaiusercontent.com`, `files.oaiusercontent.com`, `web.oaiusercontent.com`
- `auth.openai.com`, `sso.openai.com`
- `openaiapi.azureedge.net` (Azure CDN)
- `cdn.openai.com`

---

## Шаг 2: Применить изменения на роутере

```bash
ssh root@192.168.1.1 -p 222

# 1. Проверить DNS-разрешение
nslookup chatgpt.com 8.8.8.8
nslookup chat.openai.com 8.8.8.8

# 2. Обновить ipset из нового файла
/opt/bin/unblock_ipset.sh

# 3. Обновить dnsmasq конфиг
/opt/etc/web_ui/resources/scripts/unblock_dnsmasq.sh

# 4. Перезапустить dnsmasq
/opt/etc/init.d/S56dnsmasq restart

# 5. Проверить ipset
ipset list unblockvless | grep -i "openai\|chatgpt"

# 6. Проверить dnsmasq правила
grep "openai\|chatgpt" /opt/etc/unblock.dnsmasq
```

---

## Шаг 3: Проверить утечку DNS

### На роутере:
```bash
# Проверить что dnsmasq слушает порт 5353
netstat -lnp | grep 5353

# Проверить что VPN DNS (stubby) слушает порт 40500
netstat -lnp | grep 40500

# Проверить разрешение через локальный DNS
nslookup chatgpt.com 127.0.0.1 5353

# Проверить какой IP виден через VPN DNS
nslookup myip.opendns.com 8.8.8.8
```

### На клиенте (браузер):
1. Откройте https://dnsleaktest.com
2. Нажмите "Standard test"
3. Проверите что DNS-серверы принадлежат VPN провайдеру, **НЕ** вашему провайдеру

---

## Шаг 4: Проверить IPv6

### На роутере:
```bash
# Проверить включён ли IPv6
ip -6 addr show

# Если IPv6 включён и есть глобальные адреса — ОТКЛЮЧИТЬ
# В веб-интерфейсе Keenetic: Сетевые правила → IPv6 → Отключить

# Или через CLI:
no ipv6 enable
```

### На клиенте:
1. Откройте https://test-ipv6.com
2. Если IPv6 подключён — **отключите его в настройках сетевого адаптера**
3. IPv6 часто обходит VPN-туннель

---

## Шаг 5: Очистить кэш браузера

1. Откройте **инкогнито-окно** (Ctrl+Shift+N)
2. Перейдите на https://chatgpt.com
3. Если работает — проблема в cookies/session

**Очистка:**
- Chrome: `chrome://settings/clearBrowserData` →Cookies и другие данные сайта
- Или используйте режим инкогнито для теста

---

## Шаг 6: Проверить WebRTC утечку

### В браузере:
1. Установите расширение **WebRTC Leak Prevent**
   - Chrome: https://chrome.google.com/webstore/detail/webrtc-leak-prevent/eiabkoithjmldppldnfammhmdkhdapih
   - Firefox: https://addons.mozilla.org/en-US/firefox/addon/webrtc-leak-prevent/
2. Или отключите WebRTC вручную:
   - Chrome: `chrome://flags/#enable-webrtc-hide-local-ips-with-mdns` → Enabled
   - Firefox: `about:config` → `media.peerconnection.enabled` → false

### Проверка:
1. Откройте https://browserleaks.com/webrtc
2. Должен показываться **только IP VPN**, не ваш реальный IP

---

## Шаг 7: Диагностика (если всё ещё не работает)

### Запустить скрипт диагностики:
```bash
ssh root@192.168.1.1 -p 222
sh /opt/etc/web_ui/scripts/diagnose_chatgpt.sh
```

### Или вручную:
```bash
# 1. Проверить xray процесс
ps | grep xray

# 2. Проверить iptables правила
iptables -t nat -L PREROUTING -n -v | grep unblockvless

# 3. Проверить трафик на порт 443
tcpdump -i any port 443 -n 2>&1 | head -20

# 4. Проверить логи dnsmasq
tail -50 /opt/var/log/unblock_dnsmasq.log | grep -i "error\|fail"

# 5. Проверить логи ipset
tail -50 /opt/var/log/unblock_ipset.log | grep -i "error\|fail"
```

---

## Шаг 8: Перезапуск всех сервисов

```bash
# Полный перезапуск
/opt/etc/init.d/S99unblock restart
/opt/etc/init.d/S56dnsmasq restart
/opt/etc/init.d/S99web_ui restart

# Подождать 10 секунд
sleep 10

# Проверить
ps | grep -E "xray|dnsmasq"
ipset list unblockvless | wc -l
```

---

## Быстрая проверка (чеклист)

- [ ] Файл `vless.txt` содержит домены ChatGPT/OpenAI
- [ ] `ipset unblockvless` содержит IP-адреса этих доменов
- [ ] `/opt/etc/unblock.dnsmasq` содержит правила для OpenAI
- [ ] `dnsmasq` запущен и слушает порт 5353
- [ ] VPN (xray) запущен и слушает порт 40500
- [ ] DNS-запросы идут через VPN (проверено на dnsleaktest.com)
- [ ] IPv6 **отключён** на клиенте
- [ ] WebRTC **не утекает** (проверено на browserleaks.com)
- [ ] Браузер очищен от cookies или используется инкогнито

---

## Если всё ещё не работает

1. **Попробуйте другой VPN сервер** — возможно IP VPS уже в чёрном списке OpenAI
2. **Проверьте VPS локацию** — сервер должен быть в поддерживаемой стране (США, ЕС)
3. **Попробуйте другой протокол** — Hysteria 2 или Shadowsocks вместо VLESS
4. **Проверьте время на роутере** — рассинхрон может ломать TLS:
   ```bash
   date
   # Должно совпадать с реальным временем ±1 минута
   ```

---

## Поддержка

Если проблема сохраняется, запустите диагностику и отправьте вывод:
```bash
ssh root@192.168.1.1 -p 222 'sh /opt/etc/web_ui/scripts/diagnose_chatgpt.sh > /tmp/diag.log 2>&1'
# Скопируйте файл diag.log и приложите к обращению
```
