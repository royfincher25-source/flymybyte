"""
FlyMyByte Web Interface - Update Service

Handles application updates: backup, download, script execution.
"""
import os
import stat
import logging
import json
import subprocess
import shutil
import tarfile
import threading
import requests
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

from core.constants import (
    GITHUB_REPO,
    GITHUB_BRANCH,
    BACKUP_DIR,
    WEB_UI_DIR,
    INIT_SCRIPTS,
    SCRIPT_UNBLOCK_UPDATE,
    SCRIPT_UNBLOCK_DNSMASQ,
    SCRIPT_EXECUTION_TIMEOUT,
    FILE_DOWNLOAD_TIMEOUT,
    UPDATE_BACKUP_FILES,
    FILES_TO_UPDATE,
    TMP_RESTART_SCRIPT,
)
from core.update_progress import UpdateProgress

logger = logging.getLogger(__name__)


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
                tar.add(f, arcname=os.path.basename(f))
    return backup_file


def download_file(source_path: str, dest_path: str, progress, idx: int, total: int) -> bool:
    """Download a single file from GitHub."""
    if source_path == 'VERSION':
        url = f'https://raw.githubusercontent.com/{GITHUB_REPO}/{GITHUB_BRANCH}/VERSION'
    else:
        url = f'https://raw.githubusercontent.com/{GITHUB_REPO}/{GITHUB_BRANCH}/src/{source_path}'
    progress.update_progress(f'Загрузка {source_path}', file=source_path, progress=idx, total=total)
    try:
        response = requests.get(url, timeout=FILE_DOWNLOAD_TIMEOUT)
        response.raise_for_status()
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
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
        success = download_file(source_path, dest_path, progress, idx, total_files)
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
        subprocess.Popen([TMP_RESTART_SCRIPT], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        logger.info("S99web_ui restart scheduled")
    except Exception as e:
        logger.warning(f"Failed to schedule restart: {e}")
        try:
            subprocess.Popen([INIT_SCRIPTS['web_ui'], 'restart'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        except Exception as e2:
            logger.error(f"Fallback restart failed: {e2}")
