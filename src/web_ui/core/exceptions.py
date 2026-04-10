"""
Custom exceptions for FlyMyByte application.

Provides a hierarchy of exceptions for different error categories.
"""

from typing import Any, Optional


class FlyMyByteError(Exception):
    """Base exception for all FlyMyByte errors."""
    
    def __init__(self, message: str, details: Optional[Any] = None):
        super().__init__(message)
        self.message = message
        self.details = details
    
    def __str__(self) -> str:
        if self.details:
            return f"{self.message}: {self.details}"
        return self.message


class ServiceError(FlyMyByteError):
    """Error when interacting with system services (dnsmasq, vpn, etc)."""
    pass


class ConfigError(FlyMyByteError):
    """Error related to configuration."""
    pass


class BackupError(FlyMyByteError):
    """Error during backup or restore operations."""
    pass


class ValidationError(FlyMyByteError):
    """Error during input validation."""
    pass


class NetworkError(FlyMyByteError):
    """Error related to network operations."""
    pass


class ParseError(FlyMyByteError):
    """Error when parsing keys or configuration files."""
    pass


class FileError(FlyMyByteError):
    """Error related to file operations."""
    pass