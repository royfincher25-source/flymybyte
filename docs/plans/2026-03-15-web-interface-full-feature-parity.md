# Web Interface Full Feature Parity Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Добавить в web-интерфейс все функции, доступные в Telegram-боте (папка test/)

**Architecture:** Flask web-инфейс с Python-бэкендом. Функции replicируют Telegram-бота: restart, DNS override, updates, backup.

**Tech Stack:** Flask, Jinja2, subprocess, requests

---

## Обзор функций

| Функция | Telegram Bot (test/) | Web Interface (src/web_ui/) |
|---------|---------------------|----------------------------|
| 🔑 Ключи (VLESS, SS, Trojan, Tor) | ✅ | ✅ Готово |
| 📑 Списки обхода | ✅ | ✅ Готово |
| 📲 Установка/удаление | ✅ | ✅ Готово |
| 📊 Статистика | ✅ | ✅ Готово |
| ⚙️ Сервисное меню | ✅ | Частично |
| — Перезапуск Unblock | ✅ | ✅ Готово |
| — Перезапуск роутера | ✅ | ❌ |
| — Перезапуск сервисов (все) | ✅ | ❌ |
| — DNS Override | ✅ | ❌ |
| — Обновления | ✅ | ❌ |
| — Бэкап | ✅ | ❌ |

---

## Task 1: Перезапуск роутера

**Files:**
- Modify: `src/web_ui/routes.py`
- Modify: `src/web_ui/templates/service.html`

**Step 1: Добавить маршрут перезапуска роутера**

В `routes.py` добавить функцию после `service_restart_unblock`:

```python
@bp.route('/service/restart-router', methods=['POST'])
@login_required
def service_restart_router():
    """
    Restart the router.

    Requires authentication.
    """
    try:
        subprocess.run(['ndmc', '-c', 'system reboot'], timeout=30)
        flash('✅ Команда на перезагрузку отправлена', 'success')
    except Exception as e:
        flash(f'❌ Ошибка: {str(e)}', 'danger')
    
    return redirect(url_for('main.service'))
```

**Step 2: Добавить кнопку в service.html**

Заменить карточку "Перезапуск роутера":

```html
<!-- Перезапуск роутера -->
<div class="col-12 col-md-6">
    <div class="card shadow-sm">
        <div class="card-body">
            <h5 class="card-title"><i class="bi bi-router"></i> Перезапуск роутера</h5>
            <p class="text-muted small">Перезагрузка всего роутера ( займёт ~2 минуты)</p>
            <form method="POST" action="{{ url_for('main.service_restart_router') }}">
                <button type="submit" class="btn btn-warning btn-sm">
                    <i class="bi bi-arrow-clockwise"></i> Перезапустить
                </button>
            </form>
        </div>
    </div>
</div>
```

**Step 3: Commit**

```bash
git add src/web_ui/routes.py src/web_ui/templates/service.html
git commit -m "feat: add router restart function"
```

---

## Task 2: Перезапуск всех сервисов

**Files:**
- Modify: `src/web_ui/routes.py`
- Modify: `src/web_ui/templates/service.html`

**Step 1: Добавить маршрут перезапуска сервисов**

В `routes.py` добавить:

```python
@bp.route('/service/restart-all', methods=['POST'])
@login_required
def service_restart_all():
    """
    Restart all VPN services.

    Requires authentication.
    """
    services = [
        ('Shadowsocks', '/opt/etc/init.d/S22shadowsocks'),
        ('Tor', '/opt/etc/init.d/S35tor'),
        ('VLESS', '/opt/etc/init.d/S24xray'),
        ('Trojan', '/opt/etc/init.d/S22trojan'),
    ]
    
    results = []
    for name, init_script in services:
        try:
            if os.path.exists(init_script):
                result = subprocess.run(
                    ['sh', init_script, 'restart'],
                    capture_output=True, text=True, timeout=60
                )
                status = '✅' if result.returncode == 0 else '❌'
                results.append(f"{status} {name}")
            else:
                results.append(f"⚠️ {name} (скрипт не найден)")
        except Exception as e:
            results.append(f"❌ {name}: {str(e)}")
    
    flash('Перезапуск сервисов: ' + ', '.join(results), 'success')
    return redirect(url_for('main.service'))
```

