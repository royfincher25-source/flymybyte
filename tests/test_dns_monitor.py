import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'web_ui'))

from core.dns_monitor import check_dns_server, DNSMonitor


def test_vpn_dns_health_check():
    """Test that DNS monitor can check VPN DNS port 40500"""
    result = check_dns_server('127.0.0.1', port=40500, timeout=2.0)
    
    assert 'success' in result
    assert 'latency_ms' in result
    assert result['host'] == '127.0.0.1'
    assert result['port'] == 40500


def test_check_dns_server_basic():
    """Test basic DNS server check"""
    result = check_dns_server('8.8.8.8', port=53, timeout=2.0)
    
    assert 'success' in result
    assert 'latency_ms' in result
    assert result['host'] == '8.8.8.8'


def test_dns_monitor_vpn_dns_method():
    """Test that DNSMonitor has check_vpn_dns method"""
    monitor = DNSMonitor()
    
    assert hasattr(monitor, 'check_vpn_dns')
