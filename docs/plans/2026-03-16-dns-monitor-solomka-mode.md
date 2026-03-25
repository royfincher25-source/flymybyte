# DNS Monitoring ("Соломка") Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Реализовать автоматический мониторинг доступности DNS-каналов с переключением на резервный при отказе основного.

**Architecture:** Фоновый поток с периодической проверкой DNS-серверов, автоматическое переключение при обнаружении проблем, UI для управления настройками.

**Tech Stack:** Python 3.8+, threading, socket, subprocess (for dnsmasq), Flask 3.0.0

---

## Обзор задач

| Задача | Приоритет | Сложность | Файлы |
|--------|-----------|-----------|-------|
| Task 1: DNS монитор (фоновый поток) | 🔴 Критично | 6-8 ч | 3 новых, 2 измен |
| Task 2: UI для настроек DNS | 🟡 Важно | 3-4 ч | 2 новых, 2 измен |
| Task 3: Интеграция с dnsmasq | 🟢 Опционально | 2-3 ч | 1 новый, 1 измен |

---

### Task 1: DNS монитор (фоновый поток)

**Файлы:**
- Create: `src/web_ui/core/dns_monitor.py`
- Modify: `src/web_ui/app.py` (start background thread)
- Modify: `src/web_ui/routes.py` (add DNS monitor routes)
- Test: `test/web/test_dns_monitor.py`

**Step 1: Write the failing test**

```python
# test/web/test_dns_monitor.py
import pytest
from core.dns_monitor import DNSMonitor, check_dns_server

def test_check_dns_server_success():
    """Test checking a working DNS server"""
    result = check_dns_server('8.8.8.8', timeout=2)
    assert result['success'] is True
    assert 'latency_ms' in result

def test_check_dns_server_failure():
    """Test checking an unavailable DNS server"""
    result = check_dns_server('192.0.2.1', timeout=2)  # TEST-NET-1 (unreachable)
    assert result['success'] is False

def test_dns_monitor_singleton():
    """Test DNSMonitor is singleton"""
    monitor1 = DNSMonitor()
    monitor2 = DNSMonitor()
    assert monitor1 is monitor2

def test_dns_monitor_start_stop():
    """Test starting and stopping monitor"""
    monitor = DNSMonitor()
    monitor.start()
    assert monitor.is_running() is True
    monitor.stop()
    assert monitor.is_running() is False
```

**Step 2: Run test to verify it fails**

Run: `pytest test/web/test_dns_monitor.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'dns_monitor'"

**Step 3: Write minimal implementation**

```python
# src/web_ui/core/dns_monitor.py
"""
DNS Monitor - Automatic DNS channel availability checking

Monitors primary and backup DNS servers, switches on failure.
Optimized for embedded devices (128MB RAM).
"""
import threading
import time
import socket
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

logger = logging.getLogger(__name__)

# Default DNS servers
DEFAULT_DNS_SERVERS = {
    'primary': [
        {'name': 'Google DNS', 'host': '8.8.8.8', 'port': 53},
        {'name': 'Cloudflare', 'host': '1.1.1.1', 'port': 53},
    ],
    'backup': [
        {'name': 'Quad9', 'host': '9.9.9.9', 'port': 53},
        {'name': 'OpenDNS', 'host': '208.67.222.222', 'port': 53},
    ],
}

CHECK_INTERVAL = 30  # Check every 30 seconds
TIMEOUT = 2  # 2 second timeout per check


def check_dns_server(host: str, port: int = 53, timeout: float = 2.0) -> Dict[str, Any]:
    """
    Check if DNS server is reachable.
    
    Args:
        host: DNS server IP
        port: DNS port (default 53)
        timeout: Timeout in seconds
        
    Returns:
        Dict with success, latency_ms, error
    """
    start_time = time.time()
    try:
        # Simple TCP connection test
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        
        latency_ms = (time.time() - start_time) * 1000
        
        if result == 0:
            return {
                'success': True,
                'latency_ms': round(latency_ms, 2),
                'host': host,
                'port': port,
            }
        else:
            return {
                'success': False,
                'latency_ms': round(latency_ms, 2),
                'host': host,
                'port': port,
                'error': f'Connection failed (code {result})',
            }
            
    except socket.timeout:
        return {
            'success': False,
            'latency_ms': round((time.time() - start_time) * 1000, 2),
            'host': host,
            'port': port,
            'error': 'Timeout',
        }
    except Exception as e:
        return {
            'success': False,
            'latency_ms': round((time.time() - start_time) * 1000, 2),
            'host': host,
            'port': port,
            'error': str(e),
        }


