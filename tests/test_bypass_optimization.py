import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'web_ui'))

def test_add_to_bypass_exists():
    """Test that add_to_bypass function exists"""
    from routes_bypass import add_to_bypass
    assert add_to_bypass is not None
    print("✓ add_to_bypass function exists")

def test_optimized_scripts_exist():
    """Test that optimized scripts exist and are valid"""
    import os
    
    scripts = [
        'src/web_ui/resources/scripts/unblock_ipset.sh',
        'src/web_ui/resources/scripts/unblock_dnsmasq.sh',
        'src/web_ui/resources/scripts/unblock_update.sh'
    ]
    
    for script in scripts:
        assert os.path.exists(script), f"Script {script} not found"
        
        # Check script is executable (only on Unix systems, skip on Windows)
        if os.name != 'nt':
            assert os.access(script, os.X_OK), f"Script {script} is not executable"
    
    print("✓ All optimized scripts exist")

def test_routes_optimization():
    """Test that routes have been optimized (split into blueprints)"""
    import os
    
    # Check split blueprint files exist
    blueprints = [
        'src/web_ui/routes_service.py',
        'src/web_ui/routes_keys.py',
        'src/web_ui/routes_bypass.py'
    ]
    
    for bp_file in blueprints:
        assert os.path.exists(bp_file), f"Blueprint {bp_file} not found"
    
    # Check old monolith was removed
    assert not os.path.exists('src/web_ui/routes.py'), "Old routes.py should be removed"
    
    # Check for optimized logic in bypass blueprint
    with open('src/web_ui/routes_bypass.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    assert 'bulk_add_to_ipset' in content, "Bulk add to ipset not found in bypass routes"
    
    # Check for thread pool in service blueprint
    with open('src/web_ui/routes_service.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    assert 'ThreadPoolExecutor' in content, "ThreadPoolExecutor not found in service routes"
    
    print("✓ Routes have been optimized (split into blueprints)")
