"""
FlyMyByte Web Interface - Bypass Routes

Blueprint for managing bypass lists, ipset, and catalog.
"""
from flask import Blueprint, render_template, redirect, url_for, request, session, flash, jsonify
from functools import wraps
from werkzeug.utils import secure_filename
from markupsafe import escape
import os
import logging

logger = logging.getLogger(__name__)

# Validation constants for embedded devices (128MB RAM)
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
from core.app_config import WebConfig


bp = Blueprint('bypass', __name__, template_folder='templates', static_folder='static')


# =============================================================================
# DECORATORS
# =============================================================================

def login_required(f):
    """Decorator to require authentication for a route."""
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
    """Generate or get CSRF token for the session."""
    import secrets
    if 'csrf_token' not in session:
        session['csrf_token'] = secrets.token_hex(32)
    return session['csrf_token']


def validate_csrf_token() -> bool:
    """Validate CSRF token from session and form."""
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

@bp.route('/bypass')
@login_required
def bypass():
    """Render the bypass lists page."""
    config = WebConfig()
    unblock_dir = config.unblock_dir
    available_files = []
    if os.path.exists(unblock_dir):
        try:
            available_files = [
                f.replace('.txt', '')
                for f in os.listdir(unblock_dir)
                if f.endswith('.txt')
            ]
        except Exception as e:
            logger.error(f"Error listing bypass files: {e}")
    return render_template('bypass.html', available_files=available_files)


@bp.route('/bypass/view/<filename>')
@login_required
def view_bypass(filename: str):
    """View contents of a bypass list file."""
    config = WebConfig()
    filename = secure_filename(filename)
    if not filename:
        flash('Неверное имя файла', 'danger')
        return redirect(url_for('main.bypass'))
    filepath = os.path.join(config.unblock_dir, f"{filename}.txt")
    entries = load_bypass_list(filepath)
    return render_template(
        'bypass_view.html',
        filename=filename,
        entries=entries,
        filepath=filepath
    )


@bp.route('/bypass/<filename>/add', methods=['GET', 'POST'])
@login_required
@csrf_required
def add_to_bypass(filename: str):
    """Add entries to a bypass list file with optimized processing."""
    config = WebConfig()
    filename = secure_filename(filename)
    if not filename:
        flash('Неверное имя файла', 'danger')
        return redirect(url_for('main.bypass'))
    filepath = os.path.join(config.unblock_dir, f"{filename}.txt")

    if request.method == 'POST':
        entries_text = request.form.get('entries', '')

        if len(entries_text) > MAX_TOTAL_INPUT_SIZE:
            flash(f'Превышен лимит размера ввода (макс. {MAX_TOTAL_INPUT_SIZE // 1024}KB)', 'danger')
            return redirect(url_for('main.bypass'))

        new_entries = [e.strip() for e in entries_text.split('\n') if e.strip()]

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

        if added_count > 0:
            if ip_entries and not domain_entries:
                success, msg = bulk_add_to_ipset('unblock', ip_entries)
                if success:
                    logger.info(f"Directly added {len(ip_entries)} IPs to ipset")
                    flash(f'✅ Успешно добавлено: {added_count} шт. (IP в ipset: {len(ip_entries)})', 'success')
                else:
                    logger.warning(f"Failed to add IPs directly: {msg}")
                    success, output = run_unblock_update()
                    if success:
                        flash(f'✅ Успешно добавлено: {added_count} шт. Изменения применены', 'success')
                    else:
                        flash(f'⚠️ Добавлено {added_count} записей, но ошибка при применении: {output}', 'warning')
            else:
                if added_count > 0:
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
    """Remove entries from a bypass list file."""
    config = WebConfig()
    filename = secure_filename(filename)
    if not filename:
        flash('Неверное имя файла', 'danger')
        return redirect(url_for('main.bypass'))
    filepath = os.path.join(config.unblock_dir, f"{filename}.txt")

    if request.method == 'POST':
        entries_text = request.form.get('entries', '')

        if len(entries_text) > MAX_TOTAL_INPUT_SIZE:
            flash(f'Превышен лимит размера ввода (макс. {MAX_TOTAL_INPUT_SIZE // 1024}KB)', 'danger')
            return redirect(url_for('main.bypass_view', filename=filename))

        to_remove = [e.strip() for e in entries_text.split('\n') if e.strip()]

        if len(to_remove) > MAX_ENTRIES_PER_REQUEST:
            flash(f'Превышено количество записей (макс. {MAX_ENTRIES_PER_REQUEST})', 'danger')
            return redirect(url_for('main.bypass_view', filename=filename))

        current_list = load_bypass_list(filepath)

        original_count = len(current_list)
        current_list = [item for item in current_list if item not in to_remove]
        removed_count = original_count - len(current_list)

        ip_entries = [e for e in to_remove if is_ip_address(e) and e in current_list]
        ipset_msg = ''
        if ip_entries:
            success, msg = bulk_remove_from_ipset('unblock', ip_entries)
            ipset_msg = f" IP из ipset: {len(ip_entries)}"
            logger.info(f"ipset: {msg}")

        save_bypass_list(filepath, current_list)

        if removed_count > 0:
            success, output = run_unblock_update()
            if success:
                flash(f'✅ Успешно удалено: {removed_count} шт.{ipset_msg}. Изменения применены', 'success')
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
    """Refresh ipset from bypass list (resolve domains)."""
    config = WebConfig()
    filename = secure_filename(filename)
    if not filename:
        flash('Неверное имя файла', 'danger')
        return redirect(url_for('main.bypass'))
    filepath = os.path.join(config.unblock_dir, f"{filename}.txt")

    if not os.path.exists(filepath):
        flash('Файл не найден', 'danger')
        return redirect(url_for('main.view_bypass', filename=filename))

    from core.ipset_manager import refresh_ipset_from_file
    success, msg = refresh_ipset_from_file(filepath, max_workers=10)

    if success:
        flash(f'✅ {msg}', 'success')
    else:
        flash(f'❌ Ошибка: {msg}', 'danger')

    return redirect(url_for('main.view_bypass', filename=filename))


@bp.route('/bypass/catalog')
@login_required
def bypass_catalog():
    """Show list catalog."""
    from core.list_catalog import get_catalog
    catalog = get_catalog()
    return render_template('bypass_catalog.html', catalog=catalog)


@bp.route('/bypass/catalog/<name>', methods=['POST'])
@login_required
@csrf_required
def download_list(name: str):
    """Download list from catalog."""
    from core.list_catalog import download_list
    config = WebConfig()
    dest_dir = config.unblock_dir
    success, message, count = download_list(name, dest_dir)
    if success:
        flash(f'✅ {message}', 'success')
    else:
        flash(f'❌ {message}', 'danger')
    return redirect(url_for('main.bypass_catalog'))
