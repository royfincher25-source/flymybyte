"""
FlyMyByte Web Interface - Update Routes

Blueprint for updates, install, remove, and update progress:
/service/updates*, /install/*, /remove, /api/update/progress
"""
import logging
import os
import shutil
import subprocess
import json
import requests
from concurrent.futures import ThreadPoolExecutor
from flask import Blueprint, render_template, redirect, url_for, request, session, flash, jsonify
from core.decorators import login_required, validate_csrf_token, csrf_required

logger = logging.getLogger(__name__)


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


# Helper to build GitHub raw file URL (handles both old string and new dict format)
def _github_url(path: str) -> str:
    """Build GitHub raw URL from repo path."""
    if isinstance(GITHUB_REPO, dict):
        owner = GITHUB_REPO.get('owner', GITHUB_REPO.get('user', 'royfincher25-source'))
        repo = GITHUB_REPO.get('repo', 'flymybyte')
        branch = GITHUB_REPO.get('branch', 'master')
    else:
        # Fallback: GITHUB_REPO is a string like "owner/repo"
        parts = str(GITHUB_REPO).split('/')
        owner, repo = parts[0], parts[1] if len(parts) > 1 else 'flymybyte'
        branch = GITHUB_BRANCH if 'GITHUB_BRANCH' in globals() else 'master'
    return f'https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{path}'


def _download_file(source_path: str, dest_path: str, progress, idx: int, total: int, max_retries: int = 3) -> bool:
    import time
    if source_path == 'VERSION':
        url = _github_url('VERSION')
    else:
        url = _github_url(f'src/{source_path}')
    progress.update_progress(f'Загрузка {idx}/{total}: {source_path}', file=source_path, progress=idx, total=total)
    logger.info(f"[UPDATE] [{idx}/{total}] Downloading {source_path}")
    logger.info(f"[UPDATE] URL: {url}")
    logger.info(f"[UPDATE] Destination: {dest_path}")
    
    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            logger.info(f"[UPDATE] [{idx}/{total}] HTTP request (attempt {attempt})")
            response = requests.get(url, timeout=FILE_DOWNLOAD_TIMEOUT)
            logger.info(f"[UPDATE] [{idx}/{total}] HTTP {response.status_code} ({len(response.content)} bytes)")
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
            if source_path == 'VERSION':
                logger.info(f"[UPDATE] VERSION file updated to: {response.text.strip()}")
            return True
        except requests.exceptions.ConnectionError as e:
            last_error = e
            if 'Failed to resolve' in str(e) or 'NameResolutionError' in str(e):
                delay = 5 * attempt
                logger.warning(f"DNS error for {source_path} (attempt {attempt}/{max_retries}), retrying in {delay}s: {e}")
                time.sleep(delay)
            else:
                logger.error(f'Connection error with {source_path}: {e}')
                return False
        except (requests.exceptions.RequestException, OSError) as e:
            last_error = e
            if attempt < max_retries:
                delay = 3 * attempt
                logger.warning(f"Error with {source_path} (attempt {attempt}/{max_retries}), retrying in {delay}s: {e}")
                time.sleep(delay)
            else:
                logger.error(f'Error with {source_path}: {e}')
    
    logger.error(f'Failed to download {source_path} after {max_retries} attempts: {last_error}')
    return False


