import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'web_ui'))

from core.ipset_manager import save_ipset, restore_ipset, _sanitize_for_ipset, _is_valid_entry


def test_sanitize_for_ipset():
    """Test ipset entry sanitization"""
    assert _sanitize_for_ipset('1.1.1.1') == '1.1.1.1'
    assert _sanitize_for_ipset('example.com') == 'example.com'
    assert _sanitize_for_ipset('1.1.1.1;rm-rf') == '1.1.1.1rm-rf'


def test_is_valid_entry():
    """Test entry validation"""
    assert _is_valid_entry('1.1.1.1') == True
    assert _is_valid_entry('192.168.1.1') == True
    assert _is_valid_entry('example.com') == True
    assert _is_valid_entry('invalid!') == False


def test_save_restore_functions_exist():
    """Test that save and restore functions exist"""
    assert callable(save_ipset)
    assert callable(restore_ipset)