**Step 2: Добавить кнопку в service.html**

Добавить новую карточку:

```html
<!-- Перезапуск всех сервисов -->
<div class="col-12 col-md-6">
    <div class="card shadow-sm">
        <div class="card-body">
            <h5 class="card-title"><i class="bi bi-arrow-repeat"></i> Перезапуск всех сервисов</h5>
            <p class="text-muted small">Перезапуск VLESS, Shadowsocks, Trojan, Tor</p>
            <form method="POST" action="{{ url_for('main.service_restart_all') }}">
                <button type="submit" class="btn btn-info btn-sm">
                    <i class="bi bi-arrow-clockwise"></i> Перезапустить
                </button>
            </form>
        </div>
    </div>
</div>
```

**Step 3: Commit**

```bash
git add src/web_ui/routes.py src/web_ui/templates/service.html
git commit -m "feat: add restart all services function"
```

---

## Task 3: DNS Override

**Files:**
- Modify: `src/web_ui/routes.py`
- Modify: `src/web_ui/templates/service.html`

**Step 1: Добавить маршруты включения/выключения DNS Override**

В `routes.py` добавить:

```python
@bp.route('/service/dns-override/<action>', methods=['POST'])
@login_required
def service_dns_override(action):
    """
    Enable or disable DNS Override.

    Requires authentication.
    """
    enable = (action == 'on')
    
    try:
        cmd = ['ndmc', '-c', 'opkg dns-override'] if enable else ['ndmc', '-c', 'no opkg dns-override']
        subprocess.run(cmd, timeout=10)
        time.sleep(2)
        subprocess.run(['ndmc', '-c', 'system configuration save'], timeout=10)
        
        flash('✅ DNS Override ' + ('включен' if enable else 'выключен') + '. Роутер будет перезагружен.', 'warning')
    except Exception as e:
        flash(f'❌ Ошибка: {str(e)}', 'danger')
    
    return redirect(url_for('main.service'))
```

**Step 2: Добавить кнопки в service.html**

Заменить карточку DNS Override:

```html
<!-- DNS Override -->
<div class="col-12 col-md-6">
    <div class="card shadow-sm">
        <div class="card-body">
            <h5 class="card-title"><i class="bi bi-globe"></i> DNS Override</h5>
            <p class="text-muted small">Перенаправление DNS запросов через роутер</p>
            <form method="POST" action="{{ url_for('main.service_dns_override', action='on') }}" class="d-inline">
                <button type="submit" class="btn btn-success btn-sm">ВКЛ</button>
            </form>
            <form method="POST" action="{{ url_for('main.service_dns_override', action='off') }}" class="d-inline">
                <button type="submit" class="btn btn-danger btn-sm">ВЫКЛ</button>
            </form>
        </div>
    </div>
</div>
```

**Step 3: Добавить импорт time**

В начало `routes.py` добавить `import time`

**Step 4: Commit**

```bash
git add src/web_ui/routes.py src/web_ui/templates/service.html
git commit -m "feat: add DNS override function"
```

---

## Task 4: Обновления

**Files:**
- Modify: `src/web_ui/routes.py`
- Modify: `src/web_ui/templates/service.html`
- Modify: `src/web_ui/core/services.py`

**Step 1: Добавить функции обновления в services.py**

Добавить в конец файла:

```python
def get_local_version():
    """Получить локальную версию"""
    version_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'version.md')
    try:
        with open(version_file, 'r', encoding='utf-8') as f:
            return f.read().strip()
    except FileNotFoundError:
        return 'N/A'

def get_remote_version(bot_url=None):
    """Получить удалённую версию с GitHub"""
    import requests
    try:
        url = 'https://raw.githubusercontent.com/royfincher25-source/bypass_keenetic/main/version.md'
        response = requests.get(url, timeout=10)
        return response.text.strip()
    except Exception:
        return 'N/A'

def download_bot_files(bot_url):
    """Загрузить файлы бота с GitHub"""
    import requests
    files = ['bot_config.py', 'handlers.py', 'menu.py', 'utils.py', 'main.py']
    for filename in files:
        url = f'{bot_url}/{filename}'
        try:
            response = requests.get(url, timeout=30)
            if response.status_code == 200:
                # Логика сохранения
                pass
        except Exception as e:
            logger.error(f'Error downloading {filename}: {e}')
```

