"""
Bypass Keenetic Web Interface - Routes

Routes for the web interface with session-based authentication.
"""
from flask import Blueprint, render_template, redirect, url_for, request, session, flash, current_app, jsonify
from functools import wraps
from werkzeug.utils import secure_filename
from markupsafe import escape
from concurrent.futures import ThreadPoolExecutor, TimeoutError
import os
import sys
import stat
import logging
import json
import subprocess
import requests

logger = logging.getLogger(__name__)

# Thread pool for blocking operations (increased to 4 workers for better performance)
executor = ThreadPoolExecutor(max_workers=2)  # Оптимизировано для KN-1212

# Validation constants for embedded devices (128MB RAM)
MAX_ENTRIES_PER_REQUEST = 100  # Максимум записей за один запрос
MAX_ENTRY_LENGTH = 253  # Максимальная длина одной записи (DNS limit)
MAX_TOTAL_INPUT_SIZE = 50 * 1024  # 50KB лимит на общий размер ввода

# Импорты utility-функций
from core.utils import (
    load_bypass_list,
    save_bypass_list,
    validate_bypass_entry,
    run_unblock_update,
    is_ip_address
)
from core.ipset_manager import bulk_add_to_ipset, ensure_ipset_exists, bulk_remove_from_ipset
from core.services import (
    parse_vless_key, vless_config, write_json_config,
    parse_hysteria2_key, hysteria2_config, write_hysteria2_config,
    parse_shadowsocks_key, shadowsocks_config,
    parse_trojan_key, trojan_config,
    parse_tor_bridges, tor_config, write_tor_config,
    restart_service, check_service_status
)
from core.app_config import WebConfig

bp = Blueprint('main', __name__, template_folder='templates', static_folder='static')


# =============================================================================
# DECORATORS
# =============================================================================

def login_required(f):
    """
    Decorator to require authentication for a route.
    
    Redirects to /login if user is not authenticated.
    """
    from functools import wraps
    
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('authenticated'):
            # Check if it's an AJAX request
            is_ajax = (request.headers.get('X-Requested-With') == 'XMLHttpRequest' or
                      'application/json' in request.headers.get('Accept', ''))
            
            if is_ajax or request.is_json:
                return jsonify({'success': False, 'error': 'Authentication required'}), 401
            return redirect(url_for('main.login'))
        return f(*args, **kwargs)
    
    return decorated_function


def get_csrf_token():
    """Generate or get CSRF token for the session."""
    import secrets
    if 'csrf_token' not in session:
        session['csrf_token'] = secrets.token_hex(32)
    return session['csrf_token']


def validate_csrf_token() -> bool:
    """
    Validate CSRF token from session and form.
    
    Returns:
        True if valid, False otherwise
    """
    token = session.get('csrf_token')
    form_token = request.form.get('csrf_token')
    if not token or not form_token or token != form_token:
        logger.warning("CSRF token validation failed")
        return False
    return True


def csrf_required(f):
    """Decorator to require CSRF token on POST requests."""
    from functools import wraps

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if request.method == 'POST':
            if not validate_csrf_token():
                flash('Ошибка безопасности: неверный токен', 'danger')

                # Check if it's an AJAX request (X-Requested-With header or Accept header)
                is_ajax = (request.headers.get('X-Requested-With') == 'XMLHttpRequest' or
                          'application/json' in request.headers.get('Accept', ''))

                if is_ajax or request.is_json:
                    return jsonify({'success': False, 'error': 'CSRF token validation failed'}), 400

                return redirect(url_for('main.index'))
        return f(*args, **kwargs)

    return decorated_function


# =============================================================================
# ROUTES
# =============================================================================

@bp.route('/')
@login_required
def index():
    """
    Render the main dashboard page.

    Requires authentication. Redirects to /login if not authenticated.
    """
    return render_template('index.html')


@bp.route('/login', methods=['GET', 'POST'])
def login():
    """
    Handle user login.

    GET: Display login form.
    POST: Authenticate user with password.

    On success: Set session['authenticated'] = True, redirect to /
    On failure: Display flash message, redirect to /login
    """
    # Если уже авторизован - редирект на главную
    if session.get('authenticated'):
        return redirect(url_for('main.index'))

    if request.method == 'GET':
        get_csrf_token()

    if request.method == 'POST':
        # CSRF check for login
        if not validate_csrf_token():
            flash('Ошибка безопасности: неверный токен', 'danger')
            logger.warning("CSRF token validation failed on login")
            return redirect(url_for('main.login'))
        
        password = request.form.get('password', '')
        web_password = current_app.config.get('WEB_PASSWORD', 'changeme')

        # Безопасное сравнение паролей (защита от timing attacks)
        import secrets
        if password and web_password and secrets.compare_digest(password, web_password):
            # Успешная авторизация
            session.permanent = True
            session['authenticated'] = True
            logger.info("User logged in successfully")
            return redirect(url_for('main.index'))
        else:
            # Неверный пароль
            logger.warning("Failed login attempt")
            flash('Неверный пароль', 'danger')
            return redirect(url_for('main.login'))

    # GET запрос - показываем форму
    return render_template('login.html')


@bp.route('/logout')
def logout():
    """
    Handle user logout.
    
    Clears session['authenticated'] and redirects to /login.
    """
    session.pop('authenticated', None)
    flash('Вы вышли из системы', 'info')
    return redirect(url_for('main.login'))


@bp.route('/status')
@login_required
def status():
    """
    Render the status page.

    Requires authentication.
    """
    return render_template('base.html', title='Status')


@bp.route('/keys')
@login_required
def keys():
    """
    Render the keys and bridges page.

    Requires authentication.
    """
    logger.info("Accessing /keys page")
    
    # Проверка статусов сервисов
    config = WebConfig()

    services = {
        'vless': {
            'name': 'VLESS',
            'config': '/opt/etc/xray/vless.json',
            'init': '/opt/etc/init.d/S24xray',
            'status': '❓',
        },
        'hysteria2': {
            'name': 'Hysteria 2',
            'config': '/opt/etc/hysteria2.json',
            'init': '/opt/etc/init.d/S22hysteria2',
            'status': '❓',
        },
        'shadowsocks': {
            'name': 'Shadowsocks',
            'config': '/opt/etc/shadowsocks.json',
            'init': '/opt/etc/init.d/S22shadowsocks',
            'status': '❓',
        },
        'trojan': {
            'name': 'Trojan',
            'config': '/opt/etc/trojan.json',
            'init': '/opt/etc/init.d/S22trojan',
            'status': '❓',
        },
        'tor': {
            'name': 'Tor',
            'config': '/opt/etc/tor/torrc',
            'init': '/opt/etc/init.d/S35tor',
            'status': '❓',
        },
    }

    # Проверка статусов с таймаутом
    for service in services.values():
        try:
            # Проверяем существование скрипта
            if not os.path.exists(service['init']):
                logger.warning(f"Init script not found: {service['init']}")
                service['status'] = "❌ Скрипт не найден"
                service['config_exists'] = False
            else:
                # Проверяем существование конфига
                service['config_exists'] = os.path.exists(service['config'])
                # Временно не проверяем статус через subprocess (может зависать)
                # Используем простую проверку: если скрипт есть — считаем активным
                service['status'] = "✅ Активен" if service['config_exists'] else "❌ Не настроен"
            logger.debug(f"Service {service['name']}: status={service['status']}, config_exists={service['config_exists']}")
        except Exception as e:
            logger.error(f"Error checking status for {service['name']}: {e}")
            service['status'] = '❌ Ошибка'
            service['config_exists'] = False

    logger.info(f"/keys page rendered with {len(services)} services")
    return render_template('keys.html', services=services)


