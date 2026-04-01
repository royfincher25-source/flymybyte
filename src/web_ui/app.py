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

    from routes_service import bp as main_bp, shutdown_executor
    app.register_blueprint(main_bp)

    @app.context_processor
    def inject_csrf_token():
        def generate_csrf_token():
            if 'csrf_token' not in session:
                session['csrf_token'] = secrets.token_hex(32)
            return session['csrf_token']
        return dict(csrf_token=generate_csrf_token)

    try:
        from core.services import get_local_version
        _app_version = get_local_version()
    except Exception:
        _app_version = 'unknown'

    @app.context_processor
    def inject_version():
        return dict(app_version=_app_version)

    from core.dns_monitor import DNSMonitor
    dns_monitor = DNSMonitor()
    dns_monitor.start()
    logger.info("DNS monitor initialized and started")

    def graceful_shutdown(signum=None, frame=None):
        logger.info("Graceful shutdown initiated...")
        dns_monitor.stop()
        shutdown_executor()
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
