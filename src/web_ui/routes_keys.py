"""
FlyMyByte Web Interface - Keys Routes

Blueprint for managing proxy keys and service configuration.
"""
from concurrent.futures import TimeoutError
from flask import Blueprint, render_template, redirect, url_for, request, session, flash, jsonify
import os
import logging

logger = logging.getLogger(__name__)

from core.decorators import login_required, get_csrf_token, validate_csrf_token, csrf_required
from core.constants import SERVICES
from core.services import (
    parse_vless_key, vless_config, write_json_config,
    parse_hysteria2_key, hysteria2_config, write_hysteria2_config,
    parse_shadowsocks_key, shadowsocks_config,
    parse_trojan_key, trojan_config,
    parse_tor_bridges, tor_config, write_tor_config,
    restart_service, check_service_status
)
from core.app_config import WebConfig
from routes_service import executor


bp = Blueprint('keys', __name__, template_folder='templates', static_folder='static')


@bp.route('/keys')
@login_required
def keys():
    """Render the keys and bridges page."""
    logger.info("Accessing /keys page")

    services = {
        name: {
            'name': info['name'],
            'config': info['config'],
            'init': info['init'],
            'status': '❓',
        }
        for name, info in SERVICES.items()
    }

    for service in services.values():
        try:
            if not os.path.exists(service['init']):
                logger.warning(f"Init script not found: {service['init']}")
                service['status'] = "❌ Скрипт не найден"
                service['config_exists'] = False
            else:
                service['config_exists'] = os.path.exists(service['config'])
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
    """Handle key configuration for a service."""
    logger.info(f"Accessing /keys/{service} page")

    if service not in SERVICES:
        logger.warning(f"Invalid service requested: {service}")
        flash('Неверный сервис', 'danger')
        return redirect(url_for('main.keys'))

    svc_info = SERVICES[service]
    svc = {
        'name': svc_info['name'],
        'config_path': svc_info['config'],
        'init_script': svc_info['init'],
    }
    logger.debug(f"Service config: {svc}")

    if request.method == 'POST':
        key = request.form.get('key', '').strip()
        logger.info(f"POST /keys/{service}: key received (length={len(key) if key else 0})")

        if not key:
            flash('Введите ключ', 'warning')
            return redirect(url_for('main.key_config', service=service))

        try:
            if service == 'vless':
                parsed = parse_vless_key(key)
                if not parsed.get('server') or not parsed.get('port'):
                    raise ValueError("Не удалось распарсить ключ VLESS: отсутствуют server/port")
                cfg = vless_config(key)
                write_json_config(cfg, svc['config_path'])
            elif service == 'shadowsocks':
                parsed = parse_shadowsocks_key(key)
                if not parsed.get('server') or not parsed.get('port'):
                    raise ValueError("Не удалось распарсить ключ: отсутствуют server/port")
                cfg = shadowsocks_config(key)
                write_json_config(cfg, svc['config_path'])
            elif service == 'hysteria2':
                parsed = parse_hysteria2_key(key)
                if not parsed.get('server') or not parsed.get('port'):
                    raise ValueError("Не удалось распарсить ключ Hysteria 2: отсутствуют server/port")
                cfg = hysteria2_config(key)
                write_hysteria2_config(cfg, svc['config_path'])
            elif service == 'trojan':
                parsed = parse_trojan_key(key)
                if not parsed.get('server') or not parsed.get('port'):
                    raise ValueError("Не удалось распарсить ключ Trojan: отсутствуют server/port")
                cfg = trojan_config(key)
                write_json_config(cfg, svc['config_path'])
            elif service == 'tor':
                cfg = tor_config(key)
                write_tor_config(cfg, svc['config_path'])

            try:
                future = executor.submit(restart_service, svc['name'], svc['init_script'])
                success, output = future.result(timeout=30)
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

    return render_template('key_generic.html', service=service, service_name=svc['name'])