@bp.route('/keys/<service>', methods=['GET', 'POST'])
@login_required
@csrf_required
def key_config(service: str):
    """
    Handle key configuration for a service.

    Args:
        service: Service name (vless, shadowsocks, trojan, tor)

    Returns:
        Rendered key configuration page
    """
    logger.info(f"Accessing /keys/{service} page")
    config = WebConfig()

    services_config = {
        'vless': {
            'name': 'VLESS',
            'config_path': '/opt/etc/xray/vless.json',
            'init_script': '/opt/etc/init.d/S24xray',
        },
        'hysteria2': {
            'name': 'Hysteria 2',
            'config_path': '/opt/etc/hysteria2.json',
            'init_script': '/opt/etc/init.d/S22hysteria2',
        },
        'shadowsocks': {
            'name': 'Shadowsocks',
            'config_path': '/opt/etc/shadowsocks.json',
            'init_script': '/opt/etc/init.d/S22shadowsocks',
        },
        'trojan': {
            'name': 'Trojan',
            'config_path': '/opt/etc/trojan.json',
            'init_script': '/opt/etc/init.d/S22trojan',
        },
        'tor': {
            'name': 'Tor',
            'config_path': '/opt/etc/tor/torrc',
            'init_script': '/opt/etc/init.d/S35tor',
        },
    }

    if service not in services_config:
        logger.warning(f"Invalid service requested: {service}")
        flash('Неверный сервис', 'danger')
        return redirect(url_for('main.keys'))

    svc = services_config[service]
    logger.debug(f"Service config: {svc}")

    if request.method == 'POST':
        key = request.form.get('key', '').strip()
        logger.info(f"POST /keys/{service}: key received (length={len(key) if key else 0})")

        if not key:
            flash('Введите ключ', 'warning')
            return redirect(url_for('main.key_config', service=service))

        try:
            logger.info(f"Starting to process {service} key")
            
            # Парсинг ключа и генерация конфига
            if service == 'vless':
                logger.info("Parsing VLESS key")
                parsed = parse_vless_key(key)
                logger.info(f"VLESS key parsed: {list(parsed.keys())}")
                # Проверка успешности парсинга
                if not parsed.get('server') or not parsed.get('port'):
                    logger.error(f"VLESS parse failed: missing server/port")
                    raise ValueError("Не удалось распарсить ключ VLESS: отсутствуют server/port")
                logger.info(f"VLESS parse OK: server={parsed['server']}, port={parsed['port']}")
                logger.info("Generating VLESS config")
                cfg = vless_config(key)
                logger.info(f"VLESS config generated with {len(cfg)} keys")
                logger.info(f"About to write VLESS config to {svc['config_path']}")
                write_json_config(cfg, svc['config_path'])
                logger.info(f"VLESS config written successfully")
            elif service == 'shadowsocks':
                logger.info("Parsing Shadowsocks key")
                parsed = parse_shadowsocks_key(key)
                logger.info(f"Shadowsocks key parsed: {list(parsed.keys())}")
                # Проверка успешности парсинга
                if not parsed.get('server') or not parsed.get('port'):
                    logger.error(f"Shadowsocks parse failed: missing server/port")
                    raise ValueError("Не удалось распарсить ключ: отсутствуют server/port")
                logger.info(f"Shadowsocks parse OK: server={parsed['server']}, port={parsed['port']}")
                logger.info("Generating Shadowsocks config")
                cfg = shadowsocks_config(key)
                logger.info(f"Shadowsocks config generated with {len(cfg)} keys")
                logger.info(f"About to write Shadowsocks config to {svc['config_path']}")
                write_json_config(cfg, svc['config_path'])
                logger.info(f"Shadowsocks config written successfully")
            elif service == 'hysteria2':
                logger.info("Parsing Hysteria 2 key")
                parsed = parse_hysteria2_key(key)
                logger.info(f"Hysteria 2 key parsed: {list(parsed.keys())}")
                if not parsed.get('server') or not parsed.get('port'):
                    logger.error(f"Hysteria 2 parse failed: missing server/port")
                    raise ValueError("Не удалось распарсить ключ Hysteria 2: отсутствуют server/port")
                logger.info(f"Hysteria 2 parse OK: server={parsed['server']}, port={parsed['port']}")
                logger.info("Generating Hysteria 2 config")
                cfg = hysteria2_config(key)
                logger.info(f"About to write Hysteria 2 config to {svc['config_path']}")
                write_hysteria2_config(cfg, svc['config_path'])
                logger.info(f"Hysteria 2 config written successfully")
            elif service == 'trojan':
                logger.info("Parsing Trojan key")
                parsed = parse_trojan_key(key)
                logger.info(f"Trojan key parsed: {list(parsed.keys())}")
                # Проверка успешности парсинга
                if not parsed.get('server') or not parsed.get('port'):
                    logger.error(f"Trojan parse failed: missing server/port")
                    raise ValueError("Не удалось распарсить ключ Trojan: отсутствуют server/port")
                logger.info(f"Trojan parse OK: server={parsed['server']}, port={parsed['port']}")
                logger.info("Generating Trojan config")
                cfg = trojan_config(key)
                logger.info(f"About to write Trojan config to {svc['config_path']}")
                write_json_config(cfg, svc['config_path'])
                logger.info(f"Trojan config written successfully")
            elif service == 'tor':
                logger.info("Generating Tor config")
                cfg = tor_config(key)
                logger.info(f"About to write Tor config to {svc['config_path']}")
                write_tor_config(cfg, svc['config_path'])
                logger.info(f"Tor config written successfully")

            logger.info(f"Config written successfully for {service}")
            logger.info(f"About to restart {svc['name']} service")

            # Перезапуск сервиса через ThreadPoolExecutor (неблокирующий)
            try:
                future = executor.submit(restart_service, svc['name'], svc['init_script'])
                success, output = future.result(timeout=30)  # Max 30s wait

                if success:
                    flash(f'✅ {svc["name"]} успешно настроен и перезапущен', 'success')
                else:
                    flash(f'⚠️ Конфигурация сохранена, но ошибка перезапуска: {output}', 'warning')
            except TimeoutError:
                logger.warning(f"Service restart timeout: {svc['name']}")
                flash(f'⏱️ Превышено время ожидания перезапуска {svc["name"]} (30с)', 'warning')

            return redirect(url_for('main.keys'))

        except ValueError as e:
            flash(f'❌ Ошибка в ключе: {str(e)}', 'danger')
            logger.error(f"save_key ValueError: {e}")
        except Exception as e:
            flash(f'❌ Ошибка: {str(e)}', 'danger')
            logger.error(f"save_key Exception: {e}")
    
    # GET запрос - показываем форму
    return render_template('key_generic.html', service=service, service_name=svc['name'])


@bp.route('/bypass')
@login_required
def bypass():
    """
    Render the bypass lists page.

    Requires authentication.
    """
    # Загрузка конфигурации
    config = WebConfig()
    unblock_dir = config.unblock_dir
    
    # Получение списка доступных файлов
    available_files = []
    if os.path.exists(unblock_dir):
        try:
            available_files = [
                f.replace('.txt', '') 
                for f in os.listdir(unblock_dir) 
                if f.endswith('.txt')
            ]
        except Exception as e:
            logger.error(f"Error listing bypass files: {e}")
    
    return render_template('bypass.html', available_files=available_files)


@bp.route('/bypass/view/<filename>')
@login_required
def view_bypass(filename: str):
    """
    View contents of a bypass list file.

    Args:
        filename: Name of bypass list file (without .txt extension)

    Returns:
        Rendered bypass view page with file contents
    """
    config = WebConfig()
    
    # Security: sanitize filename
    filename = secure_filename(filename)
    if not filename:
        flash('Неверное имя файла', 'danger')
        return redirect(url_for('main.bypass'))
    
    filepath = os.path.join(config.unblock_dir, f"{filename}.txt")

    # Загрузка списка
    entries = load_bypass_list(filepath)

    return render_template(
        'bypass_view.html',
        filename=filename,
        entries=entries,
        filepath=filepath
    )


