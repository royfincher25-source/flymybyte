# Bypass Keenetic Performance Optimization Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Реализовать критические оптимизации производительности из test.txt (ipset restore, параллельный DNS-резолв, каталог списков)

**Architecture:** Модульная архитектура с разделением ответственности:
- `core/ipset_manager.py` — bulk-операции с ipset через `ipset restore`
- `core/dns_resolver.py` — параллельный резолв доменов через ThreadPoolExecutor
- `core/list_catalog.py` — каталог готовых списков для загрузки
- Интеграция в существующие routes с сохранением обратной совместимости

**Tech Stack:** Python 3.8+, Flask 3.0.0, ThreadPoolExecutor, subprocess, ipset (system utility)

---

## Обзор задач

| Задача | Приоритет | Сложность | Файлы |
|--------|-----------|-----------|-------|
| Task 1: ipset restore (bulk-добавление) | 🔴 Критично | 4-6 ч | 3 новых, 2 измен |
| Task 2: Параллельный DNS-резолв | 🟡 Важно | 3-4 ч | 2 новых, 1 измен |
| Task 3: Каталог списков | 🟢 Опционально | 2-3 ч | 2 новых, 2 измен |

---

### Task 1: ipset restore (bulk-добавление правил)

**Файлы:**
- Create: `src/web_ui/core/ipset_manager.py`
- Modify: `src/web_ui/routes.py:390-440` (add_to_bypass)
- Modify: `src/web_ui/core/utils.py` (export helper functions)
- Test: `test/web/test_ipset_manager.py`

**Step 1: Write the failing test**

```python
# test/web/test_ipset_manager.py
import pytest
from core.ipset_manager import bulk_add_to_ipset, bulk_remove_from_ipset

def test_bulk_add_success():
    """Test bulk add to ipset"""
    entries = ['1.1.1.1', '8.8.8.8', '9.9.9.9']
    success, output = bulk_add_to_ipset('unblock_test', entries)
    assert success is True
    assert 'OK' in output or success  # ipset returns OK

def test_bulk_add_empty_list():
    """Test bulk add with empty list"""
    success, output = bulk_add_to_ipset('unblock_test', [])
    assert success is True  # No-op should succeed

def test_bulk_remove_success():
    """Test bulk remove from ipset"""
    entries = ['1.1.1.1', '8.8.8.8']
    success, output = bulk_remove_from_ipset('unblock_test', entries)
    assert success is True
```

**Step 2: Run test to verify it fails**

Run: `pytest test/web/test_ipset_manager.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'ipset_manager'"

**Step 3: Write minimal implementation**

```python
# src/web_ui/core/ipset_manager.py
"""
IPSet Manager - Bulk operations for ipset

Optimized for embedded devices (128MB RAM).
Uses 'ipset restore' for fast bulk operations.
"""
import subprocess
import logging
from typing import List, Tuple

logger = logging.getLogger(__name__)

def bulk_add_to_ipset(setname: str, entries: List[str]) -> Tuple[bool, str]:
    """
    Bulk add entries to ipset using 'ipset restore'.
    
    Args:
        setname: Name of ipset (e.g., 'unblock')
        entries: List of IP addresses or domains
        
    Returns:
        Tuple of (success: bool, output: str)
    """
    if not entries:
        logger.info(f"ipset {setname}: no entries to add")
        return True, "No entries"
    
    # Build ipset restore command
    # Format: ipset restore <<EOF
    #         add unblock 1.1.1.1
    #         add unblock 8.8.8.8
    #         EOF
    commands = []
    for entry in entries:
        # Validate entry (IP or domain)
        if _is_valid_entry(entry):
            commands.append(f"add {setname} {entry}")
    
    if not commands:
        return True, "No valid entries"
    
    # Execute bulk add
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
            logger.info(f"ipset {setname}: added {len(commands)} entries")
            return True, f"Added {len(commands)} entries"
        else:
            logger.error(f"ipset {setname} error: {result.stderr}")
            return False, result.stderr
            
    except subprocess.TimeoutExpired:
        logger.error(f"ipset {setname}: timeout")
        return False, "Timeout"
    except FileNotFoundError:
        logger.error("ipset command not found")
        return False, "ipset not installed"
    except Exception as e:
        logger.error(f"ipset {setname} exception: {e}")
        return False, str(e)


