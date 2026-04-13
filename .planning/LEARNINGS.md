# FlyMyByte Learnings

## ipset bypass troubleshooting

При диагностике проблемы с пустым ipset на роутере (ipset -L unblockvless показывает 0 записей):

**Архитектура bypass системы:**
- Домены из bypass файлов (/opt/etc/unblock/vless.txt и др.) не добавляются в ipset напрямую
- Они обрабатываются dnsmasq через директивы ipset=/domain/ipset_name в /opt/etc/unblock.dnsmasq
- При DNS запросе клиента dnsmasq автоматически резолвит домен и добавляет IP в ipset
- CIDR и статические IP добавляются напрямую через resolve_domains_for_ipset()

**Ключевые файлы:**
- /opt/etc/unblock/vless.txt — пользовательские домены через web UI
- /opt/etc/unblock.dnsmasq — генерируется DnsmasqManager, содержит ipset=/domain/ipset_name
- src/web_ui/core/dnsmasq_manager.py — генерация конфига
- src/web_ui/core/dns_ops.py:resolve_domains_for_ipset() — добавление CIDR/IP в ipset
- src/web_ui/core/services.py:refresh_ipset_from_file() — основная функция refresh

**Команды для диагностики на роутере:**
- ipset -L unblockvless | grep -c '^[0-9]' — посчитать записи
- cat /opt/etc/unblock/vless.txt — посмотреть домены
- head -30 /opt/etc/unblock.dnsmasq — проверить директивы
- pgrep dnsmasq — проверить работает ли dnsmasq

**Известное поведение:**
- После restart web_ui ipset может быть пустым — это нормально, заполнится при первых DNS запросах
- Домены не резолвятся сразу (чтобы избежать bloat от CDN round-robin)
- IPset создаётся с timeout=300 (5 минут) для авто-очистки устаревших IP

## web_ui architecture

**Структура:**
- src/web_ui/core/ — основные модули (services.py, dns_ops.py, ipset_ops.py, dnsmasq_manager.py)
- src/web_ui/routes_*.py — endpoints
- src/web_ui/templates/ — HTML шаблоны

**Репозиторий:**
- Проектные файлы в src/web_ui/resources/lists/ — информационные шаблоны
- Реальные данные пользователей — /opt/etc/unblock/*.txt на роутере
- Web UI заполняет файлы через routes_bypass.py

## SSH подключение к роутеру

- IP: 192.168.1.1
- Порт: 222
- Пользователь: root

**Команда:** ssh root@192.168.1.1 -p 222