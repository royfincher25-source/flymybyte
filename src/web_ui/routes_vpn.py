"""
FlyMyByte Web Interface - VPN Routes

Blueprint for VPN key management: /keys/*
Refactored to use VPNManager and KeyManager.
DETAILED LOGGING added for debugging (2026-04-11).
"""
import logging
import os
import time
from flask import Blueprint, render_template, redirect, url_for, request, flash
from core.decorators import login_required, csrf_required

logger = logging.getLogger(__name__)

from core.app_config import SERVICES, CONFIG_PATHS, INIT_SCRIPTS
from core.vpn_manager import VPNManager
from core.key_manager import KeyManager
from core.handlers import redirect_with_message


bp = Blueprint('vpn', __name__, template_folder='templates', static_folder='static')


def shutdown_executor():
    """Placeholder for VPN executor shutdown."""
    logger.info("[VPN] VPN executor shutdown requested")


@bp.route('/keys')
@login_required
def keys():
    """Show all VPN services with their status."""
    logger.info("[VPN] >>> GET /keys - rendering services page")
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
        logger.debug(f"[VPN]   {svc_id}: status={services[svc_id]['status']}")
    logger.info("[VPN] <<< GET /keys - done")
    return render_template('keys.html', services=services)


@bp.route('/keys/<service>', methods=['GET', 'POST'])
@login_required
@csrf_required
def key_config(service: str):
    """Configure VPN key for a service."""
    if service not in SERVICES:
        return redirect_with_message('Invalid service', 'danger', 'vpn.keys')
    
    mgr = VPNManager(service)
    
    if request.method == 'POST':
        key = request.form.get('key', '').strip()
        if not key:
            return redirect_with_message('Enter key', 'warning', 'vpn.key_config', service=service)
        
        key_mgr = KeyManager()
        ok, msg = key_mgr.configure_and_restart(
            key=key,
            service=service,
            config_path=mgr.config_path,
            init_script=mgr.init_script,
            service_display_name=mgr.name,
            timeout=30
        )
        
        category = 'success' if ok else 'danger'
        msg_prefix = '✅' if ok else '❌'
        return redirect_with_message(f'{msg_prefix} {msg}' if ok else f'Error: {msg}', category, 'vpn.keys')
    
    return render_template('key_generic.html', service=service, service_name=mgr.name)


@bp.route('/keys/<service>/toggle', methods=['POST'])
@login_required
@csrf_required
def key_toggle(service: str):
    """Toggle service on/off."""
    logger.info(f"[VPN] >>> POST /keys/{service}/toggle - called from {request.remote_addr}")
    if service not in SERVICES:
        logger.warning(f"[VPN] <<< TOGGLE {service}: invalid service")
        return redirect_with_message('Invalid service', 'danger', 'vpn.keys')

    mgr = VPNManager(service)
    logger.info(f"[VPN]   Calling mgr.toggle() for {service}...")
    t0 = time.time()
    success, msg = mgr.toggle()
    elapsed = time.time() - t0
    logger.info(f"[VPN]   toggle() returned: success={success}, msg='{msg}', elapsed={elapsed:.1f}s")

    msg_prefix = '✅' if success else '❌'
    category = 'success' if success else 'danger'
    logger.info(f"[VPN] <<< TOGGLE {service}: {msg_prefix} {msg}")
    return redirect_with_message(f'{msg_prefix} {msg}', category, 'vpn.keys')


@bp.route('/keys/<service>/disable', methods=['POST'])
@login_required
@csrf_required
def key_disable(service: str):
    """Disable (stop) a VPN service."""
    logger.info(f"[VPN] >>> POST /keys/{service}/disable - called from {request.remote_addr}")
    if service not in SERVICES:
        logger.warning(f"[VPN] <<< DISABLE {service}: invalid service")
        return redirect_with_message('Invalid service', 'danger', 'vpn.keys')

    mgr = VPNManager(service)
    logger.info(f"[VPN]   Calling mgr.stop() for {service}...")
    t0 = time.time()
    success, msg = mgr.stop()
    elapsed = time.time() - t0
    logger.info(f"[VPN]   stop() returned: success={success}, msg='{msg}', elapsed={elapsed:.1f}s")

    msg_prefix = '✅' if success else '⚠️'
    category = 'success' if success else 'warning'
    logger.info(f"[VPN] <<< DISABLE {service}: {msg_prefix} {msg}")
    return redirect_with_message(f'{msg_prefix} {msg}', category, 'vpn.keys')