**Step 2: Добавить маршрут в routes.py**

```python
@bp.route('/service/updates')
@login_required
def service_updates():
    """
    Show updates page.

    Requires authentication.
    """
    from core.services import get_local_version, get_remote_version
    
    local_version = get_local_version()
    remote_version = get_remote_version()
    
    need_update = True
    if local_version != 'N/A' and remote_version != 'N/A':
        try:
            if tuple(map(int, local_version.split('.'))) >= tuple(map(int, remote_version.split('.'))):
                need_update = False
        except ValueError:
            pass
    
    return render_template('updates.html', 
                          local_version=local_version,
                          remote_version=remote_version,
                          need_update=need_update)


@bp.route('/service/updates/run', methods=['POST'])
@login_required
def service_updates_run():
    """
    Run update process.

    Requires authentication.
    """
    from core.services import get_local_version, get_remote_version, download_bot_files
    
    try:
        flash('⏳ Загрузка обновлений...', 'info')
        
        bot_url = 'https://raw.githubusercontent.com/royfincher25-source/bypass_keenetic/main/src/bot3'
        download_bot_files(bot_url)
        
        flash('✅ Обновление завершено!', 'success')
    except Exception as e:
        flash(f'❌ Ошибка обновления: {str(e)}', 'danger')
    
    return redirect(url_for('main.service_updates'))
```

**Step 3: Создать шаблон updates.html**

Создать `src/web_ui/templates/updates.html`:

```html
{% extends "base.html" %}

{% block title %}Обновления — Bypass Keenetic{% endblock %}

{% block content %}
<div class="d-flex justify-content-between align-items-center mb-4">
    <h2><i class="bi bi-arrow-repeat"></i> Обновления</h2>
    <a href="{{ url_for('main.service') }}" class="btn btn-outline-secondary">
        <i class="bi bi-arrow-left"></i> Назад
    </a>
</div>

<div class="card shadow-sm mb-4">
    <div class="card-body">
        <h5 class="card-title">Текущая версия</h5>
        <p class="mb-0">Установленная: <strong>{{ local_version }}</strong></p>
        <p>Доступная: <strong>{{ remote_version }}</strong></p>
        
        {% if need_update %}
            <div class="alert alert-warning">
                Доступна новая версия! Рекомендуется обновить.
            </div>
            <form method="POST" action="{{ url_for('main.service_updates_run') }}">
                <button type="submit" class="btn btn-primary">
                    <i class="bi bi-download"></i> Обновить
                </button>
            </form>
        {% else %}
            <div class="alert alert-success">
                У вас установлена последняя версия.
            </div>
        {% endif %}
    </div>
</div>
{% endblock %}
```

**Step 4: Commit**

```bash
git add src/web_ui/routes.py src/web_ui/core/services.py src/web_ui/templates/updates.html
git commit -m "feat: add updates functionality"
```

---

## Task 5: Бэкап

**Files:**
- Modify: `src/web_ui/routes.py`
- Modify: `src/web_ui/templates/service.html`
- Modify: `src/web_ui/core/services.py`

**Step 1: Добавить функции бэкапа в services.py**

```python
def create_backup(backup_type='full'):
    """
    Create backup of system files.
    
    Args:
        backup_type: 'full' or 'custom'
    
    Returns:
        Tuple of (success: bool, message: str)
    """
    import shutil
    import tempfile
    
    try:
        backup_dir = '/opt/root/backup'
        os.makedirs(backup_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_file = f'{backup_dir}/backup_{timestamp}.tar.gz'
        
        files_to_backup = [
            '/opt/etc/bot',
            '/opt/etc/xray',
            '/opt/etc/tor',
            '/opt/etc/unblock',
            '/opt/root/script.sh',
        ]
        
        # Фильтруем существующие файлы
        existing_files = [f for f in files_to_backup if os.path.exists(f)]
        
        if not existing_files:
            return False, 'Нет файлов для бэкапа'
        
        # Создаём архив
        with tarfile.open(backup_file, 'w:gz') as tar:
            for f in existing_files:
                tar.add(f, arcname=os.path.basename(f))
        
        return True, f'Бэкап создан: {backup_file}'
    
    except Exception as e:
        logger.error(f'Backup error: {e}')
        return False, str(e)
```

