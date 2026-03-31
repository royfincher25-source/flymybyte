"""
FlyMyByte Web Interface - Keys Routes

Blueprint for managing proxy keys and service configuration.
"""
from flask import Blueprint, render_template, redirect, url_for, request, session, flash, current_app, jsonify
from functools import wraps
from concurrent.futures import ThreadPoolExecutor, TimeoutError
import os
import logging

logger = logging.getLogger(__name__)

# Thread pool for blocking operations
executor = ThreadPoolExecutor(max_workers=4)

# Импорты utility-функций
from core.services import (
    parse_vless_key, vless_config, write_json_config,
    parse_hysteria2_key, hysteria2_config, write_hysteria2_config,
    parse_shadowsocks_key, shadowsocks_config,
    parse_trojan_key, trojan_config,
    parse_tor_bridges, tor_config, write_tor_config,
    restart_service, check_service_status
)
from core.app_config import WebConfig


bp = Blueprint('keys', __name__, template_folder='templates', static_folder='static')


# =============================================================================
# DECORATORS
# =============================================================================

def login_required(f):
    """
    Decorator to require authentication for a route.
    
    Redirects to /login if user is not authenticated.
    """
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
