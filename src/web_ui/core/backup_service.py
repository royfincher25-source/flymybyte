"""
FlyMyByte Web Interface - Backup Service

Handles creation, listing, and deletion of system backups.
"""
import os
import re
import logging
import tarfile
from datetime import datetime
from typing import List, Dict, Tuple

from core.constants import (
    BACKUP_DIR,
    BACKUP_FILES,
)

logger = logging.getLogger(__name__)


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
                tar.add(f, arcname=os.path.basename(f))
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
