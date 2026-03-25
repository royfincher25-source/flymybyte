# Update Progress Display Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the preloader with a detailed progress display showing which file is being downloaded and which script is being executed during the update process.

**Architecture:** 
- Use AJAX polling to get real-time progress updates from the server (SSE not suitable due to blocking operations)
- Store progress state in a global variable or file (simple approach for single-user embedded device)
- Show a progress bar with current file/script name and overall percentage
- Maintain backward compatibility with existing flash messages for final status

**Tech Stack:** Flask, JavaScript (Fetch API), Bootstrap progress bars, Python threading for background execution

---
### Task 1: Create progress state management and background update function

**Files:**
- Modify: `src/web_ui/routes.py` (add progress state management)
- Create: `src/web_ui/core/update_progress.py` (progress tracking module)

**Step 1: Write the failing test**

Create a test file `tests/test_update_progress.py`:
```python
import pytest
from src.web_ui.core.update_progress import UpdateProgress

def test_update_progress_state():
    # Test that UpdateProgress class exists and works
    progress = UpdateProgress()
    assert progress.status == 'idle'
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_update_progress.py::test_update_progress_state -v`
Expected: FAIL (module doesn't exist)

**Step 3: Write minimal implementation**

Create `src/web_ui/core/update_progress.py`:
```python
import threading
import time

class UpdateProgress:
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance.status = 'idle'
                cls._instance.message = ''
                cls._instance.current_file = ''
                cls._instance.progress = 0
                cls._instance.total_files = 0
                cls._instance.error = None
            return cls._instance
    
    def start_update(self):
        self.status = 'starting'
        self.message = 'Creating backup...'
        self.progress = 0
        self.error = None
    
    def update_progress(self, message, file='', progress=0, total=0):
        self.message = message
        self.current_file = file
        self.progress = progress
        self.total_files = total
    
    def set_error(self, error):
        self.status = 'error'
        self.error = error
    
    def complete(self):
        self.status = 'complete'
        self.message = 'Update completed'
    
    def reset(self):
        self.status = 'idle'
        self.message = ''
        self.current_file = ''
        self.progress = 0
        self.total_files = 0
        self.error = None
    
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

Run: `pytest tests/test_update_progress.py::test_update_progress_state -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_update_progress.py src/web_ui/core/update_progress.py
git commit -m "feat: add UpdateProgress class for tracking update state"
```

### Task 2: Create API endpoint for progress status

**Files:**
- Modify: `src/web_ui/routes.py` (add new endpoint)

**Step 1: Write the failing test**

Add test for progress endpoint:
```python
def test_progress_endpoint_exists():
    # Test that /api/update/progress endpoint exists
    assert False  # Will fail initially
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_update_progress.py::test_progress_endpoint_exists -v`
Expected: FAIL

**Step 3: Write minimal implementation**

Add progress endpoint:
```python
@bp.route('/api/update/progress', methods=['GET'])
@login_required
def get_update_progress():
    from core.update_progress import UpdateProgress
    progress = UpdateProgress()
    return jsonify(progress.get_status())
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_update_progress.py::test_progress_endpoint_exists -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/web_ui/routes.py
git commit -m "feat: add API endpoint for update progress status"
```

### Task 3: Update the updates.html template with progress UI

**Files:**
- Modify: `src/web_ui/templates/updates.html`

**Step 1: Write the failing test**

Create a test to verify template renders correctly:
```python
def test_updates_template_has_progress_elements():
    # Test that template contains progress bar elements
    assert False  # Will fail initially
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_update_progress.py::test_updates_template_has_progress_elements -v`
Expected: FAIL

**Step 3: Write minimal implementation**

Add progress UI to `updates.html` (replace the form with progress display):
```html
<!-- Replace the update button form with this -->
<div id="update-section">
    {% if need_update %}
        <div class="alert alert-warning">
            <i class="bi bi-exclamation-triangle"></i> Доступна новая версия! Рекомендуется обновить.
        </div>
        <form id="update-form" method="POST" action="{{ url_for('main.service_updates_run') }}">
            <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
            <button type="submit" class="btn btn-primary" id="update-btn">
                <i class="bi bi-download"></i> Обновить
            </button>
        </form>
        
        <!-- Progress display (hidden by default) -->
        <div id="progress-container" style="display: none; margin-top: 20px;">
            <div class="progress mb-3" style="height: 25px;">
                <div id="progress-bar" class="progress-bar progress-bar-striped progress-bar-animated" 
                     role="progressbar" style="width: 0%">0%</div>
            </div>
            <div id="progress-text" class="mb-2">Подготовка...</div>
            <div id="progress-details" class="small text-muted"></div>
            <div id="progress-error" class="alert alert-danger mt-2" style="display: none;"></div>
        </div>
    {% else %}
        <!-- ... existing code ... -->
    {% endif %}
</div>

<script>
// JavaScript for AJAX progress updates
let progressInterval = null;

document.getElementById('update-form').addEventListener('submit', function(e) {
    e.preventDefault();
    
    // Hide button, show progress
    document.getElementById('update-btn').style.display = 'none';
    document.getElementById('progress-container').style.display = 'block';
    
    // Start progress polling
    progressInterval = setInterval(updateProgress, 1000);
    
    // Submit form via AJAX
    const formData = new FormData(this);
    fetch(this.action, {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        clearInterval(progressInterval);
        if (data.success) {
            showCompletion(data.message);
        } else {
            showError(data.error || 'Update failed');
        }
    })
    .catch(error => {
        clearInterval(progressInterval);
        showError('Network error: ' + error.message);
    });
});

function updateProgress() {
    fetch('/api/update/progress')
        .then(response => response.json())
        .then(data => {
            updateProgressBar(data);
        })
        .catch(error => {
            console.error('Failed to get progress:', error);
        });
}

function updateProgressBar(data) {
    const progressBar = document.getElementById('progress-bar');
    const progressText = document.getElementById('progress-text');
    const progressDetails = document.getElementById('progress-details');
    
    let percentage = 0;
    if (data.total_files > 0) {
        percentage = Math.round((data.progress / data.total_files) * 100);
    }
    
    progressBar.style.width = percentage + '%';
    progressBar.textContent = percentage + '%';
    progressText.textContent = data.message;
    
    if (data.current_file) {
        progressDetails.textContent = 'Файл: ' + data.current_file;
    } else {
        progressDetails.textContent = '';
    }
    
    if (data.status === 'error') {
        showError(data.error);
    }
}

function showError(message) {
    const errorDiv = document.getElementById('progress-error');
    errorDiv.textContent = message;
    errorDiv.style.display = 'block';
    document.getElementById('progress-bar').classList.remove('progress-bar-animated');
    document.getElementById('progress-bar').classList.add('bg-danger');
}

function showCompletion(message) {
    const progressBar = document.getElementById('progress-bar');
    progressBar.style.width = '100%';
    progressBar.textContent = '100%';
    progressBar.classList.remove('progress-bar-animated');
    progressBar.classList.add('bg-success');
    document.getElementById('progress-text').textContent = message;
    document.getElementById('progress-details').textContent = '';
    
    // Reload page after 3 seconds
    setTimeout(() => {
        window.location.reload();
    }, 3000);
}
</script>
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_update_progress.py::test_updates_template_has_progress_elements -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/web_ui/templates/updates.html
git commit -m "feat: add progress display to updates page"
```

### Task 4: Integrate progress reporting into update function

**Files:**
- Modify: `src/web_ui/routes.py` (service_updates_run function)

**Step 1: Write the failing test**

Test that progress is reported during update:
```python
def test_update_reports_progress():
    # Test that UpdateProgress is used during update
    from src.web_ui.core.update_progress import UpdateProgress
    progress = UpdateProgress()
    progress.start_update()
    assert progress.status == 'starting'
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_update_progress.py::test_update_reports_progress -v`
Expected: FAIL (if UpdateProgress not properly integrated)

**Step 3: Write minimal implementation**

Modify `service_updates_run()` to update progress:
```python
@bp.route('/service/updates/run', methods=['POST'])
@login_required
@csrf_required
def service_updates_run():
    from core.update_progress import UpdateProgress
    import threading
    
    def run_update_in_background():
        progress = UpdateProgress()
        try:
            progress.start_update()
            
            # Backup logic with progress updates
            progress.update_progress('Creating backup...', total=len(files_to_backup))
            # ... backup code ...
            
            # Download files with progress updates
            for i, (source_path, dest_path) in enumerate(files_to_update.items()):
                progress.update_progress(f'Downloading {source_path}', 
                                       file=source_path, 
                                       progress=i+1, 
                                       total=len(files_to_update))
                # ... download code ...
            
            # Execute scripts with progress updates
            progress.update_progress('Executing unblock_update.sh...', file='unblock_update.sh')
            # ... script execution code ...
            
            progress.complete()
            
        except Exception as e:
            progress.set_error(str(e))
    
    # Start background thread
    thread = threading.Thread(target=run_update_in_background)
    thread.daemon = True
    thread.start()
    
    # Return immediately with success message
    return jsonify({
        'success': True,
        'message': 'Update started in background'
    })
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_update_progress.py::test_update_reports_progress -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/web_ui/routes.py
git commit -m "feat: integrate progress reporting into update process"
```

### Task 5: Test the complete update flow

**Files:**
- Test file: `tests/test_update_progress.py`

**Step 1: Write integration test**

```python
def test_complete_update_flow():
    # Test complete flow from button click to progress display
    from src.web_ui.core.update_progress import UpdateProgress
    
    # Test progress tracking through entire flow
    progress = UpdateProgress()
    progress.start_update()
    assert progress.status == 'starting'
    
    progress.update_progress('Downloading file', 'routes.py', 1, 10)
    assert progress.current_file == 'routes.py'
    assert progress.progress == 1
    assert progress.total_files == 10
    
    progress.complete()
    assert progress.status == 'complete'
```

**Step 2: Run test**

Run: `pytest tests/test_update_progress.py -v`

**Step 3: Fix any issues**

**Step 4: Commit**

```bash
git commit -m "test: add integration test for update progress flow"
```

---
## Execution Handoff

Plan complete and saved to `docs/plans/2026-03-20-update-progress-display.md`. Two execution options:

**1. Subagent-Driven (this session)** - I dispatch fresh subagent per task, review between tasks, fast iteration

**2. Parallel Session (separate)** - Open new session with executing-plans, batch execution with checkpoints

Which approach?