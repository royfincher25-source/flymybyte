"""
DNS Manager - dnsmasq configuration management

Updates dnsmasq config when DNS server changes.
Optimized for embedded devices (128MB RAM).
"""
import subprocess
import logging
from pathlib import Path
from typing import Tuple

from .constants import DNSMASQ_CONFIG, INIT_SCRIPTS

logger = logging.getLogger(__name__)

DNSMASQ_RESTART_CMD = [INIT_SCRIPTS['dnsmasq'], 'restart']


def update_dnsmasq_dns(server_host: str, fallback_servers: list = None) -> Tuple[bool, str]:
    """
    Update dnsmasq to use specific DNS server(s) with fallbacks.

    Args:
        server_host: Primary DNS server IP address
        fallback_servers: List of fallback DNS servers (default: ['1.1.1.1'])

    Returns:
        Tuple of (success: bool, message: str)

    Notes:
        - Atomic write via .tmp file to prevent corruption
        - Automatically restarts dnsmasq after config change
        - Removes existing server= lines before adding new ones
        - Adds fallback servers for redundancy
    """
    if fallback_servers is None:
        fallback_servers = ['1.1.1.1']

    logger.info(f"[DNS] Updating dnsmasq: primary={server_host}, fallbacks={fallback_servers}")

    try:
        # Read current config
        config_path = Path(DNSMASQ_CONFIG)
        if not config_path.exists():
            logger.warning(f"[DNS] dnsmasq config not found: {DNSMASQ_CONFIG}, skipping update")
            return True, "dnsmasq not configured"

        content = config_path.read_text()
        logger.debug(f"[DNS] Read dnsmasq config: {len(content)} bytes")

        # Remove existing server= lines that are bare IPs (not domain-specific server=/domain/...)
        # Keep domain-specific lines like server=/onion/127.0.0.1#9053
        lines = []
        removed_servers = 0
        for line in content.split('\n'):
            stripped = line.strip()
            if stripped.startswith('server=/'):
                lines.append(line)
            elif stripped.startswith('server='):
                removed_servers += 1
                pass
            else:
                lines.append(line)

        logger.debug(f"[DNS] Removed {removed_servers} old server= lines, keeping {len(lines)} lines")

        # Add new server lines: primary + fallbacks
        lines.append(f'server={server_host}')
        for fb in fallback_servers:
            lines.append(f'server={fb}')

        # Atomic write via .tmp file
        tmp_path = config_path.with_suffix('.tmp')
        tmp_path.write_text('\n'.join(lines))
        tmp_path.replace(config_path)

        logger.info(f"[DNS] Written new dnsmasq config: {server_host} + {len(fallback_servers)} fallback(s)")

        # Restart dnsmasq to apply changes
        logger.info(f"[DNS] Restarting dnsmasq: {' '.join(DNSMASQ_RESTART_CMD)}")
        result = subprocess.run(
            DNSMASQ_RESTART_CMD,
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode == 0:
            logger.info(f"[DNS] dnsmasq restarted successfully")
            return True, "OK"
        else:
            error_msg = result.stderr.strip() or result.stdout.strip() or f"dnsmasq restart failed (code {result.returncode})"
            logger.error(f"[DNS] dnsmasq restart failed: {error_msg}")
            return False, error_msg

    except subprocess.TimeoutExpired:
        error_msg = "dnsmasq restart timeout"
        logger.error(f"[DNS] {error_msg}")
        return False, error_msg

    except Exception as e:
        error_msg = f"Error updating dnsmasq: {e}"
        logger.error(f"[DNS] {error_msg}")
        return False, error_msg
