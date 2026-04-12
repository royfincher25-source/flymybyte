"""
FlyMyByte Web Interface - Bypass Routes

Blueprint for bypass lists and DNS spoofing:
/bypass/*, /dns-spoofing/*
"""
import logging
import os
from flask import Blueprint, render_template, redirect, url_for, request, session, flash, jsonify
from markupsafe import escape
from werkzeug.utils import secure_filename
from core.decorators import login_required, validate_csrf_token, csrf_required

logger = logging.getLogger(__name__)


def _safe_path(base_dir: str, filename: str) -> str:
    """Проверить что файл действительно внутри base_dir (защита от path traversal)."""
    safe_name = secure_filename(filename)
    filepath = os.path.join(base_dir, f"{safe_name}.txt")
    real_path = os.path.realpath(filepath)
    real_dir = os.path.realpath(base_dir)
    if not real_path.startswith(real_dir + os.sep):
        raise ValueError(f"Invalid file path: {filename}")
    return filepath


from core.constants import (
    MAX_ENTRIES_PER_REQUEST,
    MAX_ENTRY_LENGTH,
    MAX_TOTAL_INPUT_SIZE,
    AI_DOMAINS_LIST,
    WEB_UI_DIR,
)
from core.utils import (
    load_bypass_list,
    save_bypass_list,
    validate_bypass_entry,
    run_unblock_update,
    is_ip_address,
)
from core.app_config import WebConfig
from core.dnsmasq_manager import get_dnsmasq_manager
from core.services import (
    DNSSpoofing, apply_dns_spoofing, disable_dns_spoofing,
    get_dns_spoofing_status, get_catalog, download_list,
)
from core.services import refresh_ipset_from_file
from core.handlers import redirect_with_message


bp = Blueprint('bypass', __name__, template_folder='templates', static_folder='static')


# =============================================================================
# DNS SPOOFING ROUTES
# =============================================================================

@bp.route('/dns-spoofing')
@login_required
def dns_spoofing():
    return render_template('dns_spoofing.html')


@bp.route('/dns-spoofing/status')
@login_required
def dns_spoofing_status():
    try:
        status = get_dns_spoofing_status()
        # Use DnsmasqManager for accurate dnsmasq status
        try:
            dns_mgr = get_dnsmasq_manager()
            dns_status = dns_mgr.get_status()
            status['dnsmasq_running'] = dns_status['dnsmasq_running']
            status['config_valid'] = dns_status['config_valid']
        except Exception:
            pass
        return jsonify(status)
    except Exception as e:
        logger.error(f"dns_spoofing_status error: {e}")
        return jsonify({'enabled': False, 'domain_count': 0, 'config_exists': False, 'dnsmasq_running': False, 'error': str(e)})


@bp.route('/dns-spoofing/apply', methods=['POST'])
@login_required
def dns_spoofing_apply():
    """Применить DNS-обход AI-доменов через DnsmasqManager."""
    try:
        dns_mgr = get_dnsmasq_manager()
        ok, msg = dns_mgr.generate_ai_config()
        if ok:
            dns_mgr.restart_dnsmasq_with_retry()
            return jsonify({'success': True, 'message': msg})
        else:
            return jsonify({'success': False, 'error': msg})
    except Exception as e:
        logger.error(f"dns_spoofing_apply error: {e}")
        return jsonify({'success': False, 'error': str(e)})


@bp.route('/dns-spoofing/disable', methods=['POST'])
@login_required
def dns_spoofing_disable():
    """Отключить DNS-обход AI-доменов через DnsmasqManager."""
    try:
        dns_mgr = get_dnsmasq_manager()
        # Очищаем AI конфиг
        ai_conf = '/opt/etc/unblock-ai.dnsmasq'
        if os.path.exists(ai_conf):
            with open(ai_conf, 'w') as f:
                f.write('')
        # Перезапускаем dnsmasq
        dns_mgr.restart_dnsmasq_with_retry()
        return jsonify({'success': True, 'message': 'DNS-обход AI выключен'})
    except Exception as e:
        logger.error(f"dns_spoofing_disable error: {e}")
        return jsonify({'success': False, 'error': str(e)})


@bp.route('/dns-spoofing/domains')
@login_required
def dns_spoofing_get_domains():
    try:
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


# =============================================================================
# BYPASS ROUTES
# =============================================================================

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
    try:
        filepath = _safe_path(config.unblock_dir, filename)
    except ValueError as e:
        return redirect_with_message(str(e), 'danger', 'bypass.bypass')
    filename = os.path.splitext(os.path.basename(filepath))[0]
    entries = load_bypass_list(filepath)
    return render_template('bypass_view.html', filename=filename, entries=entries, filepath=filepath)


