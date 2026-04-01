# Resources Directory

Эта директория содержит все необходимые файлы для установки flymybyte через script.sh.

## Структура

```
resources/
├── scripts/          # Скрипты для роутера
│   ├── 100-ipset.sh
│   ├── 100-redirect.sh
│   ├── 100-unblock-vpn.sh
│   ├── 100-unblock-vpn-v4.sh
│   ├── unblock_ipset.sh
│   ├── unblock_dnsmasq.sh
│   ├── unblock_update.sh
│   ├── S99unblock
│   ├── S99web_ui
│   └── keensnap.sh
├── templates/        # Шаблоны конфигураций VPN
│   ├── tor_template.torrc
│   ├── vless_template.json
│   ├── trojan_template.json
│   └── shadowsocks_template.json
├── config/           # Конфигурационные файлы
│   ├── dnsmasq.conf
│   └── crontab
└── lists/            # Списки обхода
    ├── unblockvless.txt
    └── unblocktor.txt
```

## Назначение файлов

### Scripts

| Файл | Описание |
|------|----------|
| `100-ipset.sh` | Скрипт для создания ipset множеств |
| `100-redirect.sh` | Скрипт перенаправления трафика |
| `100-unblock-vpn.sh` | Проверка VPN для KeenOS 3 |
| `100-unblock-vpn-v4.sh` | Проверка VPN для KeenOS 4 |
| `unblock_ipset.sh` | Заполнение ipset IP-адресами |
| `unblock_dnsmasq.sh` | Генерация конфига dnsmasq |
| `unblock_update.sh` | Обновление системы после изменений |
| `S99unblock` | Автозапуск unblock при загрузке |
| `S99web_ui` | Автозапуск веб-интерфейса |
| `keensnap.sh` | Скрипт создания бэкапов |

### Templates

| Файл | Описание |
|------|----------|
| `tor_template.torrc` | Шаблон конфигурации Tor |
| `vless_template.json` | Шаблон конфигурации VLESS |
| `trojan_template.json` | Шаблон конфигурации Trojan |
| `shadowsocks_template.json` | Шаблон конфигурации Shadowsocks |

### Config

| Файл | Описание |
|------|----------|
| `dnsmasq.conf` | Дополнительная конфигурация dnsmasq |
| `crontab` | Задачи cron для периодического обновления |

### Lists

| Файл | Описание |
|------|----------|
| `unblockvless.txt` | Списки доменов для VLESS |
| `unblocktor.txt` | Списки доменов для Tor |

## Использование

### При установке через script.sh

Файлы автоматически копируются из `resources/` в соответствующие директории на роутере:

```bash
/opt/root/script.sh -install
```

**Куда копируются:**

| Исходный файл | Назначение |
|---------------|------------|
| `resources/scripts/*.sh` | `/opt/bin/`, `/opt/etc/ndm/` |
| `resources/templates/*` | `/opt/etc/bot/templates/` |
| `resources/config/*` | `/opt/etc/` |
| `resources/lists/*.txt` | `/opt/etc/unblock/` |
| `resources/scripts/S99*` | `/opt/etc/init.d/` |

### Обновление ресурсов

Для обновления ресурсов:

1. Отредактировать файлы в `resources/`
2. Закоммитить изменения
3. При следующей установке новые файлы будут скопированы на роутер

## Источник файлов

Файлы скопированы из проекта-донора `test/deploy/`:

```
test/deploy/router/     → resources/scripts/*.sh
test/deploy/config/     → resources/config/, resources/templates/
test/deploy/lists/      → resources/lists/
test/deploy/backup/     → resources/scripts/keensnap.sh
```

S99 скрипты созданы вручную для веб-интерфейса.

## Проверка целостности

Перед использованием проверьте наличие всех файлов:

```bash
# Проверка структуры
dir /s /b resources\

# Проверка размеров файлов
dir resources\scripts
dir resources\config
dir resources\templates
dir resources\lists
```

## Добавление новых файлов

Для добавления нового файла:

1. Создать файл в соответствующей поддиректории
2. Обновить `script.sh` для копирования нового файла
3. Закоммитить изменения

Пример добавления нового скрипта:

```bash
# Создать файл
copy test/deploy/router/new_script.sh resources/scripts/

# Обновить script.sh
# Добавить копирование в соответствующей секции

# Закоммитить
git add resources/scripts/new_script.sh
git commit -m "feat: добавить new_script.sh"
```
