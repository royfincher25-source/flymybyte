"""
FlyMyByte — Emergency Restore Module

Полный сброс к рабочему состоянию при критических ошибках.
Вызывается через кнопку "Всё сломалось — почини!" в веб-интерфейсе.

Использование:
    from core.emergency_restore import emergency_restore
    success, log = emergency_restore()
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

# VPN сервисы
VPN_SERVICES = [
    ('S24xray', 'VLESS'),
    ('S22shadowsocks', 'Shadowsocks'),
    ('S22trojan', 'Trojan'),
    ('S35tor', 'Tor'),
    ('S22hysteria2', 'Hysteria2'),
]

# IPset списки
IPSET_LIST = [
    'unblocksh',
    'unblockhysteria2',
    'unblocktor',
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


def _run_cmd(cmd: List[str], timeout: int = 10) -> Tuple[bool, str]:
    """Выполнить команду и вернуть результат."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return result.returncode == 0, result.stdout + result.stderr
    except Exception as e:
        return False, str(e)


def emergency_restore() -> Tuple[bool, List[str]]:
    """
    Полный сброс к рабочему состоянию.

    Returns:
        Tuple[bool, List[str]]: (success, log_messages)
    """
    log = []
    success = True

    logger.info("[EMERGENCY] Starting emergency restore...")
    log.append("🚨 Запуск аварийного восстановления...")

    # 1. Остановить все VPN-сервисы
    log.append("⏹️  Остановка VPN-сервисов...")
    for init_script, name in VPN_SERVICES:
        script_path = f'{INIT_DIR}/{init_script}'
        if os.path.exists(script_path):
            ok, out = _run_cmd(['sh', script_path, 'stop'], timeout=10)
            status = "✅" if ok else "⚠️"
            log.append(f"  {status} {name}: {'stopped' if ok else 'not found'}")
            logger.info(f"[EMERGENCY] Stopped {name}: {ok}")

    # 2. Очистить iptables PREROUTING
    log.append("🧹 Очистка iptables правил...")
    ok, out = _run_cmd(['iptables', '-t', 'nat', '-F', 'PREROUTING'], timeout=5)
    log.append(f"  {'✅' if ok else '⚠️'} PREROUTING flushed")
    logger.info(f"[EMERGENCY] Flush PREROUTING: {ok}")

    # 3. Очистить все ipset
    log.append("🧹 Очистка ipset списков...")
    for ipset_name in IPSET_LIST:
        ok, out = _run_cmd(['ipset', 'flush', ipset_name], timeout=5)
        status = "✅" if ok else "ℹ️"
        log.append(f"  {status} {ipset_name}")
        logger.info(f"[EMERGENCY] Flush {ipset_name}: {ok}")

    # 4. Удалить маркерные файлы
    log.append("🗑️  Удаление временных файлов...")
    for marker in MARKER_FILES:
        if os.path.exists(marker):
            try:
                os.remove(marker)
                log.append(f"  ✅ Removed {os.path.basename(marker)}")
            except Exception as e:
                log.append(f"  ⚠️ Failed to remove {marker}: {e}")

    # 5. Восстановить dnsmasq.conf из шаблона
    log.append("📄 Восстановление dnsmasq.conf...")
    if os.path.exists(DNSMASQ_TEMPLATE):
        try:
            shutil.copy2(DNSMASQ_TEMPLATE, DNSMASQ_CONF)
            log.append("  ✅ dnsmasq.conf restored from template")
            logger.info("[EMERGENCY] dnsmasq.conf restored")
        except Exception as e:
            log.append(f"  ⚠️ Failed to restore dnsmasq.conf: {e}")
            logger.error(f"[EMERGENCY] dnsmasq.conf restore error: {e}")
            success = False
    else:
        log.append("  ⚠️ Template not found, skipping")

    # 6. Очистить конфиги bypass
    log.append("🧹 Очистка конфигов bypass...")
    for conf_file in ['/opt/etc/unblock.dnsmasq', '/opt/etc/unblock-ai.dnsmasq']:
        if os.path.exists(conf_file):
            try:
                with open(conf_file, 'w') as f:
                    f.write('')
                log.append(f"  ✅ Cleared {os.path.basename(conf_file)}")
            except Exception as e:
                log.append(f"  ⚠️ Failed to clear {conf_file}: {e}")

    # 7. Перезапустить dnsmasq
    log.append("🔄 Перезапуск dnsmasq...")
    dnsmasq_script = f'{INIT_DIR}/S56dnsmasq'
    if os.path.exists(dnsmasq_script):
        ok, out = _run_cmd(['sh', dnsmasq_script, 'restart'], timeout=15)
        log.append(f"  {'✅' if ok else '❌'} dnsmasq {'restarted' if ok else 'failed'}")
        logger.info(f"[EMERGENCY] dnsmasq restart: {ok}")
        if not ok:
            success = False
    else:
        log.append("  ⚠️ dnsmasq script not found")

    # 8. Проверка DNS
    log.append("🔍 Проверка DNS...")
    try:
        ok, out = _run_cmd(['nslookup', 'google.com', '8.8.8.8'], timeout=10)
        if ok and 'Address' in out:
            log.append("  ✅ DNS работает (google.com)")
        else:
            log.append("  ⚠️ DNS проверка не прошла (но это может быть временно)")
    except Exception as e:
        log.append(f"  ⚠️ DNS check error: {e}")

    # 9. Финальный статус
    log.append("")
    if success:
        log.append("✅ Аварийное восстановление завершено успешно!")
        log.append("🌐 Интернет должен работать. Попробуйте открыть любой сайт.")
    else:
        log.append("⚠️ Восстановление завершено с предупреждениями.")
        log.append("🔧 Проверьте логи для деталей.")

    logger.info(f"[EMERGENCY] Restore completed: success={success}")
    return success, log
