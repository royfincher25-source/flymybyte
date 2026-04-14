"""
FlyMyByte Web Interface - Update Progress Tracker

Thread-safe singleton for tracking update installation progress.
Used by routes_updates.py to report progress via /api/update/progress.
"""
import threading
import time
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class ProgressTracker:
    """Tracks update progress with thread-safe state management."""

    _instance = None
    _lock = threading.Lock()

    def __init__(self):
        self._state = {
            'is_running': False,
            'message': '',
            'file': '',
            'progress': 0,
            'total': 100,
            'error': None,
            'started_at': None,
            'completed_at': None,
        }

    @classmethod
    def get_instance(cls) -> 'ProgressTracker':
        """Get singleton instance (thread-safe)."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls):
        """Reset singleton (for testing)."""
        with cls._lock:
            if cls._instance is not None:
                cls._instance = None

    # State properties

    @property
    def is_running(self) -> bool:
        return self._state['is_running']

    # Public methods

    def start_update(self, total_files: int = 0, message: str = 'Начало обновления...') -> None:
        """Mark update as started."""
        self._state.update({
            'is_running': True,
            'message': message,
            'file': '',
            'progress': 0,
            'total': max(total_files, 100),
            'error': None,
            'started_at': time.time(),
            'completed_at': None,
        })
        logger.info(f"[PROGRESS] Update started: {message}")

    def update_progress(self, message: str, file: str = '', progress: int = 0, total: int = 100) -> None:
        """Update progress state."""
        self._state.update({
            'message': message,
            'file': file,
            'progress': progress,
            'total': total,
        })
        logger.debug(f"[PROGRESS] {progress}/{total}: {message}")

    def set_error(self, error: str) -> None:
        """Mark update as failed."""
        self._state.update({
            'is_running': False,
            'error': error,
            'message': f'Ошибка: {error}',
            'completed_at': time.time(),
        })
        logger.error(f"[PROGRESS] Error: {error}")

    def complete(self) -> None:
        """Mark update as completed."""
        self._state.update({
            'is_running': False,
            'message': 'Обновление завершено!',
            'progress': self._state['total'],
            'completed_at': time.time(),
        })
        logger.info("[PROGRESS] Update completed")

    def get_status(self) -> Dict[str, Any]:
        """Get current progress state."""
        elapsed = 0
        if self._state['started_at']:
            end_time = self._state['completed_at'] or time.time()
            elapsed = int(end_time - self._state['started_at'])

        return {
            **self._state,
            'elapsed_seconds': elapsed,
        }


# Module-level singleton

def get_progress_instance() -> ProgressTracker:
    """Get ProgressTracker singleton."""
    return ProgressTracker.get_instance()
