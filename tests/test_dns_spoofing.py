import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'web_ui'))

from core.dns_spoofing import DNSSpoofing


def test_generate_config_ipv6():
    """Test that config includes AAAA records for IPv6"""
    spoofing = DNSSpoofing()
    
    domains = ['aistudio.google.com', 'gemini.google.com']
    config = spoofing.generate_config(domains)
    
    assert 'server=/aistudio.google.com/127.0.0.1#40500' in config
    assert 'server=/aistudio.google.com/::1#40500' in config
    assert 'server=/gemini.google.com/127.0.0.1#40500' in config
    assert 'server=/gemini.google.com/::1#40500' in config


def test_generate_config_ipv4_only():
    """Test that config includes IPv4 server directives"""
    spoofing = DNSSpoofing()
    
    domains = ['test.com']
    config = spoofing.generate_config(domains)
    
    assert 'server=/test.com/127.0.0.1#40500' in config
