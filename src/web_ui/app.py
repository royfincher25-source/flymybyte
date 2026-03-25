"""
flymybyte Web Interface - Main Application

Flask application for Keenetic router bypass management.
"""
import os
import sys
import secrets
import logging
from functools import wraps
from flask import Flask, session, request, abort
from datetime import timedelta

from core.app_config import WebConfig

# Создать logger для модуля
logger = logging.getLogger(__name__)


def create_app(config_class=None):
    """
    Create and configure the Flask application.

    Args:
        config_class: Optional configuration class to use.
                     If None, uses WebConfig from core.app_config.

    Returns:
        Configured Flask application instance
    """
    global app
    app = Flask(__name__)

    # Генерация случайного SECRET_KEY если не задан в окружении
    secret_key = os.environ.get('SECRET_KEY')
    if not secret_key:
        secret_key = secrets.token_hex(32)
    app.config['SECRET_KEY'] = secret_key

    # Загрузка конфигурации из WebConfig
    if config_class is None:
        config = WebConfig()
    else:
        config = config_class()

    # Применение конфигурации из WebConfig
    app.config['WEB_HOST'] = config.web_host
    app.config['WEB_PORT'] = config.web_port
    app.config['WEB_PASSWORD'] = config.web_password
    app.config['ROUTER_IP'] = config.router_ip

    # Конфигурация сессий
    app.config['SESSION_COOKIE_NAME'] = 'bypass_session'
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SECURE'] = False  # False для HTTP, True для HTTPS
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)

    # Регистрация маршрутов
    from routes import bp, register_routes
    app.register_blueprint(bp)
    register_routes(app)

    # Добавить csrf_token в контекст шаблонов
    @app.context_processor
    def inject_csrf_token():
        """Inject csrf_token into all templates"""
        def generate_csrf_token():
            if 'csrf_token' not in session:
                session['csrf_token'] = secrets.token_hex(32)
            return session['csrf_token']
        return dict(csrf_token=generate_csrf_token)
    
    # Добавить версию в контекст шаблонов
    @app.context_processor
    def inject_version():
        """Inject version into all templates"""
        from core.services import get_local_version
        version = get_local_version()
        return dict(app_version=version)

    # Запуск DNS монитора в фоновом режиме
    from core.dns_monitor import DNSMonitor
    dns_monitor = DNSMonitor()
    dns_monitor.start()
    logger.info("DNS monitor initialized and started")

    # Регистрация обработчика завершения для graceful shutdown
    import atexit
    @atexit.register
    def cleanup():
        logger.info("Shutting down DNS monitor...")
        dns_monitor.stop()
        logger.info("Shutting down ThreadPoolExecutor...")
        from routes import shutdown_executor
        shutdown_executor()

    return app


if __name__ == '__main__':
    app = create_app()
    
    host = app.config['WEB_HOST']
    port = app.config['WEB_PORT']
    
    # Production server (waitress) для embedded-устройств
    # Легче чем gunicorn (~2MB vs ~5MB), лучше для production
    try:
        from waitress import serve
        logger = logging.getLogger('waitress')
        logger.info(f"Starting waitress server on {host}:{port} with 4 threads")
        serve(
            app,
            host=host,
            port=port,
            threads=4,  # Увеличено с 2 до 4 для KN-1212 (128MB RAM)
            connection_limit=10,  # Лимит подключений для защиты от перегрузки
            cleanup_interval=30,  # Очистка каждые 30 секунд
            channel_timeout=30,  # Таймаут канала
        )
    except ImportError:
        # Fallback на development server с threaded=True
        import logging
        logging.warning("Waitress not found, using Flask development server")
        app.run(
            host=host,
            port=port,
            debug=False,
            threaded=True  # Хотя бы многопоточность
        )