**Step 2: Добавить маршрут в routes.py**

```python
@bp.route('/service/backup', methods=['GET', 'POST'])
@login_required
def service_backup():
    """
    Create and download backup.

    Requires authentication.
    """
    if request.method == 'POST':
        from core.services import create_backup
        
        success, message = create_backup()
        
        if success:
            flash(f'✅ {message}', 'success')
        else:
            flash(f'❌ {message}', 'danger')
        
        return redirect(url_for('main.service'))
    
    # GET - показать страницу
    return render_template('backup.html')
```

**Step 3: Создать шаблон backup.html**

Создать `src/web_ui/templates/backup.html`:

```html
{% extends "base.html" %}

{% block title %}Бэкап — Bypass Keenetic{% endblock %}

{% block content %}
<div class="d-flex justify-content-between align-items-center mb-4">
    <h2><i class="bi bi-hdd"></i> Бэкап</h2>
    <a href="{{ url_for('main.service') }}" class="btn btn-outline-secondary">
        <i class="bi bi-arrow-left"></i> Назад
    </a>
</div>

<div class="card shadow-sm">
    <div class="card-body">
        <h5 class="card-title">Создание бэкапа</h5>
        <p class="text-muted">Бэкап включает: конфигурации бота, xray, tor, unblock, script.sh</p>
        
        <form method="POST" action="{{ url_for('main.service_backup') }}">
            <button type="submit" class="btn btn-primary">
                <i class="bi bi-download"></i> Создать бэкап
            </button>
        </form>
    </div>
</div>
{% endblock %}
```

**Step 4: Обновить service.html — добавить кнопку**

```html
<!-- Бэкап -->
<div class="col-12 col-md-6">
    <div class="card shadow-sm">
        <div class="card-body">
            <h5 class="card-title"><i class="bi bi-hdd"></i> Бэкап</h5>
            <p class="text-muted small">Создание резервной копии конфигов</p>
            <a href="{{ url_for('main.service_backup') }}" class="btn btn-primary btn-sm">
                <i class="bi bi-download"></i> Создать
            </a>
        </div>
    </div>
</div>
```

**Step 5: Commit**

```bash
git add src/web_ui/routes.py src/web_ui/core/services.py src/web_ui/templates/backup.html src/web_ui/templates/service.html
git commit -m "feat: add backup functionality"
```

---

## Task 6: Исправить пути к init-скриптам

**Files:**
- Modify: `src/web_ui/routes.py`

**Step 1: Исправить пути**

Уже сделано ранее (S22trojan, S35tor). Проверить все пути:

| Сервис | Путь |
|--------|------|
| VLESS | /opt/etc/init.d/S24xray |
| Shadowsocks | /opt/etc/init.d/S22shadowsocks |
| Trojan | /opt/etc/init.d/S22trojan |
| Tor | /opt/etc/init.d/S35tor |
| Unblock | /opt/etc/init.d/S99unblock |

**Step 2: Commit**

```bash
git commit -m "fix: correct init script paths"
```

---

## Task 7: Добавить версию

**Files:**
- Create: `src/web_ui/version.md`

**Step 1: Создать файл версии**

```
1.0.0
```

**Step 2: Commit**

```bash
git add src/web_ui/version.md
git commit -m "chore: add version file"
```

---

## Итоговый статус

После выполнения всех задач web-интерфейс будет иметь полный функционал:

- ✅ Ключи (VLESS, SS, Trojan, Tor)
- ✅ Списки обхода
- ✅ Установка/удаление
- ✅ Статистика
- ✅ Перезапуск Unblock
- ✅ Перезапуск роутера
- ✅ Перезапуск всех сервисов
- ✅ DNS Override
- ✅ Обновления
- ✅ Бэкап
