"""
Update progress tracking for long-running update operations.

Stores progress state in memory (not persisted across restarts).
Thread-safe via threading.Lock.
"""

import threading
import time
from typing import Dict, Optional


# Singleton instance
_instance = None
_instance_lock = threading.Lock()


def get_progress_instance() -> 'UpdateProgress':
    """Get the global UpdateProgress singleton."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = UpdateProgress()
    return _instance


class UpdateProgress:
    """Thread-safe progress tracker for update operations."""

    def __init__(self):
        self._lock = threading.Lock()
        self._state = {
            'running': False,
            'total_files': 0,
            'current_file': '',
            'progress': 0,  # 0-100
            'success': 0,
            'errors': 0,
            'error_msg': None,
            'started_at': None,
        }

    @property
    def is_running(self) -> bool:
        with self._lock:
            return self._state['running']

    def start_update(self, total_files: int = 0) -> None:
        with self._lock:
            self._state['running'] = True
            self._state['total_files'] = total_files
            self._state['current_file'] = ''
            self._state['progress'] = 0
            self._state['success'] = 0
            self._state['errors'] = 0
            self._state['error_msg'] = None
            self._state['started_at'] = time.time()

    def update_progress(self, message: str = '', file: str = '', progress: int = 0, total: int = 100) -> None:
        with self._lock:
            self._state['current_file'] = file
            self._state['progress'] = min(progress, total)
            # Store last message for API endpoint
            self._state['last_message'] = message

    def set_error(self, msg: str) -> None:
        with self._lock:
            self._state['error_msg'] = msg

    def complete(self) -> None:
        with self._lock:
            self._state['running'] = False
            self._state['progress'] = 100

    def get_status(self) -> Dict:
        with self._lock:
            return dict(self._state)

    def reset(self) -> None:
        with self._lock:
            self._state = {
                'running': False,
                'total_files': 0,
                'current_file': '',
                'progress': 0,
                'success': 0,
                'errors': 0,
                'error_msg': None,
                'started_at': None,
            }