@bp.route('/bypass/<filename>/add', methods=['GET', 'POST'])
@login_required
@csrf_required
def add_to_bypass(filename: str):
    """
    Add entries to a bypass list file with optimized processing.
    
    Optimized for KN-1212 (128MB RAM):
    - Direct IP addition to ipset without full update
    - Only run full update for domain additions
    """
    config = WebConfig()
    
    # Security: sanitize filename
    filename = secure_filename(filename)
    if not filename:
        flash('Неверное имя файла', 'danger')
        return redirect(url_for('main.bypass'))
    
    filepath = os.path.join(config.unblock_dir, f"{filename}.txt")

    if request.method == 'POST':
        entries_text = request.form.get('entries', '')

        # Проверка на общий размер ввода (DoS protection)
        if len(entries_text) > MAX_TOTAL_INPUT_SIZE:
            flash(f'Превышен лимит размера ввода (макс. {MAX_TOTAL_INPUT_SIZE // 1024}KB)', 'danger')
            return redirect(url_for('main.bypass'))

        # Разбиваем на отдельные записи
        new_entries = [e.strip() for e in entries_text.split('\n') if e.strip()]

        # Проверка на количество записей (DoS protection)
        if len(new_entries) > MAX_ENTRIES_PER_REQUEST:
            flash(f'Превышено количество записей (макс. {MAX_ENTRIES_PER_REQUEST})', 'danger')
            return redirect(url_for('main.bypass'))

        # Проверка на длину записей (XSS + DoS protection)
        for entry in new_entries:
            if len(entry) > MAX_ENTRY_LENGTH:
                # XSS protection: escape user input
                flash(f'Запись слишком длинная (макс. {MAX_ENTRY_LENGTH} симв.): {escape(entry[:50])}...', 'danger')
                return redirect(url_for('main.bypass'))

        # Загружаем текущий список
        current_list = load_bypass_list(filepath)

        # Добавляем новые записи с валидацией
        added_count = 0
        invalid_entries = []
        ip_entries = []  # Отдельно собираем IP для добавления в ipset
        domain_entries = []  # Отдельно собираем домены

        for entry in new_entries:
            if entry not in current_list:
                if validate_bypass_entry(entry):
                    current_list.append(entry)
                    added_count += 1
                    # Если это IP адрес - добавляем в список для ipset
                    if is_ip_address(entry):
                        ip_entries.append(entry)
                    else:
                        domain_entries.append(entry)
                else:
                    invalid_entries.append(entry)

        # Сохраняем список
        save_bypass_list(filepath, current_list)

        # Оптимизированная логика обновления
        if added_count > 0:
            # Если только IP-адреса - добавляем напрямую в ipset
            if ip_entries and not domain_entries:
                success, msg = bulk_add_to_ipset('unblock', ip_entries)
                if success:
                    logger.info(f"Directly added {len(ip_entries)} IPs to ipset")
                    flash(f'✅ Успешно добавлено: {added_count} шт. (IP в ipset: {len(ip_entries)})', 'success')
                else:
                    logger.warning(f"Failed to add IPs directly: {msg}")
                    # Fall back to full update
                    success, output = run_unblock_update()
                    if success:
                        flash(f'✅ Успешно добавлено: {added_count} шт. Изменения применены', 'success')
                    else:
                        flash(f'⚠️ Добавлено {added_count} записей, но ошибка при применении: {output}', 'warning')
            else:
                # Для доменов или смешанных записей - использовать полное обновление
                if added_count > 0:
                    success, output = run_unblock_update()
                    if success:
                        flash(f'✅ Успешно добавлено: {added_count} шт. Изменения применены', 'success')
                    else:
                        flash(f'⚠️ Добавлено {added_count} записей, но ошибка при применении: {output}', 'warning')
        elif invalid_entries:
            # XSS protection: escape user input
            escaped_invalid = [escape(e) for e in invalid_entries[:5]]
            flash(f'⚠️ Все записи уже в списке или невалидны. Нераспознанные: {", ".join(escaped_invalid)}', 'warning')
        else:
            flash('ℹ️ Все записи уже были в списке', 'info')

        return redirect(url_for('main.view_bypass', filename=filename))
    
    # GET запрос - показываем форму
    return render_template('bypass_add.html', filename=filename)


@bp.route('/bypass/<filename>/remove', methods=['GET', 'POST'])
@login_required
@csrf_required
def remove_from_bypass(filename: str):
    """
    Remove entries from a bypass list file.

    Args:
        filename: Name of bypass list file (without .txt extension)

    Returns:
        Redirect to view page after processing
    """
    config = WebConfig()
    
    # Security: sanitize filename
    filename = secure_filename(filename)
    if not filename:
        flash('Неверное имя файла', 'danger')
        return redirect(url_for('main.bypass'))
    
    filepath = os.path.join(config.unblock_dir, f"{filename}.txt")

    if request.method == 'POST':
        entries_text = request.form.get('entries', '')

        # Проверка на общий размер ввода (DoS protection)
        if len(entries_text) > MAX_TOTAL_INPUT_SIZE:
            flash(f'Превышен лимит размера ввода (макс. {MAX_TOTAL_INPUT_SIZE // 1024}KB)', 'danger')
            return redirect(url_for('main.bypass_view', filename=filename))

        # Разбиваем на отдельные записи
        to_remove = [e.strip() for e in entries_text.split('\n') if e.strip()]

        # Проверка на количество записей (DoS protection)
        if len(to_remove) > MAX_ENTRIES_PER_REQUEST:
            flash(f'Превышено количество записей (макс. {MAX_ENTRIES_PER_REQUEST})', 'danger')
            return redirect(url_for('main.bypass_view', filename=filename))

        # Загружаем текущий список
        current_list = load_bypass_list(filepath)

        # Удаляем записи, сохраняя порядок
        original_count = len(current_list)
        current_list = [item for item in current_list if item not in to_remove]
        removed_count = original_count - len(current_list)

        # Bulk удаление из ipset
        ip_entries = [e for e in to_remove if is_ip_address(e) and e in current_list]
        ipset_msg = ''
        if ip_entries:
            success, msg = bulk_remove_from_ipset('unblock', ip_entries)
            ipset_msg = f" IP из ipset: {len(ip_entries)}"
            logger.info(f"ipset: {msg}")

        # Сохраняем список
        save_bypass_list(filepath, current_list)

        # Применяем изменения
        if removed_count > 0:
            success, output = run_unblock_update()
            if success:
                flash(f'✅ Успешно удалено: {removed_count} шт.{ipset_msg}. Изменения применены', 'success')
            else:
                flash(f'⚠️ Удалено {removed_count} записей, но ошибка при применении: {output}', 'warning')
        else:
            flash('ℹ️ Ни одна запись не найдена в списке', 'info')

        return redirect(url_for('main.view_bypass', filename=filename))
    
    # GET запрос - показываем форму
    entries = load_bypass_list(filepath)
    return render_template('bypass_remove.html', filename=filename, entries=entries)


@bp.route('/bypass/<filename>/refresh', methods=['POST'])
@login_required
@csrf_required
def refresh_bypass_ipset(filename: str):
    """
    Refresh ipset from bypass list (resolve domains).

    Resolves all domains in the bypass list and adds their IPs to ipset.
    Uses parallel DNS resolution for speed (100 domains in ~5 seconds).

    Args:
        filename: Name of bypass list file (without .txt extension)

    Returns:
        Redirect to view page after processing

    Example:
        POST /bypass/unblocktor/refresh
        → Resolves domains and adds IPs to ipset
    """
    config = WebConfig()

    # Security: sanitize filename
    filename = secure_filename(filename)
    if not filename:
        flash('Неверное имя файла', 'danger')
        return redirect(url_for('main.bypass'))

    filepath = os.path.join(config.unblock_dir, f"{filename}.txt")

    # Check if file exists
    if not os.path.exists(filepath):
        flash('Файл не найден', 'danger')
        return redirect(url_for('main.view_bypass', filename=filename))

    # Refresh ipset (resolve domains + add IPs)
    from core.ipset_manager import refresh_ipset_from_file
    success, msg = refresh_ipset_from_file(filepath, max_workers=10)

    if success:
        flash(f'✅ {msg}', 'success')
    else:
        flash(f'❌ Ошибка: {msg}', 'danger')

    return redirect(url_for('main.view_bypass', filename=filename))


@bp.route('/bypass/catalog')
@login_required
def bypass_catalog():
    """
    Show list catalog.
    
    Requires authentication.
    """
    from core.list_catalog import get_catalog
    catalog = get_catalog()
    return render_template('bypass_catalog.html', catalog=catalog)


@bp.route('/bypass/catalog/<name>', methods=['POST'])
@login_required
@csrf_required
def download_list(name: str):
    """
    Download list from catalog.
    
    Requires authentication and CSRF token.
    """
    from core.list_catalog import download_list
    
    config = WebConfig()
    dest_dir = config.unblock_dir
    
    success, message, count = download_list(name, dest_dir)
    
    if success:
        flash(f'✅ {message}', 'success')
    else:
        flash(f'❌ {message}', 'danger')
    
    return redirect(url_for('main.bypass_catalog'))


@bp.route('/install')
@login_required
def install():
    """
    Render the install/remove page.

    Requires authentication.
    """
    return render_template('install.html')


@bp.route('/stats')
@login_required
def stats():
    """
    Render the statistics page.

    Requires authentication.
    """
    config = WebConfig()
    
    # Статистика по сервисам
    services = {
        'vless': {
            'name': 'VLESS',
            'init': '/opt/etc/init.d/S24xray',
            'config': '/opt/etc/xray/vless.json',
        },
        'shadowsocks': {
            'name': 'Shadowsocks',
            'init': '/opt/etc/init.d/S22shadowsocks',
            'config': '/opt/etc/shadowsocks.json',
        },
        'trojan': {
            'name': 'Trojan',
            'init': '/opt/etc/init.d/S22trojan',
            'config': '/opt/etc/trojan.json',
        },
        'tor': {
            'name': 'Tor',
            'init': '/opt/etc/init.d/S35tor',
            'config': '/opt/etc/tor/torrc',
        },
    }
    
    # Проверка статусов
    for svc in services.values():
        svc['status'] = check_service_status(svc['init'])
        svc['config_exists'] = os.path.exists(svc['config'])
    
    # Статистика по спискам обхода
    unblock_dir = config.unblock_dir
    bypass_lists = []
    total_domains = 0
    
    if os.path.exists(unblock_dir):
        for filename in os.listdir(unblock_dir):
            if filename.endswith('.txt'):
                filepath = os.path.join(unblock_dir, filename)
                try:
                    with open(filepath, 'r') as f:
                        lines = [line.strip() for line in f if line.strip() and not line.startswith('#')]
                        count = len(lines)
                        total_domains += count
                        bypass_lists.append({
                            'name': filename,
                            'count': count,
                            'path': filepath,
                        })
                except Exception as e:
                    logger.error(f"stats Exception reading {filename}: {e}")
    
    # Общая статистика
    active_services = sum(1 for s in services.values() if s['status'] == '✅ Активен')
    config_files = sum(1 for s in services.values() if s['config_exists'])
    
    stats_data = {
        'total_services': len(services),
        'active_services': active_services,
        'config_files': config_files,
        'total_bypass_lists': len(bypass_lists),
        'total_domains': total_domains,
        'services': services,
        'bypass_lists': bypass_lists,
    }
    
    return render_template('stats.html', stats=stats_data)


