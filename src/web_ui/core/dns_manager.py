"""
DNS Manager - dnsmasq configuration management

Updates dnsmasq config when DNS server changes.
Optimized for embedded devices (128MB RAM).
"""
import subprocess
import logging
from pathlib import Path
from typing import Tuple

logger = logging.getLogger(__name__)

# dnsmasq configuration path on Keenetic (Entware)
DNSMASQ_CONFIG = '/opt/etc/dnsmasq.conf'

# Command to restart dnsmasq on Keenetic
DNSMASQ_RESTART_CMD = ['/opt/etc/init.d/S56dnsmasq', 'restart']


def update_dnsmasq_dns(server_host: str) -> Tuple[bool, str]:
    """
    Update dnsmasq to use specific DNS server.

    Args:
        server_host: DNS server IP address

    Returns:
        Tuple of (success: bool, message: str)

    Notes:
        - Atomic write via .tmp file to prevent corruption
        - Automatically restarts dnsmasq after config change
        - Removes existing server= lines before adding new one
    """
    try:
        # Read current config
        config_path = Path(DNSMASQ_CONFIG)
        if not config_path.exists():
            # dnsmasq not installed - this is OK, just skip update
            logger.warning(f"dnsmasq config not found: {DNSMASQ_CONFIG}, skipping update")
            return True, "dnsmasq not configured"

        content = config_path.read_text()

        # Remove existing server lines to avoid duplicates
        lines = []
        for line in content.split('\n'):
            if not line.strip().startswith('server='):
                lines.append(line)

        # Add new server line
        lines.append(f'server={server_host}')

        # Atomic write via .tmp file
        tmp_path = config_path.with_suffix('.tmp')
        tmp_path.write_text('\n'.join(lines))
        tmp_path.replace(config_path)

        logger.debug(f"Written new dnsmasq config with server={server_host}")

        # Restart dnsmasq to apply changes
        result = subprocess.run(
            DNSMASQ_RESTART_CMD,
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode == 0:
            logger.info(f"Updated dnsmasq to use {server_host}")
            return True, "OK"
        else:
            logger.error(f"dnsmasq restart failed: {result.stderr}")
            return False, result.stderr

    except subprocess.TimeoutExpired:
        error_msg = "dnsmasq restart timeout"
        logger.error(error_msg)
        return False, error_msg

    except Exception as e:
        error_msg = f"Error updating dnsmasq: {e}"
        logger.error(error_msg)
        return False, error_msg
