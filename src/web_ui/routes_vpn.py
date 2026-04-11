"""
FlyMyByte Web Interface - VPN Routes

Blueprint for VPN key management: /keys/*
Refactored to use VPNManager and KeyManager.
"""
import logging
import os
from flask import Blueprint, render_template, redirect, url_for, request, flash
from core.decorators import login_required, csrf_required

logger = logging.getLogger(__name__)

from core.app_config import SERVICES, CONFIG_PATHS, INIT_SCRIPTS
from core.vpn_manager import VPNManager
from core.key_manager import KeyManager


bp = Blueprint('vpn', __name__, template_folder='templates', static_folder='static')


def shutdown_executor():
    """Placeholder for VPN executor shutdown."""
    logger.info("VPN executor shutdown requested")


@bp.route('/keys')
@login_required
def keys():
    """Show all VPN services with their status."""
    services = {}
    for svc_id, svc_info in SERVICES.items():
        mgr = VPNManager(svc_id)
        services[svc_id] = {
            'name': mgr.name,
            'config': mgr.config_path,
            'init': mgr.init_script,
            'status': mgr.get_status(),
            'config_exists': mgr.is_configured(),
        }
    return render_template('keys.html', services=services)


@bp.route('/keys/<service>', methods=['GET', 'POST'])
@login_required
@csrf_required
def key_config(service: str):
    """Configure VPN key for a service."""
    if service not in SERVICES:
        flash('Invalid service', 'danger')
        return redirect(url_for('vpn.keys'))
    
    mgr = VPNManager(service)
    
    if request.method == 'POST':
        key = request.form.get('key', '').strip()
        if not key:
            flash('Enter key', 'warning')
            return redirect(url_for('vpn.key_config', service=service))
        
        key_mgr = KeyManager()
        ok, msg = key_mgr.configure_and_restart(
            key=key,
            service=service,
            config_path=mgr.config_path,
            init_script=mgr.init_script,
            service_display_name=mgr.name,
            timeout=30
        )
        
        if ok:
            flash(f'✅ {mgr.name} configured', 'success')
        else:
            flash(f'❌ Error: {msg}', 'danger')
        
        return redirect(url_for('vpn.keys'))
    
    return render_template('key_generic.html', service=service, service_name=mgr.name)


@bp.route('/keys/<service>/toggle', methods=['POST'])
@login_required
@csrf_required
def key_toggle(service: str):
    """Toggle service on/off."""
    if service not in SERVICES:
        flash('Invalid service', 'danger')
        return redirect(url_for('vpn.keys'))
    
    mgr = VPNManager(service)
    
    if not mgr.is_configured():
        flash(f'⚠️ Configure key first for {mgr.name}', 'warning')
        return redirect(url_for('vpn.key_config', service=service))
    
    success, msg = mgr.toggle()
    
    if success:
        flash(f'✅ {mgr.name} {msg}', 'success')
    else:
        flash(f'❌ {msg}', 'danger')
    
    return redirect(url_for('vpn.keys'))


@bp.route('/keys/<service>/disable', methods=['POST'])
@login_required
@csrf_required
def key_disable(service: str):
    """Disable (stop) a VPN service."""
    if service not in SERVICES:
        flash('Invalid service', 'danger')
        return redirect(url_for('vpn.keys'))
    
    mgr = VPNManager(service)
    success, msg = mgr.stop()
    
    if success:
        flash(f'✅ {mgr.name} disabled', 'success')
    else:
        flash(f'⚠️ {msg}', 'warning')
    
    return redirect(url_for('vpn.keys'))