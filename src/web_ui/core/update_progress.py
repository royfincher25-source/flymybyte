"""
Update progress tracking for long-running update operations.

Stores progress state in memory (not persisted across restarts).
Thread-safe via threading.Lock.
"""

import threading
import time
from typing import Dict, Optional


class UpdateProgress:
    """Thread-safe progress tracker for update operations."""

    def __init__(self):
        self._lock = threading.Lock()
        self._progress: Dict[str, any] = {}

    def start(self, operation: str, total_steps: int = 0) -> None:
        """Mark operation as started."""
        with self._lock:
            self._progress[operation] = {
                'status': 'running',
                'step': 0,
                'total': total_steps,
                'message': 'Starting...',
                'started_at': time.time(),
                'error': None,
            }

    def update(self, operation: str, step: int, message: str = '') -> None:
        """Update progress for an operation."""
        with self._lock:
            if operation in self._progress:
                self._progress[operation]['step'] = step
                self._progress[operation]['message'] = message

    def complete(self, operation: str, message: str = 'Completed') -> None:
        """Mark operation as completed."""
        with self._lock:
            if operation in self._progress:
                self._progress[operation]['status'] = 'completed'
                self._progress[operation]['message'] = message

    def fail(self, operation: str, error: str) -> None:
        """Mark operation as failed."""
        with self._lock:
            if operation in self._progress:
                self._progress[operation]['status'] = 'failed'
                self._progress[operation]['error'] = error
                self._progress[operation]['message'] = f'Error: {error}'

    def get(self, operation: str) -> Optional[Dict]:
        """Get current progress for an operation."""
        with self._lock:
            return self._progress.get(operation)

    def clear(self, operation: str = None) -> None:
        """Clear progress data."""
        with self._lock:
            if operation:
                self._progress.pop(operation, None)
            else:
                self._progress.clear()
