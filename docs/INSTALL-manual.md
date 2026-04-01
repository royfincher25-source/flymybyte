# Установка flymybyte вручную на роутер Keenetic KN-1212

## Требования

- Роутер Keenetic KN-1212 (или аналогичный с Entware)
- SSH доступ к роутеру (порт 22)
- Установленный и настроенный Entware

---

## Шаг 1: Подготовка

Подключитесь к роутеру по SSH:

```bash
ssh root@192.168.1.1
```

---

## Шаг 2: Создание директорий

```bash
mkdir -p /opt/bin
mkdir -p /opt/etc/unblock
mkdir -p /opt/etc/init.d
mkdir -p /opt/var/log
mkdir -p /opt/etc/web_ui/core
mkdir -p /opt/etc/web_ui/resources
```

---

## Шаг 3: Установка необходимых пакетов

```bash
opkg update
opkg install curl ipset iptables dnsmasq-full
/opt/etc/init.d/S56dnsmasq enable
/opt/etc/init.d/S56dnsmasq start
```

---

## Шаг 4: Создание ipset

```bash
ipset create unblocksh hash:net
ipset create unblocktor hash:net
ipset create unblockvless hash:net
ipset create unblocktroj hash:net
```

---

## Шаг 5: Скачивание скриптов

### Основные скрипты (скачать с GitHub):

```bash
# Скачиваем скрипты
curl -sL -o /opt/bin/unblock_ipset.sh "https://raw.githubusercontent.com/ВАШ_РЕПО/src/web_ui/resources/scripts/unblock_ipset.sh"
curl -sL -o /opt/bin/unblock_dnsmasq.sh "https://raw.githubusercontent.com/ВАШ_РЕПО/src/web_ui/resources/scripts/unblock_dnsmasq.sh"
curl -sL -o /opt/bin/unblock_update.sh "https://raw.githubusercontent.com/ВАШ_РЕПО/src/web_ui/resources/scripts/unblock_update.sh"
curl -sL -o /opt/etc/ndm/netfilter.d/100-redirect.sh "https://raw.githubusercontent.com/ВАШ_РЕПО/src/web_ui/resources/scripts/100-redirect.sh"

# Делаем исполняемыми
chmod +x /opt/bin/unblock_*.sh
chmod +x /opt/etc/ndm/netfilter.d/100-redirect.sh
```

### Или создаём вручную:

**unblock_ipset.sh:**
```bash
#!/bin/sh
cut_local() {
    grep -vE 'localhost|^0\.|^127\.|^10\.|^172\.16\.|^192\.168\.|^::|^fc..:|^fd..:|^fe..:'
}

until nslookup google.com 8.8.8.8 >/dev/null 2>&1; do sleep 5; done

for file in /opt/etc/unblock/*.txt; do
    [ -f "$file" ] || continue
    ipset_name=$(basename "$file" .txt | sed 's/^unblock//')
    [ -z "$ipset_name" ] && ipset_name="sh"
    
    while read -r line || [ -n "$line" ]; do
        [ -z "$line" ] && continue
        [ "${line#?}" = "#" ] && continue
        
        addr=$(echo "$line" | grep -Eo '[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}' | cut_local)
        [ -n "$addr" ] && ipset -exist add "unblock$ipset_name" "$addr" && continue
        
        nslookup "$line" 8.8.8.8 2>/dev/null | grep -oE '[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}' | while read -r ip; do
            ipset -exist add "unblock$ipset_name" "$ip"
        done
    done < "$file"
done

echo "✅ IPSET заполнен"
```

**unblock_dnsmasq.sh:**
```bash
#!/bin/sh
cat /dev/null > /opt/etc/unblock.dnsmasq

for file in /opt/etc/unblock/*.txt; do
    [ -f "$file" ] || continue
    ipset_name=$(basename "$file" .txt)
    
    while read -r line || [ -n "$line" ]; do
        [ -z "$line" ] && continue
        [ "${line#?}" = "#" ] && continue
        echo "$line" | grep -Eq '[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}' && continue
        
        echo "ipset=/$line/$ipset_name" >> /opt/etc/unblock.dnsmasq
        echo "server=/$line/8.8.8.8" >> /opt/etc/unblock.dnsmasq
    done < "$file"
done

/opt/etc/init.d/S56dnsmasq restart
```

**unblock_update.sh:**
```bash
#!/bin/sh
ipset flush unblocksh
ipset flush unblocktor
ipset flush unblockvless
ipset flush unblocktroj

/opt/bin/unblock_dnsmasq.sh
/opt/etc/init.d/S56dnsmasq restart
/opt/bin/unblock_ipset.sh
```

---

## Шаг 6: Настройка dnsmasq

```bash
curl -sL -o /opt/etc/dnsmasq.conf "https://raw.githubusercontent.com/ВАШ_РЕПО/src/web_ui/resources/config/dnsmasq.conf"
# Или создайте вручную (см. ниже)
```

