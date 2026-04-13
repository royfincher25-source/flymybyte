# FlyMyByte Learnings

## Вариант A: Оптимизация bypass (active)

**Изменения в ветке feature/bypass-optimization-a:**

1. **DnsmasqManager** — убраны ipset= директивы (теперь только комментарии)
2. **dns_ops.resolve_domains_for_ipset()** — добавлен proactive DNS resolve доменов:
   - MAX_IPS_PER_DOMAIN=10 (защита от CDN bloat)
   - DNS_TIMEOUT=3 сек
   - Теперь домены резолвятся сразу при refresh, а не при DNS запросе клиента

**Проверено на роутере (2026-04-13):**
- ✅ DNS resolve работает — домены добавляются в ipset
- ✅ Bypass работает — трафик перенаправляется на VPN прокси
- ✅ iptables правила работают корректно

**Важно:** Исправлен подсчёт записей в ipset (grep -E "timeout" вместо "^[0-9]")

## ipset bypass troubleshooting

При диагностике проблемы с пустым ipset на роутере (ipset -L unblockvless показывает 0 записей):

**Архитектура bypass системы:**
- Домены из bypass файлов (/opt/etc/unblock/vless.txt и др.) резолвятся через DNS resolve
- CIDR и статические IP добавляются напрямую через resolve_domains_for_ipset()
- Защита от bloat: MAX_IPS_PER_DOMAIN=10, timeout=300 сек

**Ключевые файлы:**
- /opt/etc/unblock/vless.txt — пользовательские домены через web UI
- src/web_ui/core/dns_ops.py:resolve_domains_for_ipset() — добавление IP в ipset
- src/web_ui/core/ipset_ops.py:bulk_add_to_ipset() — bulk операции
- src/web_ui/core/services.py:refresh_ipset_from_file() — основная функция refresh

**Команды для диагностики на роутере:**
- ipset -L unblockvless | tail -n +7 | grep -c "timeout" — правильный подсчёт записей
- cat /opt/etc/unblock/vless.txt — посмотреть домены
- pgrep dnsmasq — проверить работает ли dnsmasq

## SSH подключение к роутеру

- IP: 192.168.1.1
- Порт: 222
- Пользователь: root

**Команда:** ssh root@192.168.1.1 -p 222