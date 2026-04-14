"""
FlyMyByte — Emergency Restore Module

Полный сброс к рабочему состоянию при критических ошибках.
Использует IptablesManager и DnsmasqManager для централизованного управления.

Стратегия:
1. Остановить watchdog (чтобы не мешали восстановлению)
2. Остановить VPN, очистить iptables/ipset
3. Восстановить dnsmasq.conf
4. Запустить S99unblock start — полный цикл:
   - populate ipset из файлов
   - apply iptables redirect
   - запустить watchdog заново
"""
import os
import subprocess
import logging
import shutil
from typing import Tuple, List

logger = logging.getLogger(__name__)

# Пути
INIT_DIR = '/opt/etc/init.d'
WEB_UI_DIR = '/opt/etc/web_ui'
DNSMASQ_CONF = '/opt/etc/dnsmasq.conf'
DNSMASQ_TEMPLATE = '/opt/etc/web_ui/resources/config/dnsmasq.conf'
S99UNBLOCK = f'{INIT_DIR}/S99unblock'

# VPN сервисы
VPN_SERVICES = [
    ('S24xray', 'VLESS'),
    ('S22shadowsocks', 'Shadowsocks'),
    ('S22trojan', 'Trojan'),
]

# IPset списки
IPSET_LIST = [
    'unblocksh',
    'unblockvless',
    'unblocktroj',
]

# Маркерные файлы
MARKER_FILES = [
    '/tmp/dns_override_enabled',
    '/tmp/dns_override_disabled',
    '/tmp/unblock_restart.pid',
    '/tmp/unblock_restart.sh',
]


def _run_cmd(cmd: list, timeout: int = 10) -> Tuple[bool, str]:
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return result.returncode == 0, result.stdout + result.stderr
    except Exception as e:
        return False, str(e)


def _stop_watchdogs() -> List[str]:
    """Остановить все watchdog-процессы через /proc (BusyBox-совместимо)."""
    log = []
    killed = {'dnsmasq_watchdog': 0, 'vpn_watchdog': 0}

    for pid_dir in os.listdir('/proc'):
        if not pid_dir.isdigit():
            continue
        cmdline_path = f'/proc/{pid_dir}/cmdline'
        try:
            with open(cmdline_path, 'rb') as f:
                cmdline = f.read().decode('utf-8', errors='ignore')

            if 'dnsmasq_watchdog' in cmdline:
                os.kill(int(pid_dir), 9)
                killed['dnsmasq_watchdog'] += 1
            elif 'vpn_watchdog' in cmdline:
                os.kill(int(pid_dir), 9)
                killed['vpn_watchdog'] += 1
        except (FileNotFoundError, PermissionError, ProcessLookupError, ValueError):
            continue

    # Удаляем lockfile
    for lockfile in ['/tmp/dnsmasq_watchdog.pid', '/tmp/vpn_watchdog.pid']:
        if os.path.exists(lockfile):
            try:
                os.remove(lockfile)
            except Exception:
                pass

    log.append(f"Watchdog stopped: dnsmasq={killed['dnsmasq_watchdog']}, vpn={killed['vpn_watchdog']}")
    logger.info(f"[EMERGENCY] {log[0]}")
    return log


