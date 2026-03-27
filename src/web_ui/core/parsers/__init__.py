"""
VPN Key Parsers

Parsers for different VPN protocols: VLESS, Shadowsocks, Trojan, Hysteria2, Tor.
"""

from .vless_parser import VlessParser
from .shadowsocks_parser import ShadowsocksParser
from .trojan_parser import TrojanParser

__all__ = ['VlessParser', 'ShadowsocksParser', 'TrojanParser']
