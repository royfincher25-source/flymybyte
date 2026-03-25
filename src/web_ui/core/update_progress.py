import threading
import time

class UpdateProgress:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        """Initialize progress tracker (called after __new__)"""
        if self._initialized:
            return
        
        self.status = 'idle'
        self.message = ''
        self.current_file = ''
        self.progress = 0
        self.total_files = 0
        self.error = None
        self.is_running = False
        self._initialized = True

    def start_update(self, total_files=0):
        if self.is_running:
            raise Exception("Update already in progress")
        self.is_running = True
        self.status = 'starting'
        self.message = 'Creating backup...'
        self.progress = 0
        self.total_files = total_files
        self.error = None

    def update_progress(self, message, file='', progress=0, total=0):
        self.message = message
        self.current_file = file
        self.progress = progress
        self.total_files = total

    def set_error(self, error):
        self.status = 'error'
        self.error = error
        self.is_running = False

    def complete(self):
        self.status = 'complete'
        self.message = 'Update completed'
        self.is_running = False

    def reset(self):
        self.status = 'idle'
        self.message = ''
        self.current_file = ''
        self.progress = 0
        self.total_files = 0
        self.error = None
        self.is_running = False

    def get_status(self):
        return {
            'status': self.status,
            'message': self.message,
            'current_file': self.current_file,
            'progress': self.progress,
            'total_files': self.total_files,
            'error': self.error
        }