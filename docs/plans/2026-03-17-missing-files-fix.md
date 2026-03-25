# План: Добавление недостающих файлов для script.sh

## Проблема

`script.sh` пытается загрузить файлы с GitHub:
- `100-ipset.sh`
- `100-redirect.sh`
- `100-unblock-vpn.sh` / `100-unblock-vpn-v4.sh`
- `unblock_ipset.sh`
- `unblock_dnsmasq.sh`
- `unblock_update.sh`
- `tor_template.torrc`
- `vless_template.json`
- `trojan_template.json`
- `shadowsocks_template.json`
- `dnsmasq.conf`
- `crontab`
- `S99unblock`
- `S99web_ui`
- `deploy/lists/unblockvless.txt`
- `deploy/lists/unblocktor.txt`
- `deploy/backup/keensnap/keensnap.sh`

Эти файлы отсутствуют в репозитории `bypass_keenetic`.

## Решение

### Вариант A: Локальные файлы (рекомендуется)

Создать директорию `resources/` в проекте web_ui со всеми необходимыми файлами.

**Структура:**
```
src/web_ui/resources/
├── scripts/
│   ├── 100-ipset.sh
│   ├── 100-redirect.sh
│   ├── 100-unblock-vpn.sh
│   ├── 100-unblock-vpn-v4.sh
│   ├── unblock_ipset.sh
│   ├── unblock_dnsmasq.sh
│   ├── unblock_update.sh
│   ├── S99unblock
│   └── S99web_ui
├── templates/
│   ├── tor_template.torrc
│   ├── vless_template.json
│   ├── trojan_template.json
│   └── shadowsocks_template.json
├── config/
│   ├── dnsmasq.conf
│   └── crontab
└── lists/
    ├── unblockvless.txt
    └── unblocktor.txt
```

**Изменения в script.sh:**
- Заменить `$BASE_URL/...` на локальные пути `/opt/etc/web_ui/resources/...`

### Вариант B: Копирование из test/

Скопировать файлы из проекта-донора `test/`:

```bash
# Найти файлы в test/
test/deploy/scripts/
test/deploy/templates/
test/deploy/config/
test/deploy/lists/
```

### Вариант C: Загрузка с альтернативного URL

Если файлы существуют в другом репозитории, обновить `base_url`.

## Задачи

### Task 1: Найти файлы в test/

**Files:**
- Search: `H:\disk_e\dell\bypass_keenetic-web\test\deploy`

### Task 2: Создать директорию resources/

**Files:**
- Create: `src/web_ui/resources/`

### Task 3: Скопировать файлы

**Files:**
- Copy from `test/deploy/` to `src/web_ui/resources/`

### Task 4: Обновить script.sh

**Files:**
- Modify: `src/web_ui/scripts/script.sh`
- Заменить URL на локальные пути

### Task 5: Обновить web_config.py

**Files:**
- Modify: `src/web_ui/core/web_config.py`
- Добавить пути к resources

### Task 6: Обновить routes.py

**Files:**
- Modify: `src/web_ui/routes.py`
- Копировать resources при установке

## Verification

- [ ] Все файлы скопированы
- [ ] script.sh использует локальные пути
- [ ] Установка работает без ошибок curl
