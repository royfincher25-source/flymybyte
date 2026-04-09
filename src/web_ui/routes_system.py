"""
FlyMyByte Web Interface - System Routes

Blueprint for service management, system stats, DNS monitor, and logs:
/service/*, /stats, /logs, /api/system/*
"""
import logging
import os
import subprocess
import time
from flask import Blueprint, render_template, redirect, url_for, request, session, flash, current_app, jsonify
from typing import List, Dict, Tuple
from core.decorators import login_required, validate_csrf_token, csrf_required

logger = logging.getLogger(__name__)


from core.constants import (
    INIT_SCRIPTS,
    CONFIG_PATHS,
    SERVICES,
    WEB_UI_DIR,
    INIT_DIR,
    BACKUP_DIR,
    BACKUP_FILES,
    TMP_RESTART_SCRIPT,
    SCRIPT_EXECUTION_TIMEOUT,
)
from core.app_config import WebConfig
from core.services import check_service_status


# =============================================================================
# INLINED FUNCTIONS (from core/backup_service.py)
# =============================================================================

def _backup_arcname(path: str) -> str:
    if path.startswith('/opt/'):
        return path[5:]
    if path.startswith('/opt'):
        return path[4:]
    return os.path.basename(path)


def create_backup(backup_type: str = 'full') -> Tuple[bool, str]:
    import tarfile
    from datetime import datetime
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
    import re
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
    backup_path = os.path.join(BACKUP_DIR, backup_name)
    if not backup_name or not os.path.exists(backup_path):
        return False, 'Бэкап не найден'
    try:
        os.remove(backup_path)
        return True, f'Бэкап {backup_name} удалён'
    except Exception as e:
        return False, f'Ошибка удаления: {e}'


def restore_backup(backup_name: str) -> Tuple[bool, str]:
    """Restore system from backup archive."""
    backup_path = os.path.join(BACKUP_DIR, backup_name)
    if not backup_name or not os.path.exists(backup_path):
        return False, 'Бэкап не найден'

    try:
        import tarfile

        with tarfile.open(backup_path, 'r:gz') as tar:
            members = []
            for member in tar.getmembers():
                # Бэкап сохраняет пути БЕЗ /opt/ (arcname=_backup_arcname)
                # Восстанавливаем префикс /opt/ при извлечении
                safe_name = member.name.lstrip('/')
                if safe_name:
                    member.name = 'opt/' + safe_name
                    members.append(member)

            tar.extractall('/', members=members)

        logger.info(f"[BACKUP] Restored from {backup_name}")
        return True, f'Восстановлено из {backup_name}. Перезагрузите роутер для применения настроек.'
    except Exception as e:
        logger.error(f"[BACKUP] Restore failed: {e}")
        return False, f'Ошибка восстановления: {e}'


# =============================================================================
# SCHEDULE WEBUI RESTART (shared with updates)
# =============================================================================

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


bp = Blueprint('system', __name__, template_folder='templates', static_folder='static')


# =============================================================================
# ROUTES
# =============================================================================

