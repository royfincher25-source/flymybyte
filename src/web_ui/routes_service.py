"""
FlyMyByte Web Interface - Service Routes

Blueprint for service management, updates, backups, install/remove, DNS monitor, system stats, and logs.
"""
from flask import Blueprint, render_template, redirect, url_for, request, session, flash, current_app, jsonify
from concurrent.futures import ThreadPoolExecutor, TimeoutError
import json
import os
import re
import stat
import logging
import subprocess
import shutil
import tarfile
import threading
import requests
from datetime import datetime
from typing import List, Dict, Tuple

from werkzeug.utils import secure_filename
from markupsafe import escape

logger = logging.getLogger(__name__)

from core.decorators import login_required, get_csrf_token, validate_csrf_token, csrf_required
from core.constants import (
    MAX_ENTRIES_PER_REQUEST,
    MAX_ENTRY_LENGTH,
    MAX_TOTAL_INPUT_SIZE,
    GITHUB_REPO,
    GITHUB_BRANCH,
    INIT_SCRIPTS,
    CONFIG_PATHS,
    WEB_UI_DIR,
    BACKUP_DIR,
    BACKUP_FILES,
    TMP_RESTART_SCRIPT,
    SCRIPT_EXECUTION_TIMEOUT,
    FILE_DOWNLOAD_TIMEOUT,
    SERVICES,
    FILES_TO_UPDATE,
    SCRIPT_INSTALL,
    SCRIPT_UNBLOCK_UPDATE,
    SCRIPT_UNBLOCK_DNSMASQ,
    AI_DOMAINS_LIST,
    DNSMASQ_CONFIG,
    UNBLOCK_DIR,
    INIT_DIR,
    UPDATE_BACKUP_FILES,
)
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
    restart_service, check_service_status, get_local_version, get_remote_version
)
from core.app_config import WebConfig


# =============================================================================
# INLINED FUNCTIONS (from core/update_service.py)
# =============================================================================

def _update_arcname(path: str) -> str:
    """Convert absolute path to archive-relative path."""
    if path.startswith('/opt/'):
        return path[5:]
    if path.startswith('/opt'):
        return path[4:]
    return os.path.basename(path)


def check_disk_space(min_mb: float = 10) -> tuple:
    """Check available disk space on /opt."""
    try:
        statvfs = os.statvfs('/opt')
        free_mb = (statvfs.f_frsize * statvfs.f_bavail) / (1024 * 1024)
        return free_mb >= min_mb, free_mb
    except Exception as e:
        logger.warning(f"Could not check disk space: {e}")
        return True, 0


