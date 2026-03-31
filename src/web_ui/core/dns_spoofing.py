"""
DNS Spoofing Module - AI Domain Bypass

Generates dnsmasq configuration for bypassing region-based blocking of AI services.
Optimized for embedded devices (128MB RAM).

How it works:
- DNS запросы к AI доменам (aistudio.google.com, kaggle.com и т.д.) 
  перенаправляются на 1.1.1.1 (Cloudflare DNS)
- Cloudflare возвращает IP-адреса, видимые из другой локации
- AI сервис видит IP из другой страны и не блокирует доступ
- Провайдерская блокировка (DPI) не отслеживает эти соединения,
  так как блокировка установлена на стороне сайта по региону

Architecture:
- Load AI domains from list file
- Generate dnsmasq configuration with server= directives
- Route DNS queries through 1.1.1.1
- Apply configuration and restart dnsmasq

Example:
    >>> from core.dns_spoofing import DNSSpoofing
    >>> spoofing = DNSSpoofing()
    >>> success, msg = spoofing.apply_config()
    >>> print(f"Status: {success}, {msg}")

    >>> status = spoofing.get_status()
    >>> print(f"Enabled: {status['enabled']}, Domains: {status['domain_count']}")
"""
import os
import re
import threading
import logging
import subprocess
from pathlib import Path
from typing import List, Tuple, Dict, Any, Optional

logger = logging.getLogger(__name__)

# Configuration paths
AI_DOMAINS_LIST = '/opt/etc/unblock/ai-domains.txt'
DNSMASQ_AI_CONFIG = '/opt/etc/unblock-ai.dnsmasq'
DNSMASQ_AI_CONFIG_TEMPLATE = '/opt/etc/web_ui/resources/config/unblock-ai.dnsmasq.template'

# DNS configuration
# DNS-спуфинг обходит региональные блокировки AI-сервисов.
# DNS запросы к AI доменам перенаправляются на VPN DNS (DNS-over-TLS/HTTPS),
# который возвращает IP-адреса, видимые из другой локации.
# Провайдерская блокировка (DPI) не отслеживает эти соединения.
# По умолчанию используется 127.0.0.1:40500 (DNS-over-TLS порт flymybyte)
# Порт может быть изменён через WebConfig (dnsovertlsport)
VPN_DNS_HOST = '127.0.0.1'
VPN_DNS_PORT = 40500  # Будет заменён на dnsovertlsport из WebConfig при установке

# Validation
MAX_DOMAIN_LENGTH = 253
MAX_DOMAINS_COUNT = 1000


