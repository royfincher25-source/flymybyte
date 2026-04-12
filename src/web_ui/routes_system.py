"""
FlyMyByte Web Interface - System Routes

Blueprint for service management, system stats, DNS monitor, and logs:
/service/*, /stats, /logs, /api/system/*

Refactored to use BackupManager from core/backup_manager.py
"""
import logging
import os
import subprocess
import stat
import time
from flask import Blueprint, render_template, redirect, url_for, request, session, flash, jsonify
from typing import Dict
from core.decorators import login_required, validate_csrf_token, csrf_required

logger = logging.getLogger(__name__)


from core.constants import (
    INIT_SCRIPTS,
    CONFIG_PATHS,
    SERVICES,
    TMP_RESTART_SCRIPT,
    DNS_OVERRIDE_FLAG,
)
from core.app_config import WebConfig
from core.services import check_service_status
from core.backup_manager import get_backup_manager


def schedule_webui_restart():
    """Schedule web UI restart via temp script."""
    try:
        with open(TMP_RESTART_SCRIPT, 'w') as f:
            f.write(f'#!/bin/sh\nsleep 5\n{INIT_SCRIPTS["web_ui"]} restart\nrm -f {TMP_RESTART_SCRIPT}\n')
        os.chmod(TMP_RESTART_SCRIPT, stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH)
        subprocess.Popen(['sh', TMP_RESTART_SCRIPT], start_new_session=True)
        logger.info("S99web_ui restart scheduled")
    except Exception as e:
        logger.warning(f"Failed to schedule restart: {e}")
        try:
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
    }
    for svc in services.values():
        svc['status'] = check_service_status(svc['init'])
        svc['config_exists'] = os.path.exists(svc['config'])
    unblock_dir = config.unblock_dir
    bypass_lists = []
    total_domains = 0
    if os.path.exists(unblock_dir):
        from core.utils import load_bypass_list
        # Игнорируем устаревшие файлы (после удаления Tor/Hysteria2)
        IGNORED_FILES = {'tor.txt', 'hysteria2.txt', 'vpn.txt'}
        for filename in os.listdir(unblock_dir):
            if filename.endswith('.txt') and filename not in IGNORED_FILES:
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
    dns_override_enabled = os.path.exists(DNS_OVERRIDE_FLAG)

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

    # IPSET sizes (FIX: monitoring ipset bloat)
    from core.ipset_ops import _count_ipset_entries
    from core.constants import IPSET_MAP, IPSET_MAX_ENTRIES
    ipset_sizes = {}
    for ipset_name in IPSET_MAP.values():
        count = _count_ipset_entries(ipset_name)
        ipset_sizes[ipset_name] = {
            'count': count if count >= 0 else -1,
            'max': IPSET_MAX_ENTRIES,
            'status': 'ok' if count >= 0 and count < 500 else (
                'warning' if count >= 0 and count < 1000 else 'danger'
            ) if count >= 0 else 'unknown',
        }

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
        'ipset_sizes': ipset_sizes,
    }
    return render_template('stats.html', stats=stats_data, config=config)


