"""
FlyMyByte — Unified iptables Manager

Централизованное управление iptables правилами.
Заменяет разрозненные вызовы iptables в 5+ файлах.

Использование:
    from core.iptables_manager import IptablesManager

    mgr = IptablesManager()
    mgr.add_vpn_redirect('unblockvless', 10810)
    mgr.remove_vpn_redirect('unblockvless', 10810)
    mgr.add_dns_redirect('192.168.1.1', 5353)
    mgr.snapshot()   # сохранить текущее состояние
    mgr.restore()    # восстановить
"""
import subprocess
import logging
import json
import os
from typing import List, Dict, Tuple, Optional, Optional

logger = logging.getLogger(__name__)

SNAPSHOT_FILE = '/tmp/iptables_snapshot.json'


class IptablesManager:
    """Менеджер iptables правил для FlyMyByte."""

    def __init__(self):
        self._table = 'nat'
        self._chain = 'PREROUTING'

    # =========================================================================
    # VPN REDIRECT RULES
    # =========================================================================

    def add_vpn_redirect(self, ipset_name: str, port: int) -> Tuple[bool, str]:
        """
        Добавить правила перенаправления трафика для ipset на VPN-порт.

        Args:
            ipset_name: Имя ipset (напр. 'unblockvless')
            port: Порт VPN-прокси (напр. 10810)

        Returns:
            Tuple[bool, str]: (success, message)
        """
        rules_added = []
        errors = []

        for proto in ['tcp', 'udp']:
            # Сначала удаляем существующее правило (если есть), чтобы избежать дубликатов
            check_rule = ['-t', self._table, '-D', self._chain, '-p', proto,
                          '-m', 'set', '--match-set', ipset_name, 'dst',
                          '-j', 'REDIRECT', '--to-port', str(port)]
            subprocess.run(['iptables'] + check_rule, capture_output=True, text=True, timeout=5)

            # Добавляем правило через -I (insert в начало цепочки)
            rule = ['-t', self._table, '-I', self._chain, '-p', proto,
                    '-m', 'set', '--match-set', ipset_name, 'dst',
                    '-j', 'REDIRECT', '--to-port', str(port)]

            result = subprocess.run(['iptables'] + rule, capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                rules_added.append(proto)
                logger.info(f"Added iptables rule: {ipset_name} {proto} -> {port}")
            else:
                errors.append(f"{proto}: {result.stderr.strip()}")
                logger.error(f"Failed to add rule {ipset_name} {proto} -> {port}: {result.stderr.strip()}")

        if errors:
            return False, f"Errors: {'; '.join(errors)}"
        return True, f"Added: {', '.join(rules_added)}"

    def remove_vpn_redirect(self, ipset_name: str, port: int) -> Tuple[bool, str]:
        """
        Удалить правила перенаправления для ipset.

        Args:
            ipset_name: Имя ipset
            port: Порт VPN-прокси

        Returns:
            Tuple[bool, str]: (success, message)
        """
        rules_removed = []

        for proto in ['tcp', 'udp']:
            # Удаляем все копии правила (может быть несколько)
            while True:
                rule = ['-t', self._table, '-D', self._chain, '-p', proto,
                        '-m', 'set', '--match-set', ipset_name, 'dst',
                        '-j', 'REDIRECT', '--to-port', str(port)]
                result = subprocess.run(['iptables'] + rule, capture_output=True, text=True, timeout=5)
                if result.returncode != 0:
                    break
                rules_removed.append(proto)

        if rules_removed:
            logger.info(f"Removed iptables rules: {ipset_name} -> {port}")
            return True, f"Removed: {', '.join(set(rules_removed))}"
        return True, "No rules to remove"

    # =========================================================================
    # DNS REDIRECT RULES (DNS Override)
    # =========================================================================

    def add_dns_redirect(self, local_ip: str, target_port: int) -> Tuple[bool, str]:
        """
        Добавить правила DNAT для перенаправления DNS-запросов.

        Args:
            local_ip: IP роутера (напр. '192.168.1.1')
            target_port: Порт dnsmasq (напр. 5353)

        Returns:
            Tuple[bool, str]: (success, message)
        """
        rules_added = []
        errors = []

        for proto in ['udp', 'tcp']:
            rule = ['-t', self._table, '-C', self._chain, '-p', proto,
                    '--dport', '53', '-j', 'DNAT',
                    '--to-destination', f'{local_ip}:{target_port}']

            result = subprocess.run(['iptables'] + rule, capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                rules_added.append(f"{proto} (exists)")
                continue

            rule[3] = '-A'
            result = subprocess.run(['iptables'] + rule, capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                rules_added.append(proto)
                logger.info(f"Added DNS redirect: {proto} dport 53 -> {local_ip}:{target_port}")
            else:
                errors.append(f"{proto}: {result.stderr.strip()}")

        if errors:
            return False, f"Errors: {'; '.join(errors)}"
        return True, f"Added: {', '.join(rules_added)}"

    def remove_dns_redirect(self, local_ip: str, target_port: int) -> Tuple[bool, str]:
        """
        Удалить правила DNAT для DNS-запросов.

        Args:
            local_ip: IP роутера
            target_port: Порт dnsmasq

        Returns:
            Tuple[bool, str]: (success, message)
        """
        rules_removed = []

        for proto in ['udp', 'tcp']:
            while True:
                rule = ['-t', self._table, '-D', self._chain, '-p', proto,
                        '--dport', '53', '-j', 'DNAT',
                        '--to-destination', f'{local_ip}:{target_port}']
                result = subprocess.run(['iptables'] + rule, capture_output=True, text=True, timeout=5)
                if result.returncode != 0:
                    break
                rules_removed.append(proto)

            # Также удаляем вариант без порта (на всякий случай)
            while True:
                rule = ['-t', self._table, '-D', self._chain, '-p', proto,
                        '--dport', '53', '-j', 'DNAT',
                        '--to-destination', local_ip]
                result = subprocess.run(['iptables'] + rule, capture_output=True, text=True, timeout=5)
                if result.returncode != 0:
                    break
                rules_removed.append(proto)

        if rules_removed:
            logger.info(f"Removed DNS redirect rules for {local_ip}:{target_port}")
            return True, f"Removed: {', '.join(set(rules_removed))}"
        return True, "No DNS redirect rules to remove"

    # =========================================================================
    # FLUSH / RESET
    # =========================================================================

    def flush_chain(self, table: str = 'nat', chain: str = 'PREROUTING') -> Tuple[bool, str]:
        """
        Очистить всю цепочку iptables.

        Args:
            table: Таблица (nat, mangle, filter)
            chain: Цепочка

        Returns:
            Tuple[bool, str]: (success, message)
        """
        result = subprocess.run(
            ['iptables', '-t', table, '-F', chain],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            logger.warning(f"Flushed {table}:{chain}")
            return True, f"Flushed {table}:{chain}"
        return False, result.stderr.strip()

    def flush_all_flymybyte_rules(self) -> Tuple[bool, str]:
        """
        Очистить ВСЕ правила FlyMyByte из PREROUTING.
        Удаляет только правила, относящиеся к FlyMyByte (REDIRECT, DNAT).

        Returns:
            Tuple[bool, str]: (success, message)
        """
        removed = []

        # Получаем список всех правил
        result = subprocess.run(
            ['iptables', '-t', 'nat', '-L', 'PREROUTING', '-n', '-v', '--line-numbers'],
            capture_output=True, text=True, timeout=5
        )

        if result.returncode != 0:
            return False, "Failed to list rules"

        # Парсим и удаляем правила FlyMyByte (REDIRECT и DNAT на 53)
        lines = result.stdout.strip().split('\n')
        for line in reversed(lines):  # С конца, чтобы номера не сбивались
            if 'REDIRECT' in line or ('DNAT' in line and 'dpt:53' in line):
                # Извлекаем номер правила
                parts = line.strip().split()
                if parts and parts[0].isdigit():
                    rule_num = parts[0]
                    del_result = subprocess.run(
                        ['iptables', '-t', 'nat', '-D', 'PREROUTING', rule_num],
                        capture_output=True, text=True, timeout=5
                    )
                    if del_result.returncode == 0:
                        removed.append(rule_num)

        if removed:
            logger.warning(f"Removed {len(removed)} FlyMyByte rules from PREROUTING")
            return True, f"Removed {len(removed)} rules"
        return True, "No FlyMyByte rules found"

    # =========================================================================
    # SNAPSHOT / RESTORE
    # =========================================================================

    def snapshot(self) -> Tuple[bool, str]:
        """
        Сохранить текущее состояние iptables в файл.

        Returns:
            Tuple[bool, str]: (success, message)
        """
        result = subprocess.run(
            ['iptables-save', '-t', 'nat'],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode != 0:
            return False, "Failed to save iptables state"

        try:
            with open(SNAPSHOT_FILE, 'w') as f:
                f.write(result.stdout)
            logger.info(f"iptables snapshot saved to {SNAPSHOT_FILE}")
            return True, f"Snapshot saved ({len(result.stdout)} bytes)"
        except Exception as e:
            return False, str(e)

    def restore(self) -> Tuple[bool, str]:
        """
        Восстановить iptables из сохранённого снапшота.

        Returns:
            Tuple[bool, str]: (success, message)
        """
        if not os.path.exists(SNAPSHOT_FILE):
            return False, "No snapshot file found"

        try:
            with open(SNAPSHOT_FILE, 'r') as f:
                rules = f.read()

            result = subprocess.run(
                ['iptables-restore'],
                input=rules, capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                logger.info("iptables restored from snapshot")
                return True, "Restored from snapshot"
            return False, result.stderr.strip()
        except Exception as e:
            return False, str(e)

    def delete_snapshot(self) -> None:
        """Удалить файл снапшота."""
        if os.path.exists(SNAPSHOT_FILE):
            os.remove(SNAPSHOT_FILE)

    # =========================================================================
    # STATUS / INFO
    # =========================================================================

    def get_rules(self, table: str = 'nat', chain: str = 'PREROUTING') -> str:
        """
        Получить список правил в читаемом формате.

        Returns:
            str: Список правил
        """
        result = subprocess.run(
            ['iptables', '-t', table, '-L', chain, '-n', '-v'],
            capture_output=True, text=True, timeout=5
        )
        return result.stdout if result.returncode == 0 else ''

    def get_rules_count(self, table: str = 'nat', chain: str = 'PREROUTING') -> int:
        """
        Получить количество правил в цепочке.

        Returns:
            int: Количество правил
        """
        result = subprocess.run(
            ['iptables', '-t', table, '-L', chain, '-n'],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode != 0:
            return 0
        lines = result.stdout.strip().split('\n')
        return max(0, len(lines) - 2)  # Минус заголовок и итоговая строка


# =============================================================================
# MODULE-LEVEL CONVENIENCE FUNCTIONS
# =============================================================================

def get_iptables_manager() -> IptablesManager:
    """Получить экземпляр менеджера (singleton pattern)."""
    if not hasattr(get_iptables_manager, '_instance'):
        get_iptables_manager._instance = IptablesManager()
    return get_iptables_manager._instance


def ensure_base_ipsets() -> None:
    """Ensure all required base ipsets exist."""
    for ipset_name in ['unblocksh', 'unblockvless', 'unblocktroj']:
        try:
            subprocess.run(
                ['ipset', 'create', ipset_name, 'hash:net', '-exist'],
                capture_output=True, timeout=5
            )
            logger.debug(f"IPset ready: {ipset_name}")
        except Exception as e:
            logger.warning(f"Failed to ensure ipset {ipset_name}: {e}")


def detect_local_ip() -> str:
    """Detect local IP from br0 interface."""
    try:
        result = subprocess.run(
            ['ip', '-4', 'addr', 'show', 'br0'],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            import re
            match = re.search(r'inet (\d+\.\d+\.\d+\.\d+)', result.stdout)
            if match:
                ip = match.group(1)
                if ip.startswith(('192.168.', '10.', '172.')):
                    logger.debug(f"Detected local IP: {ip}")
                    return ip
    except Exception as e:
        logger.warning(f"Failed to detect local IP: {e}")
    return "192.168.1.1"


def is_service_running(pattern: str) -> bool:
    """Check if process is running by pattern."""
    try:
        for pid_dir in os.listdir('/proc'):
            if not pid_dir.isdigit():
                continue
            try:
                with open(f'/proc/{pid_dir}/cmdline', 'rb') as f:
                    if pattern.encode() in f.read():
                        return True
            except (FileNotFoundError, PermissionError):
                continue
    except Exception:
        pass
    return False


def is_dnsmasq_running() -> bool:
    """Check if dnsmasq process is running."""
    return is_service_running('dnsmasq')


VPN_SERVICES = ['IKE', 'SSTP', 'OpenVPN', 'Wireguard', 'VPNL2TP']
RT_TABLES_FILE = '/opt/etc/iproute2/rt_tables'


def get_vpn_interfaces() -> List[str]:
    """Get list of active VPN interfaces via NDMS API."""
    try:
        result = subprocess.run(
            ['curl', '-s', 'localhost:79/rci/show/interface'],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode != 0:
            return []
        
        import re
        interfaces = []
        for vpn in VPN_SERVICES:
            pattern = rf'"{vpn}"[^}]*"id"\s*:\s*"([^"]+)"'
            matches = re.findall(pattern, result.stdout)
            interfaces.extend(matches)
        
        return list(set(interfaces))
    except Exception as e:
        logger.warning(f"Failed to get VPN interfaces: {e}")
        return []


def get_vpn_info(vpn_id: str) -> Optional[Dict[str, str]]:
    """Get VPN interface info (IP, type, name) via NDMS API."""
    try:
        addr_result = subprocess.run(
            ['curl', '-s', f'localhost:79/rci/show/interface/{vpn_id}/address'],
            capture_output=True, text=True, timeout=5
        )
        vpn_ip = addr_result.stdout.strip().strip('"')
        
        if not vpn_ip:
            return None
        
        type_result = subprocess.run(
            ['ip', 'addr', 'show'],
            capture_output=True, text=True, timeout=5
        )
        vpn_type = 'unknown'
        for line in type_result.stdout.split('\n'):
            if vpn_ip in line:
                parts = line.split()
                if parts:
                    vpn_type = parts[0]
                    break
        
        desc_result = subprocess.run(
            ['curl', '-s', f'localhost:79/rci/show/interface/{vpn_id}/description'],
            capture_output=True, text=True, timeout=5
        )
        vpn_name = desc_result.stdout.strip().strip('"')
        
        return {
            'ip': vpn_ip,
            'type': vpn_type,
            'name': vpn_name,
            'ipset_name': f'unblockvpn-{vpn_name}-{vpn_id}'
        }
    except Exception as e:
        logger.warning(f"Failed to get VPN info for {vpn_id}: {e}")
        return None


def ensure_rt_tables() -> None:
    """Ensure rt_tables file exists."""
    os.makedirs('/opt/etc/iproute2', exist_ok=True)
    if not os.path.exists(RT_TABLES_FILE):
        open(RT_TABLES_FILE, 'a').close()
    os.chmod(RT_TABLES_FILE, 0o755)


def get_vpn_table_name(vpn_id: str) -> str:
    """Convert VPN ID to table name (lowercase)."""
    return vpn_id.lower()


def get_vpn_table_id(vpn_table: str) -> Optional[int]:
    """Get fwmark ID for VPN table."""
    try:
        with open(RT_TABLES_FILE, 'r') as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) >= 2 and parts[1] == vpn_table:
                    return int(parts[0])
    except Exception:
        pass
    return None


def register_vpn_table(vpn_id: str) -> int:
    """Register VPN in rt_tables, return fwmark ID."""
    ensure_rt_tables()
    vpn_table = get_vpn_table_name(vpn_id)
    
    existing_id = get_vpn_table_id(vpn_table)
    if existing_id:
        return existing_id
    
    max_id = 1000
    try:
        with open(RT_TABLES_FILE, 'r') as f:
            for line in f:
                parts = line.strip().split()
                if parts and parts[0].isdigit():
                    max_id = max(max_id, int(parts[0]))
    except Exception:
        pass
    
    new_id = max_id + 1
    
    try:
        with open(RT_TABLES_FILE, 'a') as f:
            f.write(f"{new_id} {vpn_table}\n")
        logger.info(f"Registered VPN table: {vpn_table} -> {new_id}")
    except Exception as e:
        logger.warning(f"Failed to register VPN table: {e}")
    
    return new_id


def setup_vpn_routes(vpn_id: str, vpn_ip: str, vpn_type: str) -> bool:
    """Setup routing for VPN (routes + ipset)."""
    vpn_table = get_vpn_table_name(vpn_id)
    fwmark_id = register_vpn_table(vpn_id)
    fwmark_hex = f"0x{fwmark_id}"
    
    subprocess.run(['ip', '-4', 'route', 'del', 'table', vpn_table, 'default'],
                   capture_output=True, timeout=5)
    
    result = subprocess.run(
        ['ip', '-4', 'route', 'add', 'table', vpn_table, 'default', 'via', vpn_ip, 'dev', vpn_type],
        capture_output=True, timeout=5
    )
    
    main_routes_result = subprocess.run(
        ['ip', '-4', 'route', 'show', 'table', 'main'],
        capture_output=True, text=True, timeout=5
    )
    
    if main_routes_result.returncode == 0:
        for line in main_routes_result.stdout.strip().split('\n'):
            if line and not line.startswith('default'):
                parts = line.split()
                if parts:
                    route_cmd = ['ip', '-4', 'route', 'add', 'table', vpn_table] + parts
                    subprocess.run(route_cmd, capture_output=True, timeout=5)
    
    subprocess.run(
        ['ip', '-4', 'rule', 'add', 'fwmark', fwmark_hex, 'lookup', vpn_table, 'priority', '1778'],
        capture_output=True, timeout=5
    )
    subprocess.run(['ip', '-4', 'route', 'flush', 'cache'], capture_output=True, timeout=5)
    
    vpn_name = subprocess.run(
        ['curl', '-s', f'localhost:79/rci/show/interface/{vpn_id}/description'],
        capture_output=True, text=True, timeout=5
    ).stdout.strip().strip('"')
    
    ipset_name = f"unblockvpn-{vpn_name}-{vpn_id}"
    subprocess.run(
        ['ipset', 'create', ipset_name, 'hash:net', '-exist'],
        capture_output=True, timeout=5
    )
    
    vpn_file = f"/opt/etc/unblock/vpn-{vpn_name}-{vpn_id}.txt"
    os.makedirs('/opt/etc/unblock', exist_ok=True)
    open(vpn_file, 'a').close()
    os.chmod(vpn_file, 0o644)
    
    logger.info(f"VPN routes setup: {vpn_id} ({vpn_name}) {vpn_ip} via {vpn_type}")
    return True


def remove_vpn_routes(vpn_id: str) -> bool:
    """Remove routing for VPN."""
    vpn_table = get_vpn_table_name(vpn_id)
    fwmark_id = get_vpn_table_id(vpn_table)
    
    subprocess.run(
        ['ip', '-4', 'rule', 'del', 'from', 'all', 'table', vpn_table, 'priority', '1778'],
        capture_output=True, timeout=5
    )
    
    if fwmark_id:
        subprocess.run(
            ['ip', '-4', 'rule', 'del', 'fwmark', f"0x{fwmark_id}", 'lookup', vpn_table, 'priority', '1778'],
            capture_output=True, timeout=5
        )
    
    subprocess.run(['ip', '-4', 'route', 'flush', 'table', vpn_table], capture_output=True, timeout=5)
    
    logger.info(f"VPN routes removed: {vpn_id}")
    return True


def sync_vpn_interfaces() -> None:
    """Sync all active VPN interfaces (call from S99unblock hook)."""
    ensure_rt_tables()
    
    vpn_interfaces = get_vpn_interfaces()
    logger.info(f"Syncing VPN interfaces: {vpn_interfaces}")
    
    for vpn_id in vpn_interfaces:
        info = get_vpn_info(vpn_id)
        if info:
            setup_vpn_routes(vpn_id, info['ip'], info['type'])


def apply_all_redirects() -> Tuple[bool, str]:
    """
    Apply all redirect rules (replaces 100-redirect.sh).
    
    Returns:
        Tuple[bool, str]: (success, message)
    """
    logger.info("[REDIRECT] Applying all redirect rules...")
    
    ensure_base_ipsets()
    local_ip = detect_local_ip()
    
    errors = []
    
    # DNS redirect to dnsmasq:5353
    if is_dnsmasq_running():
        ok, msg = get_iptables_manager().add_dns_redirect(local_ip, 5353)
        if ok:
            logger.info("[REDIRECT] DNS redirect enabled")
        else:
            errors.append(f"DNS redirect: {msg}")
    else:
        logger.warning("[REDIRECT] dnsmasq not running, skipping DNS redirect")
    
    # VPN redirects
    redirects = [
        ('unblocksh', 1082),
        ('unblockvless', 10810),
        ('unblocktroj', 10829),
    ]
    
    for ipset_name, port in redirects:
        pattern = {'unblocksh': 'ss-redir', 'unblockvless': 'xray', 'unblocktroj': 'trojan'}.get(ipset_name, '')
        
        if pattern and not is_service_running(pattern):
            logger.info(f"[REDIRECT] Service for {ipset_name} not running, skipping")
            continue
        
        ok, msg = get_iptables_manager().add_vpn_redirect(ipset_name, port)
        if ok:
            logger.info(f"[REDIRECT] Added {ipset_name} -> {port}")
        else:
            errors.append(f"{ipset_name}: {msg}")
    
    if errors:
        return False, f"Errors: {'; '.join(errors)}"
    return True, "All redirects applied"


# Convenience wrappers for backward compatibility with shell scripts
def add_vpn_redirect(ipset_name: str, port: int) -> Tuple[bool, str]:
    return get_iptables_manager().add_vpn_redirect(ipset_name, port)


def remove_vpn_redirect(ipset_name: str, port: int) -> Tuple[bool, str]:
    return get_iptables_manager().remove_vpn_redirect(ipset_name, port)


def add_dns_redirect(local_ip: str, target_port: int) -> Tuple[bool, str]:
    return get_iptables_manager().add_dns_redirect(local_ip, target_port)


def remove_dns_redirect(local_ip: str, target_port: int) -> Tuple[bool, str]:
    return get_iptables_manager().remove_dns_redirect(local_ip, target_port)


def flush_all_flymybyte_rules() -> Tuple[bool, str]:
    return get_iptables_manager().flush_all_flymybyte_rules()


def snapshot() -> Tuple[bool, str]:
    return get_iptables_manager().snapshot()


def restore() -> Tuple[bool, str]:
    return get_iptables_manager().restore()