@bp.route('/bypass/<filename>/add', methods=['GET', 'POST'])
@login_required
@csrf_required
def add_to_bypass(filename: str):
    config = WebConfig()
    filename = secure_filename(filename)
    if not filename:
        return redirect_with_message('Неверное имя файла', 'danger', 'bypass.bypass')
    filepath = os.path.join(config.unblock_dir, f"{filename}.txt")
    logger.info(f"[ROUTES] /bypass/{filename}/add - filepath={filepath}")
    if request.method == 'POST':
        entries_text = request.form.get('entries', '')
        if len(entries_text) > MAX_TOTAL_INPUT_SIZE:
            return redirect_with_message(f'Превышен лимит ({MAX_TOTAL_INPUT_SIZE // 1024}KB)', 'danger', 'bypass.bypass')
        new_entries = [e.strip() for e in entries_text.split('\n') if e.strip()]
        logger.info(f"[ROUTES] Adding {len(new_entries)} entries to {filepath}")
        if len(new_entries) > MAX_ENTRIES_PER_REQUEST:
            return redirect_with_message(f'Превышено записей ({MAX_ENTRIES_PER_REQUEST})', 'danger', 'bypass.bypass')
        for entry in new_entries:
            if len(entry) > MAX_ENTRY_LENGTH:
                return redirect_with_message(f'Запись слишком длинная ({MAX_ENTRY_LENGTH})', 'danger', 'bypass.bypass')
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
        
        # Show added entries in flash message
        added_preview = domain_entries + ip_entries
        if len(added_preview) > 10:
            added_text = ', '.join(added_preview[:10]) + f'... +{len(added_preview) - 10}'
        else:
            added_text = ', '.join(added_preview) if added_preview else ''

        if added_count > 0:
            # Use DnsmasqManager for atomic config regeneration and dnsmasq restart
            # DNSSpoofing will add domains to ipset automatically on DNS queries
            # IP/CIDR entries will be loaded on web_ui startup
            try:
                dns_mgr = get_dnsmasq_manager()
                ok, msg = dns_mgr.generate_all()
                if ok:
                    dns_mgr.restart_dnsmasq_with_retry()
                    flash(f'✅ Добавлено: {added_count} | {added_text}', 'success')
                else:
                    flash(f'⚠️ Добавлено {added_count}: {added_text}, ошибка: {msg}', 'warning')
            except Exception as e:
                logger.error(f"[ROUTES] DnsmasqManager error: {e}")
                # Fallback to old method
                success, output = run_unblock_update()
                if success:
                    flash(f'✅ Добавлено: {added_count} | {added_text}', 'success')
                else:
                    flash(f'⚠️ Добавлено {added_count}: {added_text}, ошибка: {output}', 'warning')
        elif invalid_entries:
            escaped_invalid = [escape(e) for e in invalid_entries[:5]]
            flash(f'⚠️ Все записи уже в списке или невалидны. Нераспознанные: {", ".join(escaped_invalid)}', 'warning')
        else:
            flash('ℹ️ Все записи уже были в списке', 'info')
        return redirect(url_for('bypass.view_bypass', filename=filename))
    return render_template('bypass_add.html', filename=filename)


@bp.route('/bypass/<filename>/remove', methods=['GET', 'POST'])
@login_required
@csrf_required
def remove_from_bypass(filename: str):
    config = WebConfig()
    filename = secure_filename(filename)
    if not filename:
        flash('Неверное имя файла', 'danger')
        return redirect(url_for('bypass.bypass'))
    filepath = os.path.join(config.unblock_dir, f"{filename}.txt")
    logger.info(f"[ROUTES] /bypass/{filename}/remove - filepath={filepath}")
    if request.method == 'POST':
        entries_text = request.form.get('entries', '')
        if len(entries_text) > MAX_TOTAL_INPUT_SIZE:
            flash(f'Превышен лимит размера ввода (макс. {MAX_TOTAL_INPUT_SIZE // 1024}KB)', 'danger')
            return redirect(url_for('bypass.view_bypass', filename=filename))
        to_remove = [e.strip() for e in entries_text.split('\n') if e.strip()]
        current_list = load_bypass_list(filepath)
        original_count = len(current_list)
        removed_entries = [item for item in current_list if item in to_remove]
        current_list = [item for item in current_list if item not in to_remove]
        removed_count = original_count - len(current_list)
        
        # Show removed entries in flash message
        if len(removed_entries) > 10:
            removed_text = ', '.join(removed_entries[:10]) + f'... +{len(removed_entries) - 10}'
        else:
            removed_text = ', '.join(removed_entries) if removed_entries else ''
        
        logger.info(f"[ROUTES] Removing {removed_count} entries from {filepath} (was {original_count}, now {len(current_list)})")
        save_bypass_list(filepath, current_list)
        
        if removed_count > 0:
            success, output = run_unblock_update()
            if success:
                flash(f'❌ Удалено: {removed_count} | {removed_text}', 'success')
            else:
                flash(f'⚠️ Удалено {removed_count}: {removed_text}, ошибка: {output}', 'warning')
        else:
            flash('ℹ️ Ни одна запись не найдена в списке', 'info')
        return redirect(url_for('bypass.view_bypass', filename=filename))
    entries = load_bypass_list(filepath)
    return render_template('bypass_remove.html', filename=filename, entries=entries)


@bp.route('/bypass/<filename>/refresh-ipset', methods=['POST'])
@login_required
@csrf_required
def refresh_ipset(filename: str):
    """Legacy route - no longer used. IP/CIDR loaded on web_ui startup."""
    config = WebConfig()
    filename = secure_filename(filename)
    if not filename:
        flash('Неверное имя файла', 'danger')
        return redirect(url_for('bypass.bypass'))
    filepath = os.path.join(config.unblock_dir, f"{filename}.txt")
    logger.info(f"[ROUTES] /bypass/{filename}/refresh-ipset - DEPRECATED")
    flash('ℹ️ Обновление ipset теперь происходит автоматически при запуске web UI', 'info')
    return redirect(url_for('bypass.view_bypass', filename=filename))


@bp.route('/bypass/catalog')
@login_required
def bypass_catalog():
    catalog = get_catalog()
    return render_template('bypass_catalog.html', catalog=catalog)


@bp.route('/bypass/catalog/<name>', methods=['POST'])
@login_required
@csrf_required
def download_list_from_catalog(name: str):
    config = WebConfig()
    dest_dir = config.unblock_dir
    success, message, count = download_list(name, dest_dir)
    if success:
        flash(f'✅ {message}', 'success')
    else:
        flash(f'❌ {message}', 'danger')
    return redirect(url_for('bypass.bypass_catalog'))