def create_update_backup() -> str:
    """Create backup before update. Returns backup file path."""
    os.makedirs(BACKUP_DIR, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_file = f'{BACKUP_DIR}/update_backup_{timestamp}.tar.gz'
    existing_files = [f for f in UPDATE_BACKUP_FILES if os.path.exists(f)]
    if existing_files:
        with tarfile.open(backup_file, 'w:gz', compresslevel=1) as tar:
            for f in existing_files:
                tar.add(f, arcname=_update_arcname(f))
    return backup_file


def _download_file(source_path: str, dest_path: str, progress, idx: int, total: int) -> bool:
    """Download a single file from GitHub."""
    if source_path == 'VERSION':
        url = f'https://raw.githubusercontent.com/{GITHUB_REPO}/{GITHUB_BRANCH}/VERSION'
    else:
        url = f'https://raw.githubusercontent.com/{GITHUB_REPO}/{GITHUB_BRANCH}/src/{source_path}'
    progress.update_progress(f'Загрузка {source_path}', file=source_path, progress=idx, total=total)
    try:
        response = requests.get(url, timeout=FILE_DOWNLOAD_TIMEOUT)
        if response.status_code == 404:
            logger.info(f"Skipping removed file: {source_path}")
            return True
        response.raise_for_status()
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        if source_path.endswith(('.woff2', '.woff', '.ttf', '.png', '.jpg', '.jpeg', '.gif', '.ico')):
            with open(dest_path, 'wb') as f:
                f.write(response.content)
        else:
            with open(dest_path, 'w', encoding='utf-8') as f:
                f.write(response.text)
        filename = os.path.basename(dest_path)
        is_executable = filename.endswith('.sh') or filename in ['S99web_ui', 'S99unblock']
        os.chmod(dest_path, 0o755 if is_executable else 0o644)
        logger.info(f"Updated {dest_path}")
        return True
    except (requests.exceptions.RequestException, OSError) as e:
        logger.error(f'Error with {source_path}: {e}')
        return False


def download_all_files(progress) -> tuple:
    """Download all update files in parallel. Returns (success_count, error_count)."""
    files_to_update = FILES_TO_UPDATE
    total_files = len(files_to_update)
    results = {'success': 0, 'errors': 0}
    lock = threading.Lock()

    def download_and_track(source_path, dest_path, idx):
        success = _download_file(source_path, dest_path, progress, idx, total_files)
        with lock:
            if success:
                results['success'] += 1
            else:
                results['errors'] += 1

    with ThreadPoolExecutor(max_workers=3) as executor:
        for i, (source_path, dest_path) in enumerate(files_to_update.items(), 1):
            executor.submit(download_and_track, source_path, dest_path, i)

    return results['success'], results['errors']


def run_update_scripts(progress, start_step: int) -> bool:
    """Run post-download update scripts. Returns True if all succeeded."""
    scripts = [
        ('Запуск unblock_update.sh', [SCRIPT_UNBLOCK_UPDATE], SCRIPT_EXECUTION_TIMEOUT),
        ('Запуск unblock_dnsmasq.sh', [SCRIPT_UNBLOCK_DNSMASQ], SCRIPT_EXECUTION_TIMEOUT),
        ('Генерация AI DNS config', ['sh', f'{WEB_UI_DIR}/resources/scripts/unblock_dnsmasq.sh'], SCRIPT_EXECUTION_TIMEOUT),
        ('Перезапуск S99unblock', [INIT_SCRIPTS['unblock'], 'restart'], 60),
        ('Перезапуск S56dnsmasq', [INIT_SCRIPTS['dnsmasq'], 'restart'], 60),
    ]

    for i, (msg, cmd, timeout) in enumerate(scripts):
        progress.update_progress(msg, file=os.path.basename(cmd[0]) if cmd else '', progress=start_step + i, total=start_step + len(scripts))
        if not os.path.exists(cmd[0]):
            continue
        try:
            result = subprocess.run(cmd, timeout=timeout, capture_output=True, text=True)
            if result.returncode != 0:
                logger.warning(f"{msg} failed: {result.stderr}")
        except (subprocess.TimeoutExpired, Exception) as e:
            logger.warning(f"{msg} error: {e}")
    return True


def schedule_webui_restart():
    """Schedule web UI restart after update."""
    try:
        with open(TMP_RESTART_SCRIPT, 'w') as f:
            f.write(f'#!/bin/sh\nsleep 5\n{INIT_SCRIPTS["web_ui"]} restart\nrm -f {TMP_RESTART_SCRIPT}\n')
        os.chmod(TMP_RESTART_SCRIPT, stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH)
        os.system(f'{TMP_RESTART_SCRIPT} &')
        logger.info("S99web_ui restart scheduled")
    except Exception as e:
        logger.warning(f"Failed to schedule restart: {e}")
        try:
            os.system(f'{INIT_SCRIPTS["web_ui"]} restart &')
        except Exception as e2:
            logger.error(f"Fallback restart failed: {e2}")


# =============================================================================
# INLINED FUNCTIONS (from core/backup_service.py)
# =============================================================================

def _backup_arcname(path: str) -> str:
    """Convert absolute path to archive-relative path."""
    if path.startswith('/opt/'):
        return path[5:]
    if path.startswith('/opt'):
        return path[4:]
    return os.path.basename(path)


def create_backup(backup_type: str = 'full') -> Tuple[bool, str]:
    """Create backup of all flymybyte files."""
    try:
        os.makedirs(BACKUP_DIR, exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_file = f'{BACKUP_DIR}/backup_{timestamp}.tar.gz'
        existing_files = [f for f in BACKUP_FILES if os.path.exists(f)]
        if not existing_files:
            return False, 'Нет файлов для бэкапа'
        with tarfile.open(backup_file, 'w:gz') as tar:
            for f in existing_files:
                tar.add(f, arcname=_backup_arcname(f))
        backup_size = os.path.getsize(backup_file)
        size_mb = backup_size / 1024 / 1024
        return True, f'Бэкап создан: {backup_file} ({size_mb:.1f} МБ, {len(existing_files)} объектов)'
    except Exception as e:
        logger.error(f'Backup error: {e}')
        return False, str(e)


def get_backup_list() -> List[Dict]:
    """List all backups sorted by date (newest first)."""
    backups = []
    if not os.path.exists(BACKUP_DIR):
        return backups
    for item in sorted(os.listdir(BACKUP_DIR), reverse=True):
        if (item.startswith('backup_') or item.startswith('update_backup_')) and item.endswith('.tar.gz'):
            item_path = os.path.join(BACKUP_DIR, item)
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
                    'name': item,
                    'path': item_path,
                    'size': size,
                    'date': f"{date_str[6:8]}.{date_str[4:6]}.{date_str[0:4]}",
                    'time': f"{time_str[0:2]}:{time_str[2:4]}" if time_str else '',
                })
            except Exception as e:
                logger.error(f"Error processing backup {item}: {e}")
    return backups


def delete_backup(backup_name: str) -> Tuple[bool, str]:
    """Delete a specific backup file."""
    backup_path = os.path.join(BACKUP_DIR, backup_name)
    if not backup_name or not os.path.exists(backup_path):
        return False, 'Бэкап не найден'
    try:
        os.remove(backup_path)
        return True, f'Бэкап {backup_name} удалён'
    except Exception as e:
        return False, f'Ошибка удаления: {e}'


bp = Blueprint('main', __name__, template_folder='templates', static_folder='static')