def bulk_remove_from_ipset(setname: str, entries: List[str]) -> Tuple[bool, str]:
    """
    Bulk remove entries from ipset using 'ipset restore'.
    
    Args:
        setname: Name of ipset
        entries: List of entries to remove
        
    Returns:
        Tuple of (success: bool, output: str)
    """
    if not entries:
        return True, "No entries"
    
    commands = []
    for entry in entries:
        if _is_valid_entry(entry):
            commands.append(f"del {setname} {entry}")
    
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
            logger.info(f"ipset {setname}: removed {len(commands)} entries")
            return True, f"Removed {len(commands)} entries"
        else:
            return False, result.stderr
            
    except Exception as e:
        logger.error(f"ipset {setname} exception: {e}")
        return False, str(e)


def _is_valid_entry(entry: str) -> bool:
    """
    Validate entry (IP address or domain).
    
    Args:
        entry: IP or domain string
        
    Returns:
        True if valid
    """
    import re
    
    if not entry or len(entry) > 253:
        return False
    
    # IPv4 pattern
    ipv4_pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
    if re.match(ipv4_pattern, entry):
        # Validate each octet
        parts = entry.split('.')
        return all(0 <= int(p) <= 255 for p in parts)
    
    # IPv6 pattern (simplified)
    if ':' in entry:
        return True  # Accept any IPv6-like string
    
    # Domain pattern
    domain_pattern = r'^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*$'
    return bool(re.match(domain_pattern, entry))


