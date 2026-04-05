"""
FlyMyByte Web Interface - Core Routes

Blueprint for authentication and basic pages: /, /login, /logout, /status
"""
import secrets
import logging
from functools import wraps
from flask import Blueprint, render_template, redirect, url_for, request, session, current_app, jsonify

logger = logging.getLogger(__name__)


# =============================================================================
# INLINED DECORATORS (from core/decorators.py)
# =============================================================================

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


def get_csrf_token():
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


bp = Blueprint('core', __name__, template_folder='templates', static_folder='static')


# =============================================================================
# ROUTES
# =============================================================================

@bp.route('/')
@login_required
def index():
    return render_template('index.html')


@bp.route('/login', methods=['GET', 'POST'])
def login():
    if session.get('authenticated'):
        return redirect(url_for('core.index'))
    if request.method == 'GET':
        get_csrf_token()
    if request.method == 'POST':
        if not validate_csrf_token():
            from flask import flash
            flash('Ошибка безопасности: неверный токен', 'danger')
            logger.warning("CSRF token validation failed on login")
            return redirect(url_for('core.login'))
        password = request.form.get('password', '')
        web_password = current_app.config.get('WEB_PASSWORD', 'changeme')
        if password and web_password and secrets.compare_digest(password, web_password):
            session.permanent = True
            session['authenticated'] = True
            logger.info("User logged in successfully")
            return redirect(url_for('core.index'))
        else:
            logger.warning("Failed login attempt")
            from flask import flash
            flash('Неверный пароль', 'danger')
            return redirect(url_for('core.login'))
    return render_template('login.html')


@bp.route('/logout')
def logout():
    session.pop('authenticated', None)
    from flask import flash
    flash('Вы вышли из системы', 'info')
    return redirect(url_for('core.login'))


@bp.route('/status')
@login_required
def status():
    return render_template('base.html', title='Status')