@bp.route('/service')
@login_required
def service():
    # FIX #4: Проверяем маркерный файл для точного статуса
    dns_override_enabled = os.path.exists(DNS_OVERRIDE_FLAG)
    
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
            # FIX: Уменьшен timeout до 30 сек — если сервис не перезапускается, не блокируем
            result = subprocess.run(['sh', init_script, 'restart'], capture_output=True, text=True, timeout=30)
            status = '✅' if result.returncode == 0 else '❌'
            results.append(f"{status} {name}")
            logger.info(f"[ROUTES] {name}: {'OK' if result.returncode == 0 else 'FAILED'} (code={result.returncode})")
        except subprocess.TimeoutExpired:
            results.append(f"⏱️ {name} (таймаут)")
            logger.error(f"[ROUTES] {name}: restart timed out after 30s")
        except Exception as e:
            results.append(f"❌ {name}: {str(e)}")
            logger.error(f"[ROUTES] service_restart_all Exception for {name}: {e}")
    flash('Перезапуск сервисов: ' + ', '.join(results), 'success')

    # FIX: После перезапуска VPN сервисов нужно обновить ipsets
    try:
        logger.info("[ROUTES] Updating ipsets after VPN restart...")
        result = subprocess.run(
            ['sh', INIT_SCRIPTS['unblock'], 'start'],
            capture_output=True, text=True, timeout=60
        )
        if result.returncode == 0:
            results.append('✅ ipset обновлён')
            logger.info("[ROUTES] ipsets updated successfully")
        else:
            logger.warning(f"[ROUTES] ipset update failed: {result.stderr}")
    except Exception as e:
        logger.warning(f"[ROUTES] ipset update error: {e}")

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

    # 2. Sanitize dnsmasq.conf — remove obsolete entries (Tor references)
    try:
        from core.dnsmasq_manager import DnsmasqManager
        mgr = DnsmasqManager()
        mgr._sanitize_dnsmasq_conf()
        results.append('✅ Конфиг dnsmasq очищен')
        logger.info("[ROUTES] DNS restore: dnsmasq.conf sanitized")
    except Exception as e:
        results.append(f'⚠️ Очистка конфига: {e}')
        logger.error(f"[ROUTES] DNS restore: sanitize error: {e}")

    # 3. Restart dnsmasq
    try:
        for init_script in ['/opt/etc/init.d/S56dnsmasq', '/opt/etc/init.d/S99unblock']:
            if os.path.exists(init_script):
                logger.info(f"[ROUTES] DNS restore: restarting via {init_script}")
                subprocess.run(['sh', init_script, 'restart'], capture_output=True, text=True, timeout=15)
                results.append('✅ dnsmasq перезапущен')
                break
        else:
            results.append('⚠️ Скрипт запуска dnsmasq не найден')
            logger.error("[ROUTES] DNS restore: dnsmasq init script not found")
    except Exception as e:
        results.append(f'⚠️ Ошибка перезапуска dnsmasq: {e}')
        logger.error(f"[ROUTES] DNS restore: restart error: {e}")

    # 4. Regenerate bypass config and refresh ipset for all active VPN services
    try:
        from core.dnsmasq_manager import DnsmasqManager
        mgr = DnsmasqManager()
        ok, msg = mgr.generate_bypass_config()
        if ok:
            results.append(f'✅ Списки обхода обновлены: {msg}')
            logger.info(f"[ROUTES] DNS restore: bypass config regenerated: {msg}")
        else:
            results.append(f'⚠️ Списки обхода: {msg}')
            logger.warning(f"[ROUTES] DNS restore: bypass config error: {msg}")
    except Exception as e:
        results.append(f'⚠️ Ошибка генерации списков: {e}')
        logger.error(f"[ROUTES] DNS restore: bypass config error: {e}")

    # 5. Restore iptables rules and refresh ipsets for active VPN services
    from core.iptables_manager import get_iptables_manager
    from core.services import refresh_ipset_from_file
    from core.constants import SERVICE_TOGGLE_CONFIG

    vpn_services = [
        ('vless', '/opt/etc/init.d/S24xray', '/opt/etc/xray/vless.json', '/opt/etc/unblock/vless.txt'),
        ('shadowsocks', '/opt/etc/init.d/S22shadowsocks', '/opt/etc/shadowsocks.json', '/opt/etc/unblock/shadowsocks.txt'),
        ('trojan', '/opt/etc/init.d/S22trojan', '/opt/etc/init.d/trojan.json', '/opt/etc/unblock/trojan.txt'),
    ]

    ipt = get_iptables_manager()

    for svc_name, init_script, config_path, bypass_file in vpn_services:
        try:
            if os.path.exists(config_path) and os.path.exists(init_script):
                # Restart the service
                subprocess.run(['sh', init_script, 'restart'], capture_output=True, text=True, timeout=15)
                results.append(f'✅ {svc_name} перезапущен')
                logger.info(f"[ROUTES] DNS restore: {svc_name} restarted")

                # Restore iptables rules
                toggle_cfg = SERVICE_TOGGLE_CONFIG.get(svc_name)
                if toggle_cfg:
                    ipset_name = toggle_cfg['ipset']
                    port = toggle_cfg['port']
                    ipt.add_rule(ipset_name, port, 'tcp')
                    ipt.add_rule(ipset_name, port, 'udp')
                    results.append(f'✅ iptables {svc_name} восстановлены')
                    logger.info(f"[ROUTES] DNS restore: iptables rules for {svc_name} restored")

                # Refresh ipset with resolved IPs
                if os.path.exists(bypass_file):
                    ok, msg = refresh_ipset_from_file(bypass_file, ipset_name)
                    if ok:
                        results.append(f'✅ ipset {svc_name} обновлён')
                        logger.info(f"[ROUTES] DNS restore: ipset {ipset_name} refreshed: {msg}")
        except Exception as e:
            logger.warning(f"[ROUTES] DNS restore: {svc_name} error: {e}")

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
            # Создаём постоянный маркер (не /tmp — он очищается при перезагрузке)
            os.makedirs(os.path.dirname(DNS_OVERRIDE_FLAG), exist_ok=True)
            with open(DNS_OVERRIDE_FLAG, 'w') as f:
                f.write(local_ip or '')
            
            flash('✅ DNS Override включен', 'success')
            logger.info("[ROUTES] DNS Override enabled successfully")
        else:
            logger.info("[ROUTES] DNS Override: disabling...")
            
            # 1. Удаляем DNAT правила DNS Override
            ipt.remove_dns_redirect(local_ip, 5353)
            
            # 2. Удаляем маркер
            if os.path.exists(DNS_OVERRIDE_FLAG):
                os.remove(DNS_OVERRIDE_FLAG)
            # Также удаляем старый маркер если он существует
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
    backup_mgr = get_backup_manager()
    backups = backup_mgr.list()
    if request.method == 'POST':
        if not validate_csrf_token():
            flash('Security error: invalid token', 'danger')
            return redirect(url_for('system.service_backup'))
        action = request.form.get('action')
        if action == 'create':
            success, message = backup_mgr.create()
            if success:
                flash(f'✅ {message}', 'success')
            else:
                flash(f'❌ {message}', 'danger')
            return redirect(url_for('system.service_backup'))
        elif action == 'delete':
            backup_name = request.form.get('backup_name')
            success, message = backup_mgr.delete(backup_name)
            if success:
                flash(f'✅ {message}', 'success')
            else:
                flash(f'❌ {message}', 'danger')
            return redirect(url_for('system.service_backup'))
        elif action == 'restore':
            backup_name = request.form.get('backup_name')
            success, message = backup_mgr.restore_async(backup_name)
            if success:
                flash(f'✅ {message}', 'success')
            else:
                flash(f'❌ {message}', 'danger')
            return redirect(url_for('system.service_backup'))
    return render_template('backup.html', backups=backups)


@bp.route('/api/restore/status')
@login_required
def api_restore_status():
    """Get async restore status."""
    backup_mgr = get_backup_manager()
    return jsonify(backup_mgr.get_restore_status())


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
