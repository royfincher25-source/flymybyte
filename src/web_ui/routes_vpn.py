"""
FlyMyByte Web Interface - VPN Routes

Blueprint for VPN key management: /keys/*
"""
import logging
import os
import subprocess
from functools import wraps
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from flask import Blueprint, render_template, redirect, url_for, request, session, flash, jsonify

logger = logging.getLogger(__name__)


# =============================================================================
# INLINED DECORATORS
# =============================================================================

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('authenticated'):
            is_ajax = (
                request.headers.get('X-Requested-With') == 'XMLHttpRequest'
                or 'application/json' in request.headers.get('Accept', '')
            )
            if is_ajax or request.is_json:
                return jsonify({'success': False, 'error': 'Authentication required'}), 401
            return redirect(url_for('core.login'))
        return f(*args, **kwargs)
    return decorated_function


def validate_csrf_token() -> bool:
    token = session.get('csrf_token')
    form_token = request.form.get('csrf_token')
    if not token or not form_token or token != form_token:
        logger.warning("CSRF token validation failed")
        return False
    return True


def csrf_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if request.method == 'POST':
            if not validate_csrf_token():
                flash('Ошибка безопасности: неверный токен', 'danger')
                is_ajax = (
                    request.headers.get('X-Requested-With') == 'XMLHttpRequest'
                    or 'application/json' in request.headers.get('Accept', '')
                )
                if is_ajax or request.is_json:
                    return jsonify({'success': False, 'error': 'CSRF token validation failed'}), 400
                return redirect(url_for('core.index'))
        return f(*args, **kwargs)
    return decorated_function


from core.constants import CONFIG_PATHS, INIT_SCRIPTS, SERVICES
from core.services import (
    parse_vless_key, vless_config, write_json_config,
    parse_hysteria2_key, hysteria2_config, write_hysteria2_config,
    parse_shadowsocks_key, shadowsocks_config,
    parse_trojan_key, trojan_config,
    parse_tor_bridges, tor_config, write_tor_config,
    restart_service, check_service_status,
)


bp = Blueprint('vpn', __name__, template_folder='templates', static_folder='static')

executor = ThreadPoolExecutor(max_workers=4)


# =============================================================================
# ROUTES
# =============================================================================

@bp.route('/keys')
@login_required
def keys():
    services = {
        'vless': {'name': 'VLESS', 'config': CONFIG_PATHS['vless'], 'init': INIT_SCRIPTS['vless']},
        'hysteria2': {'name': 'Hysteria 2', 'config': CONFIG_PATHS['hysteria2'], 'init': INIT_SCRIPTS['hysteria2']},
        'shadowsocks': {'name': 'Shadowsocks', 'config': CONFIG_PATHS['shadowsocks'], 'init': INIT_SCRIPTS['shadowsocks']},
        'trojan': {'name': 'Trojan', 'config': CONFIG_PATHS['trojan'], 'init': INIT_SCRIPTS['trojan']},
        'tor': {'name': 'Tor', 'config': CONFIG_PATHS['tor'], 'init': INIT_SCRIPTS['tor']},
    }
    for svc_name, service in services.items():
        if not os.path.exists(service['init']):
            service['status'] = '❌ Скрипт не найден'
            service['config_exists'] = False
        else:
            service['config_exists'] = os.path.exists(service['config'])
            if not service['config_exists']:
                service['status'] = '❌ Не настроен'
            else:
                # FIX: Проверяем реальный статус сервиса через /proc
                # Перед проверкой очищаем кэш чтобы получить актуальный статус
                from core.utils import Cache
                Cache.delete(f'status:{service["init"]}')
                service['status'] = check_service_status(service['init'])
                logger.info(f"[KEYS] {svc_name} status: {service['status']}")
    return render_template('keys.html', services=services)