def _load_local_manifest() -> dict:
    """Load local MANIFEST.json if exists."""
    manifest_path = os.path.join(WEB_UI_DIR, 'MANIFEST.json')
    try:
        with open(manifest_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _download_remote_manifest() -> dict:
    """Download MANIFEST.json from GitHub."""
    url = _github_url('MANIFEST.json')
    logger.info(f"[UPDATE] Fetching: {url}")
    try:
        resp = requests.get(url, timeout=15)
        logger.info(f"[UPDATE] HTTP {resp.status_code} from GitHub ({len(resp.content)} bytes)")
        if resp.status_code == 200:
            try:
                data = resp.json()
                logger.info(f"[UPDATE] Parsed manifest: {len(data.get('files', {}))} files")
                return data
            except Exception as e:
                logger.warning(f"[UPDATE] resp.json() failed: {e}")
                return {}
        else:
            logger.warning(f"[UPDATE] HTTP {resp.status_code} from GitHub")
    except Exception as e:
        logger.warning(f"[UPDATE] Failed to fetch MANIFEST.json: {e}")
    return {}


def _compute_local_md5(filepath: str) -> str:
    """Compute MD5 of a local file on the router."""
    import hashlib
    h = hashlib.md5()
    try:
        with open(filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                h.update(chunk)
        return h.hexdigest()
    except (FileNotFoundError, PermissionError):
        return None


def download_all_files(progress) -> tuple:
    """Incremental update: compare manifests and download only changed files."""
    from core.constants import FILES_TO_UPDATE

    logger.info("[UPDATE] Starting incremental update via MANIFEST.json")
    progress.update_progress('Загрузка MANIFEST.json...', file='', progress=1, total=100)

    # 1. Try to get remote manifest
    logger.info("[UPDATE] Downloading remote MANIFEST.json")
    remote = _download_remote_manifest()
    logger.info(f"[UPDATE] Remote manifest type: {type(remote).__name__}, keys: {list(remote.keys()) if isinstance(remote, dict) else 'N/A'}")
    if not remote or not isinstance(remote, dict):
        logger.warning("MANIFEST.json not available or invalid, falling back to full update")
        return _download_all_files_fallback(progress)

    # 2. Load local manifest
    logger.info("[UPDATE] Loading local MANIFEST.json")
    local = _load_local_manifest()
    logger.info(f"[UPDATE] Local manifest type: {type(local).__name__}")
    if not isinstance(local, dict):
        local = {}
    local_files = local.get('files', {})
    logger.info(f"[UPDATE] Local files type: {type(local_files).__name__}")
    if not isinstance(local_files, dict):
        local_files = {}
    remote_files = remote.get('files', {})
    logger.info(f"[UPDATE] Remote files type: {type(remote_files).__name__}, count: {len(remote_files)}")
    if not isinstance(remote_files, dict):
        logger.warning("Remote MANIFEST has invalid format, falling back to full update")
        return _download_all_files_fallback(progress)

    # 3. Determine what needs updating
    files_to_download = {}
    files_to_delete = []

    logger.info("[UPDATE] Comparing manifests...")
    for source_path, info in remote_files.items():
        if not isinstance(info, dict):
            logger.warning(f"[UPDATE] Skipping {source_path}: invalid info type {type(info).__name__}")
            continue
        local_info = local_files.get(source_path, {})
        if not isinstance(local_info, dict):
            local_info = {}
        local_md5 = local_info.get('md5', '')

        # Check if file exists locally and matches
        if local_md5 and local_md5 == info.get('md5', ''):
            # File exists and is up to date — skip
            continue

        files_to_download[source_path] = info['dest']

    # Find files that were removed from remote
    for source_path in list(local_files.keys()):
        if source_path not in remote_files:
            info = local_files[source_path]
            if isinstance(info, dict):
                files_to_delete.append(info.get('dest', ''))

    total = len(files_to_download) + len(files_to_delete)
    
    # CRITICAL: Always check if local VERSION matches remote
    # Local MANIFEST.json might have been copied with old code, making hashes match
    # but actual files on disk could be outdated
    try:
        local_version_file = os.path.join(WEB_UI_DIR, 'VERSION')
        if os.path.exists(local_version_file):
            with open(local_version_file, 'r') as f:
                local_ver = f.read().strip()
            # Get remote version from manifest
            remote_ver_url = _github_url('VERSION')
            resp = requests.get(remote_ver_url, timeout=10)
            if resp.status_code == 200:
                remote_ver = resp.text.strip()
                logger.info(f"[UPDATE] Local version: {local_ver}, Remote version: {remote_ver}")
                if local_ver != remote_ver:
                    logger.info(f"[UPDATE] Version mismatch — forcing full update")
                    return _download_all_files_fallback(progress)
    except Exception as e:
        logger.warning(f"[UPDATE] Failed to compare versions: {e}")
        # Safe fallback: download everything
        return _download_all_files_fallback(progress)

    logger.info(f"[UPDATE] Update plan: {total} files to download, {len(files_to_delete)} to delete")
    if total == 0:
        logger.info("All files are up to date")
        return 0, 0

    logger.info(f"Update plan: {len(files_to_download)} files to download, {len(files_to_delete)} to delete")

    # 4. Download changed files
    results = {'success': 0, 'errors': 0}
    step = 5
    for i, (source, dest) in enumerate(files_to_download.items(), 1):
        progress.update_progress(
            f'Скачивание {i}/{len(files_to_download)}',
            file=source,
            progress=step + i * 80 // max(len(files_to_download), 1),
            total=100
        )
        success = _download_file(source, dest, progress, i, len(files_to_download))
        if success:
            results['success'] += 1
        else:
            results['errors'] += 1

    # 5. Delete removed files
    for i, dest_path in enumerate(files_to_delete):
        progress.update_progress(
            f'Удаление {i+1}/{len(files_to_delete)}',
            file=dest_path,
            progress=85 + i * 10 // max(len(files_to_delete), 1),
            total=100
        )
        try:
            if os.path.exists(dest_path):
                os.remove(dest_path)
                logger.info(f"Deleted removed file: {dest_path}")
                results['success'] += 1
        except Exception as e:
            logger.error(f"Failed to delete {dest_path}: {e}")
            results['errors'] += 1

    # 6. Save new manifest locally
    if results['errors'] == 0:
        try:
            manifest_path = os.path.join(WEB_UI_DIR, 'MANIFEST.json')
            with open(manifest_path, 'w', encoding='utf-8') as f:
                json.dump(remote, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save local MANIFEST.json: {e}")

    return results['success'], results['errors']


def _download_all_files_fallback(progress) -> tuple:
    """Fallback: download ALL files (old behavior when manifest unavailable)."""
    logger.info("[UPDATE] FALLBACK: downloading ALL files via FILES_TO_UPDATE")
    files_to_update = FILES_TO_UPDATE
    total_files = len(files_to_update)
    logger.info(f"[UPDATE] Total files to download: {total_files}")
    results = {'success': 0, 'errors': 0}

    def download_and_track(source_path, dest_path, idx):
        logger.info(f"[UPDATE] Starting download task: {source_path} (#{idx})")
        success = _download_file(source_path, dest_path, progress, idx, total_files)
        if success:
            results['success'] += 1
            logger.info(f"[UPDATE] ✓ {source_path}")
        else:
            results['errors'] += 1
            logger.error(f"[UPDATE] ✗ {source_path}")

    with ThreadPoolExecutor(max_workers=1) as executor:
        futures = []
        for i, (source_path, dest_path) in enumerate(files_to_update.items(), 1):
            futures.append(executor.submit(download_and_track, source_path, dest_path, i))
        # Wait for all downloads to complete
        for f in futures:
            try:
                f.result(timeout=300)
            except Exception as e:
                logger.error(f"[UPDATE] Download task failed: {e}")
                results['errors'] += 1

    logger.info(f"[UPDATE] Fallback complete: {results['success']} success, {results['errors']} errors")
    return results['success'], results['errors']


def run_update_scripts(progress, start_step: int) -> bool:
    """Phase 1: Apply configs without restarting services (to avoid DNS disruption)."""
    logger.info("=" * 60)
    logger.info("[UPDATE] ===== RUN_UPDATE_SCRIPTS STARTED =====")
    logger.info("=" * 60)
    
    # Попробовать Python UnblockManager сначала
    try:
        logger.info("[UPDATE] Step 1: Trying Python UnblockManager...")
        from core.service_locator import ServiceLocator
        unblock_mgr = ServiceLocator.unblock()
        
        logger.info("[UPDATE] Getting initial status...")
        status_before = unblock_mgr.get_status()
        logger.info(f"[UPDATE] Status before: {status_before}")
        
        progress.update_progress("Обновление bypass (Python)", progress=start_step, total=start_step + 3)
        logger.info("[UPDATE] Calling unblock_mgr.update_all()...")
        
        ok, msg = unblock_mgr.update_all(timeout=SCRIPT_EXECUTION_TIMEOUT)
        
        logger.info(f"[UPDATE] update_all() result: ok={ok}, msg={msg}")
        
        status_after = unblock_mgr.get_status()
        logger.info(f"[UPDATE] Status after: {status_after}")
        
        if ok:
            logger.info("[UPDATE] Python unblock completed successfully!")
            progress.update_progress("✅ Python bypass обновлён", progress=start_step + 1, total=start_step + 3)
            logger.info("[UPDATE] ===== RUN_UPDATE_SCRIPTS COMPLETE (Python) =====")
            logger.info("=" * 60)
            return True
        else:
            logger.error(f"[UPDATE] Python unblock failed: {msg}")
            logger.error("[UPDATE] Update failed - no shell fallback (Phase 5)")
            progress.update_progress(f"❌ Ошибка: {msg}", progress=start_step + 1, total=start_step + 3)
            return False
    except Exception as e:
        logger.error(f"[UPDATE] Python unblock exception: {e}")
        import traceback
        logger.error(traceback.format_exc())
        progress.update_progress(f"❌ Исключение: {e}", progress=start_step + 1, total=start_step + 3)
        return False


def restart_services(progress, start_step: int) -> bool:
    """Phase 2: Restart services AFTER all downloads complete."""
    scripts = [
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
        # FIX: Use subprocess.Popen instead of os.system for better control
        subprocess.Popen(['sh', TMP_RESTART_SCRIPT], start_new_session=True)
        logger.info("S99web_ui restart scheduled")
    except Exception as e:
        logger.warning(f"Failed to schedule restart: {e}")
        try:
            # FIX: Use subprocess.Popen instead of os.system
            subprocess.Popen(['sh', INIT_SCRIPTS["web_ui"], 'restart'], start_new_session=True)
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
    from core.update_progress import get_progress_instance
    progress = get_progress_instance()
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

        if error_count > 0:
            progress.set_error(f'Обновлено: {updated_count}, ошибок: {error_count}')
            flash(f'⚠️ Обновлено: {updated_count}, ошибок: {error_count}', 'warning')
            return jsonify({'success': False, 'error': f'Обновлено: {updated_count}, ошибок: {error_count}', 'reload': False})

        # Phase 1: Apply configs (no restart)
        try:
            run_update_scripts(progress, total_files)
        except Exception as e:
            logger.warning(f"Failed to run update scripts: {e}")
            progress.set_error(f'Failed to run scripts: {e}')
            flash(f'❌ Ошибка применения настроек: {str(e)}', 'danger')
            return jsonify({'success': False, 'error': str(e)})

        # Phase 2: Restart services (after all downloads complete)
        restart_step = total_files + 3
        try:
            restart_services(progress, restart_step)
        except Exception as e:
            logger.warning(f"Failed to restart services: {e}")

        progress.complete()
        flash(f'✅ Обновление завершено! Обновлено файлов: {updated_count}', 'success')
        schedule_webui_restart()
        return jsonify({'success': True, 'message': f'✅ Обновление завершено! Обновлено файлов: {updated_count}', 'reload': True, 'reload_delay': 3000})
    except Exception as e:
        progress.set_error(str(e))
        flash(f'❌ Ошибка обновления: {str(e)}', 'danger')
        return jsonify({'success': False, 'error': str(e)})


@bp.route('/api/update/progress', methods=['GET'])
@login_required
def get_update_progress():
    from core.update_progress import get_progress_instance
    progress = get_progress_instance()
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
