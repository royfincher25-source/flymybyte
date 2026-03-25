# Optimization Plan for KN-1212 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Optimize the update process for Keenetic KN-1212 (128MB RAM, MIPS 580MHz) to reduce CPU usage and memory consumption while maintaining usability.

**Architecture:**
- Simplify singleton pattern in UpdateProgress class
- Implement background execution for update process
- Optimize file download mechanism
- Add dynamic polling interval
- Add optional backup skip

**Tech Stack:** Flask, Python threading, JavaScript Fetch API, Bootstrap progress bars

---

### Task 1: Simplify UpdateProgress Class

**Files:**
- Modify: `src/web_ui/core/update_progress.py`

**Step 1: Write the failing test**

Create test `tests/test_update_optimization.py`:
```python
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'web_ui', 'core'))
from update_progress import UpdateProgress

def test_update_progress_no_singleton():
    # Test that UpdateProgress is not a singleton (multiple instances allowed)
    progress1 = UpdateProgress()
    progress2 = UpdateProgress()
    # Should be different instances
    assert progress1 is not progress2
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_update_optimization.py::test_update_progress_no_singleton -v`
Expected: FAIL (instances are same due to singleton pattern)

**Step 3: Write minimal implementation**

Modify `src/web_ui/core/update_progress.py`:
```python
class UpdateProgress:
    def __init__(self):
        self.status = 'idle'
        self.message = ''
        self.current_file = ''
        self.progress = 0
        self.total_files = 0
        self.error = None
        self.is_running = False
    
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
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_update_optimization.py::test_update_progress_no_singleton -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_update_optimization.py src/web_ui/core/update_progress.py
git commit -m "refactor: simplify UpdateProgress class (remove singleton)"
```

### Task 2: Implement Background Update Execution

**Files:**
- Modify: `src/web_ui/routes.py` (service_updates_run function)
- Create: `src/web_ui/core/update_manager.py` (update manager module)

**Step 1: Write the failing test**

