"""
FlyMyByte Web Interface - Update Routes

Blueprint for updates, install, remove, and update progress:
/service/updates*, /install/*, /remove, /api/update/progress
"""
import secrets
import logging
import os
import shutil
import subprocess
import threading
from functools import wraps
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


from core.constants import (
    GITHUB_REPO,
    GITHUB_BRANCH,
    INIT_SCRIPTS,
    WEB_UI_DIR,
    BACKUP_DIR,
    TMP_RESTART_SCRIPT,
    SCRIPT_EXECUTION_TIMEOUT,
    FILE_DOWNLOAD_TIMEOUT,
    FILES_TO_UPDATE,
    SCRIPT_INSTALL,
    SCRIPT_UNBLOCK_UPDATE,
    SCRIPT_UNBLOCK_DNSMASQ,
    INIT_DIR,
    UPDATE_BACKUP_FILES,
)
from core.services import get_local_version, get_remote_version


# =============================================================================
# INLINED FUNCTIONS (from core/update_service.py)
# =============================================================================

def _update_arcname(path: str) -> str:
    if path.startswith('/opt/'):
        return path[5:]
    if path.startswith('/opt'):
        return path[4:]
    return os.path.basename(path)


def check_disk_space(min_mb: float = 10) -> tuple:
    try:
        statvfs = os.statvfs('/opt')
        free_mb = (statvfs.f_frsize * statvfs.f_bavail) / (1024 * 1024)
        return free_mb >= min_mb, free_mb
    except Exception as e:
        logger.warning(f"Could not check disk space: {e}")
        return True, 0


def create_update_backup() -> str:
    import tarfile
    from datetime import datetime
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
    import requests
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
    from concurrent.futures import ThreadPoolExecutor
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
    import stat
    try:
        with open(TMP_RESTART_SCRIPT, 'w') as f:
            f.write(f'#!/bin/sh\nsleep 5\n{INIT_SCRIPTS["web_ui"]} restart\nrm -f {TMP_RESTART_SCRIPT}\n')
        os.chmod(TMP_RESTART_SCRIPT, stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH)
        os.system(f'{TMP_RESTART_SCRIPT} &')
        logger.info("S99web_ui restart scheduled")
    except Exception as e:
        logger.warning(f"Failed to schedule restart: {e}")
        try:
            rc = os.system(f'{INIT_SCRIPTS["web_ui"]} restart &')
            if rc != 0:
                logger.error(f"Fallback restart failed with exit code: {rc}")
        except Exception as e2:
            logger.error(f"Fallback restart exception: {e2}")


bp = Blueprint('updates', __name__, template_folder='templates', static_folder='static')


# =============================================================================
# ROUTES
# =============================================================================

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


@bp.route('/api/update/progress', methods=['GET'])
@login_required
def get_update_progress():
    from core.update_progress import UpdateProgress
    progress = UpdateProgress()
    return jsonify(progress.get_status())


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
                return redirect(url_for('updates.service_install'))
            with open(local_script_path, 'r', encoding='utf-8') as f:
                script_content = f.read()
            os.makedirs(os.path.dirname(SCRIPT_INSTALL), exist_ok=True)
            with open(SCRIPT_INSTALL, 'w', encoding='utf-8') as f:
                f.write(script_content)
            os.chmod(SCRIPT_INSTALL, 0o755)
            flash('✅ Скрипт скопирован', 'success')
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
            return redirect(url_for('updates.service_install'))
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
                    return redirect(url_for('updates.service_remove'))
                with open(local_script_path, 'r', encoding='utf-8') as f:
                    script_content = f.read()
                os.makedirs(os.path.dirname(SCRIPT_INSTALL), exist_ok=True)
                with open(SCRIPT_INSTALL, 'w', encoding='utf-8') as f:
                    f.write(script_content)
                os.chmod(SCRIPT_INSTALL, 0o755)
                flash('✅ Скрипт скопирован', 'success')
            except Exception as e:
                flash(f'❌ Ошибка копирования скрипта: {str(e)}', 'danger')
                return redirect(url_for('updates.service_remove'))
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
