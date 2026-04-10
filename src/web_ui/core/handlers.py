"""
Error handlers and decorators for consistent error handling.
"""
from functools import wraps
from flask import jsonify, request
import logging

from .exceptions import (
    FlyMyByteError,
    ValidationError,
    ServiceError,
    ConfigError,
    BackupError,
    NetworkError,
)

logger = logging.getLogger(__name__)


def api_error(f):
    """
    Decorator for consistent API error handling.
    
    Catches FlyMyByteError subclasses and returns formatted JSON response.
    """
    @wraps(f)
    def wrapper(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except ValidationError as e:
            logger.warning(f"Validation error: {e}")
            return jsonify({
                'success': False,
                'error': str(e),
                'error_type': 'validation'
            }), 400
        except FlyMyByteError as e:
            logger.warning(f"Application error: {e}")
            return jsonify({
                'success': False,
                'error': str(e),
                'error_type': e.__class__.__name__.replace('Error', '').lower()
            }), 400
        except Exception as e:
            logger.exception("Unexpected error in API")
            return jsonify({
                'success': False,
                'error': 'Internal error',
                'error_type': 'internal'
            }), 500
    return wrapper


def handle_service_errors(f):
    """
    Decorator specifically for service operations.
    """
    @wraps(f)
    def wrapper(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except ServiceError as e:
            logger.warning(f"Service error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 503
        except Exception as e:
            logger.exception("Service operation failed")
            return jsonify({'success': False, 'error': 'Service unavailable'}), 500
    return wrapper


def require_json(f):
    """Decorator to require JSON content type."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not request.is_json:
            return jsonify({'success': False, 'error': 'JSON required'}), 400
        return f(*args, **kwargs)
    return wrapper