def emergency_restore() -> Tuple[bool, List[str]]:
    """
    Полный сброс к рабочему состоянию.
    1. Останавливает watchdog (чтобы не мешали)
    2. Останавливает VPN, чистит iptables/ipset
    3. Восстанавливает dnsmasq.conf из шаблона
    4. Запускает S99unblock start для полного восстановления
    """
    log = []
    success = True

    logger.info("[EMERGENCY] Starting emergency restore...")
    log.append("🚨 Запуск аварийного восстановления...")

    # 0. Остановить watchdog (чтобы не мешали восстановлению)
    log.append("🛑 Остановка watchdog-скриптов...")
    try:
        wd_log = _stop_watchdogs()
        log.append(f"  ✅ {wd_log[0]}")
    except Exception as e:
        log.append(f"  ⚠️ Watchdog stop error: {e}")
        logger.warning(f"[EMERGENCY] Watchdog stop failed: {e}")

    # 1. Остановить все VPN-сервисы
    log.append("⏹️  Остановка VPN-сервисов...")
    for init_script, name in VPN_SERVICES:
        script_path = f'{INIT_DIR}/{init_script}'
        if os.path.exists(script_path):
            ok, out = _run_cmd(['sh', script_path, 'stop'], timeout=10)
            status = "✅" if ok else "⚠️"
            log.append(f"  {status} {name}: {'stopped' if ok else 'not found'}")

    # 2. Очистить iptables PREROUTING через IptablesManager
    log.append("🧹 Очистка iptables правил...")
    try:
        from core.iptables_manager import get_iptables_manager
        ipt = get_iptables_manager()
        ok, msg = ipt.flush_all_flymybyte_rules()
        log.append(f"  {'✅' if ok else '⚠️'} {msg}")
    except Exception as e:
        log.append(f"  ⚠️ IptablesManager error: {e}")
        # Fallback на прямой вызов
        ok, out = _run_cmd(['iptables', '-t', 'nat', '-F', 'PREROUTING'], timeout=5)
        log.append(f"  {'✅' if ok else '⚠️'} Fallback flush: {'OK' if ok else 'failed'}")

    # 3. Очистить все ipset
    log.append("🧹 Очистка ipset списков...")
    for ipset_name in IPSET_LIST:
        ok, out = _run_cmd(['ipset', 'flush', ipset_name], timeout=5)
        status = "✅" if ok else "ℹ️"
        log.append(f"  {status} {ipset_name}")

    # 4. Удалить маркерные файлы
    log.append("🗑️  Удаление временных файлов...")
    for marker in MARKER_FILES:
        if os.path.exists(marker):
            try:
                os.remove(marker)
                log.append(f"  ✅ Removed {os.path.basename(marker)}")
            except Exception as e:
                log.append(f"  ⚠️ Failed to remove {marker}: {e}")

    # 5. Восстановить dnsmasq.conf и очистить конфиги bypass
    log.append("📄 Восстановление dnsmasq конфигурации...")
    try:
        from core.dnsmasq_manager import get_dnsmasq_manager
        dns_mgr = get_dnsmasq_manager()

        # Восстанавливаем шаблон
        if os.path.exists(DNSMASQ_TEMPLATE):
            shutil.copy2(DNSMASQ_TEMPLATE, DNSMASQ_CONF)
            log.append("  ✅ dnsmasq.conf restored from template")

        # Очищаем конфиги bypass
        for conf_file in [DNSMASQ_CONF.replace('dnsmasq.conf', 'unblock.dnsmasq'),
                          DNSMASQ_CONF.replace('dnsmasq.conf', 'unblock-ai.dnsmasq')]:
            if os.path.exists(conf_file):
                with open(conf_file, 'w') as f:
                    f.write('')
                log.append(f"  ✅ Cleared {os.path.basename(conf_file)}")
    except Exception as e:
        log.append(f"  ⚠️ DnsmasqManager error: {e}")
        success = False

    # 6. Перезапустить dnsmasq
    log.append("🔄 Перезапуск dnsmasq...")
    dnsmasq_script = f'{INIT_DIR}/S56dnsmasq'
    if os.path.exists(dnsmasq_script):
        ok, out = _run_cmd(['sh', dnsmasq_script, 'restart'], timeout=15)
        log.append(f"  {'✅' if ok else '❌'} dnsmasq {'restarted' if ok else 'failed'}")
        if not ok:
            success = False
    else:
        log.append("  ⚠️ dnsmasq script not found")

    # 7. Проверка DNS
    log.append("🔍 Проверка DNS...")
    try:
        ok, out = _run_cmd(['nslookup', 'google.com', '8.8.8.8'], timeout=10)
        if ok and 'Address' in out:
            log.append("  ✅ DNS работает (google.com)")
        else:
            log.append("  ⚠️ DNS проверка не прошла (но это может быть временно)")
    except Exception as e:
        log.append(f"  ⚠️ DNS check error: {e}")

    # 8. Запустить S99unblock start — полный цикл восстановления
    log.append("🔄 Полный цикл восстановления (S99unblock)...")
    log.append("  ⏳ Это может занять 15-30 секунд...")
    if os.path.exists(S99UNBLOCK):
        try:
            ok, out = _run_cmd(['sh', S99UNBLOCK, 'start'], timeout=120)
            if ok:
                log.append("  ✅ S99unblock start completed")
                logger.info("[EMERGENCY] S99unblock start succeeded")
            else:
                log.append(f"  ⚠️ S99unblock exit code: {out[:200]}")
                logger.warning(f"[EMERGENCY] S99unblock start returned: {out[:200]}")
        except subprocess.TimeoutExpired:
            log.append("  ⚠️ S99unblock timed out (120s)")
            logger.warning("[EMERGENCY] S99unblock start timed out")
        except Exception as e:
            log.append(f"  ⚠️ S99unblock error: {e}")
            logger.error(f"[EMERGENCY] S99unblock start error: {e}")
    else:
        log.append(f"  ⚠️ S99unblock not found at {S99UNBLOCK}")
        logger.warning("[EMERGENCY] S99unblock not found")

    # 9. Финальная проверка — работают ли VPN сервисы
    log.append("🔍 Проверка VPN сервисов...")
    vpn_ok = True
    for init_script, name in VPN_SERVICES:
        script_path = f'{INIT_DIR}/{init_script}'
        if os.path.exists(script_path):
            ok, out = _run_cmd(['sh', script_path, 'status'], timeout=5)
            if ok and 'running' in out.lower():
                log.append(f"  ✅ {name}: running")
            else:
                log.append(f"  ⚠️ {name}: not running (это может быть нормально если нет конфига)")
                vpn_ok = False
        else:
            log.append(f"  ℹ️ {name}: script not found")

    # 10. Финальный статус
    log.append("")
    if success and vpn_ok:
        log.append("✅ Аварийное восстановление завершено успешно!")
        log.append("🌐 Интернет должен работать. Попробуйте открыть любой сайт.")
    elif success:
        log.append("✅ Аварийное восстановление завершено (но VPN могут быть не активны)")
        log.append("🔧 Проверьте что VPN-ключи установлены на странице 'Ключи'")
    else:
        log.append("⚠️ Восстановление завершено с предупреждениями.")
        log.append("🔧 Проверьте логи для деталей.")

    logger.info(f"[EMERGENCY] Restore completed: success={success}, vpn_ok={vpn_ok}")
    return success or vpn_ok, log
