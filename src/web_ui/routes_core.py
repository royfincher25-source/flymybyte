"""
FlyMyByte Web Interface - Core Routes

Blueprint for authentication and basic pages: /, /login, /logout, /status
"""
import logging
from flask import Blueprint, render_template, redirect, url_for, request, session, current_app, jsonify
from core.decorators import login_required, get_csrf_token, validate_csrf_token, csrf_required

logger = logging.getLogger(__name__)

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