@bp.route('/service')
@login_required
def service():
    """
    Render the service menu page.

    Requires authentication.
    """
    # Проверка статуса DNS Override
    dns_override_enabled = False
    try:
        # Проверяем наличие команды ndmc
        which_result = subprocess.run(['which', 'ndmc'], capture_output=True, text=True)
        if which_result.returncode != 0:
            logger.warning("ndmc command not found, skipping DNS Override check")
            dns_override_enabled = False
        else:
            # Пробуем разные команды для проверки DNS Override
            # Используем shell=True для поддержки pipe
            commands_to_try = [
                'ndmc -c "show running" | grep -i dns-override',
                'ndmc -c "show dns-override"',
                'ndmc -c "show dns override"',
            ]

            for cmd in commands_to_try:
                try:
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=5, shell=True)
                    if result.returncode == 0 and result.stdout.strip():
                        output = result.stdout.lower()
                        # Проверяем различные варианты
                        if 'dns-override' in output or 'dns override' in output:
                            dns_override_enabled = True
                            logger.debug(f"DNS Override found with command: {cmd}")
                            break
                        # Также проверяем, если в выводе есть enabled/disabled
                        if 'enabled' in output and 'disabled' not in output:
                            dns_override_enabled = True
                            break
                except subprocess.TimeoutExpired:
                    continue
                except Exception as e:
                    logger.debug(f"Command {cmd} failed: {e}")
                    continue

            logger.debug(f"DNS Override status: {dns_override_enabled}")
    except Exception as e:
        logger.error(f"Error checking DNS Override status: {e}")
        dns_override_enabled = False

    return render_template('service.html', dns_override_enabled=dns_override_enabled)


@bp.route('/service/restart-unblock', methods=['POST'])
@login_required
@csrf_required
def service_restart_unblock():
    """
    Restart the unblock service.

    Requires authentication.
    """
    init_script = '/opt/etc/init.d/S99unblock'
    success, output = restart_service('Unblock', init_script)
    
    if success:
        flash('✅ Unblock-сервис успешно перезапущен', 'success')
    else:
        flash(f'⚠️ Ошибка перезапуска: {output}', 'danger')
    
    return redirect(url_for('main.service'))


@bp.route('/service/restart-router', methods=['POST'])
@login_required
@csrf_required
def service_restart_router():
    """
    Restart the router.

    Requires authentication.
    """
    try:
        subprocess.run(['ndmc', '-c', 'system', 'reboot'], timeout=30)
        flash('✅ Команда на перезагрузку отправлена', 'success')
    except Exception as e:
        flash(f'❌ Ошибка: {str(e)}', 'danger')
        logger.error(f"service_reboot Exception: {e}")
    
    return redirect(url_for('main.service'))


@bp.route('/service/restart-all', methods=['POST'])
@login_required
@csrf_required
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
            logger.error(f"service_restart_all Exception for {name}: {e}")
    
    flash('Перезапуск сервисов: ' + ', '.join(results), 'success')
    return redirect(url_for('main.service'))