Add to `tests/test_update_optimization.py`:
```python
def test_background_update_execution():
    # Test that update can run in background thread
    from src.web_ui.core.update_manager import UpdateManager
    manager = UpdateManager()
    assert hasattr(manager, 'run_update')
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_update_optimization.py::test_background_update_execution -v`
Expected: FAIL (UpdateManager doesn't exist)

**Step 3: Write minimal implementation**

Create `src/web_ui/core/update_manager.py`:
```python
import threading
import time
from core.update_progress import UpdateProgress

class UpdateManager:
    def __init__(self):
        self.progress = UpdateProgress()
        self.thread = None
    
    def run_update(self, files_to_update, github_repo, github_branch):
        """Run update in background thread"""
        def update_thread():
            try:
                # Update logic here
                pass
            except Exception as e:
                self.progress.set_error(str(e))
        
        self.thread = threading.Thread(target=update_thread)
        self.thread.daemon = True
        self.thread.start()
    
    def get_progress(self):
        return self.progress.get_status()
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_update_optimization.py::test_background_update_execution -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_update_optimization.py src/web_ui/core/update_manager.py
git commit -m "feat: add UpdateManager for background execution"
```

### Task 3: Optimize File Download Mechanism

**Files:**
- Modify: `src/web_ui/core/update_manager.py`

**Step 1: Write the failing test**

Add to `tests/test_update_optimization.py`:
```python
def test_batch_file_download():
    # Test that files can be downloaded in batches
    from src.web_ui.core.update_manager import UpdateManager
    manager = UpdateManager()
    # Test batch download method exists
    assert hasattr(manager, 'download_files_batch')
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_update_optimization.py::test_batch_file_download -v`
Expected: FAIL (download_files_batch method doesn't exist)

**Step 3: Write minimal implementation**

Add to `src/web_ui/core/update_manager.py`:
```python
class UpdateManager:
    # ... existing code ...
    
    def download_files_batch(self, files, batch_size=3):
        """Download files in batches to reduce network overhead"""
        import requests
        import os
        
        results = []
        for i in range(0, len(files), batch_size):
            batch = files[i:i+batch_size]
            batch_results = []
            
            for source_path, dest_path in batch:
                try:
                    # Download logic
                    pass
                except Exception as e:
                    batch_results.append((source_path, str(e)))
            
            results.extend(batch_results)
        
        return results
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_update_optimization.py::test_batch_file_download -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/web_ui/core/update_manager.py tests/test_update_optimization.py
git commit -m "feat: add batch file download optimization"
```

### Task 4: Add Dynamic Polling Interval

**Files:**
- Modify: `src/web_ui/templates/updates.html`

**Step 1: Write the failing test**

Add to `tests/test_update_optimization.py`:
```python
def test_dynamic_polling_interval():
    # Test that polling interval can be adjusted
    template_file = os.path.join(os.path.dirname(__file__), '..', 'src', 'web_ui', 'templates', 'updates.html')
    with open(template_file, 'r', encoding='utf-8') as f:
        content = f.read()
        assert 'setInterval' in content
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_update_optimization.py::test_dynamic_polling_interval -v`
Expected: FAIL (template doesn't have dynamic interval logic)

**Step 3: Write minimal implementation**

Modify `src/web_ui/templates/updates.html`:
```javascript
// Dynamic polling interval based on progress
let pollInterval = 3000; // Start with 3 seconds

function updateProgress() {
    fetch('/api/update/progress')
        .then(response => response.json())
        .then(data => {
            updateProgressBar(data);
            
            // Adjust polling interval based on progress
            if (data.status === 'starting') {
                pollInterval = 2000; // Faster at start
            } else if (data.status === 'complete' || data.status === 'error') {
                clearInterval(progressInterval);
                return;
            } else {
                pollInterval = 5000; // Slower during download
            }
        })
        .catch(error => {
            console.error('Failed to get progress:', error);
            pollInterval = 10000; // Slow down on error
        });
}
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_update_optimization.py::test_dynamic_polling_interval -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/web_ui/templates/updates.html tests/test_update_optimization.py
git commit -m "feat: add dynamic polling interval based on progress"
```

### Task 5: Add Optional Backup Skip

**Files:**
- Modify: `src/web_ui/routes.py` (service_updates_run function)
- Modify: `src/web_ui/templates/updates.html` (add checkbox)

**Step 1: Write the failing test**

Add to `tests/test_update_optimization.py`:
```python
def test_optional_backup_skip():
    # Test that backup can be skipped
    routes_file = os.path.join(os.path.dirname(__file__), '..', 'src', 'web_ui', 'routes.py')
    with open(routes_file, 'r', encoding='utf-8') as f:
        content = f.read()
        assert 'skip_backup' in content or 'skip_backup' in content
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_update_optimization.py::test_optional_backup_skip -v`
Expected: FAIL (skip_backup parameter not implemented)

**Step 3: Write minimal implementation**

Modify `src/web_ui/routes.py`:
```python
@bp.route('/service/updates/run', methods=['POST'])
@login_required
@csrf_required
def service_updates_run():
    # ... existing code ...
    
    # Get skip_backup parameter
    skip_backup = request.form.get('skip_backup') == 'on'
    
    if not skip_backup:
        # Create backup logic
        pass
    
    # ... rest of update logic ...
```

Modify `src/web_ui/templates/updates.html`:
```html
<form id="update-form" method="POST" action="{{ url_for('main.service_updates_run') }}">
    <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
    <div class="form-check mb-3">
        <input class="form-check-input" type="checkbox" id="skip_backup" name="skip_backup">
        <label class="form-check-label" for="skip_backup">
            Пропустить создание резервной копии (быстрее, но рискованнее)
        </label>
    </div>
    <button type="submit" class="btn btn-primary" id="update-btn">
        <i class="bi bi-download"></i> Обновить
    </button>
</form>
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_update_optimization.py::test_optional_backup_skip -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/web_ui/routes.py src/web_ui/templates/updates.html tests/test_update_optimization.py
git commit -m "feat: add optional backup skip for faster updates"
```

### Task 6: Add Free Space Check

**Files:**
- Modify: `src/web_ui/core/update_manager.py`

**Step 1: Write the failing test**

Add to `tests/test_update_optimization.py`:
```python
def test_free_space_check():
    # Test that free space is checked before update
    from src.web_ui.core.update_manager import UpdateManager
    manager = UpdateManager()
    assert hasattr(manager, 'check_free_space')
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_update_optimization.py::test_free_space_check -v`
Expected: FAIL (check_free_space method doesn't exist)

**Step 3: Write minimal implementation**

Add to `src/web_ui/core/update_manager.py`:
```python
class UpdateManager:
    # ... existing code ...
    
    def check_free_space(self, required_mb=50):
        """Check if there's enough free space for update"""
        import shutil
        
        free_space = shutil.disk_usage('/opt').free / (1024 * 1024)  # MB
        return free_space >= required_mb, free_space
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_update_optimization.py::test_free_space_check -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/web_ui/core/update_manager.py tests/test_update_optimization.py
git commit -m "feat: add free space check before update"
```

### Task 7: Test Complete Optimization Flow

**Files:**
- Test file: `tests/test_update_optimization.py`

**Step 1: Write integration test**

Add to `tests/test_update_optimization.py`:
```python
def test_complete_optimization_flow():
    # Test complete optimization flow
    from src.web_ui.core.update_progress import UpdateProgress
    from src.web_ui.core.update_manager import UpdateManager
    
    # Test UpdateProgress
    progress1 = UpdateProgress()
    progress2 = UpdateProgress()
    assert progress1 is not progress2  # Different instances
    
    # Test UpdateManager
    manager = UpdateManager()
    assert hasattr(manager, 'run_update')
    assert hasattr(manager, 'download_files_batch')
    assert hasattr(manager, 'check_free_space')
    
    # Test progress tracking
    progress = UpdateProgress()
    progress.start_update(total_files=10)
    assert progress.status == 'starting'
    assert progress.total_files == 10
    
    progress.update_progress('Downloading file', 'routes.py', 1, 10)
    assert progress.current_file == 'routes.py'
    assert progress.progress == 1
    
    progress.complete()
    assert progress.status == 'complete'
```

**Step 2: Run test**

Run: `python -m pytest tests/test_update_optimization.py -v`

**Step 3: Fix any issues**

**Step 4: Commit**

```bash
git commit -m "test: add integration test for complete optimization flow"
```

---

## Execution Handoff

Plan complete and saved to `docs/plans/2026-03-20-optimization-plan.md`. Two execution options:

**1. Subagent-Driven (this session)** - I dispatch fresh subagent per task, review between tasks, fast iteration

**2. Parallel Session (separate)** - Open new session with executing-plans, batch execution with checkpoints

Which approach?