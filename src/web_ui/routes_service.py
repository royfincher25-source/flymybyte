"""
FlyMyByte Web Interface - Service Routes

Blueprint for service management, updates, backups, install/remove, DNS monitor, system stats, and logs.
"""
from flask import Blueprint, render_template, redirect, url_for, request, session, flash, current_app, jsonify
from functools import wraps
from concurrent.futures import ThreadPoolExecutor, TimeoutError
import os
import sys
import stat
import logging
import json
import subprocess
import requests

logger = logging.getLogger(__name__)

executor = ThreadPoolExecutor(max_workers=4)

MAX_ENTRIES_PER_REQUEST = 100
MAX_ENTRY_LENGTH = 253
MAX_TOTAL_INPUT_SIZE = 50 * 1024

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
    restart_service, check_service_status, create_backup, get_local_version, get_remote_version
)
from core.app_config import WebConfig


bp = Blueprint('main', __name__, template_folder='templates', static_folder='static')


# =============================================================================
# DECORATORS
# =============================================================================

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('authenticated'):
            is_ajax = (request.headers.get('X-Requested-With') == 'XMLHttpRequest' or
                      'application/json' in request.headers.get('Accept', ''))
            if is_ajax or request.is_json:
                return jsonify({'success': False, 'error': 'Authentication required'}), 401
            return redirect(url_for('main.login'))
        return f(*args, **kwargs)
    return decorated_function


def get_csrf_token():
    import secrets
    if 'csrf_token' not in session:
        session['csrf_token'] = secrets.token_hex(32)
    return session['csrf_token']


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
    return render_template('index.html')


@bp.route('/login', methods=['GET', 'POST'])
def login():
    if session.get('authenticated'):
        return redirect(url_for('main.index'))
    if request.method == 'GET':
        get_csrf_token()
    if request.method == 'POST':
        if not validate_csrf_token():
            flash('Ошибка безопасности: неверный токен', 'danger')
            logger.warning("CSRF token validation failed on login")
            return redirect(url_for('main.login'))
        password = request.form.get('password', '')
        web_password = current_app.config.get('WEB_PASSWORD', 'changeme')
        import secrets
        if password and web_password and secrets.compare_digest(password, web_password):
            session.permanent = True
            session['authenticated'] = True
            logger.info("User logged in successfully")
            return redirect(url_for('main.index'))
        else:
            logger.warning("Failed login attempt")
            flash('Неверный пароль', 'danger')
            return redirect(url_for('main.login'))
    return render_template('login.html')


@bp.route('/logout')
def logout():
    session.pop('authenticated', None)
    flash('Вы вышли из системы', 'info')
    return redirect(url_for('main.login'))


@bp.route('/status')
@login_required
def status():
    return render_template('base.html', title='Status')


@bp.route('/stats')
@login_required
def stats():
    config = WebConfig()
    services = {
        'vless': {'name': 'VLESS', 'init': '/opt/etc/init.d/S24xray', 'config': '/opt/etc/xray/vless.json'},
        'shadowsocks': {'name': 'Shadowsocks', 'init': '/opt/etc/init.d/S22shadowsocks', 'config': '/opt/etc/shadowsocks.json'},
        'trojan': {'name': 'Trojan', 'init': '/opt/etc/init.d/S22trojan', 'config': '/opt/etc/trojan.json'},
        'tor': {'name': 'Tor', 'init': '/opt/etc/init.d/S35tor', 'config': '/opt/etc/tor/torrc'},
    }
    for svc in services.values():
        svc['status'] = check_service_status(svc['init'])
        svc['config_exists'] = os.path.exists(svc['config'])
    unblock_dir = config.unblock_dir
    bypass_lists = []
    total_domains = 0
    if os.path.exists(unblock_dir):
        for filename in os.listdir(unblock_dir):
            if filename.endswith('.txt'):
                try:
                    data = load_bypass_list(filename, unblock_dir)
                    lines = data.get('entries', [])
                    count = len(lines)
                    total_domains += count
                    bypass_lists.append({'name': filename, 'count': count, 'path': os.path.join(unblock_dir, filename)})
                except Exception as e:
                    logger.error(f"stats Exception reading {filename}: {e}")
    active_services = sum(1 for s in services.values() if s['status'] == '✅ Активен')
    config_files = sum(1 for s in services.values() if s['config_exists'])
    stats_data = {
        'total_services': len(services), 'active_services': active_services,
        'config_files': config_files, 'total_bypass_lists': len(bypass_lists),
        'total_domains': total_domains, 'services': services, 'bypass_lists': bypass_lists,
    }
    return render_template('stats.html', stats=stats_data)


