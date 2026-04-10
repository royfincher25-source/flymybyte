"""
FlyMyByte Web Interface - Route Handlers

Common helpers for routes to reduce duplication.
"""
import os
import logging
from typing import Dict, Any, Optional, List, Tuple
from flask import flash, redirect, url_for

from .utils import logger
from .app_config import WebConfig


def get_common_template_data() -> Dict[str, Any]:
    """
    Get common template data used across all routes.
    
    Returns:
        Dict with common template variables
    """
    config = WebConfig()
    return {
        'router_ip': config.router_ip,
        'web_port': config.web_port,
    }


def require_service_configured(mgr, service_name: str) -> Tuple[bool, str]:
    """
    Check if service has valid configuration.
    
    Args:
        mgr: VPN manager instance
        service_name: Human-readable service name
    
    Returns:
        Tuple of (is_configured: bool, message: str)
    """
    if not mgr.is_configured():
        return False, f"Configure {service_name} key first"
    
    if not mgr.is_valid():
        msg = mgr.get_last_error() or "Invalid configuration"
        return False, msg
    
    return True, "OK"


def handle_service_error(error: Exception, service_name: str) -> Tuple[str, str]:
    """
    Handle service operation errors consistently.
    
    Args:
        error: Exception that occurred
        service_name: Service name for logging
    
    Returns:
        Tuple of (message: str, category: str)
    """
    msg = str(error)
    logger.error(f"[HANDLER] {service_name} error: {msg}")
    return msg, "danger"


def handle_service_success(service_name: str, action: str) -> Tuple[str, str]:
    """
    Generate success message for service operations.
    
    Args:
        service_name: Service name
        action: Action performed
    
    Returns:
        Tuple of (message: str, category: str)
    """
    return f"✅ {service_name} {action}", "success"


def handle_service_warning(service_name: str, message: str) -> Tuple[str, str]:
    """
    Generate warning message for service operations.
    
    Args:
        service_name: Service name
        message: Warning message
    
    Returns:
        Tuple of (message: str, category: str)
    """
    return f"⚠️ {service_name}: {message}", "warning"


def redirect_with_message(message: str, category: str, endpoint: str, **kwargs) -> Any:
    """
    Redirect to endpoint with flash message.
    
    Args:
        message: Flash message text
        category: Flash category (success, danger, warning, info)
        endpoint: Target endpoint name
        **kwargs: Arguments for url_for
    
    Returns:
        Flask redirect response
    """
    flash(message, category)
    return redirect(url_for(endpoint, **kwargs))


def validate_file_path(filename: str, allowed_dirs: List[str]) -> Tuple[bool, str]:
    """
    Validate file path for security (prevent directory traversal).
    
    Args:
        filename: Requested filename
        allowed_dirs: List of allowed directories
    
    Returns:
        Tuple of (is_valid: bool, error_message: str)
    """
    if not filename or '..' in filename or '/' in filename or '\\' in filename:
        return False, "Invalid filename"
    
    for allowed_dir in allowed_dirs:
        real_dir = os.path.realpath(allowed_dir)
        if os.path.exists(real_dir):
            return True, "OK"
    
    return False, "Directory not found"


def get_safe_filename(filename: str) -> str:
    """
    Sanitize filename for safe use.
    
    Args:
        filename: Original filename
    
    Returns:
        Sanitized filename
    """
    # Remove potentially dangerous characters
    sanitized = ''.join(c for c in filename if c.isalnum() or c in '._- ')
    return sanitized[:255]


def format_service_status(is_running: bool, is_configured: bool) -> str:
    """
    Format service status string.
    
    Args:
        is_running: Whether service is running
        is_configured: Whether service has configuration
    
    Returns:
        Status emoji and text
    """
    if is_running and is_configured:
        return "✅ Активен"
    elif is_configured:
        return "⚠️ Неактивен"
    else:
        return "❌ Не настроен"


def parse_entries_from_input(raw_input: str, max_entries: int = 100) -> Tuple[List[str], List[str]]:
    """
    Parse domain/IP entries from raw input.
    
    Args:
        raw_input: Raw user input
        max_entries: Maximum number of entries to process
    
    Returns:
        Tuple of (valid_entries, invalid_entries)
    """
    valid = []
    invalid = []
    
    lines = raw_input.strip().split('\n')
    
    for line in lines[:max_entries]:
        entry = line.strip()
        
        if not entry or entry.startswith('#'):
            continue
        
        if len(entry) > 253:
            invalid.append(entry)
            continue
        
        valid.append(entry)
    
    return valid, invalid


def handle_bypass_operation_result(
    added_count: int,
    removed_count: int,
    error_msg: Optional[str] = None
) -> None:
    """
    Handle bypass operation result with flash messages.
    
    Args:
        added_count: Number of entries added
        removed_count: Number of entries removed
        error_msg: Error message if operation failed
    """
    if error_msg:
        flash(f"❌ Ошибка: {error_msg}", "danger")
    elif added_count > 0:
        flash(f"✅ Успешно добавлено: {added_count} шт. Изменения применены", "success")
    elif removed_count > 0:
        flash(f"✅ Успешно удалено: {removed_count} шт. Изменения применены", "success")
    else:
        flash("ℹ️ Нет изменений", "info")


def get_backup_list(backup_dir: str) -> List[Dict[str, Any]]:
    """
    Get list of available backups.
    
    Args:
        backup_dir: Path to backup directory
    
    Returns:
        List of backup info dicts
    """
    backups = []
    
    if not os.path.exists(backup_dir):
        return backups
    
    for item in os.listdir(backup_dir):
        item_path = os.path.join(backup_dir, item)
        
        if os.path.isdir(item_path):
            size = 0
            for root, dirs, files in os.walk(item_path):
                for f in files:
                    fp = os.path.join(root, f)
                    try:
                        size += os.path.getsize(fp)
                    except OSError:
                        pass
            
            backups.append({
                'name': item,
                'path': item_path,
                'size': size,
                'size_mb': round(size / (1024 * 1024), 2),
            })
    
    # Sort by name (newest first)
    backups.sort(key=lambda x: x['name'], reverse=True)
    return backups


def format_bytes(bytes_count: int) -> str:
    """
    Format bytes to human-readable string.
    
    Args:
        bytes_count: Number of bytes
    
    Returns:
        Formatted string (e.g., "1.5 MB")
    """
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_count < 1024.0:
            return f"{bytes_count:.1f} {unit}"
        bytes_count /= 1024.0
    return f"{bytes_count:.1f} TB"