class DNSSpoofing:
    """
    DNS Spoofing for AI domain bypass.
    
    Generates dnsmasq configuration to route AI domain DNS queries through VPN.
    Thread-safe singleton pattern.
    """
    
    _instance: Optional['DNSSpoofing'] = None
    _lock = threading.Lock()
    
    def __new__(cls) -> 'DNSSpoofing':
        """Singleton pattern with thread safety"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialize DNS spoofing module"""
        if hasattr(self, '_initialized'):
            return
        
        self._domains: List[str] = []
        self._enabled: bool = False
        self._config_path = DNSMASQ_AI_CONFIG
        self._domains_path = AI_DOMAINS_LIST
        
        self._initialized = True
        logger.debug("DNSSpoofing initialized")
    
    def load_domains(self) -> List[str]:
        """
        Load AI domains from list file.
        
        Returns:
            List of valid domain names
            
        Notes:
            - Skips comments (lines starting with #)
            - Skips empty lines
            - Skips IP addresses
            - Validates domain format
        """
        domains = []
        domains_path = Path(self._domains_path)
        
        if not domains_path.exists():
            logger.warning(f"AI domains list not found: {self._domains_path}")
            return []
        
        try:
            content = domains_path.read_text(encoding='utf-8')
            
            for line in content.splitlines():
                line = line.strip()
                
                # Skip empty lines and comments
                if not line or line.startswith('#'):
                    continue
                
                # Skip wildcard domains (dnsmasq handles them differently)
                if line.startswith('*.'):
                    # Convert wildcard to base domain
                    line = line[2:]
                
                # Skip IP addresses
                if self._is_ip_address(line):
                    logger.debug(f"Skipping IP address: {line}")
                    continue
                
                # Validate domain
                if self._validate_domain(line):
                    domains.append(line)
                else:
                    logger.warning(f"Invalid domain skipped: {line}")
            
            # Limit domains count
            if len(domains) > MAX_DOMAINS_COUNT:
                logger.warning(f"Too many domains ({len(domains)}), limiting to {MAX_DOMAINS_COUNT}")
                domains = domains[:MAX_DOMAINS_COUNT]
            
            self._domains = domains
            logger.info(f"Loaded {len(domains)} AI domains from {self._domains_path}")
            
        except Exception as e:
            logger.error(f"Error loading AI domains: {e}")
            return []
        
        return domains
    
    def _validate_domain(self, domain: str) -> bool:
        """
        Validate domain name format.
        
        Args:
            domain: Domain name to validate
            
        Returns:
            True if valid, False otherwise
        """
        if not domain:
            return False
        
        if len(domain) > MAX_DOMAIN_LENGTH:
            return False
        
        # Basic domain pattern: letters, numbers, dots, hyphens
        # Must have at least one dot (TLD required)
        pattern = r'^[a-zA-Z0-9]([a-zA-Z0-9\-]*[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]*[a-zA-Z0-9])?)+$'
        
        if not re.match(pattern, domain):
            return False
        
        return True
    
    def _is_ip_address(self, entry: str) -> bool:
        """
        Check if entry is an IP address.
        
        Args:
            entry: Entry to check
            
        Returns:
            True if IP address, False otherwise
        """
        ip_pattern = r'^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}$'
        return bool(re.match(ip_pattern, entry))
    
    def generate_config(self, domains: Optional[List[str]] = None) -> str:
        """
        Generate dnsmasq configuration for AI domains.
        
        Args:
            domains: List of domains (default: load from file)
            
        Returns:
            dnsmasq configuration string
            
        Format:
            # AI Domains DNS Spoofing
            # Generated by dns_spoofing.py
            server=/domain.com/1.1.1.1
        """
        if domains is None:
            domains = self.load_domains()
        
        if not domains:
            logger.warning("No domains to generate config for")
            return ""
        
        lines = [
            "# AI Domains DNS Spoofing",
            "# Generated by dns_spoofing.py",
            f"# Domains count: {len(domains)}",
            "",
        ]
        
        for domain in domains:
            lines.append(f"server=/{domain}/{VPN_DNS_HOST}#{VPN_DNS_PORT}")
        
        config = '\n'.join(lines)
        logger.debug(f"Generated dnsmasq config: {len(lines)} lines")
        
        return config
    
    def write_config(self, config: str) -> Tuple[bool, str]:
        """
        Write dnsmasq configuration to file (atomic write).
        
        Args:
            config: Configuration string
            
        Returns:
            Tuple of (success: bool, message: str)
            
        Notes:
            - Uses atomic write via .tmp file
            - Creates directory if not exists
        """
        config_path = Path(self._config_path)
        
        try:
            # Create directory if needed
            config_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Atomic write via .tmp file
            tmp_path = config_path.with_suffix('.tmp')
            tmp_path.write_text(config, encoding='utf-8')
            tmp_path.replace(config_path)
            
            logger.info(f"Written AI domains config to {self._config_path}")
            return True, "OK"
            
        except Exception as e:
            error_msg = f"Error writing config: {e}"
            logger.error(error_msg)
            return False, error_msg
    
    def apply_config(self) -> Tuple[bool, str]:
        """
        Apply dnsmasq configuration and restart dnsmasq.
        
        Returns:
            Tuple of (success: bool, message: str)
            
        Steps:
            1. Load AI domains
            2. Generate dnsmasq config
            3. Write config to file
            4. Restart dnsmasq
        """
        # Load domains
        domains = self.load_domains()
        
        if not domains:
            error_msg = "No AI domains to apply"
            logger.warning(error_msg)
            return False, error_msg
        
        # Generate config
        config = self.generate_config(domains)
        
        if not config:
            error_msg = "Failed to generate config"
            logger.error(error_msg)
            return False, error_msg
        
        # Write config
        success, msg = self.write_config(config)
        
        if not success:
            return False, msg
        
        # Restart dnsmasq
        success, msg = self._restart_dnsmasq()
        
        if success:
            self._enabled = True
            logger.info(f"AI domains DNS spoofing enabled ({len(domains)} domains)")
            return True, f"Enabled ({len(domains)} domains)"
        else:
            logger.error(f"Failed to restart dnsmasq: {msg}")
            return False, msg
    
    def _restart_dnsmasq(self) -> Tuple[bool, str]:
        """
        Restart dnsmasq service.
        
        Returns:
            Tuple of (success: bool, message: str)
        """
        import subprocess
        
        dnsmasq_init = '/opt/etc/init.d/S56dnsmasq'
        
        if not Path(dnsmasq_init).exists():
            logger.warning("dnsmasq init script not found")
            return False, "dnsmasq not installed"
        
        try:
            result = subprocess.run(
                [dnsmasq_init, 'restart'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                logger.info("dnsmasq restarted successfully")
                return True, "OK"
            else:
                error_msg = result.stderr.strip() or "Unknown error"
                logger.error(f"dnsmasq restart failed: {error_msg}")
                return False, error_msg
                
        except subprocess.TimeoutExpired:
            error_msg = "dnsmasq restart timeout"
            logger.error(error_msg)
            return False, error_msg
            
        except Exception as e:
            error_msg = f"Error restarting dnsmasq: {e}"
            logger.error(error_msg)
            return False, error_msg
    
    def disable(self) -> Tuple[bool, str]:
        """
        Disable DNS spoofing (remove config and restart dnsmasq).
        
        Returns:
            Tuple of (success: bool, message: str)
        """
        config_path = Path(self._config_path)
        
        try:
            if config_path.exists():
                config_path.unlink()
                logger.info(f"Removed AI domains config: {self._config_path}")
            
            # Restart dnsmasq
            success, msg = self._restart_dnsmasq()
            
            if success:
                self._enabled = False
                self._domains = []
                logger.info("AI domains DNS spoofing disabled")
                return True, "Disabled"
            else:
                logger.warning(f"Config removed but dnsmasq restart failed: {msg}")
                self._enabled = False
                self._domains = []
                return True, f"Config removed (dnsmasq restart: {msg})"
                
        except Exception as e:
            error_msg = f"Error disabling DNS spoofing: {e}"
            logger.error(error_msg)
            return False, error_msg
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get current DNS spoofing status.
        
        Returns:
            Dict with status information:
            - enabled: bool
            - domain_count: int
            - config_exists: bool
            - dnsmasq_running: bool
        """
        config_path = Path(self._config_path)
        domains_path = Path(self._domains_path)
        
        # Check if config exists
        config_exists = config_path.exists()
        
        # Load domains if not loaded
        if not self._domains and domains_path.exists():
            self.load_domains()
        
        # Check if dnsmasq is running
        dnsmasq_running = self._check_dnsmasq_status()
        
        return {
            'enabled': self._enabled or config_exists,
            'domain_count': len(self._domains),
            'config_exists': config_exists,
            'dnsmasq_running': dnsmasq_running,
            'config_path': self._config_path,
            'domains_path': self._domains_path,
        }
    
    def _check_dnsmasq_status(self) -> bool:
        """
        Check if dnsmasq is running.
        
        Returns:
            True if running, False otherwise
        """
        import subprocess
        
        try:
            result = subprocess.run(
                ['pgrep', 'dnsmasq'],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            return result.returncode == 0
            
        except Exception:
            return False
    
    def test_domain(self, domain: str) -> Dict[str, Any]:
        """
        Test DNS resolution for a domain.

        Args:
            domain: Domain to test

        Returns:
            Dict with test results:
            - domain: str
            - resolved: bool
            - ips: List[str]
            - dns_server: str
            - error: Optional[str]
        """
        import subprocess
        import re

        result = {
            'domain': domain,
            'resolved': False,
            'ips': [],
            'dns_server': f'{VPN_DNS_HOST}:{VPN_DNS_PORT}',
            'error': None,
        }

        try:
            # First try: resolve through VPN DNS (127.0.0.1:40500)
            # Use nslookup with shell=True for Keenetic compatibility
            try:
                proc_result = subprocess.run(
                    f'nslookup {domain} {VPN_DNS_HOST} 2>/dev/null',
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                
                if proc_result.returncode == 0:
                    # Extract IPv4 addresses only
                    # Match formats: "Address: X.X.X.X", "Address 1: X.X.X.X", "Addresses: X.X.X.X"
                    ips = re.findall(
                        r'Address(?:es)?\s*\d*:\s*([0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3})',
                        proc_result.stdout
                    )
                    
                    # Filter out VPN_DNS_HOST itself
                    ips = [ip for ip in ips if ip != VPN_DNS_HOST]
                    ips = list(set(ips))
                    
                    if ips:
                        result['resolved'] = True
                        result['ips'] = ips
                        result['dns_server'] = f'{VPN_DNS_HOST}:{VPN_DNS_PORT} (VPN)'
                        return result
                        
            except Exception as e:
                logger.debug(f"nslookup error: {e}")
                pass
            
            # If no IPs found, check if domain is valid
            # Try system DNS as fallback to verify domain exists
            try:
                proc_result = subprocess.run(
                    f'nslookup {domain} 2>/dev/null',
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                
                if proc_result.stdout.strip():
                    # Domain exists but not resolved through VPN DNS
                    ips = re.findall(
                        r'([0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3})',
                        proc_result.stdout
                    )
                    
                    if ips:
                        result['error'] = f'Домен существует, но не резолвится через VPN DNS (порт {VPN_DNS_PORT}). Проверьте, запущен ли dnsmasq/stubby и применена ли конфигурация.'
                        result['ips'] = ips
                        return result
                    
            except Exception:
                pass
            
            result['error'] = 'No IPs found'
            
        except subprocess.TimeoutExpired:
            result['error'] = 'Timeout'
        except Exception as e:
            result['error'] = str(e)

        return result


# Module-level convenience functions

def apply_dns_spoofing() -> Tuple[bool, str]:
    """Apply DNS spoofing configuration"""
    spoofing = DNSSpoofing()
    return spoofing.apply_config()


def disable_dns_spoofing() -> Tuple[bool, str]:
    """Disable DNS spoofing"""
    spoofing = DNSSpoofing()
    return spoofing.disable()


def get_dns_spoofing_status() -> Dict[str, Any]:
    """Get DNS spoofing status"""
    spoofing = DNSSpoofing()
    return spoofing.get_status()