class DNSMonitor:
    """
    Background DNS monitoring service.
    
    Singleton pattern - only one instance allowed.
    Runs in background thread, checks DNS servers periodically.
    """
    
    _instance: Optional['DNSMonitor'] = None
    _lock = threading.Lock()
    
    def __new__(cls) -> 'DNSMonitor':
        """Singleton pattern with thread safety"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialize monitor"""
        if hasattr(self, '_initialized'):
            return
        
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._current_server: Optional[Dict] = None
        self._last_check: Optional[datetime] = None
        self._failures = 0
        self._servers = DEFAULT_DNS_SERVERS.copy()
        
        self._initialized = True
        logger.info("DNSMonitor initialized")
    
    def start(self) -> None:
        """Start background monitoring"""
        if self._running:
            logger.warning("DNSMonitor already running")
            return
        
        self._running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()
        logger.info("DNSMonitor started")
    
    def stop(self) -> None:
        """Stop background monitoring"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("DNSMonitor stopped")
    
    def is_running(self) -> bool:
        """Check if monitor is running"""
        return self._running
    
    def get_status(self) -> Dict[str, Any]:
        """Get current monitor status"""
        return {
            'running': self._running,
            'current_server': self._current_server,
            'last_check': self._last_check.isoformat() if self._last_check else None,
            'failures': self._failures,
        }
    
    def _monitor_loop(self) -> None:
        """Background monitoring loop"""
        logger.info("DNSMonitor loop started")
        
        while self._running:
            try:
                # Check current server
                if self._current_server:
                    result = check_dns_server(
                        self._current_server['host'],
                        self._current_server['port'],
                        TIMEOUT
                    )
                    
                    if result['success']:
                        self._failures = 0
                        logger.debug(f"DNS check OK: {self._current_server['name']} ({result['latency_ms']}ms)")
                    else:
                        self._failures += 1
                        logger.warning(f"DNS check failed: {self._current_server['name']} - {result['error']}")
                        
                        # Switch to backup after 3 consecutive failures
                        if self._failures >= 3:
                            self._switch_to_backup()
                
                else:
                    # No current server - select best from primary
                    self._select_best_primary()
                
                self._last_check = datetime.now()
                
            except Exception as e:
                logger.error(f"DNSMonitor error: {e}")
            
            # Wait for next check
            time.sleep(CHECK_INTERVAL)
    
    def _select_best_primary(self) -> None:
        """Select best primary DNS server"""
        best_server = None
        best_latency = float('inf')
        
        for server in self._servers['primary']:
            result = check_dns_server(server['host'], server['port'], TIMEOUT)
            if result['success'] and result['latency_ms'] < best_latency:
                best_server = server
                best_latency = result['latency_ms']
        
        if best_server:
            self._current_server = best_server
            logger.info(f"Selected primary DNS: {best_server['name']} ({best_latency}ms)")
        else:
            # Try backup
            self._switch_to_backup()
    
    def _switch_to_backup(self) -> None:
        """Switch to backup DNS server"""
        logger.warning("Switching to backup DNS")
        
        for server in self._servers['backup']:
            result = check_dns_server(server['host'], server['port'], TIMEOUT)
            if result['success']:
                self._current_server = server
                self._failures = 0
                logger.info(f"Switched to backup DNS: {server['name']}")
                return
        
        logger.error("No working backup DNS found")
        self._current_server = None


# Global instance for routes
def get_dns_monitor() -> DNSMonitor:
    """Get DNS monitor instance"""
    return DNSMonitor()
```

**Step 4: Run test to verify it passes**

Run: `pytest test/web/test_dns_monitor.py::test_check_dns_server_success -v`
Expected: PASS (if network available)

Run: `pytest test/web/test_dns_monitor.py::test_check_dns_server_failure -v`
Expected: PASS

Run: `pytest test/web/test_dns_monitor.py::test_dns_monitor_singleton -v`
Expected: PASS

Run: `pytest test/web/test_dns_monitor.py::test_dns_monitor_start_stop -v`
Expected: PASS

**Step 5: Integrate with app.py**

```python
# src/web_ui/app.py (modify create_app function)

def create_app(config_class=None):
    """Create and configure the Flask application."""
    global app
    app = Flask(__name__)
    
    # ... existing configuration ...
    
    # Start DNS monitor in background
    from core.dns_monitor import DNSMonitor
    dns_monitor = DNSMonitor()
    dns_monitor.start()
    
    # Register shutdown hook
    import atexit
    @atexit.register
    def cleanup():
        logger.info("Shutting down DNS monitor...")
        dns_monitor.stop()
    
    # ... rest of configuration ...
    
    return app
```

**Step 6: Add routes for DNS monitor control**

```python
# src/web_ui/routes.py (add new routes)

@bp.route('/service/dns-monitor')
@login_required
def dns_monitor_status():
    """Show DNS monitor status"""
    from core.dns_monitor import get_dns_monitor
    monitor = get_dns_monitor()
    status = monitor.get_status()
    return render_template('dns_monitor.html', status=status)

@bp.route('/service/dns-monitor/start', methods=['POST'])
@login_required
@csrf_required
def dns_monitor_start():
    """Start DNS monitor"""
    from core.dns_monitor import get_dns_monitor
    monitor = get_dns_monitor()
    monitor.start()
    flash('✅ DNS monitor started', 'success')
    return redirect(url_for('main.dns_monitor_status'))

@bp.route('/service/dns-monitor/stop', methods=['POST'])
@login_required
@csrf_required
def dns_monitor_stop():
    """Stop DNS monitor"""
    from core.dns_monitor import get_dns_monitor
    monitor = get_dns_monitor()
    monitor.stop()
    flash('ℹ️ DNS monitor stopped', 'info')
    return redirect(url_for('main.dns_monitor_status'))

@bp.route('/service/dns-monitor/check', methods=['POST'])
@login_required
@csrf_required
def dns_monitor_check():
    """Force DNS check"""
    from core.dns_monitor import get_dns_monitor, check_dns_server
    
    monitor = get_dns_monitor()
    
    # Check current server
    if monitor._current_server:
        result = check_dns_server(
            monitor._current_server['host'],
            monitor._current_server['port']
        )
        if result['success']:
            flash(f"✅ DNS OK: {result['latency_ms']}ms", 'success')
        else:
            flash(f"❌ DNS failed: {result['error']}", 'danger')
    else:
        flash('⚠️ No DNS server selected', 'warning')
    
    return redirect(url_for('main.dns_monitor_status'))
```

**Step 7: Commit**

```bash
git add src/web_ui/core/dns_monitor.py src/web_ui/app.py src/web_ui/routes.py test/web/test_dns_monitor.py
git commit -m "feat: add DNS monitor (Соломка mode)

- Create core/dns_monitor.py with background monitoring
- Singleton pattern with thread safety
- Automatic failover to backup DNS after 3 failures
- Check interval: 30 seconds
- Add /service/dns-monitor routes for control
- Add tests for DNS monitoring
- Graceful shutdown on app exit

Fixes: #dns #monitoring #failover"
```

---

### Task 2: UI для настроек DNS

**Файлы:**
- Create: `src/web_ui/templates/dns_monitor.html`
- Modify: `src/web_ui/templates/service.html` (add DNS monitor card)
- Test: Manual testing via browser

**Step 1: Create DNS monitor UI template**

```html
<!-- src/web_ui/templates/dns_monitor.html -->
{% extends "base.html" %}

{% block title %}DNS Монитор — Bypass Keenetic{% endblock %}

{% block content %}
<div class="d-flex justify-content-between align-items-center mb-4">
    <h2><i class="bi bi-activity"></i> DNS Монитор</h2>
    <a href="{{ url_for('main.service') }}" class="btn btn-outline-secondary">
        <i class="bi bi-arrow-left"></i> Назад
    </a>
</div>

<!-- Status Card -->
<div class="card shadow-sm mb-4">
    <div class="card-header d-flex justify-content-between align-items-center">
        <span><i class="bi bi-hdd-network"></i> Статус монитора</span>
        {% if status.running %}
        <span class="badge bg-success">Запущен</span>
        {% else %}
        <span class="badge bg-secondary">Остановлен</span>
        {% endif %}
    </div>
    <div class="card-body">
        <div class="row">
            <div class="col-md-6">
                <h5>Текущий DNS сервер</h5>
                {% if status.current_server %}
                <p class="mb-0">
                    <strong>{{ status.current_server.name }}</strong><br>
                    <small class="text-muted">{{ status.current_server.host }}:{{ status.current_server.port }}</small>
                </p>
                {% else %}
                <p class="text-muted">Не выбран</p>
                {% endif %}
            </div>
            <div class="col-md-6">
                <h5>Последняя проверка</h5>
                {% if status.last_check %}
                <p class="mb-0">{{ status.last_check }}</p>
                {% else %}
                <p class="text-muted">Не проверялся</p>
                {% endif %}
            </div>
        </div>
        
        {% if status.failures > 0 %}
        <div class="alert alert-warning mt-3">
            <i class="bi bi-exclamation-triangle"></i>
            Последовательных неудач: {{ status.failures }}
            {% if status.failures >= 3 %}
            (будет переключение на резервный)
            {% endif %}
        </div>
        {% endif %}
        
        <!-- Controls -->
        <div class="mt-4">
            {% if status.running %}
            <form method="POST" action="{{ url_for('main.dns_monitor_stop') }}" class="d-inline">
                <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
                <button type="submit" class="btn btn-warning btn-sm">
                    <i class="bi bi-pause"></i> Остановить
                </button>
            </form>
            {% else %}
            <form method="POST" action="{{ url_for('main.dns_monitor_start') }}" class="d-inline">
                <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
                <button type="submit" class="btn btn-success btn-sm">
                    <i class="bi bi-play"></i> Запустить
                </button>
            </form>
            {% endif %}
            
            <form method="POST" action="{{ url_for('main.dns_monitor_check') }}" class="d-inline ms-2">
                <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
                <button type="submit" class="btn btn-info btn-sm">
                    <i class="bi bi-arrow-repeat"></i> Проверить сейчас
                </button>
            </form>
        </div>
    </div>
</div>

<!-- DNS Servers List -->
<div class="card shadow-sm">
    <div class="card-header">
        <i class="bi bi-list-ul"></i> Доступные DNS серверы
    </div>
    <div class="card-body">
        <div class="row">
            <div class="col-md-6">
                <h6>Основные:</h6>
                <ul class="list-group">
                    <li class="list-group-item">Google DNS (8.8.8.8)</li>
                    <li class="list-group-item">Cloudflare (1.1.1.1)</li>
                </ul>
            </div>
            <div class="col-md-6">
                <h6>Резервные:</h6>
                <ul class="list-group">
                    <li class="list-group-item">Quad9 (9.9.9.9)</li>
                    <li class="list-group-item">OpenDNS (208.67.222.222)</li>
                </ul>
            </div>
        </div>
    </div>
</div>
{% endblock %}
```

**Step 2: Update service.html with DNS monitor card**

```html
<!-- src/web_ui/templates/service.html -->
<!-- Add new card after DNS Override card -->

<!-- DNS Монитор -->
<div class="col-12 col-md-6">
    <div class="card shadow-sm">
        <div class="card-body">
            <h5 class="card-title"><i class="bi bi-activity"></i> DNS Монитор</h5>
            <p class="text-muted small">Автоматическое переключение при отказе DNS</p>
            <a href="{{ url_for('main.dns_monitor_status') }}" class="btn btn-primary btn-sm">
                <i class="bi bi-gear"></i> Настроить
            </a>
        </div>
    </div>
</div>
```

**Step 3: Commit**

```bash
git add src/web_ui/templates/dns_monitor.html src/web_ui/templates/service.html
git commit -m "feat: add DNS monitor UI

- Create dns_monitor.html template with status and controls
- Add DNS monitor card to service.html
- Show current server, last check, failure count
- Start/Stop/Check controls
- List of primary and backup DNS servers

Fixes: #ui #dns #monitoring"
```

---

### Task 3: Интеграция с dnsmasq

**Файлы:**
- Create: `src/web_ui/core/dns_manager.py`
- Modify: `src/web_ui/core/dns_monitor.py` (update dnsmasq config on switch)

**Step 1: Create DNS manager for dnsmasq**

```python
# src/web_ui/core/dns_manager.py
"""
DNS Manager - dnsmasq configuration management