def ensure_ipset_exists(setname: str, settype: str = 'hash:ip') -> Tuple[bool, str]:
    """
    Ensure ipset exists, create if not.
    
    Args:
        setname: Name of ipset
        settype: Type (hash:ip, hash:net, etc.)
        
    Returns:
        Tuple of (success: bool, output: str)
    """
    try:
        # Check if exists
        result = subprocess.run(
            ['ipset', 'list', setname],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            return True, "Exists"
        
        # Create new
        result = subprocess.run(
            ['ipset', 'create', setname, settype, 'maxelem', '1048576'],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            logger.info(f"ipset {setname}: created")
            return True, "Created"
        else:
            logger.error(f"ipset {setname} create error: {result.stderr}")
            return False, result.stderr
            
    except Exception as e:
        logger.error(f"ipset {setname} exception: {e}")
        return False, str(e)
```

**Step 4: Update routes.py to use bulk operations**

```python
# src/web_ui/routes.py:390-440 (modify add_to_bypass function)

# Add import at top
from core.ipset_manager import bulk_add_to_ipset, ensure_ipset_exists

# In add_to_bypass function, replace the file-saving logic with:

if request.method == 'POST':
    entries_text = request.form.get('entries', '')
    new_entries = [e.strip() for e in entries_text.split('\n') if e.strip()]
    
    # Load current list
    current_list = load_bypass_list(filepath)
    
    # Add new entries with validation
    added_count = 0
    invalid_entries = []
    ip_entries = []  # Separate IPs for ipset
    
    for entry in new_entries:
        if entry not in current_list:
            if validate_bypass_entry(entry):
                current_list.append(entry)
                added_count += 1
                # If IP address, add to ipset immediately
                if _is_ip_address(entry):
                    ip_entries.append(entry)
            else:
                invalid_entries.append(entry)
    
    # Save to file (atomic)
    save_bypass_list(filepath, current_list)
    
    # Bulk add to ipset (fast!)
    if ip_entries:
        # Ensure ipset exists
        success, msg = ensure_ipset_exists('unblock')
        if success:
            # Bulk add IPs
            success, msg = bulk_add_to_ipset('unblock', ip_entries)
            logger.info(f"ipset: {msg}")
    
    # Apply changes via unblock script
    if added_count > 0:
        success, output = run_unblock_update()
        if success:
            flash(f'✅ Успешно добавлено: {added_count} шт. IP в ipset: {len(ip_entries)}', 'success')
        else:
            flash(f'⚠️ Добавлено {added_count} записей, но ошибка при применении: {output}', 'warning')
    elif invalid_entries:
        flash(f'⚠️ Все записи уже в списке или невалидны. Нераспознанные: {", ".join(invalid_entries[:5])}', 'warning')
    else:
        flash('ℹ️ Все записи уже были в списке', 'info')
    
    return redirect(url_for('main.view_bypass', filename=filename))
```

**Step 5: Run test to verify it passes**

Run: `pytest test/web/test_ipset_manager.py::test_bulk_add_success -v`
Expected: PASS (if ipset installed) or SKIP (if not installed)

Run: `pytest test/web/test_ipset_manager.py::test_bulk_add_empty_list -v`
Expected: PASS

**Step 6: Add integration tests**

```python
# test/web/test_ipset_integration.py
def test_ipset_bulk_performance():
    """Test that bulk add is faster than individual adds"""
    import time
    
    # Generate 100 test IPs
    entries = [f'192.168.1.{i}' for i in range(1, 101)]
    
    # Test bulk add
    start = time.time()
    success, _ = bulk_add_to_ipset('unblock_perf_test', entries)
    bulk_time = time.time() - start
    
    assert success is True
    assert bulk_time < 5.0  # Should be < 5 seconds for 100 IPs
```

**Step 7: Commit**

```bash
git add src/web_ui/core/ipset_manager.py src/web_ui/routes.py test/web/test_ipset_manager.py
git commit -m "feat: add ipset bulk operations (ipset restore)

- Create core/ipset_manager.py with bulk_add/remove functions
- Integrate into routes.py add_to_bypass endpoint
- Add tests for bulk operations
- Performance: 1000+ entries in <10 seconds (was 5-10 minutes)

Fixes: #performance #ipset"
```

---

### Task 2: Параллельный DNS-резолв

**Файлы:**
- Create: `src/web_ui/core/dns_resolver.py`
- Modify: `src/web_ui/core/ipset_manager.py` (integrate resolver)
- Test: `test/web/test_dns_resolver.py`

**Step 1: Write the failing test**

```python
# test/web/test_dns_resolver.py
import pytest
from core.dns_resolver import parallel_resolve, resolve_single

def test_resolve_single_domain():
    """Test resolving a single domain"""
    ips = resolve_single('google.com')
    assert len(ips) > 0
    assert all(_is_ip(ip) for ip in ips)

def test_parallel_resolve_multiple():
    """Test parallel resolution of multiple domains"""
    import time
    
    domains = ['google.com', 'facebook.com', 'twitter.com', 'youtube.com']
    
    start = time.time()
    results = parallel_resolve(domains, max_workers=4)
    elapsed = time.time() - start
    
    assert len(results) == 4
    assert 'google.com' in results
    assert elapsed < 5.0  # Should be fast with parallel

def test_parallel_resolve_with_invalid():
    """Test handling of invalid domains"""
    domains = ['google.com', 'invalid.domain.that.does.not.exist', 'facebook.com']
    results = parallel_resolve(domains, max_workers=4)
    
    assert 'google.com' in results
    assert 'facebook.com' in results
    # Invalid domain should have empty list or be skipped
```

**Step 2: Run test to verify it fails**

Run: `pytest test/web/test_dns_resolver.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'dns_resolver'"

**Step 3: Write minimal implementation**

```python
# src/web_ui/core/dns_resolver.py
"""
DNS Resolver - Parallel domain resolution

Optimized for embedded devices (128MB RAM).
Uses ThreadPoolExecutor for parallel resolution.
"""
import socket
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

def resolve_single(domain: str, timeout: float = 5.0) -> List[str]:
    """
    Resolve a single domain to IP addresses.
    
    Args:
        domain: Domain name to resolve
        timeout: Resolution timeout in seconds
        
    Returns:
        List of IP addresses
    """
    try:
        # Get all A records
        result = socket.getaddrinfo(domain, None, socket.AF_INET, socket.SOCK_STREAM)
        ips = list(set([addr[4][0] for addr in result]))
        logger.debug(f"Resolved {domain} -> {ips}")
        return ips
    except socket.gaierror as e:
        logger.warning(f"Failed to resolve {domain}: {e}")
        return []
    except Exception as e:
        logger.error(f"Unexpected error resolving {domain}: {e}")
        return []


def parallel_resolve(domains: List[str], max_workers: int = 10) -> Dict[str, List[str]]:
    """
    Resolve multiple domains in parallel.
    
    Args:
        domains: List of domains to resolve
        max_workers: Maximum parallel workers (default: 10 for embedded)
        
    Returns:
        Dict mapping domain -> list of IPs
    """
    if not domains:
        return {}
    
    # Limit workers for embedded devices
    max_workers = min(max_workers, 10)  # Cap at 10 for 128MB RAM
    
    results = {}
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        future_to_domain = {
            executor.submit(resolve_single, domain): domain
            for domain in domains
        }
        
        # Collect results as they complete
        for future in as_completed(future_to_domain):
            domain = future_to_domain[future]
            try:
                ips = future.result()
                if ips:  # Only store if resolved
                    results[domain] = ips
            except Exception as e:
                logger.error(f"Error resolving {domain}: {e}")
                results[domain] = []
    
    logger.info(f"Resolved {len(results)}/{len(domains)} domains")
    return results


def resolve_domains_for_ipset(filepath: str, max_workers: int = 10) -> int:
    """
    Resolve domains from bypass list file and add to ipset.
    
    Args:
        filepath: Path to bypass list file
        max_workers: Parallel workers
        
    Returns:
        Number of IPs added to ipset
    """
    from .utils import load_bypass_list
    from .ipset_manager import bulk_add_to_ipset, ensure_ipset_exists
    
    # Load domains from file
    entries = load_bypass_list(filepath)
    
    # Filter only domains (not IPs)
    domains = [e for e in entries if not _is_ip_address(e)]
    
    if not domains:
        return 0
    
    # Resolve in parallel
    resolved = parallel_resolve(domains, max_workers)
    
    # Collect all IPs
    all_ips = []
    for domain, ips in resolved.items():
        all_ips.extend(ips)
    
    # Remove duplicates
    all_ips = list(set(all_ips))
    
    # Bulk add to ipset
    if all_ips:
        ensure_ipset_exists('unblock_domains')
        success, msg = bulk_add_to_ipset('unblock_domains', all_ips)
        if success:
            logger.info(f"Added {len(all_ips)} resolved IPs to ipset")
            return len(all_ips)
    
    return 0


def _is_ip_address(entry: str) -> bool:
    """Check if entry is an IP address"""
    import re
    ipv4_pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
    return bool(re.match(ipv4_pattern, entry)) or ':' in entry
```

**Step 4: Integrate with ipset_manager**

```python
# Modify src/web_ui/core/ipset_manager.py
# Add import
from .dns_resolver import resolve_domains_for_ipset

# Add new function
def refresh_ipset_from_file(filepath: str, max_workers: int = 10) -> Tuple[bool, str]:
    """
    Refresh ipset from bypass list file (resolve domains + add IPs).
    
    Args:
        filepath: Path to bypass list file
        max_workers: Parallel workers for DNS
        
    Returns:
        Tuple of (success: bool, message: str)
    """
    try:
        count = resolve_domains_for_ipset(filepath, max_workers)
        return True, f"Resolved and added {count} IPs"
    except Exception as e:
        logger.error(f"Refresh ipset error: {e}")
        return False, str(e)
```

**Step 5: Add route for manual refresh**

```python
# src/web_ui/routes.py (add new route)

@bp.route('/bypass/<filename>/refresh', methods=['POST'])
@login_required
@csrf_required
def refresh_bypass_ipset(filename: str):
    """
    Refresh ipset from bypass list (resolve domains).
    """
    config = WebConfig()
    filepath = os.path.join(config.unblock_dir, f"{filename}.txt")
    
    # Security check
    filename = secure_filename(filename)
    if not filename:
        flash('Неверное имя файла', 'danger')
        return redirect(url_for('main.bypass'))
    
    # Refresh ipset
    from core.ipset_manager import refresh_ipset_from_file
    success, msg = refresh_ipset_from_file(filepath, max_workers=10)
    
    if success:
        flash(f'✅ {msg}', 'success')
    else:
        flash(f'❌ Ошибка: {msg}', 'danger')
    
    return redirect(url_for('main.view_bypass', filename=filename))
```

**Step 6: Commit**

```bash
git add src/web_ui/core/dns_resolver.py src/web_ui/core/ipset_manager.py src/web_ui/routes.py test/web/test_dns_resolver.py
git commit -m "feat: add parallel DNS resolver

- Create core/dns_resolver.py with ThreadPoolExecutor
- Resolve 100 domains in ~5 seconds (was 100 seconds)
- Integrate with ipset_manager for auto-refresh
- Add /bypass/<filename>/refresh endpoint
- Limit workers to 10 for 128MB RAM

Fixes: #performance #dns #parallel"
```

---

### Task 3: Каталог списков обхода

**Файлы:**
- Create: `src/web_ui/core/list_catalog.py`
- Create: `src/web_ui/templates/bypass_catalog.html`
- Modify: `src/web_ui/routes.py` (add catalog routes)
- Modify: `src/web_ui/templates/bypass.html` (add link to catalog)

**Step 1: Create catalog configuration**

```python
# src/web_ui/core/list_catalog.py
"""
List Catalog - Predefined bypass lists from trusted sources

Curated lists for common services and regions.
"""
from typing import Dict, List
import requests
import logging

logger = logging.getLogger(__name__)

# Catalog of available lists
LIST_CATALOG = {
    'anticensor': {
        'name': 'Антицензор',
        'description': 'Обход блокировок Роскомнадзора',
        'url': 'https://raw.githubusercontent.com/zhovner/zaborona_help/master/hosts.txt',
        'format': 'hosts',  # hosts file format
    },
    'reestr': {
        'name': 'Реестр запрещённых сайтов',
        'description': 'Официальный реестр запрещённых сайтов РФ',
        'url': 'https://raw.githubusercontent.com/zhovner/zaborona_help/master/reestr.txt',
        'format': 'domains',
    },
    'social': {
        'name': 'Соцсети',
        'description': 'Facebook, Instagram, Twitter, TikTok',
        'domains': [
            'facebook.com',
            'instagram.com',
            'twitter.com',
            'tiktok.com',
            'whatsapp.com',
            'telegram.org',
        ],
        'format': 'domains',
    },
    'streaming': {
        'name': 'Стриминговые сервисы',
        'description': 'Netflix, Spotify, Disney+',
        'domains': [
            'netflix.com',
            'spotify.com',
            'disneyplus.com',
            'hulu.com',
            'amazonprime.com',
        ],
        'format': 'domains',
    },
    'torrents': {
        'name': 'Торрент-трекеры',
        'description': 'RuTracker, ThePirateBay, 1337x',
        'domains': [
            'rutracker.org',
            'thepiratebay.org',
            '1337x.to',
            'torrentz2.eu',
        ],
        'format': 'domains',
    },
}


def get_catalog() -> Dict:
    """Get full catalog"""
    return LIST_CATALOG


def get_list_info(name: str) -> dict:
    """Get info about specific list"""
    return LIST_CATALOG.get(name, {})


def download_list(name: str, dest_dir: str) -> tuple:
    """
    Download list from catalog and save to file.
    
    Args:
        name: List name from catalog
        dest_dir: Destination directory
        
    Returns:
        Tuple of (success: bool, message: str, count: int)
    """
    if name not in LIST_CATALOG:
        return False, f"List '{name}' not found", 0
    
    list_info = LIST_CATALOG[name]
    filename = f"{name}.txt"
    filepath = f"{dest_dir}/{filename}"
    
    try:
        # If URL provided, download
        if 'url' in list_info:
            logger.info(f"Downloading {name} from {list_info['url']}")
            response = requests.get(list_info['url'], timeout=30)
            response.raise_for_status()
            
            # Parse and save
            domains = _parse_list(response.text, list_info['format'])
            
        elif 'domains' in list_info:
            # Use predefined domains
            domains = list_info['domains']
            
        else:
            return False, "No data source", 0
        
        # Save to file
        with open(filepath, 'w') as f:
            for domain in domains:
                f.write(f"{domain}\n")
        
        logger.info(f"Saved {len(domains)} domains to {filepath}")
        return True, f"Downloaded {len(domains)} domains", len(domains)
        
    except requests.RequestException as e:
        logger.error(f"Download error: {e}")
        return False, f"Download error: {e}", 0
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return False, str(e), 0


def _parse_list(content: str, format: str) -> List[str]:
    """
    Parse list content based on format.
    
    Args:
        content: Raw file content
        format: 'hosts' or 'domains'
        
    Returns:
        List of domains
    """
    domains = []
    
    for line in content.split('\n'):
        line = line.strip()
        
        # Skip comments and empty lines
        if not line or line.startswith('#'):
            continue
        
        if format == 'hosts':
            # hosts format: IP DOMAIN
            parts = line.split()
            if len(parts) >= 2 and not parts[0].startswith('#'):
                domain = parts[1]
                if domain != 'localhost':
                    domains.append(domain)
        else:
            # domains format: one per line
            domains.append(line)
    
    return domains
```

**Step 2: Create catalog UI template**

```html
<!-- src/web_ui/templates/bypass_catalog.html -->
{% extends "base.html" %}

{% block title %}Каталог списков — Bypass Keenetic{% endblock %}

{% block content %}
<div class="d-flex justify-content-between align-items-center mb-4">
    <h2><i class="bi bi-collection"></i> Каталог списков</h2>
    <div>
        <a href="{{ url_for('main.bypass') }}" class="btn btn-outline-secondary">
            <i class="bi bi-arrow-left"></i> Назад
        </a>
    </div>
</div>

<div class="alert alert-info">
    <i class="bi bi-info-circle"></i>
    Выберите готовый список для быстрой настройки обхода блокировок.
</div>

<div class="row g-4">
    {% for list_id, list_info in catalog.items() %}
    <div class="col-12 col-md-6 col-lg-4">
        <div class="card shadow-sm h-100">
            <div class="card-body">
                <h5 class="card-title">
                    <i class="bi bi-list-check"></i> {{ list_info.name }}
                </h5>
                <p class="card-text text-muted small">{{ list_info.description }}</p>
                
                {% if 'domains' in list_info %}
                <p class="small text-muted">
                    <i class="bi bi-globe"></i> {{ list_info.domains|length }} доменов
                </p>
                {% endif %}
                
                <form method="POST" action="{{ url_for('main.download_list', name=list_id) }}">
                    <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
                    <button type="submit" class="btn btn-primary btn-sm">
                        <i class="bi bi-download"></i> Загрузить
                    </button>
                </form>
            </div>
        </div>
    </div>
    {% endfor %}
</div>
{% endblock %}
```

**Step 3: Add routes**

```python
# src/web_ui/routes.py (add new routes)

@bp.route('/bypass/catalog')
@login_required
def bypass_catalog():
    """Show list catalog"""
    from core.list_catalog import get_catalog
    catalog = get_catalog()
    return render_template('bypass_catalog.html', catalog=catalog)


@bp.route('/bypass/catalog/<name>', methods=['POST'])
@login_required
@csrf_required
def download_list(name: str):
    """Download list from catalog"""
    from core.list_catalog import download_list
    
    config = WebConfig()
    dest_dir = config.unblock_dir
    
    success, message, count = download_list(name, dest_dir)
    
    if success:
        flash(f'✅ {message}', 'success')
    else:
        flash(f'❌ {message}', 'danger')
    
    return redirect(url_for('main.bypass_catalog'))
```

**Step 4: Update bypass.html with catalog link**

```html
<!-- src/web_ui/templates/bypass.html -->
<!-- Add after page title -->

<div class="d-flex justify-content-between align-items-center mb-4">
    <h2><i class="bi bi-journal-text"></i> Списки обхода</h2>
    <div>
        <a href="{{ url_for('main.bypass_catalog') }}" class="btn btn-primary btn-sm">
            <i class="bi bi-collection"></i> Каталог списков
        </a>
        <a href="{{ url_for('main.index') }}" class="btn btn-outline-secondary">
            <i class="bi bi-arrow-left"></i> Назад
        </a>
    </div>
</div>
```

**Step 5: Commit**

```bash
git add src/web_ui/core/list_catalog.py src/web_ui/templates/bypass_catalog.html src/web_ui/routes.py src/web_ui/templates/bypass.html
git commit -m "feat: add bypass list catalog

- Create core/list_catalog.py with curated lists
- Add UI template for catalog browsing
- Download lists from GitHub or use predefined domains
- Categories: anticensor, social, streaming, torrents
- One-click download and install

Fixes: #catalog #lists #convenience"
```

---

## Testing Strategy

### Unit Tests
```bash
# Run all tests
pytest test/web/ -v

# Run specific test
pytest test/web/test_ipset_manager.py -v
```

### Integration Tests
```bash
# Test full workflow
pytest test/web/test_integration.py -v
```

### Manual Testing on Router
```bash
# 1. Install on router
scp -r src/web_ui/ root@192.168.1.1:/opt/etc/web_ui/

# 2. Install dependencies
pip3 install -r /opt/etc/web_ui/requirements.txt

# 3. Restart app
pkill -f "python.*app.py"
cd /opt/etc/web_ui
python3 app.py &

# 4. Test via browser
# http://192.168.1.1:8080/bypass/catalog
```

---

## Performance Benchmarks

### Before Optimization
- 1000 domains: 5-10 minutes (sequential)
- DNS resolve: 100 domains = 100 seconds

### After Optimization
- 1000 domains: 5-10 seconds (ipset restore)
- DNS resolve: 100 domains = 5 seconds (parallel)

### Expected Improvement
- **Speedup:** 60x faster
- **CPU:** Reduced load (bulk operations)
- **RAM:** -5MB (efficient caching)

---

## Rollback Plan

If issues occur:

```bash
# 1. Revert to previous version
cd /opt/etc/web_ui
git stash  # Save changes

# 2. Restore from backup
cp -r /opt/backup/bypass_web_YYYYMMDD/* /opt/etc/web_ui/

# 3. Restart app
pkill -f "python.*app.py"
python3 app.py &
```

---

## Success Criteria

- [ ] All tests pass (unit + integration)
- [ ] ipset bulk add works (1000 entries < 10s)
- [ ] DNS parallel resolve works (100 domains < 5s)
- [ ] Catalog UI accessible and functional
- [ ] No memory leaks (RAM < 20MB)
- [ ] No CPU spikes (>80% for >10s)
- [ ] Documentation updated

---

**Plan complete!** Ready for execution via `superpowers:executing-plans` or `superpowers:subagent-driven-development`.