@bp.route('/stats')
@login_required
def stats():
    config = WebConfig()
    services = {
        'vless': {'name': 'VLESS', 'init': INIT_SCRIPTS['vless'], 'config': CONFIG_PATHS['vless']},
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
        from core.utils import load_bypass_list
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
    from core.services import DNSSpoofing
    try:
        spoofing = DNSSpoofing()
        dns_status = spoofing.get_status()
    except Exception:
        dns_status = {'enabled': False, 'domain_count': 0}

    # DNS Override status
    # FIX #4: Проверяем маркерный файл для точного статуса
    dns_override_enabled = os.path.exists('/tmp/dns_override_enabled')
    
    # Fallback: если маркера нет, проверяем iptables
    if not dns_override_enabled:
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
    # FIX #4: Проверяем маркерный файл для точного статуса
    dns_override_enabled = os.path.exists('/tmp/dns_override_enabled')
    
    # Fallback: если маркера нет, проверяем iptables
    if not dns_override_enabled:
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
    from core.services import restart_service
    success, output = restart_service('Unblock', INIT_SCRIPTS['unblock'])
    if success:
        flash('✅ Unblock-сервис успешно перезапущен', 'success')
    else:
        flash(f'⚠️ Ошибка перезапуска: {output}', 'danger')
    return redirect(url_for('system.service'))


@bp.route('/service/restart-unblock-async', methods=['POST'])
@login_required
@csrf_required
def service_restart_unblock_async():
    """Запуск перезапуска unblock в фоновом режиме"""
    logger.info("[ROUTES] /service/restart-unblock-async")
    
    import stat
    import tempfile
    import time
    
    # Путь к скрипту фонового перезапуска
    restart_script = '/tmp/unblock_restart.sh'
    log_file = '/opt/var/log/unblock_restart.log'
    pid_file = '/tmp/unblock_restart.pid'
    
    # Проверяем, не запущен ли уже перезапуск
    if os.path.exists(pid_file):
        try:
            with open(pid_file, 'r') as f:
                old_pid = int(f.read().strip())
            # Проверяем, жив ли процесс
            result = subprocess.run(['kill', '-0', str(old_pid)], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                return jsonify({
                    'success': False,
                    'error': 'Перезапуск уже запущен',
                    'pid': old_pid
                }), 409
        except Exception:
            pass  # Старый процесс мёртв, удаляем pid файл
        os.remove(pid_file)
    
    # SAFETY: Проверяем что скрипт не завис более 10 минут
    if os.path.exists(log_file):
        try:
            log_mtime = os.path.getmtime(log_file)
            if time.time() - log_mtime > 600:  # 10 минут
                logger.warning("[ROUTES] Old restart log found, cleaning up")
                os.remove(log_file)
                os.remove(pid_file) if os.path.exists(pid_file) else None
        except Exception:
            pass
    
    # Создаём скрипт фонового перезапуска
    try:
        with open(restart_script, 'w') as f:
            f.write(f'''#!/bin/sh
# Фоновый перезапуск unblock (с таймаутом безопасности)
echo $$ > {pid_file}
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting unblock restart..." > {log_file}

# Запускаем перезапуск с таймаутом 5 минут
TIMEOUT=300
START_TIME=$(date +%s)

sh {INIT_SCRIPTS['unblock']} restart >> {log_file} 2>&1 &
RESTART_PID=$!

# Ждём завершения с проверкой таймаута
while kill -0 $RESTART_PID 2>/dev/null; do
    CURRENT_TIME=$(date +%s)
    ELAPSED=$((CURRENT_TIME - START_TIME))

    if [ $ELAPSED -ge $TIMEOUT ]; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] TIMEOUT: restart exceeded ${{TIMEOUT}}s, killing..." >> {log_file}
        kill -9 $RESTART_PID 2>/dev/null
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] Restart killed after timeout" >> {log_file}
        rm -f {pid_file}
        exit 1
    fi

    sleep 2
done

# Ждём завершения процесса
wait $RESTART_PID 2>/dev/null
EXIT_CODE=$?

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Restart finished with exit code: $EXIT_CODE" >> {log_file}
rm -f {pid_file}
exit $EXIT_CODE
''')
        os.chmod(restart_script, stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH)
        
        # Запускаем в фоне
        subprocess.Popen(['sh', restart_script], start_new_session=True)
        
        logger.info("[ROUTES] Background unblock restart started")
        
        return jsonify({
            'success': True,
            'message': 'Перезапуск запущен (выполняется 1-5 минут)',
            'log_file': log_file
        })
        
    except Exception as e:
        logger.error(f"[ROUTES] Failed to start background restart: {e}")
        return jsonify({
            'success': False,
            'error': f'Ошибка запуска: {str(e)}'
        }), 500


@bp.route('/service/restart-unblock-status')
@login_required
def service_restart_unblock_status():
    """Проверка статуса фонового перезапуска"""
    pid_file = '/tmp/unblock_restart.pid'
    log_file = '/opt/var/log/unblock_restart.log'
    
    # Проверяем, запущен ли ещё процесс
    is_running = False
    pid = None
    
    if os.path.exists(pid_file):
        try:
            with open(pid_file, 'r') as f:
                pid = int(f.read().strip())
            result = subprocess.run(['kill', '-0', str(pid)], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                is_running = True
        except Exception:
            pass
    
    # Читаем логи
    logs = []
    if os.path.exists(log_file):
        try:
            with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                logs = f.readlines()[-20:]  # Последние 20 строк
        except Exception:
            pass
    
    return jsonify({
        'running': is_running,
        'pid': pid,
        'logs': logs
    })


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
    return redirect(url_for('system.service'))


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
    return redirect(url_for('system.service'))


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
    return redirect(url_for('system.service'))


@bp.route('/service/restore-dns', methods=['POST'])
@login_required
@csrf_required
def service_restore_dns():
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

    # 2. Remove DNS redirect rules
    try:
        for proto in ['udp', 'tcp']:
            subprocess.run(
                ['iptables', '-t', 'nat', '-D', 'PREROUTING', '-p', proto, '--dport', '53', '-j', 'DNAT', '--to-destination', '192.168.1.1:5353'],
                capture_output=True, text=True, timeout=5
            )
            subprocess.run(
                ['iptables', '-t', 'nat', '-D', 'PREROUTING', '-p', proto, '--dport', '53', '-j', 'DNAT', '--to-destination', '192.168.1.1'],
                capture_output=True, text=True, timeout=5
            )
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
    return redirect(url_for('system.service'))


@bp.route('/service/dns-override/<action>', methods=['POST'])
@login_required
@csrf_required
def service_dns_override(action):
    """Включить/выключить DNS Override через IptablesManager."""
    enable = (action == 'on')
    logger.info(f"[ROUTES] /service/dns-override/{action} - {'enabling' if enable else 'disabling'}")
    
    from core.iptables_manager import get_iptables_manager
    from core.dnsmasq_manager import get_dnsmasq_manager
    
    ipt = get_iptables_manager()
    dns_mgr = get_dnsmasq_manager()
    
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
            
            # 1. Перезапускаем dnsmasq и генерируем конфиги
            dns_mgr.restart_dnsmasq()
            time.sleep(1)
            dns_mgr.generate_all()
            
            # 2. Применяем правила VPN redirect
            redirect_script = '/opt/etc/ndm/netfilter.d/100-redirect.sh'
            if os.path.exists(redirect_script):
                subprocess.run(['sh', redirect_script], capture_output=True, text=True, timeout=15)
            
            # 3. Добавляем DNAT правила DNS Override
            ipt.add_dns_redirect(local_ip, 5353)
            
            # 4. Создаём маркер
            with open('/tmp/dns_override_enabled', 'w') as f:
                f.write(local_ip)
            
            flash('✅ DNS Override включен', 'success')
            logger.info("[ROUTES] DNS Override enabled successfully")
        else:
            logger.info("[ROUTES] DNS Override: disabling...")
            
            # 1. Удаляем DNAT правила DNS Override
            ipt.remove_dns_redirect(local_ip, 5353)
            
            # 2. Удаляем маркер
            if os.path.exists('/tmp/dns_override_enabled'):
                os.remove('/tmp/dns_override_enabled')
            
            flash('✅ DNS Override выключен', 'success')
            logger.info("[ROUTES] DNS Override disabled successfully")
    except Exception as e:
        flash(f'❌ Ошибка: {str(e)}', 'danger')
        logger.error(f"[ROUTES] DNS Override exception: {e}")
    return redirect(url_for('system.service'))


@bp.route('/service/backup', methods=['GET', 'POST'])
@login_required
def service_backup():
    backups = get_backup_list()
    if request.method == 'POST':
        if not validate_csrf_token():
            flash('Ошибка безопасности: неверный токен', 'danger')
            return redirect(url_for('system.service_backup'))
        action = request.form.get('action')
        if action == 'create':
            success, message = create_backup()
            if success:
                flash(f'✅ {message}', 'success')
            else:
                flash(f'❌ {message}', 'danger')
            return redirect(url_for('system.service_backup'))
        elif action == 'delete':
            backup_name = request.form.get('backup_name')
            success, message = delete_backup(backup_name)
            if success:
                flash(f'✅ {message}', 'success')
            else:
                flash(f'❌ {message}', 'danger')
            return redirect(url_for('system.service_backup'))
        elif action == 'restore':
            backup_name = request.form.get('backup_name')
            success, message = restore_backup(backup_name)
            if success:
                flash(f'✅ {message}', 'success')
            else:
                flash(f'❌ {message}', 'danger')
            return redirect(url_for('system.service_backup'))
    return render_template('backup.html', backups=backups)


# DNS Monitor
@bp.route('/service/dns-monitor')
@login_required
def dns_monitor_status():
    from core.dns_ops import get_dns_monitor
    monitor = get_dns_monitor()
    status = monitor.get_status()
    return render_template('dns_monitor.html', status=status)


@bp.route('/service/emergency-restore', methods=['POST'])
@login_required
@csrf_required
def emergency_restore():
    """Аварийное восстановление — полный сброс к рабочему состоянию."""
    logger.info("[ROUTES] /service/emergency-restore - Starting emergency restore")
    from core.emergency_restore import emergency_restore as do_restore
    success, log = do_restore()
    
    if success:
        flash('✅ Аварийное восстановление завершено! Интернет должен работать.', 'success')
    else:
        flash('⚠️ Восстановление завершено с предупреждениями. Проверьте логи.', 'warning')
    
    # Сохраняем детальный лог в сессию для отображения
    session['emergency_log'] = log
    logger.info(f"[ROUTES] Emergency restore completed: success={success}")
    return redirect(url_for('system.service'))


@bp.route('/service/dns-monitor/start', methods=['POST'])
@login_required
@csrf_required
def dns_monitor_start():
    from core.dns_ops import get_dns_monitor
    monitor = get_dns_monitor()
    monitor.start()
    flash('✅ DNS monitor started', 'success')
    return redirect(url_for('system.dns_monitor_status'))


@bp.route('/service/dns-monitor/stop', methods=['POST'])
@login_required
@csrf_required
def dns_monitor_stop():
    from core.dns_ops import get_dns_monitor
    monitor = get_dns_monitor()
    monitor.stop()
    flash('ℹ️ DNS monitor stopped', 'info')
    return redirect(url_for('system.dns_monitor_status'))


@bp.route('/service/dns-monitor/check', methods=['POST'])
@login_required
@csrf_required
def dns_monitor_check():
    from core.dns_ops import get_dns_monitor, check_dns_server
    monitor = get_dns_monitor()
    if monitor._current_server:
        result = check_dns_server(monitor._current_server['host'], monitor._current_server['port'])
        if result['success']:
            flash(f"✅ DNS OK: {result['latency_ms']}ms", 'success')
        else:
            flash(f"❌ DNS failed: {result['error']}", 'danger')
    else:
        flash('⚠️ No DNS server selected', 'warning')
    return redirect(url_for('system.dns_monitor_status'))


# System Stats API
@bp.route('/api/system/stats')
@login_required
def system_stats():
    from core.utils import get_memory_stats, get_cpu_stats, MemoryManager
    from core.dns_ops import get_dns_monitor
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
    return redirect(url_for('system.view_logs'))