@bp.route('/keys/<service>', methods=['GET', 'POST'])
@login_required
@csrf_required
def key_config(service: str):
    services_config = {
        'vless': {'name': 'VLESS', 'config_path': CONFIG_PATHS['vless'], 'init_script': INIT_SCRIPTS['vless']},
        'hysteria2': {'name': 'Hysteria 2', 'config_path': CONFIG_PATHS['hysteria2'], 'init_script': INIT_SCRIPTS['hysteria2']},
        'shadowsocks': {'name': 'Shadowsocks', 'config_path': CONFIG_PATHS['shadowsocks'], 'init_script': INIT_SCRIPTS['shadowsocks']},
        'trojan': {'name': 'Trojan', 'config_path': CONFIG_PATHS['trojan'], 'init_script': INIT_SCRIPTS['trojan']},
        'tor': {'name': 'Tor', 'config_path': CONFIG_PATHS['tor'], 'init_script': INIT_SCRIPTS['tor']},
    }
    if service not in services_config:
        flash('Неверный сервис', 'danger')
        return redirect(url_for('vpn.keys'))
    svc = services_config[service]
    if request.method == 'POST':
        key = request.form.get('key', '').strip()
        if not key:
            flash('Введите ключ', 'warning')
            return redirect(url_for('vpn.key_config', service=service))
        try:
            if service == 'vless':
                parsed = parse_vless_key(key)
                if not parsed.get('server') or not parsed.get('port'):
                    raise ValueError('Не удалось распарсить ключ VLESS: отсутствуют server/port')
                cfg = vless_config(key)
                write_json_config(cfg, svc['config_path'])
            elif service == 'shadowsocks':
                parsed = parse_shadowsocks_key(key)
                if not parsed.get('server') or not parsed.get('port'):
                    raise ValueError('Не удалось распарсить ключ: отсутствуют server/port')
                cfg = shadowsocks_config(key)
                write_json_config(cfg, svc['config_path'])
            elif service == 'hysteria2':
                parsed = parse_hysteria2_key(key)
                if not parsed.get('server') or not parsed.get('port'):
                    raise ValueError('Не удалось распарсить ключ Hysteria 2: отсутствуют server/port')
                cfg = hysteria2_config(key)
                write_hysteria2_config(cfg, svc['config_path'])
            elif service == 'trojan':
                parsed = parse_trojan_key(key)
                if not parsed.get('server') or not parsed.get('port'):
                    raise ValueError('Не удалось распарсить ключ Trojan: отсутствуют server/port')
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
                flash(f'⏱️ Превышено время ожидания перезапуска {svc["name"]} (30с)', 'warning')
            return redirect(url_for('vpn.keys'))
        except ValueError as e:
            flash(f'❌ Ошибка в ключе: {str(e)}', 'danger')
        except Exception as e:
            flash(f'❌ Ошибка: {str(e)}', 'danger')
    return render_template('key_generic.html', service=service, service_name=svc['name'])


