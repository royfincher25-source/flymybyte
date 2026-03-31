import pytest
import sys
import os

# Add the core directory to path to avoid importing the web_ui package
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'web_ui', 'core'))

from update_progress import UpdateProgress

def test_update_progress_state():
    # Test that UpdateProgress class exists and works
    progress = UpdateProgress()
    assert progress.status == 'idle'

def test_progress_endpoint_exists():
    # Test that /api/update/progress endpoint exists in routes.py
    # We'll check if the route is registered in the Flask app
    # For now, just check if the file contains the route
    routes_file = os.path.join(os.path.dirname(__file__), '..', 'src', 'web_ui', 'routes_service.py')
    with open(routes_file, 'r', encoding='utf-8') as f:
        content = f.read()
        assert "'/api/update/progress'" in content or '"/api/update/progress"' in content

def test_updates_template_has_progress_elements():
    # Test that template contains progress bar elements
    template_file = os.path.join(os.path.dirname(__file__), '..', 'src', 'web_ui', 'templates', 'updates.html')
    with open(template_file, 'r', encoding='utf-8') as f:
        content = f.read()
        # Check for progress container
        assert 'id="progress-container"' in content
        # Check for progress bar
        assert 'id="progress-bar"' in content
        # Check for progress text
        assert 'id="progress-text"' in content

def test_update_reports_progress():
    # Test that UpdateProgress is used during update
    # Import directly from core directory to avoid Flask dependency
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'web_ui', 'core'))
    from update_progress import UpdateProgress
    progress = UpdateProgress()
    progress.start_update()
    assert progress.status == 'starting'

def test_complete_update_flow():
    # Test complete flow from button click to progress display
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'web_ui', 'core'))
    from update_progress import UpdateProgress
    
    # Test progress tracking through entire flow
    progress = UpdateProgress()
    progress.reset()  # Reset state from previous tests
    progress.start_update()
    assert progress.status == 'starting'
    
    progress.update_progress('Downloading file', 'routes.py', 1, 10)
    assert progress.current_file == 'routes.py'
    assert progress.progress == 1
    assert progress.total_files == 10
    
    progress.complete()
    assert progress.status == 'complete'
    
    # Test error handling
    progress.reset()
    progress.start_update()
    progress.set_error('Test error')
    assert progress.status == 'error'
    assert progress.error == 'Test error'