Updates dnsmasq config when DNS server changes.
"""
import subprocess
import logging
from pathlib import Path
from typing import Tuple

logger = logging.getLogger(__name__)

DNSMASQ_CONFIG = '/opt/etc/dnsmasq.conf'
DNSMASQ_RESTART_CMD = ['/etc/init.d/S56dnsmasq', 'restart']


def update_dnsmasq_dns(server_host: str) -> Tuple[bool, str]:
    """
    Update dnsmasq to use specific DNS server.
    
    Args:
        server_host: DNS server IP
        
    Returns:
        Tuple of (success: bool, message: str)
    """
    try:
        # Read current config
        config_path = Path(DNSMASQ_CONFIG)
        if not config_path.exists():
            return False, f"Config not found: {DNSMASQ_CONFIG}"
        
        content = config_path.read_text()
        
        # Remove existing server lines
        lines = []
        for line in content.split('\n'):
            if not line.startswith('server='):
                lines.append(line)
        
        # Add new server
        lines.append(f'server={server_host}')
        
        # Write back (atomic)
        temp_path = str(config_path) + '.tmp'
        Path(temp_path).write_text('\n'.join(lines))
        Path(temp_path).rename(config_path)
        
        # Restart dnsmasq
        result = subprocess.run(
            DNSMASQ_RESTART_CMD,
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            logger.info(f"Updated dnsmasq to use {server_host}")
            return True, f"Switched to {server_host}"
        else:
            logger.error(f"dnsmasq restart failed: {result.stderr}")
            return False, f"Restart failed: {result.stderr}"
            
    except Exception as e:
        logger.error(f"Error updating dnsmasq: {e}")
        return False, str(e)
```

**Step 2: Integrate with DNS monitor**

```python
# src/web_ui/core/dns_monitor.py (modify _switch_to_backup)

def _switch_to_backup(self) -> None:
    """Switch to backup DNS server"""
    logger.warning("Switching to backup DNS")
    
    for server in self._servers['backup']:
        result = check_dns_server(server['host'], server['port'], TIMEOUT)
        if result['success']:
            self._current_server = server
            self._failures = 0
            
            # Update dnsmasq config
            from .dns_manager import update_dnsmasq_dns
            success, msg = update_dnsmasq_dns(server['host'])
            if success:
                logger.info(f"Switched to backup DNS: {server['name']} (dnsmasq updated)")
            else:
                logger.error(f"Failed to update dnsmasq: {msg}")
            
            return
    
    logger.error("No working backup DNS found")
    self._current_server = None
```

**Step 3: Commit**

```bash
git add src/web_ui/core/dns_manager.py src/web_ui/core/dns_monitor.py
git commit -m "feat: integrate DNS monitor with dnsmasq

- Create core/dns_manager.py for dnsmasq config management
- Update dnsmasq.conf when DNS server switches
- Automatic dnsmasq restart after config change
- Atomic config writes for safety

Fixes: #dnsmasq #dns #integration"
```

---

## Testing Strategy

### Unit Tests
```bash
# Run all DNS monitor tests
pytest test/web/test_dns_monitor.py -v

# Run specific test
pytest test/web/test_dns_monitor.py::test_dns_monitor_singleton -v
```

### Manual Testing
```bash
# 1. Start app
cd /opt/etc/web_ui
python3 app.py &

# 2. Check logs
tail -f /opt/var/log/web_ui.log | grep DNS

# 3. Access UI
# http://192.168.1.1:8080/service/dns-monitor

# 4. Test failover
# - Stop primary DNS (block with iptables)
# - Wait for 3 checks (90 seconds)
# - Verify switch to backup
```

---

## Performance Benchmarks

### Expected Behavior
- **Check interval:** 30 seconds
- **Timeout per check:** 2 seconds
- **Failover threshold:** 3 consecutive failures (90 seconds)
- **Memory usage:** +2-3MB (background thread)
- **CPU usage:** Minimal (<1% in idle)

---

## Success Criteria

- [ ] DNS monitor starts automatically with app
- [ ] Background thread checks DNS every 30 seconds
- [ ] Automatic failover after 3 failures
- [ ] UI shows current server and status
- [ ] Manual check button works
- [ ] dnsmasq config updated on switch
- [ ] Graceful shutdown on app exit
- [ ] All tests pass

---

**Plan complete!** Ready for execution via `superpowers:executing-plans` or `superpowers:subagent-driven-development`.
