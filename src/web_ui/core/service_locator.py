"""
Service Locator — unified access point to all managers.

Replaces individual get_*_manager() functions with a single entry point.
Provides lazy loading and caching of manager instances.
"""
from typing import Any, Dict, Optional
import logging

logger = logging.getLogger(__name__)

_managers: Dict[str, Any] = {}


def _register_manager(name: str, factory: callable) -> None:
    """Register a manager factory."""
    _managers[name] = factory


def ipset():
    """Get IPSet operations manager."""
    from .ipset_ops import IptablesManager
    return IptablesManager()


def dnsmasq():
    """Get Dnsmasq manager."""
    from .dnsmasq_manager import DnsmasqManager
    return DnsmasqManager()


def dns():
    """Get DNS monitor."""
    from .dns_ops import DNSMonitor
    return DNSMonitor()


def iptables():
    """Get iptables manager."""
    from .iptables_manager import IptablesManager
    return IptablesManager()


def backup():
    """Get backup manager."""
    from .backup_manager import get_backup_manager
    return get_backup_manager()


def vpn():
    """Get VPN manager factory."""
    from .vpn_manager import VPNManager
    return VPNManager


def key():
    """Get key manager."""
    from .key_manager import KeyManager
    return KeyManager()


class ServiceLocator:
    """
    Unified service access point.
    
    Usage:
        from core.service_locator import ServiceLocator
        
        ipset_mgr = ServiceLocator.ipset()
        dnsmasq_mgr = ServiceLocator.dnsmasq()
    """
    
    @staticmethod
    def ipset():
        """Get IPSet manager."""
        return ipset()
    
    @staticmethod
    def dnsmasq():
        """Get Dnsmasq manager."""
        return dnsmasq()
    
    @staticmethod
    def dns():
        """Get DNS monitor."""
        return dns()
    
    @staticmethod
    def iptables():
        """Get iptables manager."""
        return iptables()
    
    @staticmethod
    def backup():
        """Get backup manager."""
        return backup()
    
    @staticmethod
    def vpn(service_name: str):
        """Get VPN manager for specific service."""
        from .vpn_manager import VPNManager
        return VPNManager(service_name)
    
    @staticmethod
    def key():
        """Get key manager."""
        return key()
    
    @staticmethod
    def all_managers() -> Dict[str, Any]:
        """Get dict of all available managers."""
        return {
            'ipset': ipset(),
            'dnsmasq': dnsmasq(),
            'dns': dns(),
            'iptables': iptables(),
            'backup': backup(),
            'key': key(),
        }


def get_service(name: str) -> Any:
    """Get service by name (for dynamic access)."""
    services = {
        'ipset': ipset,
        'dnsmasq': dnsmasq,
        'dns': dns,
        'iptables': iptables,
        'backup': backup,
        'vpn': vpn,
        'key': key,
    }
    if name not in services:
        raise ValueError(f"Unknown service: {name}")
    return services[name]()


def reload_managers() -> None:
    """Reload all managers (useful for testing)."""
    global _managers
    _managers.clear()
    logger.info("Service managers cleared")