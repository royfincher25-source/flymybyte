"""
Authentication and CSRF decorators.

Centralized to avoid duplication across route modules.
"""

from functools import wraps
from flask import session, request, redirect, url_for, jsonify, flash
import secrets
import logging

logger = logging.getLogger(__name__)


def login_required(f):
    """Decorator to require authentication for a route."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('authenticated'):
            is_ajax = (
                request.headers.get('X-Requested-With') == 'XMLHttpRequest'
                or 'application/json' in request.headers.get('Accept', '')
            )
            if is_ajax or request.is_json:
                return jsonify({'success': False, 'error': 'Authentication required'}), 401
            return redirect(url_for('core.login'))
        return f(*args, **kwargs)
    return decorated_function


def get_csrf_token() -> str:
    """Generate or get CSRF token for the session."""
    if 'csrf_token' not in session:
        session['csrf_token'] = secrets.token_hex(32)
    return session['csrf_token']


def validate_csrf_token() -> bool:
    """Validate CSRF token from session and form."""
    token = session.get('csrf_token')
    form_token = request.form.get('csrf_token')
    if not token or not form_token or token != form_token:
        logger.warning("CSRF token validation failed")
        return False
    return True


def csrf_required(f):
    """Decorator to require CSRF token on POST requests."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if request.method == 'POST':
            if not validate_csrf_token():
                flash('Ошибка безопасности: неверный токен', 'danger')
                is_ajax = (
                    request.headers.get('X-Requested-With') == 'XMLHttpRequest'
                    or 'application/json' in request.headers.get('Accept', '')
                )
                if is_ajax or request.is_json:
                    return jsonify({'success': False, 'error': 'CSRF token validation failed'}), 400
                return redirect(url_for('core.index'))
        return f(*args, **kwargs)
    return decorated_function