@bp.route('/keys/<service>/toggle', methods=['POST'])
@login_required
@csrf_required
def key_toggle(service: str):
    services_config = {
        'vless': {'name': 'VLESS', 'config_path': CONFIG_PATHS['vless'], 'init_script': INIT_SCRIPTS['vless'], 'ipset': 'unblockvless', 'port': 10810},
        'hysteria2': {'name': 'Hysteria 2', 'config_path': CONFIG_PATHS['hysteria2'], 'init_script': INIT_SCRIPTS['hysteria2'], 'ipset': 'unblockhysteria2', 'port': 0},
        'shadowsocks': {'name': 'Shadowsocks', 'config_path': CONFIG_PATHS['shadowsocks'], 'init_script': INIT_SCRIPTS['shadowsocks'], 'ipset': 'unblocksh', 'port': 1082},
        'trojan': {'name': 'Trojan', 'config_path': CONFIG_PATHS['trojan'], 'init_script': INIT_SCRIPTS['trojan'], 'ipset': 'unblocktroj', 'port': 10829},
        'tor': {'name': 'Tor', 'config_path': CONFIG_PATHS['tor'], 'init_script': INIT_SCRIPTS['tor'], 'ipset': 'unblocktor', 'port': 9141},
    }
    if service not in services_config:
        flash('Неверный сервис', 'danger')
        return redirect(url_for('vpn.keys'))
    svc = services_config[service]
    config_exists = os.path.exists(svc['config_path'])

    if config_exists:
        is_running = check_service_status(svc['init_script']) == '✅ Активен'
        logger.info(f"[TOGGLE] {service} initial status: is_running={is_running}")

        if is_running:
            try:
                import time
                import re
                from core.utils import Cache
                from core.iptables_manager import get_iptables_manager
                
                ipt = get_iptables_manager()
                
                # Шаг 1: Останавливаем через init скрипт
                stop_output = ""
                if os.path.exists(svc['init_script']):
                    result = subprocess.run(['sh', svc['init_script'], 'stop'], capture_output=True, text=True, timeout=15)
                    stop_output = result.stdout + result.stderr
                    logger.info(f"[TOGGLE] {service} stop script: rc={result.returncode}, output={stop_output[:300]}")
                
                # Шаг 2: Извлекаем PID из вывода скрипта
                pid = None
                pid_match = re.search(r'PID:\s*(\d+)', stop_output)
                if pid_match:
                    pid = pid_match.group(1)
                    logger.info(f"[TOGGLE] {service} PID from script: {pid}")
                
                # Шаг 3: Если PID не найден — ищем через pgrep
                if not pid:
                    proc_name_map = {
                        'shadowsocks': 'ss-redir',
                        'vless': 'xray',
                        'hysteria2': 'hysteria',
                        'trojan': 'trojan',
                        'tor': 'tor',
                    }
                    proc_name = proc_name_map.get(service, service)
                    pgrep_result = subprocess.run(['pgrep', '-f', proc_name], capture_output=True, text=True, timeout=3)
                    if pgrep_result.returncode == 0 and pgrep_result.stdout.strip():
                        pid = pgrep_result.stdout.strip().split('\n')[0]
                        logger.info(f"[TOGGLE] {service} PID from pgrep: {pid}")
                
                # Шаг 4: Ждём 2 секунды и проверяем остановился ли процесс
                time.sleep(2)
                Cache.delete(f'status:{svc["init_script"]}')
                
                # Шаг 5: Если процесс всё ещё жив — убиваем через kill -9
                still_alive = False
                if pid:
                    try:
                        kill_check = subprocess.run(['kill', '-0', pid], capture_output=True, text=True, timeout=3)
                        if kill_check.returncode == 0:
                            still_alive = True
                            logger.warning(f"[TOGGLE] {service} PID {pid} still alive, sending kill -9")
                            subprocess.run(['kill', '-9', pid], capture_output=True, text=True, timeout=5)
                            time.sleep(2)
                    except Exception as e:
                        logger.error(f"[TOGGLE] {service} kill check error: {e}")
                
                # Шаг 6: Очищаем iptables и ipset через IptablesManager
                subprocess.run(['ipset', 'flush', svc['ipset']], capture_output=True)
                ipt.remove_vpn_redirect(svc['ipset'], svc['port'])
                
                # Шаг 7: Финальная проверка статуса
                Cache.delete(f'status:{svc["init_script"]}')
                final_status = check_service_status(svc['init_script'])
                logger.info(f"[TOGGLE] {service} final status after stop: {final_status}")
                
                if final_status != '✅ Активен':
                    flash(f'✅ {svc["name"]} отключён (ключ сохранён)', 'success')
                else:
                    flash(f'⚠️ {svc["name"]} всё ещё активен после остановки', 'warning')
                    logger.warning(f"[TOGGLE] {service} still active after stop attempt!")
                    
            except Exception as e:
                flash(f'❌ Ошибка при отключении: {str(e)}', 'danger')
                logger.error(f"[TOGGLE] {service} stop error: {e}")
        else:
            # Сервис не запущен — включаем
            import time
            logger.info(f"[TOGGLE] {service} is not running, starting...")
            try:
                if os.path.exists(svc['init_script']):
                    result = subprocess.run(['sh', svc['init_script'], 'start'], capture_output=True, text=True, timeout=15)
                    logger.info(f"[TOGGLE] {service} start script: rc={result.returncode}, output={result.stdout[:200]}")
                    
                    time.sleep(2)
                
                from core.services import restart_service
                success, output = restart_service(svc['name'], svc['init_script'])
                
                # Очищаем кэш статуса после перезапуска
                from core.utils import Cache
                Cache.delete(f'status:{svc["init_script"]}')
                
                if success:
                    flash(f'✅ {svc["name"]} включён', 'success')
                    logger.info(f"[TOGGLE] {service} started successfully")
                else:
                    flash(f'⚠️ {svc["name"]} запущен, но ошибка: {output}', 'warning')
                    logger.warning(f"[TOGGLE] {service} restart_service returned: {output}")
                
                # Ждём чтобы процесс успел стартовать перед проверкой статуса
                time.sleep(1)
            except Exception as e:
                flash(f'❌ Ошибка при включении: {str(e)}', 'danger')
                logger.error(f"[TOGGLE] {service} start error: {e}")
    else:
        flash(f'⚠️ Для включения {svc["name"]} необходимо настроить ключ', 'warning')
        return redirect(url_for('vpn.key_config', service=service))
    return redirect(url_for('vpn.keys'))


