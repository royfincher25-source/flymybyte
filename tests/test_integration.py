"""
FlyMyByte — Integration and unit tests for Blueprints, services, and optimizations.
"""
import pytest
import sys
import os
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'web_ui'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'web_ui', 'core'))


# =============================================================================
# BLUEPRINT TESTS
# =============================================================================

def test_routes_service_exists():
    """Test that routes_service.py exists and has main blueprint"""
    from routes_service import bp
    assert bp.name == 'main'
    assert bp.url_prefix is None


def test_routes_keys_exists():
    """Test that keys routes exist in routes_service.py"""
    from routes_service import keys, key_config
    assert keys is not None
    assert key_config is not None


def test_routes_bypass_exists():
    """Test that bypass routes exist in routes_service.py"""
    from routes_service import bypass, view_bypass, add_to_bypass, remove_from_bypass
    assert bypass is not None
    assert view_bypass is not None
    assert add_to_bypass is not None
    assert remove_from_bypass is not None


def test_blueprint_routes_registered():
    """Test that all routes are registered in routes_service.py"""
    service_file = os.path.join(os.path.dirname(__file__), '..', 'src', 'web_ui', 'routes_service.py')
    with open(service_file, 'r', encoding='utf-8') as f:
        content = f.read()
    # Service routes
    assert "@bp.route('/')" in content
    assert "@bp.route('/login'" in content
    assert "@bp.route('/service/updates/run'" in content
    assert "@bp.route('/dns-spoofing'" in content
    assert "@bp.route('/api/system/stats'" in content
    # Keys routes
    assert "@bp.route('/keys')" in content
    assert "@bp.route('/keys/<service>'" in content
    # Bypass routes
    assert "@bp.route('/bypass')" in content
    assert "@bp.route('/bypass/catalog'" in content
    assert "@bp.route('/bypass/view/<filename>')" in content
    assert "@bp.route('/bypass/<filename>/add'" in content
    assert "@bp.route('/bypass/<filename>/remove'" in content


# =============================================================================
# CSRF PROTECTION TESTS
# =============================================================================

def test_csrf_field_in_templates():
    """Test that CSRF field macro exists in macros.html"""
    macros_file = os.path.join(os.path.dirname(__file__), '..', 'src', 'web_ui', 'templates', 'macros.html')
    with open(macros_file, 'r', encoding='utf-8') as f:
        content = f.read()
    assert 'csrf_field' in content
    assert 'csrf_token()' in content


def test_flash_messages_macro():
    """Test that flash messages macro exists"""
    macros_file = os.path.join(os.path.dirname(__file__), '..', 'src', 'web_ui', 'templates', 'macros.html')
    with open(macros_file, 'r', encoding='utf-8') as f:
        content = f.read()
    assert 'flash_messages' in content
    assert 'get_flashed_messages' in content


def test_service_icon_macro():
    """Test that service icon macro covers all services"""
    macros_file = os.path.join(os.path.dirname(__file__), '..', 'src', 'web_ui', 'templates', 'macros.html')
    with open(macros_file, 'r', encoding='utf-8') as f:
        content = f.read()
    assert 'service_icon' in content
    for svc in ['vless', 'hysteria2', 'shadowsocks', 'trojan', 'tor']:
        assert f"'{svc}'" in content or f'"{svc}"' in content


# =============================================================================
# OPTIMIZATION TESTS
# =============================================================================

def test_thread_pool_workers_increased():
    """Test that ThreadPoolExecutor uses 4 workers"""
    from constants import THREAD_POOL_WORKERS
    assert THREAD_POOL_WORKERS == 4


def test_cache_uses_ordered_dict():
    """Test that Cache class uses OrderedDict for O(1) LRU operations"""
    from collections import OrderedDict
    from utils import Cache
    assert isinstance(Cache._access_order, OrderedDict)


def test_cache_lru_eviction():
    """Test LRU eviction with OrderedDict"""
    from utils import Cache

    Cache.clear()
    Cache.MAX_ENTRIES = 3

    Cache.set('a', 1)
    Cache.set('b', 2)
    Cache.set('c', 3)

    # Access 'a' to make it most recently used
    Cache.get('a')

    # Add 'd' — should evict 'b' (least recently used)
    Cache.set('d', 4)

    assert Cache.get('a') == 1  # Still there (was accessed)
    assert Cache.get('b') is None  # Evicted (LRU)
    assert Cache.get('c') == 3  # Still there
    assert Cache.get('d') == 4  # Just added

    Cache.MAX_ENTRIES = 30  # Reset


def test_memory_stats_caching():
    """Test that get_memory_stats caches results (skipped on Windows without /proc/meminfo)"""
    if not os.path.exists('/proc/meminfo'):
        pytest.skip('/proc/meminfo not available')
    from utils import get_memory_stats, _memory_stats_cache

    # First call should populate cache
    result1 = get_memory_stats()
    assert _memory_stats_cache['data'] is not None

    # Second call should return cached data
    result2 = get_memory_stats()
    assert result1 is result2  # Same object (cached)


def test_update_progress_auto_reset():
    """Test that UpdateProgress auto-resets after TTL"""
    from update_progress import UpdateProgress

    progress = UpdateProgress()
    progress.reset()

    progress.start_update(total_files=10)
    assert progress.status == 'starting'

    progress.complete()
    assert progress.status == 'complete'
    assert progress._completed_at is not None

    # Manually advance time past TTL
    progress._completed_at = time.time() - 400  # 400 seconds ago (> 300 TTL)

    status = progress.get_status()
    assert status['status'] == 'idle'  # Auto-reset


