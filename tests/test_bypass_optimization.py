import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'web_ui'))

def test_add_to_bypass_exists():
    """Test that add_to_bypass function exists in routes_service"""
    from routes_service import add_to_bypass
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
        
        if os.name != 'nt':
            assert os.access(script, os.X_OK), f"Script {script} is not executable"
    
    print("✓ All optimized scripts exist")

def test_routes_optimization():
    """Test that routes are consolidated in routes_service.py"""
    import os
    
    # Check routes_service exists
    assert os.path.exists('src/web_ui/routes_service.py'), "routes_service.py not found"
    
    # Check old monolith was removed
    assert not os.path.exists('src/web_ui/routes.py'), "Old routes.py should be removed"
    
    with open('src/web_ui/routes_service.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check for optimized logic
    assert 'bulk_add_to_ipset' in content, "Bulk add to ipset not found in routes_service"
    assert 'ThreadPoolExecutor' in content, "ThreadPoolExecutor not found in routes_service"
    assert "@bp.route('/keys')" in content, "Keys route not found"
    assert "@bp.route('/bypass')" in content, "Bypass route not found"
    
    print("✓ Routes have been consolidated into routes_service.py")
