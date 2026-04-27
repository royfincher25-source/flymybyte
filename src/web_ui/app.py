"""
flymybyte Web Interface - Main Application

Flask application for Keenetic router bypass management.
"""
import os
import sys
import atexit
import signal
import secrets
import logging
from flask import Flask, session
from datetime import timedelta

# Setup logging before anything else
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core.utils import setup_logging
setup_logging()

logger = logging.getLogger(__name__)


def create_app(config_class=None):
    """Create and configure the Flask application."""
    import mimetypes
    mimetypes.add_type('font/woff2', '.woff2')

    app = Flask(__name__)

    secret_key = os.environ.get('SECRET_KEY') or secrets.token_hex(32)
    app.config['SECRET_KEY'] = secret_key

    from core.app_config import WebConfig
    config = config_class() if config_class else WebConfig()

    app.config['WEB_HOST'] = config.web_host
    app.config['WEB_PORT'] = config.web_port
    app.config['WEB_PASSWORD'] = config.web_password
    app.config['ROUTER_IP'] = config.router_ip

    app.config['SESSION_COOKIE_NAME'] = 'bypass_session'
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SECURE'] = False
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)

    # Register all 5 blueprints
    from routes_core import bp as core_bp, login_required as core_login_required
    app.register_blueprint(core_bp)

    from routes_system import bp as system_bp, schedule_webui_restart
    app.register_blueprint(system_bp)

    from routes_vpn import bp as vpn_bp, shutdown_executor as vpn_shutdown
    app.register_blueprint(vpn_bp)

    from routes_bypass import bp as bypass_bp
    app.register_blueprint(bypass_bp)

    from routes_updates import bp as updates_bp
    app.register_blueprint(updates_bp)

    @app.context_processor
    def inject_csrf_token():
        def generate_csrf_token():
            if 'csrf_token' not in session:
                session['csrf_token'] = secrets.token_hex(32)
            return session['csrf_token']
        return dict(csrf_token=generate_csrf_token)

    try:
        from core.utils import get_local_version
        _app_version = get_local_version()
    except Exception:
        _app_version = 'unknown'

    @app.context_processor
    def inject_version():
        return dict(app_version=_app_version)

    # DNS Monitor — disabled. Monitoring only, no config changes.
    from core.dns_ops import DNSMonitor
    dns_monitor = DNSMonitor()
    # dns_monitor.start()  # DISABLED — causes dnsmasq.conf overwrite
    logger.info("DNS monitor initialized (disabled — monitoring only)")

    # Auto-restore VPN iptables rules on startup (SAFE — no dnsmasq restart)
    try:
        from core.dnsmasq_manager import DnsmasqManager
        mgr = DnsmasqManager()
        # Только sanitize — НЕ перегенерируем конфиг и НЕ рестартуем dnsmasq
        mgr._sanitize_dnsmasq_conf()
        logger.info("dnsmasq.conf sanitized (safe startup)")
    except Exception as e:
        logger.warning(f"Failed to sanitize dnsmasq.conf: {e}")

    # Add DNS redirect at startup (перенаправляет DNS через dnsmasq:5353)
    try:
        from core.iptables_manager import get_iptables_manager
        ipt = get_iptables_manager()
        ipt.add_dns_redirect('192.168.1.1', 5353)
        logger.info("DNS redirect added on startup")
    except Exception as e:
        logger.warning(f"Failed to add DNS redirect: {e}")

    # Load IP/CIDR entries from bypass files on startup
    # - Domains: resolved via S99unblock start (resolve_bypass.sh)
    # - IP/CIDR: added manually from bypass files
    try:
        from core.app_config import WebConfig
        from core.utils import load_bypass_list
        from core.utils import is_ip_address, is_cidr
        from core.ipset_ops import bulk_add_to_ipset, ensure_ipset_exists
        from core.constants import IPSET_MAP
        import subprocess
        
        config = WebConfig()
        unblock_dir = config.unblock_dir
        
        if os.path.exists(unblock_dir):
            for filename in os.listdir(unblock_dir):
                if not filename.endswith('.txt'):
                    continue
                    
                filepath = os.path.join(unblock_dir, filename)
                entries = load_bypass_list(filepath)
                
                # Get IP/CIDR only (skip domains - они долго резолвятся и вызывают зависание)
                ip_or_cidr = [e for e in entries if is_ip_address(e) or is_cidr(e)]
                
                # Map filename -> ipset name (e.g., vless.txt -> unblockvless)
                name_stem = filename.replace('.txt', '')
                ipset_name = IPSET_MAP.get(name_stem, f'unblock{name_stem}')

                # FIX: Do NOT flush ipset on startup - preserve existing entries!
                # Old: flush cleared all IPs and caused Telegram to stop working
                # New: keep existing entries, add new ones only
                logger.info(f"[STARTUP] Preserving {ipset_name} entries (skip flush)")
                
                ensure_ipset_exists(ipset_name)
                
                # Add IP/CIDR entries (только IP, без доменов - домены резолвятся асинхронно)
                if ip_or_cidr:
                    ok, msg = bulk_add_to_ipset(ipset_name, ip_or_cidr)
                    logger.info(f"[STARTUP] Loaded {len(ip_or_cidr)} IP/CIDR to {ipset_name}")
                
                # Запустить S99unblock start в фоне для резолва доменов
                # Это нужно для YouTube и других доменов
                # Запускаем ТОЛЬКО ОДИН РАЗ - не дублируем при нескольких вызовах
                import threading

                S99UNBLOCK_LOCK = "/tmp/s99unblock_startup.lock"

                def _run_s99unblock():
                    # Проверяем lock файл - если уже запущен, выходим
                    if os.path.exists(S99UNBLOCK_LOCK):
                        # Проверим age файла - если старше 10 минут, перезапустим
                        try:
                            import time
                            mtime = os.path.getmtime(S99UNBLOCK_LOCK)
                            if time.time() - mtime > 600:  # 10 минут
                                os.remove(S99UNBLOCK_LOCK)
                            else:
                                logger.info("[STARTUP] S99unblock already running (lock exists), skipping")
                                return
                        except:
                            pass

                    # Создаём lock файл
                    try:
                        with open(S99UNBLOCK_LOCK, 'w') as f:
                            f.write(str(os.getpid()))
                    except:
                        pass

                    try:
                        # Убрали таймаут - пусть работает сколько нужно
                        # Но добавим проверку процесса чтобы не запускать повторно
                        result = subprocess.run(
                            ['sh', '/opt/etc/init.d/S99unblock', 'start'],
                            capture_output=True, timeout=0  # Без таймаута
                        )
                        logger.info(f"[STARTUP] S99unblock background completed: {result.returncode}")
                    except subprocess.TimeoutExpired:
                        logger.warning(f"[STARTUP] S99unblock background timed out")
                    except Exception as e:
                        logger.warning(f"[STARTUP] S99unblock background failed: {e}")
                    finally:
                        # Удаляем lock
                        try:
                            os.remove(S99UNBLOCK_LOCK)
                        except:
                            pass

                # Проверим что S99unblock не запущен
                running = False
                for pid_dir in os.listdir('/proc'):
                    if pid_dir.isdigit():
                        try:
                            with open(f'/proc/{pid_dir}/cmdline', 'r') as f:
                                if 'S99unblock' in f.read():
                                    running = True
                                    break
                        except:
                            pass

                if not running:
                    bg_thread = threading.Thread(target=_run_s99unblock, daemon=True)
                    bg_thread.start()
                    logger.info("[STARTUP] S99unblock started in background for domain resolution")
                else:
                    logger.info("[STARTUP] S99unblock already running, skipping startup launch")
    except Exception as e:
        logger.warning(f"Failed to load bypass lists on startup: {e}")

    def graceful_shutdown(signum=None, frame=None):
        logger.info("Graceful shutdown initiated...")
        dns_monitor.stop()
        vpn_shutdown()
        logger.info("All services stopped")

    atexit.register(graceful_shutdown)
    try:
        signal.signal(signal.SIGTERM, graceful_shutdown)
        signal.signal(signal.SIGINT, graceful_shutdown)
    except (ValueError, OSError):
        pass

    return app


if __name__ == '__main__':
    app = create_app()
    host = app.config['WEB_HOST']
    port = app.config['WEB_PORT']

    try:
        from waitress import serve
        logging.getLogger('waitress').info(f"Starting waitress server on {host}:{port} with 4 threads")
        serve(
            app,
            host=host,
            port=port,
            threads=4,
            connection_limit=10,
            cleanup_interval=30,
            channel_timeout=30,
        )
    except ImportError:
        logging.warning("Waitress not found, using Flask development server")
        app.run(host=host, port=port, debug=False, threaded=True)
