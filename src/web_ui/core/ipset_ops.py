"""
IPSET operations module.

Contains bulk ipset operations extracted from services.py to break
circular dependency with dns_ops.py.
"""

import logging
import subprocess
from typing import List, Tuple

from .constants import IPSET_MAX_BULK_ENTRIES

logger = logging.getLogger(__name__)


# ===========================================================================
# Sanitization helpers
# ===========================================================================

def _sanitize_for_ipset(entry: str) -> str:
    """Sanitize ipset entry (strip whitespace, reject null bytes)."""
    if not entry or not isinstance(entry, str):
        raise ValueError("Invalid entry type")
    cleaned = entry.strip()
    if '\0' in cleaned or '\n' in cleaned or '\r' in cleaned:
        raise ValueError("Entry contains control characters")
    return cleaned


def _is_valid_ipset_entry(entry: str) -> bool:
    """Basic validation — IP or domain string."""
    import re
    # IPv4
    if re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}(/\d{1,2})?$', entry):
        return True
    # IPv6
    if ':' in entry and re.match(r'^[0-9a-fA-F:]+(/\d{1,3})?$', entry):
        return True
    return False


# ===========================================================================
# Bulk operations
# ===========================================================================

def bulk_add_to_ipset(setname: str, entries: List[str]) -> Tuple[bool, str]:
    """Bulk add entries to ipset using 'ipset restore'."""
    if not entries:
        logger.info(f"[IPSET] {setname}: no entries to add")
        return True, "No entries"

    if len(entries) > IPSET_MAX_BULK_ENTRIES:
        logger.error(f"[IPSET] {setname}: too many entries ({len(entries)} > {IPSET_MAX_BULK_ENTRIES})")
        return False, f"Too many entries (max {IPSET_MAX_BULK_ENTRIES})"

    commands = []
    skipped = 0
    for entry in entries:
        try:
            sanitized = _sanitize_for_ipset(entry)
            if _is_valid_ipset_entry(sanitized):
                commands.append(f"add {setname} {sanitized}")
            else:
                skipped += 1
        except ValueError:
            skipped += 1

    if skipped > 0:
        logger.warning(f"[IPSET] {setname}: skipped {skipped} invalid entries")

    if not commands:
        logger.warning(f"[IPSET] {setname}: no valid entries after sanitization")
        return True, "No valid entries"

    cmd_text = "\n".join(commands)
    try:
        # FIX: Flush set before restore to avoid "already added" errors
        subprocess.run(
            ['ipset', 'flush', setname],
            capture_output=True,
            text=True,
            timeout=10
        )

        result = subprocess.run(
            ['ipset', 'restore', '-exist'],
            input=cmd_text,
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode == 0:
            logger.info(f"[IPSET] {setname}: successfully added {len(commands)} entries")
            return True, f"Added {len(commands)} entries"
        else:
            logger.error(f"[IPSET] {setname} restore failed: {result.stderr[:200]}")
            return False, result.stderr[:200]

    except subprocess.TimeoutExpired:
        logger.error(f"[IPSET] {setname}: timeout after 30s")
        return False, "Timeout"
    except FileNotFoundError:
        return False, "ipset not installed"
    except Exception as e:
        logger.error(f"[IPSET] {setname} exception: {e}")
        return False, str(e)


def bulk_remove_from_ipset(setname: str, entries: List[str]) -> Tuple[bool, str]:
    """Bulk remove entries from ipset using 'ipset restore'."""
    if not entries:
        return True, "No entries"

    commands = []
    for entry in entries:
        try:
            sanitized = _sanitize_for_ipset(entry)
            if _is_valid_ipset_entry(sanitized):
                commands.append(f"del {setname} {sanitized}")
        except ValueError:
            pass

    if not commands:
        return True, "No valid entries"

    cmd_text = "\n".join(commands)
    try:
        result = subprocess.run(
            ['ipset', 'restore'],
            input=cmd_text,
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode == 0:
            logger.info(f"[IPSET] {setname}: successfully removed {len(commands)} entries")
            return True, f"Removed {len(commands)} entries"
        else:
            return False, result.stderr[:200]

    except subprocess.TimeoutExpired:
        return False, "Timeout"
    except FileNotFoundError:
        return False, "ipset not installed"
    except Exception as e:
        logger.error(f"[IPSET] {setname} exception: {e}")
        return False, str(e)


def ensure_ipset_exists(setname: str, settype: str = 'hash:ip') -> Tuple[bool, str]:
    """Ensure ipset exists, create if not."""
    try:
        result = subprocess.run(
            ['ipset', 'list', setname],
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode == 0:
            return True, "Exists"

        result = subprocess.run(
            ['ipset', 'create', setname, settype, 'maxelem', '1048576'],
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode == 0:
            logger.info(f"[IPSET] {setname}: created successfully")
            return True, "Created"
        else:
            return False, result.stderr[:200]

    except subprocess.TimeoutExpired:
        return False, "Timeout"
    except FileNotFoundError:
        return False, "ipset not installed"
    except Exception as e:
        logger.error(f"[IPSET] {setname} exception: {e}")
        return False, str(e)