executor = ThreadPoolExecutor(max_workers=4)


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
        'vless': {'name': 'VLESS', 'init': INIT_SCRIPTS['vless'], 'config': CONFIG_PATHS['vless']},
        'hysteria2': {'name': 'Hysteria 2', 'init': INIT_SCRIPTS['hysteria2'], 'config': CONFIG_PATHS['hysteria2']},
        'shadowsocks': {'name': 'Shadowsocks', 'init': INIT_SCRIPTS['shadowsocks'], 'config': CONFIG_PATHS['shadowsocks']},
        'trojan': {'name': 'Trojan', 'init': INIT_SCRIPTS['trojan'], 'config': CONFIG_PATHS['trojan']},
        'tor': {'name': 'Tor', 'init': INIT_SCRIPTS['tor'], 'config': CONFIG_PATHS['tor']},
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
                    filepath = os.path.join(unblock_dir, filename)
                    entries = load_bypass_list(filepath)
                    count = len(entries)
                    total_domains += count
                    bypass_lists.append({'name': filename, 'count': count, 'path': filepath})
                except Exception as e:
                    logger.error(f"stats Exception reading {filename}: {e}")
    active_services = sum(1 for s in services.values() if s['status'] == '✅ Активен')
    config_files = sum(1 for s in services.values() if s['config_exists'])

    # DNS spoofing status
    try:
        from core.dns_spoofing import DNSSpoofing
        spoofing = DNSSpoofing()
        dns_status = spoofing.get_status()
    except Exception:
        dns_status = {'enabled': False, 'domain_count': 0}

    # DNS Override status
    dns_override_enabled = False
    try:
        result = subprocess.run(
            ['iptables', '-t', 'nat', '-L', 'PREROUTING', '-n', '-v'],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0 and 'dpt:53' in result.stdout and 'DNAT' in result.stdout:
            dns_override_enabled = True
    except Exception:
        pass

    stats_data = {
        'total_services': len(services),
        'active_services': active_services,
        'config_files': config_files,
        'total_bypass_lists': len(bypass_lists),
        'total_domains': total_domains,
        'services': services,
        'bypass_lists': bypass_lists,
        'dns_spoofing_enabled': dns_status.get('enabled', False),
        'dns_spoofing_domains': dns_status.get('domain_count', 0),
        'dns_override_enabled': dns_override_enabled,
    }
    return render_template('stats.html', stats=stats_data, config=config)


@bp.route('/service')
@login_required
def service():
    dns_override_enabled = False
    try:
        result = subprocess.run(
            ['iptables', '-t', 'nat', '-L', 'PREROUTING', '-n', '-v'],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            if 'dpt:53' in result.stdout and 'DNAT' in result.stdout:
                dns_override_enabled = True
    except Exception as e:
        logger.error(f"Error checking DNS Override status: {e}")
    return render_template('service.html', dns_override_enabled=dns_override_enabled)


@bp.route('/service/restart-unblock', methods=['POST'])
@login_required
@csrf_required
def service_restart_unblock():
    logger.info("[ROUTES] /service/restart-unblock")
    success, output = restart_service('Unblock', INIT_SCRIPTS['unblock'])
    if success:
        flash('✅ Unblock-сервис успешно перезапущен', 'success')
    else:
        flash(f'⚠️ Ошибка перезапуска: {output}', 'danger')
    return redirect(url_for('main.service'))


@bp.route('/service/restart-router', methods=['POST'])
@login_required
@csrf_required
def service_restart_router():
    logger.info("[ROUTES] /service/restart-router")
    try:
        subprocess.run(['ndmc', '-c', 'system', 'reboot'], timeout=30)
        flash('✅ Команда на перезагрузку отправлена', 'success')
    except Exception as e:
        flash(f'❌ Ошибка: {str(e)}', 'danger')
        logger.error(f"[ROUTES] service_reboot Exception: {e}")
    return redirect(url_for('main.service'))


@bp.route('/service/restart-all', methods=['POST'])
@login_required
@csrf_required
def service_restart_all():
    logger.info("[ROUTES] /service/restart-all")
    services = [
        (SERVICES['shadowsocks']['name'], SERVICES['shadowsocks']['init'], SERVICES['shadowsocks']['config']),
        (SERVICES['tor']['name'], SERVICES['tor']['init'], SERVICES['tor']['config']),
        (SERVICES['vless']['name'], SERVICES['vless']['init'], SERVICES['vless']['config']),
        (SERVICES['trojan']['name'], SERVICES['trojan']['init'], SERVICES['trojan']['config']),
    ]
    results = []
    for name, init_script, config_path in services:
        try:
            # Skip if not configured (no config file) or init script missing
            if not os.path.exists(config_path):
                results.append(f"⏭️ {name} (не настроен)")
                logger.info(f"[ROUTES] {name}: skipped, no config")
                continue
            if not os.path.exists(init_script):
                results.append(f"⚠️ {name} (скрипт не найден)")
                logger.warning(f"[ROUTES] {name}: init script not found at {init_script}")
                continue
            logger.info(f"[ROUTES] Restarting {name} via {init_script}")
            result = subprocess.run(['sh', init_script, 'restart'], capture_output=True, text=True, timeout=180)
            status = '✅' if result.returncode == 0 else '❌'
            results.append(f"{status} {name}")
            logger.info(f"[ROUTES] {name}: {'OK' if result.returncode == 0 else 'FAILED'} (code={result.returncode})")
        except Exception as e:
            results.append(f"❌ {name}: {str(e)}")
            logger.error(f"[ROUTES] service_restart_all Exception for {name}: {e}")
    flash('Перезапуск сервисов: ' + ', '.join(results), 'success')
    return redirect(url_for('main.service'))


@bp.route('/service/restart-webui', methods=['POST'])
@login_required
@csrf_required
def service_restart_webui():
    logger.info("[ROUTES] /service/restart-webui")
    try:
        schedule_webui_restart()
        flash('✅ Веб-интерфейс будет перезапущен через 5 секунд', 'success')
    except Exception as e:
        flash(f'❌ Ошибка: {str(e)}', 'danger')
        logger.error(f"[ROUTES] service_restart_webui Exception: {e}")
    return redirect(url_for('main.service'))


@bp.route('/service/restore-dns', methods=['POST'])
@login_required
@csrf_required
def service_restore_dns():
    """
    Restore internet when dnsmasq is broken.
    Removes DNS redirect rules and tries to restart dnsmasq.
    """
    logger.info("[ROUTES] /service/restore-dns - Starting DNS restoration")
    results = []
    # 1. Check if dnsmasq is running
    try:
        result = subprocess.run(['pgrep', 'dnsmasq'], capture_output=True, text=True)
        if result.returncode == 0:
            results.append('✅ dnsmasq работает')
            logger.info("[ROUTES] DNS restore: dnsmasq is running")
        else:
            results.append('⚠️ dnsmasq не запущен')
            logger.warning("[ROUTES] DNS restore: dnsmasq NOT running")
    except Exception:
        results.append('⚠️ Не удалось проверить dnsmasq')

    # 2. Remove DNS redirect rules (restore router DNS)
    try:
        for proto in ['udp', 'tcp']:
            # Remove DNAT rules (DNS Override)
            subprocess.run(
                ['iptables', '-t', 'nat', '-D', 'PREROUTING', '-p', proto, '--dport', '53', '-j', 'DNAT', '--to-destination', '192.168.1.1:5353'],
                capture_output=True, text=True, timeout=5
            )
            subprocess.run(
                ['iptables', '-t', 'nat', '-D', 'PREROUTING', '-p', proto, '--dport', '53', '-j', 'DNAT', '--to-destination', '192.168.1.1'],
                capture_output=True, text=True, timeout=5
            )
            # Remove REDIRECT rules (legacy)
            subprocess.run(
                ['iptables', '-D', 'PREROUTING', '-t', 'nat', '-p', proto, '--dport', '53', '-j', 'REDIRECT', '--to-ports', '5353'],
                capture_output=True, text=True, timeout=5
            )
        results.append('✅ Правила перенаправления DNS удалены')
        logger.info("[ROUTES] DNS restore: redirect rules removed")
    except Exception as e:
        results.append(f'⚠️ Ошибка удаления правил: {e}')
        logger.error(f"[ROUTES] DNS restore: failed to remove rules: {e}")

    # 3. Try to fix dnsmasq config and restart
    try:
        result = subprocess.run(['dnsmasq', '--test'], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            # Config OK, try restart
            for init_script in ['/opt/etc/init.d/S56dnsmasq', '/opt/etc/init.d/S99unblock']:
                if os.path.exists(init_script):
                    logger.info(f"[ROUTES] DNS restore: restarting via {init_script}")
                    subprocess.run(['sh', init_script, 'restart'], capture_output=True, text=True, timeout=15)
                    results.append('✅ dnsmasq перезапущен')
                    break
            else:
                results.append('⚠️ Скрипт запуска dnsmasq не найден')
                logger.error("[ROUTES] DNS restore: dnsmasq init script not found")
        else:
            results.append(f'⚠️ Ошибка в dnsmasq.conf: {result.stderr.strip()[:100]}')
            logger.error(f"[ROUTES] DNS restore: dnsmasq config invalid: {result.stderr.strip()[:100]}")
    except Exception as e:
        results.append(f'⚠️ Ошибка проверки dnsmasq: {e}')
        logger.error(f"[ROUTES] DNS restore: dnsmasq check error: {e}")

    logger.info(f"[ROUTES] DNS restore completed: {results}")
    flash('Восстановление DNS: ' + ', '.join(results), 'warning')
    return redirect(url_for('main.service'))


@bp.route('/service/dns-override/<action>', methods=['POST'])
@login_required
@csrf_required
def service_dns_override(action):
    import time
    enable = (action == 'on')
    logger.info(f"[ROUTES] /service/dns-override/{action} - {'enabling' if enable else 'disabling'}")
    try:
        local_ip = subprocess.run(
            ['sh', '-c', "ip -4 addr show br0 | awk '/inet /{print $2}' | cut -d/ -f1 | grep -E '^(192\\.168\\.|10\\.|172\\.(1[6-9]|2[0-9]|3[0-1])\\.)' | head -n1"],
            capture_output=True, text=True, timeout=5
        ).stdout.strip()
        if not local_ip:
            local_ip = '192.168.1.1'
        logger.info(f"[ROUTES] DNS Override: local_ip={local_ip}")

        if enable:
            logger.info("[ROUTES] DNS Override: enabling...")
            # Flush old DNS redirect rules
            logger.debug("[ROUTES] Flushing PREROUTING rules")
            subprocess.run(['iptables', '-t', 'nat', '-F', 'PREROUTING'], capture_output=True, text=True, timeout=5)
            # Start dnsmasq on port 5353
            logger.debug("[ROUTES] Restarting dnsmasq")
            subprocess.run(['/opt/etc/init.d/S56dnsmasq', 'restart'], capture_output=True, text=True, timeout=15)
            time.sleep(1)
            # Run unblock_dnsmasq to generate bypass rules
            logger.debug("[ROUTES] Running unblock_dnsmasq.sh")
            subprocess.run(['/opt/bin/unblock_dnsmasq.sh'], capture_output=True, text=True, timeout=30)
            # Re-add proxy redirect rules
            redirect_script = '/opt/etc/ndm/netfilter.d/100-redirect.sh'
            if os.path.exists(redirect_script):
                logger.debug(f"[ROUTES] Running {redirect_script}")
                subprocess.run(['sh', redirect_script], capture_output=True, text=True, timeout=15)
            else:
                logger.warning(f"[ROUTES] Redirect script not found: {redirect_script}")
            # Add DNAT rules for DNS to dnsmasq:5353
            for proto in ['udp', 'tcp']:
                logger.debug(f"[ROUTES] Adding DNAT rule for {proto}")
                subprocess.run(
                    ['iptables', '-t', 'nat', '-A', 'PREROUTING', '-p', proto, '--dport', '53',
                     '-j', 'DNAT', '--to-destination', f'{local_ip}:5353'],
                    capture_output=True, text=True, timeout=5
                )
            flash('✅ DNS Override включен', 'success')
            logger.info("[ROUTES] DNS Override enabled successfully")
        else:
            logger.info("[ROUTES] DNS Override: disabling...")
            # Remove all DNAT rules for port 53
            for proto in ['udp', 'tcp']:
                logger.debug(f"[ROUTES] Removing DNAT rules for {proto}")
                subprocess.run(
                    ['iptables', '-t', 'nat', '-D', 'PREROUTING', '-p', proto, '--dport', '53',
                     '-j', 'DNAT', '--to-destination', f'{local_ip}:5353'],
                    capture_output=True, text=True, timeout=5
                )
                subprocess.run(
                    ['iptables', '-t', 'nat', '-D', 'PREROUTING', '-p', proto, '--dport', '53',
                     '-j', 'DNAT', '--to-destination', local_ip],
                    capture_output=True, text=True, timeout=5
                )
            # Stop dnsmasq
            logger.debug("[ROUTES] Stopping dnsmasq")
            subprocess.run(['/opt/etc/init.d/S56dnsmasq', 'stop'], capture_output=True, text=True, timeout=10)
            flash('✅ DNS Override выключен', 'success')
            logger.info("[ROUTES] DNS Override disabled successfully")
    except Exception as e:
        flash(f'❌ Ошибка: {str(e)}', 'danger')
        logger.error(f"[ROUTES] DNS Override exception: {e}")
    return redirect(url_for('main.service'))


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
            success, message = delete_backup(backup_name)
            if success:
                flash(f'✅ {message}', 'success')
            else:
                flash(f'❌ {message}', 'danger')
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
    from core.update_progress import UpdateProgress
    progress = UpdateProgress()
    try:
        if progress.is_running:
            return jsonify({'success': False, 'error': 'Update already in progress'})

        ok, free_mb = check_disk_space()
        if not ok:
            flash(f'❌ Недостаточно места: {free_mb:.1f} МБ свободно (нужно минимум 10 МБ)', 'danger')
            return jsonify({'success': False, 'error': f'Insufficient disk space: {free_mb:.1f} MB free'})

        flash('⏳ Создание резервной копии...', 'info')
        backup_file = create_update_backup()
        if backup_file:
            flash(f'💾 Бэкап сохранён: {backup_file}', 'info')

        flash('⏳ Загрузка обновлений...', 'info')
        total_files = len(FILES_TO_UPDATE)
        progress.start_update(total_files=total_files)

        updated_count, error_count = download_all_files(progress)

        try:
            run_update_scripts(progress, total_files)
        except Exception as e:
            logger.warning(f"Failed to run update scripts: {e}")
            progress.set_error(f'Failed to run scripts: {e}')

        if error_count == 0:
            progress.complete()
            flash(f'✅ Обновление завершено! Обновлено файлов: {updated_count}', 'success')
            schedule_webui_restart()
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
        local_script_path = os.path.join(os.path.dirname(__file__), 'scripts', 'script.sh')
        resources_dir = os.path.join(os.path.dirname(__file__), 'resources')
        try:
            flash('⏳ Копирование скрипта установки...', 'info')
            if not os.path.exists(local_script_path):
                flash('❌ Ошибка: локальный скрипт не найден', 'danger')
                return redirect(url_for('main.service_install'))
            with open(local_script_path, 'r', encoding='utf-8') as f:
                script_content = f.read()
            os.makedirs(os.path.dirname(SCRIPT_INSTALL), exist_ok=True)
            with open(SCRIPT_INSTALL, 'w', encoding='utf-8') as f:
                f.write(script_content)
            os.chmod(SCRIPT_INSTALL, 0o755)
            flash('✅ Скрипт скопирован', 'success')
            import shutil
            from datetime import datetime
            backup_dir = f'{WEB_UI_DIR}/backup'
            backup_subdir = os.path.join(backup_dir, datetime.now().strftime('%Y%m%d_%H%M%S'))
            if os.path.exists(WEB_UI_DIR):
                try:
                    os.makedirs(backup_dir, exist_ok=True)
                    shutil.copytree(WEB_UI_DIR, backup_subdir)
                    flash(f'💾 Бэкап создан: {backup_subdir}', 'info')
                except Exception as e:
                    flash(f'⚠️ Бэкап не создан: {e}', 'warning')
            if os.path.exists(resources_dir):
                flash('⏳ Копирование ресурсов...', 'info')
                resources_dest = f'{WEB_UI_DIR}/resources'
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
                local_dnsmasq_script = f'{WEB_UI_DIR}/resources/scripts/unblock_dnsmasq.sh'
                result = subprocess.run(['sh', local_dnsmasq_script], capture_output=True, text=True, timeout=30)
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
            process = subprocess.Popen([SCRIPT_INSTALL, '-install'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
            for line in process.stdout:
                flash(f'⏳ {line.strip()}', 'info')
            process.wait(timeout=600)
            if process.returncode == 0:
                flash('✅ Установка flymybyte завершена', 'success')
                try:
                    result = subprocess.run(['sh', '-c', 'ipset list -n'], capture_output=True, text=True, timeout=10)
                    if 'unblocksh' in result.stdout:
                        flash('✅ ipset initialized', 'success')
                    for script_name in ['S99unblock', 'S99web_ui']:
                        if os.path.exists(f'{INIT_DIR}/{script_name}'):
                            flash(f'✅ {script_name} installed', 'success')
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
        if not os.path.exists(SCRIPT_INSTALL):
            local_script_path = os.path.join(os.path.dirname(__file__), 'scripts', 'script.sh')
            try:
                flash('⏳ Копирование скрипта...', 'info')
                if not os.path.exists(local_script_path):
                    flash('❌ Ошибка: локальный скрипт не найден', 'danger')
                    return redirect(url_for('main.service_remove'))
                with open(local_script_path, 'r', encoding='utf-8') as f:
                    script_content = f.read()
                os.makedirs(os.path.dirname(SCRIPT_INSTALL), exist_ok=True)
                with open(SCRIPT_INSTALL, 'w', encoding='utf-8') as f:
                    f.write(script_content)
                os.chmod(SCRIPT_INSTALL, 0o755)
                flash('✅ Скрипт скопирован', 'success')
            except Exception as e:
                flash(f'❌ Ошибка копирования скрипта: {str(e)}', 'danger')
                return redirect(url_for('main.service_remove'))
        try:
            flash('⏳ Удаление началось...', 'info')
            process = subprocess.Popen([SCRIPT_INSTALL, '-remove'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
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
        domains_path = Path(AI_DOMAINS_LIST)
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
        preset_path = Path(f'{WEB_UI_DIR}/resources/lists/unblock-ai-domains.txt')
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


# Keys & Bypass routes
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
    for service in services.values():
        if not os.path.exists(service['init']):
            service['status'] = '❌ Скрипт не найден'
            service['config_exists'] = False
        else:
            service['config_exists'] = os.path.exists(service['config'])
            service['status'] = '✅ Активен' if service['config_exists'] else '❌ Не настроен'
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
        return redirect(url_for('main.keys'))
    svc = services_config[service]
    if request.method == 'POST':
        key = request.form.get('key', '').strip()
        if not key:
            flash('Введите ключ', 'warning')
            return redirect(url_for('main.key_config', service=service))
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
            return redirect(url_for('main.keys'))
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
        return redirect(url_for('main.keys'))
    svc = services_config[service]
    config_exists = os.path.exists(svc['config_path'])

    if config_exists:
        # Check if service is currently running
        is_running = check_service_status(svc['init_script']) == '✅ Активен'

        if is_running:
            # Disable: stop service, flush ipset, remove iptables — keep config
            try:
                if os.path.exists(svc['init_script']):
                    subprocess.run(['sh', svc['init_script'], 'stop'], capture_output=True, timeout=15)
                subprocess.run(['ipset', 'flush', svc['ipset']], capture_output=True)
                for proto in ['tcp', 'udp']:
                    subprocess.run(['iptables', '-t', 'nat', '-D', 'PREROUTING', '-p', proto, '-m', 'set', '--match-set', svc['ipset'], 'dst', '-j', 'REDIRECT', '--to-port', str(svc['port'])], capture_output=True)
                flash(f'✅ {svc["name"]} отключён (ключ сохранён)', 'success')
            except Exception as e:
                flash(f'❌ Ошибка при отключении: {str(e)}', 'danger')
        else:
            # Enable: start service (config already exists)
            try:
                if os.path.exists(svc['init_script']):
                    subprocess.run(['sh', svc['init_script'], 'start'], capture_output=True, timeout=15)
                # Rebuild ipset and iptables rules
                from core.services import restart_service
                success, output = restart_service(svc['name'], svc['init_script'])
                if success:
                    flash(f'✅ {svc["name"]} включён', 'success')
                else:
                    flash(f'⚠️ {svc["name"]} запущен, но ошибка: {output}', 'warning')
            except Exception as e:
                flash(f'❌ Ошибка при включении: {str(e)}', 'danger')
    else:
        # No config: redirect to config page to enter key
        flash(f'⚠️ Для включения {svc["name"]} необходимо настроить ключ', 'warning')
        return redirect(url_for('main.key_config', service=service))
    return redirect(url_for('main.keys'))


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
        return redirect(url_for('main.keys'))
    svc = services_config[service]
    try:
        # Stop the service
        if os.path.exists(svc['init_script']):
            subprocess.run(['sh', svc['init_script'], 'stop'], capture_output=True, timeout=15)
        # Flush ipset
        subprocess.run(['ipset', 'flush', svc['ipset']], capture_output=True)
        # Remove iptables redirect rules for this ipset
        for proto in ['tcp', 'udp']:
            subprocess.run(['iptables', '-t', 'nat', '-D', 'PREROUTING', '-p', proto, '-m', 'set', '--match-set', svc['ipset'], 'dst', '-j', 'REDIRECT', '--to-port', str(svc['port'])], capture_output=True)
        flash(f'✅ {svc["name"]} отключён (ключ сохранён)', 'success')
    except Exception as e:
        flash(f'❌ Ошибка при отключении: {str(e)}', 'danger')
    return redirect(url_for('main.keys'))


@bp.route('/bypass')
@login_required
def bypass():
    config = WebConfig()
    unblock_dir = config.unblock_dir
    logger.info(f"[ROUTES] /bypass - unblock_dir={unblock_dir}")
    available_files = []
    if os.path.exists(unblock_dir):
        try:
            available_files = [f.replace('.txt', '') for f in os.listdir(unblock_dir) if f.endswith('.txt')]
            logger.info(f"[ROUTES] Found {len(available_files)} bypass files: {available_files}")
        except Exception as e:
            logger.error(f"[ROUTES] Error listing bypass files: {e}")
    else:
        logger.warning(f"[ROUTES] Unblock dir does not exist: {unblock_dir}")
    return render_template('bypass.html', available_files=available_files)


@bp.route('/bypass/view/<filename>')
@login_required
def view_bypass(filename: str):
    config = WebConfig()
    filename = secure_filename(filename)
    if not filename:
        flash('Неверное имя файла', 'danger')
        return redirect(url_for('main.bypass'))
    filepath = os.path.join(config.unblock_dir, f"{filename}.txt")
    entries = load_bypass_list(filepath)
    return render_template('bypass_view.html', filename=filename, entries=entries, filepath=filepath)


@bp.route('/bypass/<filename>/add', methods=['GET', 'POST'])
@login_required
@csrf_required
def add_to_bypass(filename: str):
    config = WebConfig()
    filename = secure_filename(filename)
    if not filename:
        flash('Неверное имя файла', 'danger')
        return redirect(url_for('main.bypass'))
    filepath = os.path.join(config.unblock_dir, f"{filename}.txt")
    logger.info(f"[ROUTES] /bypass/{filename}/add - filepath={filepath}")
    if request.method == 'POST':
        entries_text = request.form.get('entries', '')
        if len(entries_text) > MAX_TOTAL_INPUT_SIZE:
            flash(f'Превышен лимит размера ввода (макс. {MAX_TOTAL_INPUT_SIZE // 1024}KB)', 'danger')
            return redirect(url_for('main.bypass'))
        new_entries = [e.strip() for e in entries_text.split('\n') if e.strip()]
        logger.info(f"[ROUTES] Adding {len(new_entries)} entries to {filepath}")
        if len(new_entries) > MAX_ENTRIES_PER_REQUEST:
            flash(f'Превышено количество записей (макс. {MAX_ENTRIES_PER_REQUEST})', 'danger')
            return redirect(url_for('main.bypass'))
        for entry in new_entries:
            if len(entry) > MAX_ENTRY_LENGTH:
                flash(f'Запись слишком длинная (макс. {MAX_ENTRY_LENGTH} симв.): {escape(entry[:50])}...', 'danger')
                return redirect(url_for('main.bypass'))
        current_list = load_bypass_list(filepath)
        added_count = 0
        invalid_entries = []
        ip_entries = []
        domain_entries = []
        for entry in new_entries:
            if entry not in current_list:
                if validate_bypass_entry(entry):
                    current_list.append(entry)
                    added_count += 1
                    if is_ip_address(entry):
                        ip_entries.append(entry)
                    else:
                        domain_entries.append(entry)
                else:
                    invalid_entries.append(entry)
        save_bypass_list(filepath, current_list)
        logger.info(f"[ROUTES] Saved {added_count} new entries (IPs: {len(ip_entries)}, domains: {len(domain_entries)}, invalid: {len(invalid_entries)})")
        if added_count > 0:
            if ip_entries and not domain_entries:
                logger.info(f"[ROUTES] Adding {len(ip_entries)} IPs directly to ipset")
                success, msg = bulk_add_to_ipset('unblock', ip_entries)
                if success:
                    flash(f'✅ Успешно добавлено: {added_count} шт. (IP в ipset: {len(ip_entries)})', 'success')
                else:
                    logger.warning(f"[ROUTES] ipset add failed, falling back to unblock_update: {msg}")
                    success, output = run_unblock_update()
                    if success:
                        flash(f'✅ Успешно добавлено: {added_count} шт. Изменения применены', 'success')
                    else:
                        flash(f'⚠️ Добавлено {added_count} записей, но ошибка при применении: {output}', 'warning')
            else:
                logger.info(f"[ROUTES] Running unblock_update for {added_count} mixed entries")
                success, output = run_unblock_update()
                if success:
                    flash(f'✅ Успешно добавлено: {added_count} шт. Изменения применены', 'success')
                else:
                    flash(f'⚠️ Добавлено {added_count} записей, но ошибка при применении: {output}', 'warning')
        elif invalid_entries:
            escaped_invalid = [escape(e) for e in invalid_entries[:5]]
            flash(f'⚠️ Все записи уже в списке или невалидны. Нераспознанные: {", ".join(escaped_invalid)}', 'warning')
        else:
            flash('ℹ️ Все записи уже были в списке', 'info')
        return redirect(url_for('main.view_bypass', filename=filename))
    return render_template('bypass_add.html', filename=filename)


@bp.route('/bypass/<filename>/remove', methods=['GET', 'POST'])
@login_required
@csrf_required
def remove_from_bypass(filename: str):
    config = WebConfig()
    filename = secure_filename(filename)
    if not filename:
        flash('Неверное имя файла', 'danger')
        return redirect(url_for('main.bypass'))
    filepath = os.path.join(config.unblock_dir, f"{filename}.txt")
    logger.info(f"[ROUTES] /bypass/{filename}/remove - filepath={filepath}")
    if request.method == 'POST':
        entries_text = request.form.get('entries', '')
        if len(entries_text) > MAX_TOTAL_INPUT_SIZE:
            flash(f'Превышен лимит размера ввода (макс. {MAX_TOTAL_INPUT_SIZE // 1024}KB)', 'danger')
            return redirect(url_for('main.view_bypass', filename=filename))
        to_remove = [e.strip() for e in entries_text.split('\n') if e.strip()]
        current_list = load_bypass_list(filepath)
        original_count = len(current_list)
        current_list = [item for item in current_list if item not in to_remove]
        removed_count = original_count - len(current_list)
        logger.info(f"[ROUTES] Removing {removed_count} entries from {filepath} (was {original_count}, now {len(current_list)})")
        save_bypass_list(filepath, current_list)
        if removed_count > 0:
            success, output = run_unblock_update()
            if success:
                flash(f'✅ Успешно удалено: {removed_count} шт. Изменения применены', 'success')
            else:
                flash(f'⚠️ Удалено {removed_count} записей, но ошибка при применении: {output}', 'warning')
        else:
            flash('ℹ️ Ни одна запись не найдена в списке', 'info')
        return redirect(url_for('main.view_bypass', filename=filename))
    entries = load_bypass_list(filepath)
    return render_template('bypass_remove.html', filename=filename, entries=entries)


@bp.route('/bypass/<filename>/refresh', methods=['POST'])
@login_required
@csrf_required
def refresh_bypass_ipset(filename: str):
    config = WebConfig()
    filename = secure_filename(filename)
    if not filename:
        flash('Неверное имя файла', 'danger')
        return redirect(url_for('main.bypass'))
    filepath = os.path.join(config.unblock_dir, f"{filename}.txt")
    logger.info(f"[ROUTES] /bypass/{filename}/refresh - filepath={filepath}")
    if not os.path.exists(filepath):
        flash('Файл не найден', 'danger')
        return redirect(url_for('main.view_bypass', filename=filename))
    from core.ipset_manager import refresh_ipset_from_file
    success, msg = refresh_ipset_from_file(filepath, max_workers=10)
    if success:
        logger.info(f"[ROUTES] Refresh succeeded: {msg}")
        flash(f'✅ {msg}', 'success')
    else:
        logger.error(f"[ROUTES] Refresh failed: {msg}")
        flash(f'❌ Ошибка: {msg}', 'danger')
    return redirect(url_for('main.view_bypass', filename=filename))


@bp.route('/bypass/catalog')
@login_required
def bypass_catalog():
    from core.list_catalog import get_catalog
    catalog = get_catalog()
    return render_template('bypass_catalog.html', catalog=catalog)


@bp.route('/bypass/catalog/<name>', methods=['POST'])
@login_required
@csrf_required
def download_list(name: str):
    from core.list_catalog import download_list
    config = WebConfig()
    dest_dir = config.unblock_dir
    success, message, count = download_list(name, dest_dir)
    if success:
        flash(f'✅ {message}', 'success')
    else:
        flash(f'❌ {message}', 'danger')
    return redirect(url_for('main.bypass_catalog'))


def shutdown_executor():
    logger.info("Shutting down ThreadPoolExecutor...")
    executor.shutdown(wait=False)
    logger.info("ThreadPoolExecutor stopped")