def test_disk_space_check_in_updates():
    """Test that disk space check exists in update service"""
    update_file = os.path.join(os.path.dirname(__file__), '..', 'src', 'web_ui', 'core', 'update_service.py')
    service_file = os.path.join(os.path.dirname(__file__), '..', 'src', 'web_ui', 'routes_service.py')
    with open(update_file, 'r', encoding='utf-8') as f:
        update_content = f.read()
    with open(service_file, 'r', encoding='utf-8') as f:
        service_content = f.read()
    combined = update_content + service_content
    assert 'statvfs' in combined
    assert 'free_mb' in combined
    assert 'Insufficient disk space' in combined or 'Недостаточно места' in combined


def test_parallel_downloads_in_updates():
    """Test that parallel downloads are used in update process"""
    update_file = os.path.join(os.path.dirname(__file__), '..', 'src', 'web_ui', 'core', 'update_service.py')
    with open(update_file, 'r', encoding='utf-8') as f:
        content = f.read()
    assert 'ThreadPoolExecutor' in content
    assert 'max_workers=3' in content


def test_pgrep_service_status():
    """Test that pgrep is used for service status check"""
    services_file = os.path.join(os.path.dirname(__file__), '..', 'src', 'web_ui', 'core', 'services.py')
    with open(services_file, 'r', encoding='utf-8') as f:
        content = f.read()
    assert 'pgrep' in content


def test_sigterm_handler():
    """Test that SIGTERM handler is registered in app.py"""
    app_file = os.path.join(os.path.dirname(__file__), '..', 'src', 'web_ui', 'app.py')
    with open(app_file, 'r', encoding='utf-8') as f:
        content = f.read()
    assert 'signal.SIGTERM' in content
    assert 'graceful_shutdown' in content


def test_reboot_confirmation_modal():
    """Test that reboot confirmation modal exists in service.html"""
    template_file = os.path.join(os.path.dirname(__file__), '..', 'src', 'web_ui', 'templates', 'service.html')
    with open(template_file, 'r', encoding='utf-8') as f:
        content = f.read()
    assert 'rebootModal' in content
    assert 'openModal' in content
    assert 'closeModal' in content
    assert 'Подтверждение' in content


def test_constants_has_init_scripts():
    """Test that constants.py has all init scripts defined"""
    from constants import INIT_SCRIPTS
    expected = ['vless', 'hysteria2', 'shadowsocks', 'trojan', 'tor', 'unblock', 'dnsmasq', 'web_ui']
    for svc in expected:
        assert svc in INIT_SCRIPTS


def test_constants_has_config_paths():
    """Test that constants.py has all config paths defined"""
    from constants import CONFIG_PATHS
    expected = ['vless', 'hysteria2', 'shadowsocks', 'trojan', 'tor', 'dnsmasq']
    for svc in expected:
        assert svc in CONFIG_PATHS


def test_app_config_uses_constants():
    """Test that app_config.py imports from constants.py"""
    config_file = os.path.join(os.path.dirname(__file__), '..', 'src', 'web_ui', 'core', 'app_config.py')
    with open(config_file, 'r', encoding='utf-8') as f:
        content = f.read()
    assert 'from .constants import' in content
    assert 'DEFAULT_WEB_HOST' in content


def test_dns_spoofing_uses_pgrep():
    """Test that dns_spoofing.py uses pgrep instead of 'ps | grep'"""
    dns_file = os.path.join(os.path.dirname(__file__), '..', 'src', 'web_ui', 'core', 'dns_spoofing.py')
    with open(dns_file, 'r', encoding='utf-8') as f:
        content = f.read()
    assert "['pgrep', 'dnsmasq']" in content
    assert "['ps', '|', 'grep'" not in content


def test_dns_spoofing_threading_at_top():
    """Test that threading is imported at the top of dns_spoofing.py"""
    dns_file = os.path.join(os.path.dirname(__file__), '..', 'src', 'web_ui', 'core', 'dns_spoofing.py')
    with open(dns_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    # threading import should be in first 40 lines
    threading_line = None
    for i, line in enumerate(lines):
        if 'import threading' in line and not line.strip().startswith('#'):
            threading_line = i
            break

    assert threading_line is not None, "threading import not found"
    assert threading_line < 40, f"threading import at line {threading_line}, should be < 40"


def test_dns_spoofing_singleton_class_level_lock():
    """Test that DNSSpoofing has class-level lock"""
    from dns_spoofing import DNSSpoofing
    assert DNSSpoofing._lock is not None


def test_macros_html_exists():
    """Test that macros.html template exists and has all macros"""
    macros_file = os.path.join(os.path.dirname(__file__), '..', 'src', 'web_ui', 'templates', 'macros.html')
    assert os.path.exists(macros_file)

    with open(macros_file, 'r', encoding='utf-8') as f:
        content = f.read()

    expected_macros = [
        'csrf_field',
        'flash_messages',
        'page_header',
        'service_icon',
        'info_card',
        'action_card',
        'table_card',
        'alert',
        'menu_card',
    ]
    for macro in expected_macros:
        assert macro in content, f"Macro '{macro}' not found in macros.html"


def test_base_html_uses_macros():
    """Test that base.html imports and uses macros"""
    base_file = os.path.join(os.path.dirname(__file__), '..', 'src', 'web_ui', 'templates', 'base.html')
    with open(base_file, 'r', encoding='utf-8') as f:
        content = f.read()
    assert 'import "macros.html"' in content
    assert 'm.flash_messages()' in content
