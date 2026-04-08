# Инструкция по восстановлению после обновления 2.3.0
# Если после обновления сломался интернет и веб-интерфейс

## Шаг 1: Подключиться к роутеру по SSH
ssh root@192.168.1.1 -p 222

## Шаг 2: Проверить состояние веб-интерфейса
ps | grep web_ui | grep -v grep
ls -la /opt/etc/web_ui/core/

## Шаг 3: Найти бэкап
ls -lt /opt/root/backup/backup_*.tar.gz | head -5

## Шаг 4: Распаковать бэкап
# ВАЖНО: Бэкап хранит пути без префикса /opt/
# Например: etc/web_ui/core/decorators.py вместо opt/etc/web_ui/core/decorators.py

cd /
tar xzf /opt/root/backup/backup_YYYYMMDD_HHMMSS.tar.gz

# Или если используете tarfile через Python (альтернатива):
python3 -c "
import tarfile, os
with tarfile.open('/opt/root/backup/backup_YYYYMMDD_HHMMSS.tar.gz', 'r:gz') as tar:
    for member in tar.getmembers():
        safe_name = member.name.lstrip('/')
        if safe_name:
            member.name = 'opt/' + safe_name
    tar.extractall('/')
"

## Шаг 5: Перезапустить сервисы
/opt/etc/init.d/S99web_ui restart
/opt/etc/init.d/S56dnsmasq restart

## Шаг 6: Проверить работу
ps | grep web_ui | grep -v grep
netstat -lnp | grep 8080

# Если веб-интерфейс запустился, проверьте интернет
nslookup google.com 192.168.1.1 5353

## Экстренное восстановление (если бэкапа нет)
# Переустановка с нуля:
cd /opt/etc/web_ui && git fetch origin && git reset --hard origin/master
pip3 install -r /opt/etc/web_ui/requirements.txt
/opt/etc/init.d/S99web_ui restart

## Если сломан dnsmasq (нет DNS)
# Временное решение — прямой DNS:
kill $(pgrep dnsmasq)
dnsmasq --no-daemon --port=53 --server=8.8.8.8 --server=1.1.1.1 &