@bp.route('/service')
@login_required
def service():
    dns_override_enabled = False
    try:
        which_result = subprocess.run(['which', 'ndmc'], capture_output=True, text=True)
        if which_result.returncode == 0:
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
                        if 'dns-override' in output or 'dns override' in output:
                            dns_override_enabled = True
                            break
                        if 'enabled' in output and 'disabled' not in output:
                            dns_override_enabled = True
                            break
                except (subprocess.TimeoutExpired, Exception):
                    continue
    except Exception as e:
        logger.error(f"Error checking DNS Override status: {e}")
    return render_template('service.html', dns_override_enabled=dns_override_enabled)


@bp.route('/service/restart-unblock', methods=['POST'])
@login_required
@csrf_required
def service_restart_unblock():
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
                result = subprocess.run(['sh', init_script, 'restart'], capture_output=True, text=True, timeout=60)
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
    import time
    enable = (action == 'on')
    try:
        result = subprocess.run(['which', 'ndmc'], capture_output=True, text=True)
        if result.returncode != 0:
            flash('⚠️ ndmc не найден. DNS Override недоступен.', 'warning')
            return redirect(url_for('main.service'))
        cmd = ['ndmc', '-c', 'opkg dns-override'] if enable else ['ndmc', '-c', 'no opkg dns-override']
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if result.returncode != 0:
            flash(f'❌ Ошибка: {result.stderr}', 'danger')
            logger.error(f"DNS Override error: {result.stderr}")
            return redirect(url_for('main.service'))
        time.sleep(2)
        subprocess.run(['ndmc', '-c', 'system', 'configuration', 'save'], timeout=10)
        flash('✅ DNS Override ' + ('включен' if enable else 'выключен') + '. Роутер будет перезагружен...', 'success')
        logger.info("DNS Override changed, rebooting...")
        subprocess.Popen(['ndmc', '-c', 'system', 'reboot'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        flash(f'❌ Ошибка: {str(e)}', 'danger')
        logger.error(f"service_dns_override Exception: {e}")
    return redirect(url_for('main.service'))


def get_backup_list():
    import re
    backup_dir = '/opt/root/backup'
    backups = []
    if os.path.exists(backup_dir):
        for item in sorted(os.listdir(backup_dir), reverse=True):
            if (item.startswith('backup_') or item.startswith('update_backup_')) and item.endswith('.tar.gz'):
                item_path = os.path.join(backup_dir, item)
                try:
                    size = os.path.getsize(item_path)
                    match = re.match(r'(backup|update_backup)_(\d{8})_(\d{6})\.tar\.gz', item)
                    if match:
                        date_str = match.group(2)
                        time_str = match.group(3)
                    else:
                        date_str = item
                        time_str = ''
                    backups.append({
                        'name': item, 'path': item_path, 'size': size,
                        'date': f"{date_str[6:8]}.{date_str[4:6]}.{date_str[0:4]}",
                        'time': f"{time_str[0:2]}:{time_str[2:4]}" if time_str else '',
                    })
                except Exception as e:
                    logger.error(f"Error processing backup {item}: {e}")
    return backups


@bp.route('/service/backup', methods=['GET', 'POST'])
@login_required
def service_backup():
    backups = get_backup_list()
    if request.method == 'POST':
        if not validate_csrf_token():
            flash('Ошибка безопасности: неверный токен', 'danger')
            return redirect(url_for('main.service_backup'))
        action = request.form.get('action')
        if action == 'create':
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
                try:
                    os.remove(backup_path)
                    flash(f'✅ Бэкап {backup_name} удалён', 'success')
                except Exception as e:
                    flash(f'❌ Ошибка удаления: {e}', 'danger')
            else:
                flash(f'❌ Бэкап не найден', 'danger')
            return redirect(url_for('main.service_backup'))
    return render_template('backup.html', backups=backups)


@bp.route('/service/updates')
@login_required
def service_updates():
    local_version = get_local_version()
    remote_version = get_remote_version()
    need_update = True
    if local_version != 'N/A' and remote_version != 'N/A':
        try:
            if tuple(map(int, local_version.split('.'))) >= tuple(map(int, remote_version.split('.'))):
                need_update = False
        except ValueError:
            logger.warning(f"version parse error - local={local_version}, remote={remote_version}")
    return render_template('updates.html', local_version=local_version, remote_version=remote_version, need_update=need_update)


@bp.route('/service/updates/run', methods=['POST'])
@login_required
@csrf_required
def service_updates_run():
    from datetime import datetime
    import shutil
    import tarfile
    from core.update_progress import UpdateProgress
    progress = UpdateProgress()
    try:
        if progress.is_running:
            return jsonify({'success': False, 'error': 'Update already in progress'})
        # Check available disk space before update
        try:
            statvfs = os.statvfs('/opt')
            free_mb = (statvfs.f_frsize * statvfs.f_bavail) / (1024 * 1024)
            if free_mb < 10:
                flash(f'❌ Недостаточно места: {free_mb:.1f} МБ свободно (нужно минимум 10 МБ)', 'danger')
                return jsonify({'success': False, 'error': f'Insufficient disk space: {free_mb:.1f} MB free'})
        except Exception as e:
            logger.warning(f"Could not check disk space: {e}")
        flash('⏳ Создание резервной копии...', 'info')
        backup_dir = '/opt/root/backup'
        os.makedirs(backup_dir, exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_file = f'{backup_dir}/update_backup_{timestamp}.tar.gz'
        files_to_backup = [
            '/opt/etc/web_ui', '/opt/etc/xray', '/opt/etc/tor', '/opt/etc/unblock',
            '/opt/etc/shadowsocks.json', '/opt/etc/trojan',
            '/opt/etc/unblock-ai.dnsmasq', '/opt/etc/unblock/ai-domains.txt',
        ]
        existing_files = [f for f in files_to_backup if os.path.exists(f)]
        if existing_files:
            with tarfile.open(backup_file, 'w:gz', compresslevel=1) as tar:
                for f in existing_files:
                    tar.add(f, arcname=os.path.basename(f))
            flash(f'💾 Бэкап сохранён: {backup_file}', 'info')
        flash('⏳ Загрузка обновлений...', 'info')
        github_repo = 'royfincher25-source/flymybyte'
        github_branch = 'master'
        files_to_update = {
            'VERSION': '/opt/etc/web_ui/VERSION',
            'web_ui/.env.example': '/opt/etc/web_ui/.env.example',
            'web_ui/__init__.py': '/opt/etc/web_ui/__init__.py',
            'web_ui/routes_service.py': '/opt/etc/web_ui/routes_service.py',
            'web_ui/routes_keys.py': '/opt/etc/web_ui/routes_keys.py',
            'web_ui/routes_bypass.py': '/opt/etc/web_ui/routes_bypass.py',
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
            'web_ui/core/list_catalog.py': '/opt/etc/web_ui/core/list_catalog.py',
            'web_ui/core/update_progress.py': '/opt/etc/web_ui/core/update_progress.py',
            'web_ui/core/dns_spoofing.py': '/opt/etc/web_ui/core/dns_spoofing.py',
            'web_ui/resources/scripts/S99unblock': '/opt/etc/init.d/S99unblock',
            'web_ui/resources/scripts/S99web_ui': '/opt/etc/init.d/S99web_ui',
            'web_ui/resources/scripts/100-redirect.sh': '/opt/etc/ndm/netfilter.d/100-redirect.sh',
            'web_ui/resources/scripts/100-unblock-vpn.sh': '/opt/etc/ndm/ifstatechanged.d/100-unblock-vpn.sh',
            'web_ui/resources/scripts/100-ipset.sh': '/opt/etc/ndm/fs.d/100-ipset.sh',
            'web_ui/resources/scripts/unblock_ipset.sh': '/opt/bin/unblock_ipset.sh',
            'web_ui/resources/scripts/unblock_dnsmasq.sh': '/opt/bin/unblock_dnsmasq.sh',
            'web_ui/resources/scripts/unblock_update.sh': '/opt/bin/unblock_update.sh',
            'web_ui/resources/config/dnsmasq.conf': '/opt/etc/dnsmasq.conf',
            'web_ui/resources/config/crontab': '/opt/etc/crontab',
            'web_ui/scripts/script.sh': '/opt/root/script.sh',
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
            'web_ui/static/style.css': '/opt/etc/web_ui/static/style.css',
            'web_ui/resources/lists/unblock-ai-domains.txt': '/opt/etc/web_ui/resources/lists/unblock-ai-domains.txt',
            'web_ui/resources/config/unblock-ai.dnsmasq.template': '/opt/etc/web_ui/resources/config/unblock-ai.dnsmasq.template',
            'web_ui/resources/scripts/unblock_dnsmasq.sh': '/opt/etc/web_ui/resources/scripts/unblock_dnsmasq.sh',
        }
        updated_count = 0
        error_count = 0
        total_files = len(files_to_update)
        progress.start_update(total_files=total_files)
        
        # Parallel file downloads using ThreadPoolExecutor (3 workers for KN-1212)
        download_results = {'success': [], 'errors': []}
        download_lock = threading.Lock()
        
        def download_file(source_path, dest_path, idx):
            if source_path == 'VERSION':
                url = f'https://raw.githubusercontent.com/{github_repo}/{github_branch}/VERSION'
            else:
                url = f'https://raw.githubusercontent.com/{github_repo}/{github_branch}/src/{source_path}'
            progress.update_progress(f'Загрузка {source_path}', file=source_path, progress=idx, total=total_files)
            try:
                response = requests.get(url, timeout=60)
                response.raise_for_status()
                os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                with open(dest_path, 'w', encoding='utf-8') as f:
                    f.write(response.text)
                filename = os.path.basename(dest_path)
                is_executable = filename.endswith('.sh') or filename in ['S99web_ui', 'S99unblock']
                os.chmod(dest_path, 0o755 if is_executable else 0o644)
                logger.info(f"Updated {dest_path}")
                with download_lock:
                    download_results['success'].append(source_path)
            except requests.exceptions.RequestException as e:
                logger.error(f'Error downloading {source_path}: {e}')
                with download_lock:
                    download_results['errors'].append(source_path)
            except OSError as e:
                logger.error(f'Error writing {dest_path}: {e}')
                with download_lock:
                    download_results['errors'].append(source_path)
        
        import threading
        with ThreadPoolExecutor(max_workers=3) as download_executor:
            futures = []
            for i, (source_path, dest_path) in enumerate(files_to_update.items(), 1):
                future = download_executor.submit(download_file, source_path, dest_path, i)
                futures.append(future)
            for future in futures:
                future.result()
        
        updated_count = len(download_results['success'])
        error_count = len(download_results['errors'])
        try:
            script_steps = 5
            total_steps = total_files + script_steps
            current_step = total_files
            progress.update_progress('Запуск unblock_update.sh', file='unblock_update.sh', progress=current_step, total=total_steps)
            if os.path.exists('/opt/bin/unblock_update.sh'):
                result = subprocess.run(['/opt/bin/unblock_update.sh'], timeout=120, capture_output=True, text=True)
                if result.returncode != 0:
                    logger.error(f"unblock_update.sh failed: {result.stderr}")
            current_step += 1
            progress.update_progress('Запуск unblock_dnsmasq.sh', file='unblock_dnsmasq.sh', progress=current_step, total=total_steps)
            if os.path.exists('/opt/bin/unblock_dnsmasq.sh'):
                result = subprocess.run(['/opt/bin/unblock_dnsmasq.sh'], timeout=120, capture_output=True, text=True)
                if result.returncode != 0:
                    logger.error(f"unblock_dnsmasq.sh failed: {result.stderr}")
            current_step += 1
            progress.update_progress('Генерация AI DNS config', file='resources/scripts/unblock_dnsmasq.sh', progress=current_step, total=total_steps)
            if os.path.exists('/opt/etc/web_ui/resources/scripts/unblock_dnsmasq.sh'):
                result = subprocess.run(['sh', '/opt/etc/web_ui/resources/scripts/unblock_dnsmasq.sh'], timeout=120, capture_output=True, text=True)
                if result.returncode != 0:
                    logger.error(f"resources/unblock_dnsmasq.sh failed: {result.stderr}")
            current_step += 1
            progress.update_progress('Перезапуск S99unblock', file='S99unblock', progress=current_step, total=total_steps)
            if os.path.exists('/opt/etc/init.d/S99unblock'):
                try:
                    result = subprocess.run(['/opt/etc/init.d/S99unblock', 'restart'], timeout=60, capture_output=True, text=True)
                    if result.returncode != 0:
                        logger.warning(f"S99unblock restart failed: {result.stderr}")
                except (subprocess.TimeoutExpired, Exception) as e:
                    logger.warning(f"S99unblock restart error: {e}")
            current_step += 1
            progress.update_progress('Перезапуск S56dnsmasq', file='S56dnsmasq', progress=current_step, total=total_steps)
            if os.path.exists('/opt/etc/init.d/S56dnsmasq'):
                try:
                    result = subprocess.run(['/opt/etc/init.d/S56dnsmasq', 'restart'], timeout=60, capture_output=True, text=True)
                    if result.returncode != 0:
                        logger.warning(f"S56dnsmasq restart failed: {result.stderr}")
                except (subprocess.TimeoutExpired, Exception) as e:
                    logger.warning(f"S56dnsmasq restart error: {e}")
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
            try:
                restart_script = '/tmp/restart_webui.sh'
                with open(restart_script, 'w') as f:
                    f.write('#!/bin/sh\nsleep 5\n/opt/etc/init.d/S99web_ui restart\nrm -f /tmp/restart_webui.sh\n')
                os.chmod(restart_script, stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH)
                subprocess.Popen([restart_script], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
                logger.info("S99web_ui restart scheduled")
            except Exception as e:
                logger.warning(f"Failed to schedule restart: {e}")
                try:
                    subprocess.Popen(['/opt/etc/init.d/S99web_ui', 'restart'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
                except Exception as e2:
                    logger.error(f"Fallback restart failed: {e2}")
            return jsonify({'success': True, 'message': f'✅ Обновление завершено! Обновлено файлов: {updated_count}', 'reload': True, 'reload_delay': 3000})
        else:
            progress.set_error(f'Обновлено: {updated_count}, ошибок: {error_count}')
            flash(f'⚠️ Обновлено: {updated_count}, ошибок: {error_count}', 'warning')
            return jsonify({'success': False, 'error': f'Обновлено: {updated_count}, ошибок: {error_count}', 'reload': False})
    except Exception as e:
        progress.set_error(str(e))
        flash(f'❌ Ошибка обновления: {str(e)}', 'danger')
        return jsonify({'success': False, 'error': str(e)})


@bp.route('/install', methods=['GET', 'POST'])
@login_required
@csrf_required
def service_install():
    if request.method == 'POST':
        script_path = '/opt/root/script.sh'
        local_script_path = os.path.join(os.path.dirname(__file__), 'scripts', 'script.sh')
        resources_dir = os.path.join(os.path.dirname(__file__), 'resources')
        try:
            flash('⏳ Копирование скрипта установки...', 'info')
            if not os.path.exists(local_script_path):
                flash('❌ Ошибка: локальный скрипт не найден', 'danger')
                return redirect(url_for('main.service_install'))
            with open(local_script_path, 'r', encoding='utf-8') as f:
                script_content = f.read()
            os.makedirs(os.path.dirname(script_path), exist_ok=True)
            with open(script_path, 'w', encoding='utf-8') as f:
                f.write(script_content)
            os.chmod(script_path, 0o755)
            flash('✅ Скрипт скопирован', 'success')
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
                except Exception as e:
                    flash(f'⚠️ Бэкап не создан: {e}', 'warning')
            if os.path.exists(resources_dir):
                flash('⏳ Копирование ресурсов...', 'info')
                resources_dest = '/opt/etc/web_ui/resources'
                os.makedirs(resources_dest, exist_ok=True)
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
            flash('⏳ Генерация конфигурации DNS-обхода AI...', 'info')
            try:
                result = subprocess.run(['sh', '/opt/etc/web_ui/resources/scripts/unblock_dnsmasq.sh'], capture_output=True, text=True, timeout=30)
                if result.returncode == 0:
                    flash('✅ DNS-обход AI сгенерирован', 'success')
                else:
                    flash(f'⚠️ DNS-обход AI: {result.stderr.strip()}', 'warning')
            except Exception as e:
                flash(f'⚠️ DNS-обход AI: {str(e)}', 'warning')
        except Exception as e:
            flash(f'❌ Ошибка копирования: {str(e)}', 'danger')
            return redirect(url_for('main.service_install'))
        try:
            flash('⏳ Установка началась...', 'info')
            process = subprocess.Popen([script_path, '-install'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
            for line in process.stdout:
                flash(f'⏳ {line.strip()}', 'info')
            process.wait(timeout=600)
            if process.returncode == 0:
                flash('✅ Установка flymybyte завершена', 'success')
                try:
                    result = subprocess.run(['sh', '-c', 'ipset list -n'], capture_output=True, text=True, timeout=10)
                    if 'unblocksh' in result.stdout:
                        flash('✅ ipset initialized', 'success')
                    for script in ['S99unblock', 'S99web_ui']:
                        if os.path.exists(f'/opt/etc/init.d/{script}'):
                            flash(f'✅ {script} installed', 'success')
                except Exception as e:
                    logger.error(f"Post-install verification error: {e}")
            else:
                flash('❌ Ошибка установки', 'danger')
        except subprocess.TimeoutExpired:
            flash('❌ Превышен таймаут (10 минут)', 'danger')
        except Exception as e:
            flash(f'❌ Ошибка: {str(e)}', 'danger')
    return render_template('install.html')


@bp.route('/remove', methods=['GET', 'POST'])
@login_required
@csrf_required
def service_remove():
    if request.method == 'POST':
        script_path = '/opt/root/script.sh'
        local_script_path = os.path.join(os.path.dirname(__file__), 'scripts', 'script.sh')
        if not os.path.exists(script_path):
            try:
                flash('⏳ Копирование скрипта...', 'info')
                if not os.path.exists(local_script_path):
                    flash('❌ Ошибка: локальный скрипт не найден', 'danger')
                    return redirect(url_for('main.service_remove'))
                with open(local_script_path, 'r', encoding='utf-8') as f:
                    script_content = f.read()
                os.makedirs(os.path.dirname(script_path), exist_ok=True)
                with open(script_path, 'w', encoding='utf-8') as f:
                    f.write(script_content)
                os.chmod(script_path, 0o755)
                flash('✅ Скрипт скопирован', 'success')
            except Exception as e:
                flash(f'❌ Ошибка копирования скрипта: {str(e)}', 'danger')
                return redirect(url_for('main.service_remove'))
        try:
            flash('⏳ Удаление началось...', 'info')
            process = subprocess.Popen([script_path, '-remove'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
            for line in process.stdout:
                flash(f'⏳ {line.strip()}', 'info')
            process.wait(timeout=300)
            if process.returncode == 0:
                flash('✅ Удаление завершено', 'success')
            else:
                flash('❌ Ошибка удаления', 'danger')
        except subprocess.TimeoutExpired:
            flash('❌ Превышен таймаут (5 минут)', 'danger')
        except Exception as e:
            flash(f'❌ Ошибка: {str(e)}', 'danger')
    return render_template('install.html')


# DNS Monitor
@bp.route('/service/dns-monitor')
@login_required
def dns_monitor_status():
    from core.dns_monitor import get_dns_monitor
    monitor = get_dns_monitor()
    status = monitor.get_status()
    return render_template('dns_monitor.html', status=status)


@bp.route('/service/dns-monitor/start', methods=['POST'])
@login_required
@csrf_required
def dns_monitor_start():
    from core.dns_monitor import get_dns_monitor
    monitor = get_dns_monitor()
    monitor.start()
    flash('✅ DNS monitor started', 'success')
    return redirect(url_for('main.dns_monitor_status'))


@bp.route('/service/dns-monitor/stop', methods=['POST'])
@login_required
@csrf_required
def dns_monitor_stop():
    from core.dns_monitor import get_dns_monitor
    monitor = get_dns_monitor()
    monitor.stop()
    flash('ℹ️ DNS monitor stopped', 'info')
    return redirect(url_for('main.dns_monitor_status'))


@bp.route('/service/dns-monitor/check', methods=['POST'])
@login_required
@csrf_required
def dns_monitor_check():
    from core.dns_monitor import get_dns_monitor, check_dns_server
    monitor = get_dns_monitor()
    if monitor._current_server:
        result = check_dns_server(monitor._current_server['host'], monitor._current_server['port'])
        if result['success']:
            flash(f"✅ DNS OK: {result['latency_ms']}ms", 'success')
        else:
            flash(f"❌ DNS failed: {result['error']}", 'danger')
    else:
        flash('⚠️ No DNS server selected', 'warning')
    return redirect(url_for('main.dns_monitor_status'))


# System Stats API
@bp.route('/api/system/stats')
@login_required
def system_stats():
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
    from core.update_progress import UpdateProgress
    progress = UpdateProgress()
    return jsonify(progress.get_status())


@bp.route('/api/system/memory-manager/<action>', methods=['POST'])
@login_required
def memory_manager_action(action):
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


# Logs
@bp.route('/logs')
@login_required
def view_logs():
    log_file = os.environ.get('LOG_FILE', '/opt/var/log/web_ui.log')
    lines = []
    error_lines = []
    try:
        if os.path.exists(log_file):
            with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                all_lines = f.readlines()
                lines = all_lines[-100:]
                error_lines = [l for l in all_lines if 'ERROR' in l or 'CRITICAL' in l][-20:]
    except Exception as e:
        logger.error(f"view_logs Exception: {e}")
        flash(f'❌ Ошибка чтения логов: {str(e)}', 'danger')
    return render_template('logs.html', log_lines=lines, error_lines=error_lines, log_file=log_file)


@bp.route('/logs/clear', methods=['POST'])
@login_required
@csrf_required
def clear_logs():
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


# DNS Spoofing
@bp.route('/dns-spoofing')
@login_required
def dns_spoofing():
    return render_template('dns_spoofing.html')


@bp.route('/dns-spoofing/status')
@login_required
def dns_spoofing_status():
    try:
        from core.dns_spoofing import get_dns_spoofing_status
        status = get_dns_spoofing_status()
        return jsonify(status)
    except Exception as e:
        logger.error(f"dns_spoofing_status error: {e}")
        return jsonify({'enabled': False, 'domain_count': 0, 'config_exists': False, 'dnsmasq_running': False, 'error': str(e)})


@bp.route('/dns-spoofing/apply', methods=['POST'])
@login_required
def dns_spoofing_apply():
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
    try:
        from core.dns_spoofing import DNSSpoofing
        spoofing = DNSSpoofing()
        domains = spoofing.load_domains()
        return jsonify({'success': True, 'domains': domains})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e), 'domains': []})


@bp.route('/dns-spoofing/domains', methods=['POST'])
@login_required
def dns_spoofing_save_domains():
    try:
        from pathlib import Path
        data = request.get_json()
        domains = data.get('domains', [])
        if not isinstance(domains, list):
            return jsonify({'success': False, 'error': 'Invalid domains format'})
        from core.dns_spoofing import DNSSpoofing
        spoofing = DNSSpoofing()
        valid_domains = [d for d in domains if spoofing._validate_domain(d)]
        domains_path = Path('/opt/etc/unblock/ai-domains.txt')
        domains_path.parent.mkdir(parents=True, exist_ok=True)
        domains_path.write_text('\n'.join(valid_domains), encoding='utf-8')
        logger.info(f"Saved {len(valid_domains)} AI domains")
        return jsonify({'success': True, 'count': len(valid_domains), 'message': f'Сохранено {len(valid_domains)} доменов'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@bp.route('/dns-spoofing/preset')
@login_required
def dns_spoofing_preset():
    try:
        from pathlib import Path
        preset_path = Path('/opt/etc/web_ui/resources/lists/unblock-ai-domains.txt')
        if not preset_path.exists():
            return jsonify({'success': False, 'error': 'Preset not found'})
        content = preset_path.read_text(encoding='utf-8')
        domains = [line.strip() for line in content.splitlines() if line.strip() and not line.startswith('#')]
        return jsonify({'success': True, 'domains': domains, 'count': len(domains)})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e), 'domains': []})


@bp.route('/dns-spoofing/test', methods=['POST'])
@login_required
def dns_spoofing_test():
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
        return jsonify({'domain': domain, 'resolved': False, 'error': str(e)})


@bp.route('/dns-spoofing/logs')
@login_required
def dns_spoofing_logs():
    try:
        from pathlib import Path
        log_file = Path('/opt/var/log/unblock_dnsmasq.log')
        if not log_file.exists():
            return jsonify({'success': True, 'logs': 'Логов нет'})
        content = log_file.read_text(encoding='utf-8', errors='ignore')
        lines = content.splitlines()[-50:]
        return jsonify({'success': True, 'logs': '\n'.join(lines) if lines else 'Логов нет'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


def shutdown_executor():
    logger.info("Shutting down ThreadPoolExecutor...")
    executor.shutdown(wait=False)
    logger.info("ThreadPoolExecutor stopped")
