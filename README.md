# FlyMyByte

Веб-интерфейс для управления обходом блокировок на роутерах Keenetic.

## Возможности

- 🔑 **VPN-ключи** — настройка VLESS, Hysteria 2, Shadowsocks, Trojan, Tor
- 📑 **Списки обхода** — управление доменами для обхода блокировок (ipset + dnsmasq)
- 🌐 **DNS-обход AI** — обход региональных блокировок Google AI Studio, Gemini, Colab
- 📊 **Статистика** — статусы сервисов, списки, DNS-состояние
- ⚙️ **Сервис** — перезапуск, бэкап, DNS Override, обновление
- 📲 **Установка** — установка и удаление flymybyte в один клик

## Быстрая установка

```bash
curl -sL https://raw.githubusercontent.com/royfincher25-source/flymybyte/master/src/web_ui/scripts/install_web.sh | sh
```

Затем откройте http://192.168.1.1:8080 и нажмите **Установить**.

## Автоматический мониторинг

После установки автоматически запускаются два watchdog-сервиса:

- **dnsmasq_watchdog** — мониторит dnsmasq:5353, удаляет DNAT при падении
- **vpn_watchdog** — мониторит VLESS/Shadowsocks/Trojan, перезапускает при падении

Логи: `/opt/var/log/dnsmasq_watchdog.log`, `/opt/var/log/vpn_watchdog.log`

## Требования

- Python 3.8+
- Flask 3.0.0, waitress 2.1.2
- Entware на роутере

## Потребление ресурсов

| Ресурс | Значение |
|--------|----------|
| **Память** | ~15MB |
| **Диск** | ~7MB |
| **Порт** | 8080 |

## Конфигурация

Файл `.env` в `/opt/etc/web_ui/`:

```bash
WEB_HOST=0.0.0.0
WEB_PORT=8080
WEB_PASSWORD=changeme
UNBLOCK_DIR=/opt/etc/unblock/
```

## Архитектура

```
src/web_ui/
├── app.py                      # Flask приложение (factory)
│
├── routes_core.py              # Главная, авторизация
├── routes_system.py            # Сервисное меню, статистика, логи
├── routes_vpn.py               # Управление VPN-ключами
├── routes_bypass.py            # Списки обхода, DNS-обход AI
├── routes_updates.py           # Обновления, установка
│
├── core/
│   ├── __init__.py             # Экспорты модулей
│   ├── services.py             # VPN-парсеры, ipset, DNS-обход, каталог списков
│   ├── dns_ops.py              # DNS мониторинг, управление dnsmasq
│   ├── dnsmasq_manager.py     # Управление dnsmasq конфигурацией
│   ├── ipset_ops.py            # Операции с ipset (create, flush, add)
│   ├── iptables_manager.py     # Управление iptables правилами
│   ├── vpn_manager.py          # Управление VPN процессами
│   ├── unblock_manager.py      # Управление bypass списками
│   ├── service_ops.py          # Операции с сервисами (restart, status)
│   ├── service_locator.py      # DI контейнер для сервисов
│   ├── key_manager.py          # Управление ключами активации
│   ├── parsers.py              # Парсеры VPN ключей
│   ├── backup_manager.py       # Резервное копирование
│   ├── decorators.py           # Decorators (auth, csrf)
│   ├── exceptions.py           # Кастомные исключения
│   ├── handlers.py             # Обработчики ошибок
│   ├── utils.py                # Утилиты, кэш, логирование
│   ├── constants.py            # Константы и пути
│   ├── app_config.py           # WebConfig
│   └── update_progress.py      # Прогресс обновлений
│
├── templates/                  # HTML шаблоны
│   ├── base.html
│   ├── index.html
│   ├── keys.html, bypass.html, install.html, stats.html
│   ├── service.html, updates.html, dns_spoofing.html
│   └── ...
│
├── static/
│   ├── style.css
│   └── fonts/flymybyte-icons.*
│
└── scripts/
    └── install_web.sh
```

## Безопасность

⚠️ Измените пароль по умолчанию в `.env`:

```bash
WEB_PASSWORD=your_secure_password_here
```

## Документация

- [Установка на роутер](docs/INSTALL-manual.md)
- [Оптимизация ipset bypass](docs/IPSET-BYPASS-OPTIMIZATION.md)
- [План рефакторинга](docs/plans/2026-04-10-refactoring-plan.md)

## Поддержка

https://github.com/royfincher25-source/flymybyte