@bp.route('/keys/<service>/disable', methods=['POST'])
@login_required
@csrf_required
def key_disable(service: str):
    services_config = {
        'vless': {'name': 'VLESS', 'config_path': CONFIG_PATHS['vless'], 'init_script': INIT_SCRIPTS['vless'], 'ipset': 'unblockvless', 'port': 10810},
        'hysteria2': {'name': 'Hysteria 2', 'config_path': CONFIG_PATHS['hysteria2'], 'init_script': INIT_SCRIPTS['hysteria2'], 'ipset': 'unblockhysteria2', 'port': 0},
        'shadowsocks': {'name': 'Shadowsocks', 'config_path': CONFIG_PATHS['shadowsocks'], 'init_script': INIT_SCRIPTS['shadowsocks'], 'ipset': 'unblocksh', 'port': 1082},
        'trojan': {'name': 'Trojan', 'config_path': CONFIG_PATHS['trojan'], 'init_script': INIT_SCRIPTS['trojan'], 'ipset': 'unblocktroj', 'port': 10829},
        'tor': {'name': 'Tor', 'config_path': CONFIG_PATHS['tor'], 'init_script': INIT_SCRIPTS['tor'], 'ipset': 'unblocktor', 'port': 9141},
    }
    if service not in services_config:
        flash('Неверный сервис', 'danger')
        return redirect(url_for('vpn.keys'))
    svc = services_config[service]
    try:
        import time
        import re
        from core.iptables_manager import get_iptables_manager
        
        ipt = get_iptables_manager()
        stop_output = ""
        stopped_via_script = False
        if os.path.exists(svc['init_script']):
            result = subprocess.run(['sh', svc['init_script'], 'stop'], capture_output=True, text=True, timeout=15)
            stop_output = result.stdout + result.stderr
            logger.info(f"[DISABLE] {service} stop: rc={result.returncode}, output={stop_output[:300]}")
            
            if 'stopped gracefully' in stop_output.lower() or 'stopped' in stop_output.lower():
                stopped_via_script = True
                logger.info(f"[DISABLE] {service} script reports: stopped")
        
        # Ждём пока процесс умрёт
        killed = False
        for attempt in range(5):
            time.sleep(1)
            from core.utils import Cache
            Cache.delete(f'status:{svc["init_script"]}')
            
            still_running = check_service_status(svc['init_script']) == '✅ Активен'
            if not still_running:
                killed = True
                logger.info(f"[DISABLE] {service} stopped after {attempt+1}s")
                break
        
        # Если не умер — kill -9
        if not killed:
            logger.warning(f"[DISABLE] {service} still alive, force killing...")
            try:
                pid = None
                if stopped_via_script:
                    pid_match = re.search(r'PID:\s*(\d+)', stop_output)
                    if pid_match:
                        pid = pid_match.group(1)
                
                if not pid:
                    proc_name_map = {
                        'shadowsocks': 'ss-redir',
                        'vless': 'xray',
                        'hysteria2': 'hysteria',
                        'trojan': 'trojan',
                        'tor': 'tor',
                    }
                    proc_name = proc_name_map.get(service, service)
                    pgrep_result = subprocess.run(['pgrep', '-f', proc_name], capture_output=True, text=True, timeout=3)
                    if pgrep_result.returncode == 0 and pgrep_result.stdout.strip():
                        pid = pgrep_result.stdout.strip().split('\n')[0]
                
                if pid:
                    logger.info(f"[DISABLE] {service} kill -9 PID {pid}")
                    subprocess.run(['kill', '-9', pid], capture_output=True, text=True, timeout=5)
                    time.sleep(2)
                    from core.utils import Cache
                    Cache.delete(f'status:{svc["init_script"]}')
                    still_running = check_service_status(svc['init_script']) == '✅ Активен'
                    if not still_running:
                        killed = True
            except Exception as e:
                logger.error(f"[DISABLE] {service} kill error: {e}")
        
        # Очищаем через IptablesManager
        subprocess.run(['ipset', 'flush', svc['ipset']], capture_output=True)
        ipt.remove_vpn_redirect(svc['ipset'], svc['port'])
        
        from core.utils import Cache
        Cache.delete(f'status:{svc["init_script"]}')
        
        if killed:
            flash(f'✅ {svc["name"]} отключён (ключ сохранён)', 'success')
        else:
            flash(f'⚠️ {svc["name"]} не удалось остановить (процесс всё ещё активен)', 'warning')
            logger.error(f"[DISABLE] {service} FAILED to stop!")
    except Exception as e:
        flash(f'❌ Ошибка при отключении: {str(e)}', 'danger')
        logger.error(f"[DISABLE] {service} stop error: {e}")
    return redirect(url_for('vpn.keys'))


def shutdown_executor():
    logger.info("Shutting down ThreadPoolExecutor...")
    executor.shutdown(wait=False)
    logger.info("ThreadPoolExecutor stopped")