**Минимальный dnsmasq.conf:**
```
user=nobody
interface=br0
listen-address=127.0.0.1
listen-address=192.168.1.1

bogus-priv
no-negcache
no-resolv
no-poll
clear-on-reload
domain-needed
log-async
stop-dns-rebind
rebind-localhost-ok
rebind-domain-ok=/lan/local/onion/

# DNS серверы (прямые, без DoT/DoH)
server=8.8.8.8
server=1.1.1.1

conf-file=/opt/etc/unblock.dnsmasq

domain=local,192.168.1.0/24
```

---

## Шаг 7: Создание списков доменов

```bash
# VLESS список
cat > /opt/etc/unblock/vless.txt << 'EOF'
telegram.org
t.me
web.telegram.org
wa.me
whatsapp.com
facebook.com
instagram.com
youtube.com
EOF

# Tor список
cat > /opt/etc/unblock/tor.txt << 'EOF'
facebook.com
instagram.com
twitter.com
telegram.org
EOF

# Shadowsocks (пустой или свои домены)
touch /opt/etc/unblock/shadowsocks.txt

# Trojan (пустой или свои домены)
touch /opt/etc/unblock/trojan.txt
```

---

## Шаг 8: Настройка iptables правил

```bash
# Применяем правила перенаправления
/opt/etc/ndm/netfilter.d/100-redirect.sh
```

Проверяем:

```bash
iptables -t nat -L PREROUTING -v -n | head -15
```

---

## Шаг 9: Настройка cron (автообновление)

```bash
echo "0 */6 * * * /opt/bin/unblock_update.sh" >> /opt/etc/crontab
```

---

## Шаг 10: Перезапуск служб

```bash
/opt/etc/init.d/S56dnsmasq restart
/opt/bin/unblock_update.sh
```

---

## Проверка работоспособности

```bash
# Проверка ipset
ipset -L unblocksh | head -20
ipset -L unblockvless | head -20

# Проверка iptables
iptables -t nat -L PREROUTING -v -n | grep REDIRECT

# Проверка dnsmasq
cat /opt/etc/unblock.dnsmasq | head -20

# Тест DNS
nslookup youtube.com
```

---

## Возможные проблемы

### 1. ipset пустой
```bash
# Запустите вручную
/opt/bin/unblock_ipset.sh
```

### 2. iptables правила не работают
```bash
# Проверьте наличие ipset
ipset -L -n

# Пересоздайте правила
ipset flush
/opt/bin/unblock_ipset.sh
/opt/etc/ndm/netfilter.d/100-redirect.sh
```

### 3. DNS не резолвит
```bash
# Проверьте dnsmasq
/opt/etc/init.d/S56dnsmasq restart
logread | grep dnsmasq
```

---

## Автозапуск при загрузке

Создайте init скрипт `/opt/etc/init.d/S99unblock`:

```bash
#!/bin/sh
case "$1" in
    start)
        /opt/bin/unblock_update.sh
        /opt/etc/ndm/netfilter.d/100-redirect.sh
        ;;
    stop)
        ;;
    *)
        echo "Usage: $0 {start|stop}"
        ;;
esac
```

```bash
chmod +x /opt/etc/init.d/S99unblock
```

---

## Готово!

- Откройте веб-интерфейс: http://192.168.1.1:8080
- Перейдите в раздел "Ключи" для добавления VPN ключей
- Добавьте домены в списки обхода
- Включите "DNS Override" в настройках Keenetic
- **Настройте DNS-обход AI-доменов** (Сервис → DNS-обход AI → Применить)

---

## DNS-обход AI-доменов (новое!)

Для обхода региональных блокировок AI-сервисов (Google AI Studio, Gemini, Colab):

```bash
# 1. Скачайте список AI-доменов
curl -sL -o /opt/etc/unblock/ai-domains.txt \
  https://raw.githubusercontent.com/royfincher25-source/flymybyte/master/src/web_ui/resources/lists/unblock-ai-domains.txt

# 2. Примените конфигурацию
sh /opt/etc/web_ui/resources/scripts/unblock_dnsmasq.sh

# 3. Проверьте конфигурацию
cat /opt/etc/unblock-ai.dnsmasq

# Ожидается:
# address=/aistudio.google.com/127.0.0.1#40500
# server=/aistudio.google.com/127.0.0.1#40500
# ...
```

**Или через веб-интерфейс:**
1. Откройте http://192.168.1.1:8080
2. Перейдите в **Сервис** → **DNS-обход AI**
3. Нажмите **Загрузить готовый список**
4. Нажмите **Применить**

**Проверка:**
```bash
# Тест разрешения домена
nslookup aistudio.google.com 192.168.1.1

# Ожидается: IP адрес (не блокируемый)
```