@bp.route('/service/dns-override/<action>', methods=['POST'])
@login_required
@csrf_required
def service_dns_override(action):
    """
    Enable or disable DNS Override.

    Requires authentication.
    """
    import time
    enable = (action == 'on')

    try:
        # Проверка наличия ndmc
        result = subprocess.run(['which', 'ndmc'], capture_output=True, text=True)
        if result.returncode != 0:
            flash('⚠️ ndmc не найден. DNS Override недоступен.', 'warning')
            logger.warning("ndmc command not found")
            return redirect(url_for('main.service'))
        
        # Включение/выключение DNS Override (как в Telegram боте)
        cmd = ['ndmc', '-c', 'opkg dns-override'] if enable else ['ndmc', '-c', 'no opkg dns-override']
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        
        if result.returncode != 0:
            flash(f'❌ Ошибка: {result.stderr}', 'danger')
            logger.error(f"DNS Override error: {result.stderr}")
            return redirect(url_for('main.service'))
        
        time.sleep(2)
        
        # Сохранение конфигурации
        subprocess.run(['ndmc', '-c', 'system', 'configuration', 'save'], timeout=10)
        
        # Автоматическая перезагрузка
        flash('✅ DNS Override ' + ('включен' if enable else 'выключен') + '. Роутер будет перезагружен...', 'success')
        logger.info("DNS Override changed, rebooting...")
        
        # Асинхронная перезагрузка (не блокируем ответ)
        subprocess.Popen(['ndmc', '-c', 'system', 'reboot'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
    except Exception as e:
        flash(f'❌ Ошибка: {str(e)}', 'danger')
        logger.error(f"service_dns_override Exception: {e}")

    return redirect(url_for('main.service'))


def get_backup_list():
    """Get list of backups with size and date info"""
    import os
    import re
    backup_dir = '/opt/root/backup'
    backups = []
    
    if os.path.exists(backup_dir):
        for item in sorted(os.listdir(backup_dir), reverse=True):
            if (item.startswith('backup_') or item.startswith('update_backup_')) and item.endswith('.tar.gz'):
                item_path = os.path.join(backup_dir, item)
                try:
                    size = os.path.getsize(item_path)
                    # Extract date from filename: backup_YYYYMMDD_HHMMSS.tar.gz or update_backup_YYYYMMDD_HHMMSS.tar.gz
                    match = re.match(r'(backup|update_backup)_(\d{8})_(\d{6})\.tar\.gz', item)
                    if match:
                        date_str = match.group(2)
                        time_str = match.group(3)
                    else:
                        date_str = item
                        time_str = ''
                    
                    backups.append({
                        'name': item,
                        'path': item_path,
                        'size': size,
                        'date': f"{date_str[6:8]}.{date_str[4:6]}.{date_str[0:4]}",
                        'time': f"{time_str[0:2]}:{time_str[2:4]}" if time_str else '',
                    })
                except Exception as e:
                    logger.error(f"Error processing backup {item}: {e}")
    
    return backups


@bp.route('/service/backup', methods=['GET', 'POST'])
@login_required
def service_backup():
    """
    Create and manage backups of configuration files.

    Requires authentication.
    """
    backups = get_backup_list()

    if request.method == 'POST':
        # CSRF check for POST requests
        if not validate_csrf_token():
            flash('Ошибка безопасности: неверный токен', 'danger')
            logger.warning("CSRF token validation failed in service_backup")
            return redirect(url_for('main.service_backup'))
        
        action = request.form.get('action')
        
        if action == 'create':
            from core.services import create_backup
            success, message = create_backup()
            if success:
                flash(f'✅ {message}', 'success')
            else:
                flash(f'❌ {message}', 'danger')
            return redirect(url_for('main.service_backup'))
        
        elif action == 'delete':
            backup_name = request.form.get('backup_name')
            backup_path = os.path.join('/opt/root/backup', backup_name)
            
            if backup_name and os.path.exists(backup_path):
                import shutil
                try:
                    os.remove(backup_path)
                    flash(f'✅ Бэкап {backup_name} удалён', 'success')
                    logger.info(f"Backup deleted: {backup_path}")
                except Exception as e:
                    flash(f'❌ Ошибка удаления: {e}', 'danger')
                    logger.error(f"Backup delete error: {e}")
            else:
                flash(f'❌ Бэкап не найден', 'danger')
            
            return redirect(url_for('main.service_backup'))

    # GET - показать страницу бэкапа
    return render_template('backup.html', backups=backups)


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
            logger.warning(f"get_updates_version: version parse error - local={local_version}, remote={remote_version}")
    
    return render_template('updates.html', 
                          local_version=local_version,
                          remote_version=remote_version,
                          need_update=need_update)


@bp.route('/service/updates/run', methods=['POST'])
@login_required
@csrf_required
def service_updates_run():
    """
    Smart update process - updates only code files, preserves user data.
    
    Files that WILL be updated (code):
    - /opt/etc/web_ui/ (web interface code)
    - /opt/etc/init.d/ (init scripts)
    - /opt/etc/ndm/ (system scripts)
    - /opt/bin/ (bypass scripts)
    - /opt/etc/dnsmasq.conf
    - /opt/etc/crontab
    - /opt/root/script.sh
    
    Files that will be PRESERVED (user data):
    - /opt/etc/xray/ (VLESS keys)
    - /opt/etc/tor/ (Tor settings)
    - /opt/etc/trojan/ (Trojan settings)
    - /opt/etc/shadowsocks.json (Shadowsocks keys)
    - /opt/etc/unblock/*.txt (bypass lists)
    
    Requires authentication.
    """
    from datetime import datetime
    import shutil
    from core.update_progress import UpdateProgress
    
    # Get progress instance
    progress = UpdateProgress()
    
    try:
        # Check if update is already running
        if progress.is_running:
            return jsonify({
                'success': False,
                'error': 'Update already in progress'
            })
        
        flash('⏳ Создание резервной копии...', 'info')
        
        # Create backup before update
        backup_dir = '/opt/root/backup'
        os.makedirs(backup_dir, exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_file = f'{backup_dir}/update_backup_{timestamp}.tar.gz'
        
        files_to_backup = [
            '/opt/etc/web_ui',
            '/opt/etc/xray',
            '/opt/etc/tor',
            '/opt/etc/unblock',
            '/opt/etc/shadowsocks.json',
            '/opt/etc/trojan',
            '/opt/etc/unblock-ai.dnsmasq',
            '/opt/etc/unblock/ai-domains.txt',
        ]
        existing_files = [f for f in files_to_backup if os.path.exists(f)]
        
        if existing_files:
            import tarfile
            # Use faster compression level for KN-1212 (level 1 instead of default 6)
            with tarfile.open(backup_file, 'w:gz', compresslevel=1) as tar:
                for f in existing_files:
                    tar.add(f, arcname=os.path.basename(f))
            flash(f'💾 Бэкап сохранён: {backup_file}', 'info')
        
        flash('⏳ Загрузка обновлений...', 'info')
        
        github_repo = 'royfincher25-source/flymybyte'
        github_branch = 'master'
        
        # Files to update (code only, not user data)
        files_to_update = {
            # Version file
            'VERSION': '/opt/etc/web_ui/VERSION',
            
            # Environment template
            'web_ui/.env.example': '/opt/etc/web_ui/.env.example',
            
            # Web UI core files
            'web_ui/__init__.py': '/opt/etc/web_ui/__init__.py',
            'web_ui/routes.py': '/opt/etc/web_ui/routes.py',
            'web_ui/app.py': '/opt/etc/web_ui/app.py',
            'web_ui/env_parser.py': '/opt/etc/web_ui/env_parser.py',
            'web_ui/core/__init__.py': '/opt/etc/web_ui/core/__init__.py',
            'web_ui/core/utils.py': '/opt/etc/web_ui/core/utils.py',
            'web_ui/core/services.py': '/opt/etc/web_ui/core/services.py',
            'web_ui/core/dns_monitor.py': '/opt/etc/web_ui/core/dns_monitor.py',
            'web_ui/core/dns_manager.py': '/opt/etc/web_ui/core/dns_manager.py',
            'web_ui/core/dns_resolver.py': '/opt/etc/web_ui/core/dns_resolver.py',
            'web_ui/core/ipset_manager.py': '/opt/etc/web_ui/core/ipset_manager.py',
            'web_ui/core/app_config.py': '/opt/etc/web_ui/core/app_config.py',
            'web_ui/core/web_config.py': '/opt/etc/web_ui/core/web_config.py',
            'web_ui/core/list_catalog.py': '/opt/etc/web_ui/core/list_catalog.py',
            'web_ui/core/update_progress.py': '/opt/etc/web_ui/core/update_progress.py',
            'web_ui/core/dns_spoofing.py': '/opt/etc/web_ui/core/dns_spoofing.py',
            
            # Init scripts
            'web_ui/resources/scripts/S99unblock': '/opt/etc/init.d/S99unblock',
            'web_ui/resources/scripts/S99web_ui': '/opt/etc/init.d/S99web_ui',
            
            # NDM scripts
            'web_ui/resources/scripts/100-redirect.sh': '/opt/etc/ndm/netfilter.d/100-redirect.sh',
            'web_ui/resources/scripts/100-unblock-vpn.sh': '/opt/etc/ndm/ifstatechanged.d/100-unblock-vpn.sh',
            'web_ui/resources/scripts/100-ipset.sh': '/opt/etc/ndm/fs.d/100-ipset.sh',
            
            # Bypass scripts
            'web_ui/resources/scripts/unblock_ipset.sh': '/opt/bin/unblock_ipset.sh',
            'web_ui/resources/scripts/unblock_dnsmasq.sh': '/opt/bin/unblock_dnsmasq.sh',
            'web_ui/resources/scripts/unblock_update.sh': '/opt/bin/unblock_update.sh',

            # Redirect scripts
            'web_ui/resources/scripts/100-redirect.sh': '/opt/etc/ndm/netfilter.d/100-redirect.sh',
            
            # Config files
            'web_ui/resources/config/dnsmasq.conf': '/opt/etc/dnsmasq.conf',
            'web_ui/resources/config/crontab': '/opt/etc/crontab',
            
            # Main script
            'web_ui/scripts/script.sh': '/opt/root/script.sh',
            
            # Templates
            'web_ui/templates/base.html': '/opt/etc/web_ui/templates/base.html',
            'web_ui/templates/login.html': '/opt/etc/web_ui/templates/login.html',
            'web_ui/templates/index.html': '/opt/etc/web_ui/templates/index.html',
            'web_ui/templates/keys.html': '/opt/etc/web_ui/templates/keys.html',
            'web_ui/templates/bypass.html': '/opt/etc/web_ui/templates/bypass.html',
            'web_ui/templates/install.html': '/opt/etc/web_ui/templates/install.html',
            'web_ui/templates/stats.html': '/opt/etc/web_ui/templates/stats.html',
            'web_ui/templates/service.html': '/opt/etc/web_ui/templates/service.html',
            'web_ui/templates/updates.html': '/opt/etc/web_ui/templates/updates.html',
            'web_ui/templates/bypass_view.html': '/opt/etc/web_ui/templates/bypass_view.html',
            'web_ui/templates/bypass_add.html': '/opt/etc/web_ui/templates/bypass_add.html',
            'web_ui/templates/bypass_remove.html': '/opt/etc/web_ui/templates/bypass_remove.html',
            'web_ui/templates/bypass_catalog.html': '/opt/etc/web_ui/templates/bypass_catalog.html',
            'web_ui/templates/key_generic.html': '/opt/etc/web_ui/templates/key_generic.html',
            'web_ui/templates/backup.html': '/opt/etc/web_ui/templates/backup.html',
            'web_ui/templates/dns_monitor.html': '/opt/etc/web_ui/templates/dns_monitor.html',
            'web_ui/templates/logs.html': '/opt/etc/web_ui/templates/logs.html',
            'web_ui/templates/dns_spoofing.html': '/opt/etc/web_ui/templates/dns_spoofing.html',
            
            # Static files
            'web_ui/static/style.css': '/opt/etc/web_ui/static/style.css',

            # Resources (lists, configs, scripts)
            'web_ui/resources/lists/unblock-ai-domains.txt': '/opt/etc/web_ui/resources/lists/unblock-ai-domains.txt',
            'web_ui/resources/config/unblock-ai.dnsmasq.template': '/opt/etc/web_ui/resources/config/unblock-ai.dnsmasq.template',
            'web_ui/resources/scripts/unblock_dnsmasq.sh': '/opt/etc/web_ui/resources/scripts/unblock_dnsmasq.sh',
        }
        
        updated_count = 0
        error_count = 0
        total_files = len(files_to_update)
        
        # Start progress tracking after we know total files
        progress.start_update(total_files=total_files)
        
        for i, (source_path, dest_path) in enumerate(files_to_update.items(), 1):
            # VERSION file is in root, others are in src/
            if source_path == 'VERSION':
                url = f'https://raw.githubusercontent.com/{github_repo}/{github_branch}/VERSION'
            else:
                url = f'https://raw.githubusercontent.com/{github_repo}/{github_branch}/src/{source_path}'
            
            # Update progress
            progress.update_progress(f'Загрузка {source_path}', file=source_path, progress=i, total=total_files)
            
            try:
                response = requests.get(url, timeout=60)
                response.raise_for_status()
                
                os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                with open(dest_path, 'w', encoding='utf-8') as f:
                    f.write(response.text)
                
                # Set executable permissions for scripts
                filename = os.path.basename(dest_path)
                is_executable = filename.endswith('.sh') or filename in ['S99web_ui', 'S99unblock']
                os.chmod(dest_path, 0o755 if is_executable else 0o644)
                logger.info(f"Updated {dest_path}")
                updated_count += 1
                
            except requests.exceptions.RequestException as e:
                logger.error(f'Error downloading {source_path}: {e}')
                error_count += 1
            except OSError as e:
                logger.error(f'Error writing {dest_path}: {e}')
                error_count += 1
        
        # Apply updated scripts
        try:
            # Add script execution steps to total
            script_steps = 5  # unblock_update, unblock_dnsmasq, S99unblock, S56dnsmasq, S99web_ui
            total_steps = total_files + script_steps
            current_step = total_files  # Start from where file download ended

            progress.update_progress('Запуск unblock_update.sh', file='unblock_update.sh', progress=current_step, total=total_steps)

            # Run bypass update scripts
            if os.path.exists('/opt/bin/unblock_update.sh'):
                result = subprocess.run(['/opt/bin/unblock_update.sh'], timeout=120, capture_output=True, text=True)
                if result.returncode != 0:
                    logger.error(f"unblock_update.sh failed with code {result.returncode}: {result.stderr}")
                else:
                    logger.info("Ran unblock_update.sh")
            current_step += 1

            progress.update_progress('Запуск unblock_dnsmasq.sh', file='unblock_dnsmasq.sh', progress=current_step, total=total_steps)

            # Run unblock_dnsmasq.sh from /opt/bin if exists
            if os.path.exists('/opt/bin/unblock_dnsmasq.sh'):
                result = subprocess.run(['/opt/bin/unblock_dnsmasq.sh'], timeout=120, capture_output=True, text=True)
                if result.returncode != 0:
                    logger.error(f"unblock_dnsmasq.sh failed with code {result.returncode}: {result.stderr}")
                else:
                    logger.info("Ran unblock_dnsmasq.sh from /opt/bin")
            current_step += 1

            # Also run from resources if exists (for AI domains config)
            progress.update_progress('Генерация AI DNS config', file='resources/scripts/unblock_dnsmasq.sh', progress=current_step, total=total_steps)
            if os.path.exists('/opt/etc/web_ui/resources/scripts/unblock_dnsmasq.sh'):
                result = subprocess.run(['sh', '/opt/etc/web_ui/resources/scripts/unblock_dnsmasq.sh'], timeout=120, capture_output=True, text=True)
                if result.returncode != 0:
                    logger.error(f"resources/unblock_dnsmasq.sh failed: {result.stderr}")
                else:
                    logger.info("Ran resources/unblock_dnsmasq.sh - AI domains config generated")
            current_step += 1

            progress.update_progress('Перезапуск S99unblock', file='S99unblock', progress=current_step, total=total_steps)

            # Restart related services with error handling
            if os.path.exists('/opt/etc/init.d/S99unblock'):
                try:
                    result = subprocess.run(['/opt/etc/init.d/S99unblock', 'restart'],
                                          timeout=60, capture_output=True, text=True)
                    if result.returncode != 0:
                        logger.warning(f"S99unblock restart failed: {result.stderr}")
                    else:
                        logger.info("Restarted S99unblock")
                except subprocess.TimeoutExpired:
                    logger.warning("S99unblock restart timeout")
                except Exception as e:
                    logger.warning(f"S99unblock restart error: {e}")
            current_step += 1

            progress.update_progress('Перезапуск S56dnsmasq', file='S56dnsmasq', progress=current_step, total=total_steps)

            if os.path.exists('/opt/etc/init.d/S56dnsmasq'):
                try:
                    result = subprocess.run(['/opt/etc/init.d/S56dnsmasq', 'restart'],
                                          timeout=60, capture_output=True, text=True)
                    if result.returncode != 0:
                        logger.warning(f"S56dnsmasq restart failed: {result.stderr}")
                    else:
                        logger.info("Restarted S56dnsmasq")
                except subprocess.TimeoutExpired:
                    logger.warning("S56dnsmasq restart timeout")
                except Exception as e:
                    logger.warning(f"S56dnsmasq restart error: {e}")
            current_step += 1

            # S99web_ui будет перезапущен ПОСЛЕ отправки ответа
            # чтобы не прерывать AJAX-запрос
            current_step += 1
                
        except subprocess.TimeoutExpired:
            logger.warning("Script execution timeout")
            progress.set_error('Script execution timeout')
        except Exception as e:
            logger.warning(f"Failed to run update scripts: {e}")
            progress.set_error(f'Failed to run scripts: {e}')
        
        if error_count == 0:
            progress.complete()
            flash(f'✅ Обновление завершено! Обновлено файлов: {updated_count}', 'success')

            # Перезапуск S99web_ui ПОСЛЕ отправки ответа (в фоне)
            # чтобы не прерывать AJAX-запрос
            try:
                # Создаём скрипт для отложенного перезапуска
                restart_script = '/tmp/restart_webui.sh'
                with open(restart_script, 'w') as f:
                    f.write('#!/bin/sh\n')
                    f.write('sleep 5\n')
                    f.write('/opt/etc/init.d/S99web_ui restart\n')
                    f.write('rm -f /tmp/restart_webui.sh\n')
                
                import stat
                os.chmod(restart_script, stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH)
                
                # Запускаем скрипт в фоне
                subprocess.Popen([restart_script], 
                               stdout=subprocess.DEVNULL, 
                               stderr=subprocess.DEVNULL,
                               start_new_session=True)
                logger.info("S99web_ui restart scheduled via /tmp/restart_webui.sh")
            except Exception as e:
                logger.warning(f"Failed to schedule S99web_ui restart: {e}")
                # Fallback: пробуем перезапустить напрямую (может прервать AJAX)
                try:
                    subprocess.Popen(['/opt/etc/init.d/S99web_ui', 'restart'],
                                   stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL,
                                   start_new_session=True)
                    logger.info("S99web_ui restart triggered directly (fallback)")
                except Exception as e2:
                    logger.error(f"Fallback restart also failed: {e2}")

            return jsonify({
                'success': True,
                'message': f'✅ Обновление завершено! Обновлено файлов: {updated_count}',
                'reload': True,
                'reload_delay': 3000  # 3 секунды
            })
        else:
            progress.set_error(f'Обновлено: {updated_count}, ошибок: {error_count}')
            flash(f'⚠️ Обновлено: {updated_count}, ошибок: {error_count}', 'warning')
            return jsonify({
                'success': False,
                'error': f'Обновлено: {updated_count}, ошибок: {error_count}',
                'reload': False
            })
            
    except Exception as e:
        progress.set_error(str(e))
        flash(f'❌ Ошибка обновления: {str(e)}', 'danger')
        logger.error(f"service_updates_run Exception: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        })


@bp.route('/install', methods=['GET', 'POST'])
@login_required
@csrf_required
def service_install():
    """
    Run installation script.

    Requires authentication.
    """
    if request.method == 'POST':
        script_path = '/opt/root/script.sh'
        local_script_path = os.path.join(os.path.dirname(__file__), 'scripts', 'script.sh')
        resources_dir = os.path.join(os.path.dirname(__file__), 'resources')

        try:
            flash('⏳ Копирование скрипта установки...', 'info')

            # Проверка наличия локального скрипта
            if not os.path.exists(local_script_path):
                flash('❌ Ошибка: локальный скрипт не найден', 'danger')
                logger.error(f"Local script not found: {local_script_path}")
                return redirect(url_for('main.service_install'))

            # Чтение локального скрипта
            with open(local_script_path, 'r', encoding='utf-8') as f:
                script_content = f.read()

            # Создание директории назначения
            os.makedirs(os.path.dirname(script_path), exist_ok=True)

            # Запись скрипта на роутер
            with open(script_path, 'w', encoding='utf-8') as f:
                f.write(script_content)
            os.chmod(script_path, 0o755)

            flash('✅ Скрипт скопирован', 'success')
            logger.info(f"Script copied to {script_path}")

            # Бэкап текущей версии перед обновлением
            import shutil
            from datetime import datetime
            backup_dir = '/opt/etc/web_ui/backup'
            backup_subdir = os.path.join(backup_dir, datetime.now().strftime('%Y%m%d_%H%M%S'))
            web_ui_dir = '/opt/etc/web_ui'
            
            if os.path.exists(web_ui_dir):
                try:
                    os.makedirs(backup_dir, exist_ok=True)
                    shutil.copytree(web_ui_dir, backup_subdir)
                    flash(f'💾 Бэкап создан: {backup_subdir}', 'info')
                    logger.info(f"Backup created: {backup_subdir}")
                except Exception as e:
                    flash(f'⚠️ Бэкап не создан: {e}', 'warning')
                    logger.warning(f"Backup failed: {e}")

            # Копирование ресурсов на роутер
            if os.path.exists(resources_dir):
                flash('⏳ Копирование ресурсов...', 'info')
                resources_dest = '/opt/etc/web_ui/resources'
                os.makedirs(resources_dest, exist_ok=True)

                # Копирование файлов ресурсов
                for item in os.listdir(resources_dir):
                    src_item = os.path.join(resources_dir, item)
                    dest_item = os.path.join(resources_dest, item)
                    if os.path.isfile(src_item):
                        shutil.copy2(src_item, dest_item)
                    elif os.path.isdir(src_item):
                        if os.path.exists(dest_item):
                            shutil.rmtree(dest_item)
                        shutil.copytree(src_item, dest_item)

                flash('✅ Ресурсы скопированы', 'success')
                logger.info(f"Resources copied to {resources_dest}")

            # Запуск скрипта генерации dnsmasq конфигурации для AI-доменов
            flash('⏳ Генерация конфигурации DNS-обхода AI...', 'info')
            try:
                result = subprocess.run(
                    ['sh', '/opt/etc/web_ui/resources/scripts/unblock_dnsmasq.sh'],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                if result.returncode == 0:
                    flash('✅ DNS-обход AI сгенерирован', 'success')
                    logger.info("unblock_dnsmasq.sh executed successfully")
                else:
                    flash(f'⚠️ DNS-обход AI: {result.stderr.strip()}', 'warning')
                    logger.warning(f"unblock_dnsmasq.sh warning: {result.stderr}")
            except Exception as e:
                flash(f'⚠️ DNS-обход AI: {str(e)}', 'warning')
                logger.warning(f"unblock_dnsmasq.sh error: {e}")

        except Exception as e:
            flash(f'❌ Ошибка копирования: {str(e)}', 'danger')
            logger.error(f"service_install copy Exception: {e}")
            return redirect(url_for('main.service_install'))
        
        try:
            flash('⏳ Установка началась...', 'info')
            
            process = subprocess.Popen(
                [script_path, '-install'],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
            
            output_lines = []
            for line in process.stdout:
                output_lines.append(line.strip())
                flash(f'⏳ {line.strip()}', 'info')
            
            process.wait(timeout=600)
            
            if process.returncode == 0:
                flash('✅ Установка flymybyte завершена', 'success')
                
                try:
                    result = subprocess.run(
                        ['sh', '-c', 'ipset list -n'],
                        capture_output=True,
                        text=True,
                        timeout=10
                    )
                    if 'unblocksh' in result.stdout:
                        flash('✅ ipset initialized', 'success')
                    else:
                        flash('⚠️ ipset not found', 'warning')
                        
                    for script in ['S99unblock', 'S99web_ui']:
                        if os.path.exists(f'/opt/etc/init.d/{script}'):
                            flash(f'✅ {script} installed', 'success')
                            
                except Exception as e:
                    logger.error(f"Post-install verification error: {e}")
            else:
                flash('❌ Ошибка установки', 'danger')
                
        except subprocess.TimeoutExpired:
            flash('❌ Превышен таймаут (10 минут)', 'danger')
            logger.error("service_install: timeout exceeded (10 minutes)")
        except Exception as e:
            flash(f'❌ Ошибка: {str(e)}', 'danger')
            logger.error(f"service_install Exception: {e}")
    
    return render_template('install.html')


@bp.route('/remove', methods=['GET', 'POST'])
@login_required
@csrf_required
def service_remove():
    """
    Run removal script.

    Requires authentication.
    """
    if request.method == 'POST':
        script_path = '/opt/root/script.sh'
        local_script_path = os.path.join(os.path.dirname(__file__), 'scripts', 'script.sh')

        if not os.path.exists(script_path):
            try:
                flash('⏳ Копирование скрипта...', 'info')

                # Проверка наличия локального скрипта
                if not os.path.exists(local_script_path):
                    flash('❌ Ошибка: локальный скрипт не найден', 'danger')
                    logger.error(f"Local script not found: {local_script_path}")
                    return redirect(url_for('main.service_remove'))

                # Чтение локального скрипта
                with open(local_script_path, 'r', encoding='utf-8') as f:
                    script_content = f.read()

                # Создание директории назначения
                os.makedirs(os.path.dirname(script_path), exist_ok=True)

                # Запись скрипта на роутер
                with open(script_path, 'w', encoding='utf-8') as f:
                    f.write(script_content)
                os.chmod(script_path, 0o755)

                flash('✅ Скрипт скопирован', 'success')
                logger.info(f"Script copied to {script_path}")

            except Exception as e:
                flash(f'❌ Ошибка копирования скрипта: {str(e)}', 'danger')
                logger.error(f"service_remove copy Exception: {e}")
                return redirect(url_for('main.service_remove'))
        
        try:
            flash('⏳ Удаление началось...', 'info')
            
            process = subprocess.Popen(
                [script_path, '-remove'],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
            
            for line in process.stdout:
                flash(f'⏳ {line.strip()}', 'info')
            
            process.wait(timeout=300)
            
            if process.returncode == 0:
                flash('✅ Удаление завершено', 'success')
            else:
                flash('❌ Ошибка удаления', 'danger')
                
        except subprocess.TimeoutExpired:
            flash('❌ Превышен таймаут (5 минут)', 'danger')
            logger.error("service_remove: timeout exceeded (5 minutes)")
        except Exception as e:
            flash(f'❌ Ошибка: {str(e)}', 'danger')
            logger.error(f"service_remove Exception: {e}")
    
    return render_template('install.html')


# =============================================================================
# DNS MONITOR ROUTES
# =============================================================================

@bp.route('/service/dns-monitor')
@login_required
def dns_monitor_status():
    """Show DNS monitor status"""
    from core.dns_monitor import get_dns_monitor
    monitor = get_dns_monitor()
    status = monitor.get_status()
    return render_template('dns_monitor.html', status=status)


@bp.route('/service/dns-monitor/start', methods=['POST'])
@login_required
@csrf_required
def dns_monitor_start():
    """Start DNS monitor"""
    from core.dns_monitor import get_dns_monitor
    monitor = get_dns_monitor()
    monitor.start()
    flash('✅ DNS monitor started', 'success')
    return redirect(url_for('main.dns_monitor_status'))


@bp.route('/service/dns-monitor/stop', methods=['POST'])
@login_required
@csrf_required
def dns_monitor_stop():
    """Stop DNS monitor"""
    from core.dns_monitor import get_dns_monitor
    monitor = get_dns_monitor()
    monitor.stop()
    flash('ℹ️ DNS monitor stopped', 'info')
    return redirect(url_for('main.dns_monitor_status'))


@bp.route('/service/dns-monitor/check', methods=['POST'])
@login_required
@csrf_required
def dns_monitor_check():
    """Force DNS check"""
    from core.dns_monitor import get_dns_monitor, check_dns_server

    monitor = get_dns_monitor()

    # Check current server
    if monitor._current_server:
        result = check_dns_server(
            monitor._current_server['host'],
            monitor._current_server['port']
        )
        if result['success']:
            flash(f"✅ DNS OK: {result['latency_ms']}ms", 'success')
        else:
            flash(f"❌ DNS failed: {result['error']}", 'danger')
    else:
        flash('⚠️ No DNS server selected', 'warning')

    return redirect(url_for('main.dns_monitor_status'))


# =============================================================================
# SYSTEM STATS
# =============================================================================

@bp.route('/api/system/stats')
@login_required
def system_stats():
    """Get system memory and cache statistics"""
    from core.utils import get_memory_stats, get_cpu_stats, MemoryManager
    from core.dns_monitor import get_dns_monitor
    
    stats = get_memory_stats()
    cpu_stats = get_cpu_stats()
    stats.update(cpu_stats)
    stats['memory_manager'] = MemoryManager.get_status()
    
    monitor = get_dns_monitor()
    stats['dns_status'] = {
        'running': monitor.is_running(),
        'current_server': monitor._current_server.get('name') if monitor._current_server else None,
        'failures': monitor._failures,
        'last_check': monitor._last_check.isoformat() if monitor._last_check else None,
    }
    
    return jsonify(stats)


@bp.route('/api/update/progress', methods=['GET'])
@login_required
def get_update_progress():
    """Get update progress status"""
    from core.update_progress import UpdateProgress
    progress = UpdateProgress()
    return jsonify(progress.get_status())


@bp.route('/api/system/memory-manager/<action>', methods=['POST'])
@login_required
def memory_manager_action(action):
    """Enable/disable auto memory optimization"""
    from core.utils import MemoryManager
    
    if action == 'enable':
        MemoryManager.enable()
        return jsonify({'success': True, 'message': 'Авто оптимизация включена'})
    elif action == 'disable':
        MemoryManager.disable()
        return jsonify({'success': True, 'message': 'Авто оптимизация выключена'})
    elif action == 'status':
        return jsonify(MemoryManager.get_status())
    else:
        return jsonify({'success': False, 'error': 'Unknown action'}), 400


@bp.route('/api/system/optimize', methods=['POST'])
@login_required
def manual_optimize():
    """Manually optimize memory by clearing cache"""
    from core.utils import Cache, get_memory_stats, MemoryManager
    
    before = get_memory_stats()
    Cache.clear()
    after = get_memory_stats()
    
    MemoryManager.check_and_optimize()
    final = MemoryManager.get_status()
    
    return jsonify({
        'success': True,
        'message': f'Cache cleared: {before["cache_entries"]} entries. Free: {after["free_mb"]}MB',
        'stats': {
            'cache_cleared': before['cache_entries'],
            'free_before': before['free_mb'],
            'free_after': after['free_mb'],
            'current_cache_size': final['current_cache'],
        }
    })


# =============================================================================
# ROUTE REGISTRATION
# =============================================================================

def register_routes(app):
    """
    Register all routes with the Flask application.
    
    This function is called by create_app() to register all routes.
    The blueprint is already registered, this function can be used
    for additional route registration if needed.
    
    Args:
        app: Flask application instance
    """
    # Blueprint already registered in create_app()
    # This function exists for future extensibility
    pass


@bp.route('/logs')
@login_required
def view_logs():
    """
    View application logs.
    
    Requires authentication.
    """
    log_file = os.environ.get('LOG_FILE', '/opt/var/log/web_ui.log')
    lines = []
    error_lines = []
    
    try:
        if os.path.exists(log_file):
            with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                all_lines = f.readlines()
                lines = all_lines[-100:]  # Last 100 lines
                error_lines = [l for l in all_lines if 'ERROR' in l or 'CRITICAL' in l][-20:]
    except Exception as e:
        logger.error(f"view_logs Exception: {e}")
        flash(f'❌ Ошибка чтения логов: {str(e)}', 'danger')
    
    return render_template('logs.html', 
                          log_lines=lines, 
                          error_lines=error_lines,
                          log_file=log_file)


@bp.route('/logs/clear', methods=['POST'])
@login_required
@csrf_required
def clear_logs():
    """
    Clear application logs.

    Requires authentication.
    """
    log_file = os.environ.get('LOG_FILE', '/opt/var/log/web_ui.log')

    try:
        if os.path.exists(log_file):
            with open(log_file, 'w') as f:
                f.write('')
            flash('✅ Логи очищены', 'success')
        else:
            flash('⚠️ Файл логов не найден', 'warning')
    except Exception as e:
        flash(f'❌ Ошибка: {str(e)}', 'danger')
        logger.error(f"clear_logs Exception: {e}")

    return redirect(url_for('main.view_logs'))


# =============================================================================
# DNS SPOOFING ROUTES
# =============================================================================

@bp.route('/dns-spoofing')
@login_required
def dns_spoofing():
    """
    DNS Spoofing management page for AI domains.
    
    Requires authentication.
    """
    logger.info("Accessing /dns-spoofing page")
    return render_template('dns_spoofing.html')


@bp.route('/dns-spoofing/status')
@login_required
def dns_spoofing_status():
    """
    Get DNS spoofing status.
    
    Returns:
        JSON with status information
    """
    try:
        from core.dns_spoofing import get_dns_spoofing_status
        
        status = get_dns_spoofing_status()
        return jsonify(status)
        
    except Exception as e:
        logger.error(f"dns_spoofing_status error: {e}")
        return jsonify({
            'enabled': False,
            'domain_count': 0,
            'config_exists': False,
            'dnsmasq_running': False,
            'error': str(e)
        })


@bp.route('/dns-spoofing/apply', methods=['POST'])
@login_required
def dns_spoofing_apply():
    """
    Apply DNS spoofing configuration.
    
    Returns:
        JSON with success/error
    """
    try:
        from core.dns_spoofing import apply_dns_spoofing
        
        success, message = apply_dns_spoofing()
        
        if success:
            return jsonify({'success': True, 'message': message})
        else:
            return jsonify({'success': False, 'error': message})
            
    except Exception as e:
        logger.error(f"dns_spoofing_apply error: {e}")
        return jsonify({'success': False, 'error': str(e)})


@bp.route('/dns-spoofing/disable', methods=['POST'])
@login_required
def dns_spoofing_disable():
    """
    Disable DNS spoofing.
    
    Returns:
        JSON with success/error
    """
    try:
        from core.dns_spoofing import disable_dns_spoofing
        
        success, message = disable_dns_spoofing()
        
        if success:
            return jsonify({'success': True, 'message': message})
        else:
            return jsonify({'success': False, 'error': message})
            
    except Exception as e:
        logger.error(f"dns_spoofing_disable error: {e}")
        return jsonify({'success': False, 'error': str(e)})


@bp.route('/dns-spoofing/domains')
@login_required
def dns_spoofing_get_domains():
    """
    Get AI domains list.
    
    Returns:
        JSON with domains list
    """
    try:
        from core.dns_spoofing import DNSSpoofing
        
        spoofing = DNSSpoofing()
        domains = spoofing.load_domains()
        
        return jsonify({'success': True, 'domains': domains})
        
    except Exception as e:
        logger.error(f"dns_spoofing_get_domains error: {e}")
        return jsonify({'success': False, 'error': str(e), 'domains': []})


@bp.route('/dns-spoofing/domains', methods=['POST'])
@login_required
def dns_spoofing_save_domains():
    """
    Save AI domains list.
    
    Returns:
        JSON with success/error
    """
    try:
        import json
        from pathlib import Path
        
        data = request.get_json()
        domains = data.get('domains', [])
        
        if not isinstance(domains, list):
            return jsonify({'success': False, 'error': 'Invalid domains format'})
        
        # Validate domains
        from core.dns_spoofing import DNSSpoofing
        
        spoofing = DNSSpoofing()
        valid_domains = [d for d in domains if spoofing._validate_domain(d)]
        
        # Write domains file
        domains_path = Path('/opt/etc/unblock/ai-domains.txt')
        domains_path.parent.mkdir(parents=True, exist_ok=True)
        domains_path.write_text('\n'.join(valid_domains), encoding='utf-8')
        
        logger.info(f"Saved {len(valid_domains)} AI domains")
        
        return jsonify({
            'success': True,
            'count': len(valid_domains),
            'message': f'Сохранено {len(valid_domains)} доменов'
        })
        
    except Exception as e:
        logger.error(f"dns_spoofing_save_domains error: {e}")
        return jsonify({'success': False, 'error': str(e)})


@bp.route('/dns-spoofing/preset')
@login_required
def dns_spoofing_preset():
    """
    Load preset AI domains list.
    
    Returns:
        JSON with preset domains
    """
    try:
        from pathlib import Path
        
        preset_path = Path('/opt/etc/web_ui/resources/lists/unblock-ai-domains.txt')
        
        if not preset_path.exists():
            return jsonify({'success': False, 'error': 'Preset not found'})
        
        content = preset_path.read_text(encoding='utf-8')
        domains = []
        
        for line in content.splitlines():
            line = line.strip()
            if line and not line.startswith('#'):
                domains.append(line)
        
        return jsonify({
            'success': True,
            'domains': domains,
            'count': len(domains)
        })
        
    except Exception as e:
        logger.error(f"dns_spoofing_preset error: {e}")
        return jsonify({'success': False, 'error': str(e), 'domains': []})


@bp.route('/dns-spoofing/test', methods=['POST'])
@login_required
def dns_spoofing_test():
    """
    Test DNS resolution for a domain.
    
    Returns:
        JSON with test results
    """
    try:
        data = request.get_json()
        domain = data.get('domain', '')
        
        if not domain:
            return jsonify({'success': False, 'error': 'Domain required'})
        
        from core.dns_spoofing import DNSSpoofing
        
        spoofing = DNSSpoofing()
        result = spoofing.test_domain(domain)
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"dns_spoofing_test error: {e}")
        return jsonify({
            'domain': domain,
            'resolved': False,
            'error': str(e)
        })


@bp.route('/dns-spoofing/logs')
@login_required
def dns_spoofing_logs():
    """
    Get DNS spoofing logs.
    
    Returns:
        JSON with logs
    """
    try:
        from pathlib import Path
        
        log_file = Path('/opt/var/log/unblock_dnsmasq.log')
        
        if not log_file.exists():
            return jsonify({'success': True, 'logs': 'Логов нет'})
        
        content = log_file.read_text(encoding='utf-8', errors='ignore')
        lines = content.splitlines()[-50:]  # Last 50 lines
        
        return jsonify({
            'success': True,
            'logs': '\n'.join(lines) if lines else 'Логов нет'
        })
        
    except Exception as e:
        logger.error(f"dns_spoofing_logs error: {e}")
        return jsonify({'success': False, 'error': str(e)})


# =============================================================================
# SHUTDOWN HOOKS
# =============================================================================

def shutdown_executor():
    """
    Gracefully shutdown ThreadPoolExecutor.

    Call this function during application shutdown to prevent resource leaks.
    """
    logger.info("Shutting down ThreadPoolExecutor...")
    executor.shutdown(wait=False)
    logger.info("ThreadPoolExecutor stopped")
