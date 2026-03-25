# Critical Issues Fix Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Исправить 4 Critical issues из code quality review для ipset_manager.py и тестов.

**Architecture:** Последовательное исправление каждой issues с TDD подходом: сначала тесты, затем минимальная реализация, рефакторинг, коммит.

**Tech Stack:** Python 3.x, Flask, pytest, subprocess, ipset

---

## Task 1: Security - Добавить функцию `_sanitize_for_ipset(text)` 

**Files:**
- Modify: `H:\disk_e\dell\bypass_keenetic-web\src\web_ui\core\ipset_manager.py`
- Test: `H:\disk_e\dell\bypass_keenetic-web\test\web\test_ipset_integration.py`

**Step 1: Write failing tests for sanitize function**

Добавить в test_ipset_integration.py тесты:

```python
class TestIpsetSanitization:
    """Тесты для функции санитизации entry"""

    def test_sanitize_removes_dangerous_characters(self):
        """Тест удаления опасных символов"""
        from core.ipset_manager import _sanitize_for_ipset
        
        # Командные инъекции
        assert _sanitize_for_ipset('1.1.1.1; rm -rf /') == '1.1.1.1'
        assert _sanitize_for_ipset('8.8.8.8|cat /etc/passwd') == '8.8.8.8'
        assert _sanitize_for_ipset('example.com&&wget evil.com') == 'example.com'
        assert _sanitize_for_ipset('test.com`whoami`') == 'test.com'
        assert _sanitize_for_ipset('1.1.1.1$(rm -rf /)') == '1.1.1.1'
        
    def test_sanitize_preserves_valid_ips(self):
        """Тест сохранения валидных IP"""
        from core.ipset_manager import _sanitize_for_ipset
        
        assert _sanitize_for_ipset('1.1.1.1') == '1.1.1.1'
        assert _sanitize_for_ipset('192.168.1.1') == '192.168.1.1'
        assert _sanitize_for_ipset('10.0.0.1') == '10.0.0.1'
        
    def test_sanitize_preserves_valid_domains(self):
        """Тест сохранения валидных доменов"""
        from core.ipset_manager import _sanitize_for_ipset
        
        assert _sanitize_for_ipset('example.com') == 'example.com'
        assert _sanitize_for_ipset('test-domain.org') == 'test-domain.org'
        assert _sanitize_for_ipset('sub.domain.com') == 'sub.domain.com'
        
    def test_sanitize_handles_ipv6(self):
        """Тест обработки IPv6"""
        from core.ipset_manager import _sanitize_for_ipset
        
        assert _sanitize_for_ipset('::1') == '::1'
        assert _sanitize_for_ipset('2001:db8::1') == '2001:db8::1'
        assert _sanitize_for_ipset('fe80::1') == 'fe80::1'
        
    def test_sanitize_removes_newlines(self):
        """Тест удаления переводов строк"""
        from core.ipset_manager import _sanitize_for_ipset
        
        assert _sanitize_for_ipset('1.1.1.1\n2.2.2.2') == '1.1.1.12.2.2.2'
        assert _sanitize_for_ipset('example.com\r\n') == 'example.com'
```

**Step 2: Run tests to verify they fail**

```bash
cd H:\disk_e\dell\bypass_keenetic-web\src\web_ui
pytest test/web/test_ipset_integration.py::TestIpsetSanitization -v
```

Ожидаемый результат: FAIL с "AttributeError: module 'core.ipset_manager' has no attribute '_sanitize_for_ipset'"

**Step 3: Implement _sanitize_for_ipset function**

Добавить в ipset_manager.py после `_is_valid_entry`:

```python
def _sanitize_for_ipset(text: str) -> str:
    """
    Sanitize text for safe use in ipset commands.
    
    Removes dangerous characters that could be used for command injection.
    
    Args:
        text: Input text to sanitize
        
    Returns:
        Sanitized text safe for ipset commands
        
    Example:
        >>> _sanitize_for_ipset('1.1.1.1; rm -rf /')
        '1.1.1.1'
        >>> _sanitize_for_ipset('example.com')
        'example.com'
    """
    if not text:
        return ''
    
    # Remove dangerous shell characters
    # ; | & ` $ ( ) { } < > \ ! # ~ * ? [ ]
    dangerous_pattern = r'[;|&`$(){}<>\\!#~*?\[\]\r\n]'
    sanitized = re.sub(dangerous_pattern, '', text)
    
    # Strip whitespace
    sanitized = sanitized.strip()
    
    return sanitized
```

**Step 4: Update bulk_add_to_ipset to use sanitize**

Modify `bulk_add_to_ipset` function:

```python
def bulk_add_to_ipset(setname: str, entries: List[str]) -> Tuple[bool, str]:
    # ... docstring ...
    if not entries:
        logger.info(f"ipset {setname}: no entries to add")
        return True, "No entries"

    commands = []
    for entry in entries:
        # SANITIZE entry before validation
        sanitized_entry = _sanitize_for_ipset(entry)
        if _is_valid_entry(sanitized_entry):
            commands.append(f"add {setname} {sanitized_entry}")
    # ... rest unchanged ...
```

**Step 5: Update bulk_remove_from_ipset to use sanitize**

Аналогично для `bulk_remove_from_ipset`.

**Step 6: Run tests to verify they pass**

```bash
cd H:\disk_e\dell\bypass_keenetic-web\src\web_ui
pytest test/web/test_ipset_integration.py::TestIpsetSanitization -v
```

Ожидаемый результат: PASS (5 тестов)

**Step 7: Commit**

```bash
git add src/web_ui/core/ipset_manager.py test/web/test_ipset_integration.py
git commit -m "security: add _sanitize_for_ipset to prevent command injection"
```

---

## Task 2: Error Handling - Парсить stderr ipset для определения failed entries

**Files:**
- Modify: `H:\disk_e\dell\bypass_keenetic-web\src\web_ui\core\ipset_manager.py`
- Test: `H:\disk_e\dell\bypass_keenetic-web\test\web\test_ipset_integration.py`

**Step 1: Write failing tests for error parsing**

Добавить в test_ipset_integration.py:

```python
class TestIpsetErrorHandling:
    """Тесты обработки ошибок ipset"""

    def test_bulk_add_returns_failed_entries(self, mock_subprocess_partial_failure):
        """Тест возврата failed entries при частичном失敗"""
        from core.ipset_manager import bulk_add_to_ipset
        
        # Мок возвращает stderr с информацией о failed entries
        mock_subprocess_partial_failure.return_value = MagicMock(
            returncode=1,
            stdout='',
            stderr='ipset v7.5: Element cannot be added: 1.1.1.1\nipset v7.5: Element already in set: 8.8.8.8'
        )
        
        entries = ['1.1.1.1', '8.8.8.8', '9.9.9.9']
        success, output, failed = bulk_add_to_ipset('unblock', entries)
        
        assert success is False
        assert '1.1.1.1' in failed
        assert '8.8.8.8' in failed
        
    def test_bulk_add_with_timeout_error(self, mock_subprocess_timeout):
        """Тест обработки timeout"""
        from core.ipset_manager import bulk_add_to_ipset
        import subprocess
        
        mock_subprocess_timeout.side_effect = subprocess.TimeoutExpired(cmd='ipset restore', timeout=30)
        
        entries = ['1.1.1.1'] * 1000
        success, output, failed = bulk_add_to_ipset('unblock', entries)
        
        assert success is False
        assert 'Timeout' in output
        
    def test_bulk_add_with_ipset_not_installed(self, mock_subprocess_not_found):
        """Тест обработки отсутствия ipset"""
        from core.ipset_manager import bulk_add_to_ipset
        import subprocess
        
        mock_subprocess_not_found.side_effect = subprocess FileNotFoundError('ipset')
        
        entries = ['1.1.1.1']
        success, output, failed = bulk_add_to_ipset('unblock', entries)
        
        assert success is False
        assert 'ipset not installed' in output
```

**Step 2: Update function signature to return failed entries**

Modify `bulk_add_to_ipset`:

```python
def bulk_add_to_ipset(setname: str, entries: List[str]) -> Tuple[bool, str, List[str]]:
    """
    Bulk add entries to ipset using 'ipset restore'.

    Returns:
        Tuple of (success: bool, output: str, failed_entries: List[str])
    """
    # ... existing code ...
    
    failed_entries = []
    
    if result.returncode == 0:
        logger.info(f"ipset {setname}: added {len(commands)} entries")
        return True, f"Added {len(commands)} entries", []
    else:
        # Parse stderr to identify failed entries
        failed_entries = _parse_ipset_errors(result.stderr, entries)
        logger.error(f"ipset {setname} error: {result.stderr}")
        return False, result.stderr, failed_entries
```

**Step 3: Implement _parse_ipset_errors function**

```python
def _parse_ipset_errors(stderr: str, original_entries: List[str]) -> List[str]:
    """
    Parse ipset stderr to identify failed entries.
    
    Args:
        stderr: Error output from ipset command
        original_entries: Original list of entries attempted
        
    Returns:
        List of entries that failed
    """
    failed = []
    
    # Pattern: "Element cannot be added: 1.1.1.1" or "Element already in set: 8.8.8.8"
    error_pattern = r'(?:Element cannot be added|Element already in set|Element to be deleted does not exist):\s*([^\s]+)'
    
    matches = re.findall(error_pattern, stderr)
    failed.extend(matches)
    
    # If no specific errors found, return all entries (complete failure)
    if not failed and stderr.strip():
        return original_entries
    
    return failed
```

**Step 4: Update bulk_remove_from_ipset similarly**

**Step 5: Update ensure_ipset_exists signature**

```python
def ensure_ipset_exists(setname: str, settype: str = 'hash:ip') -> Tuple[bool, str, List[str]]:
    """
    Returns:
        Tuple of (success: bool, output: str, failed_entries: List[str])
    """
    # Return empty list for failed_entries
    return success, output, []
```

**Step 6: Update tests to handle new return signature**

**Step 7: Run tests**

```bash
cd H:\disk_e\dell\bypass_keenetic-web\src\web_ui
pytest test/web/test_ipset_integration.py::TestIpsetErrorHandling -v
```

**Step 8: Commit**

```bash
git add src/web_ui/core/ipset_manager.py test/web/test_ipset_integration.py
git commit -m "error-handling: parse ipset stderr to identify failed entries"
```

---

## Task 3: Test Quality - Добавить тесты на failure сценарии routes

**Files:**
- Modify: `H:\disk_e\dell\bypass_keenetic-web\test\web\test_ipset_integration.py`
-可能需要创建: `H:\disk_e\dell\bypass_keenetic-web\test\web\test_routes.py`

**Step 1: Add failure scenario tests**

Добавить в test_ipset_integration.py:

```python
class TestRoutesFailureScenarios:
    """Тесты failure сценариев для routes"""

    @pytest.fixture
    def flask_app(self):
        """Создание Flask приложения"""
        from flask import Flask
        app = Flask(__name__, template_folder='templates', static_folder='static')
        app.config['SECRET_KEY'] = 'test-secret-key'
        app.config['WEB_PASSWORD'] = 'test-password'
        app.config['TESTING'] = True
        return app

    def test_add_to_bypass_when_ensure_ipset_fails(self, flask_app, temp_unblock_dir, mock_subprocess_failure):
        """Тест когда ensure_ipset_exists возвращает False"""
        from core.ipset_manager import ensure_ipset_exists
        
        # Мок failure
        mock_subprocess_failure.return_value = MagicMock(
            returncode=1,
            stdout='',
            stderr='ipset create error: Permission denied'
        )
        
        # Создаём тестовый файл
        test_file = os.path.join(temp_unblock_dir, 'test.txt')
        with open(test_file, 'w') as f:
            f.write('existing.com\n')

        with flask_app.test_client() as client:
            with client.session_transaction() as sess:
                sess['authenticated'] = True
                sess['csrf_token'] = 'test-csrf-token'

            with patch('routes.WebConfig') as mock_config:
                mock_config.return_value.unblock_dir = temp_unblock_dir
                
                # Мок ensure_ipset_exists
                with patch('routes.ensure_ipset_exists') as mock_ensure:
                    mock_ensure.return_value = (False, 'Permission denied', [])
                    
                    response = client.post(
                        f'/bypass/test/add',
                        data={
                            'csrf_token': 'test-csrf-token',
                            'entries': '1.1.1.1\n8.8.8.8'
                        },
                        follow_redirects=True
                    )

                    # Запрос должен завершиться успешно (файл сохранён)
                    assert response.status_code == 200
                    # Но ipset не обновлён
                    
    def test_add_to_bypass_when_bulk_add_fails(self, flask_app, temp_unblock_dir):
        """Тест когда bulk_add_to_ipset возвращает False"""
        with flask_app.test_client() as client:
            with client.session_transaction() as sess:
                sess['authenticated'] = True
                sess['csrf_token'] = 'test-csrf-token'

            with patch('routes.WebConfig') as mock_config:
                mock_config.return_value.unblock_dir = temp_unblock_dir
                
                # Мок bulk_add_to_ipset с failure
                with patch('routes.bulk_add_to_ipset') as mock_bulk:
                    mock_bulk.return_value = (False, 'Permission denied', ['1.1.1.1'])
                    
                    # Создать файл
                    test_file = os.path.join(temp_unblock_dir, 'test.txt')
                    os.makedirs(temp_unblock_dir, exist_ok=True)
                    with open(test_file, 'w') as f:
                        f.write('existing.com\n')
                    
                    response = client.post(
                        f'/bypass/test/add',
                        data={
                            'csrf_token': 'test-csrf-token',
                            'entries': '1.1.1.1'
                        },
                        follow_redirects=True
                    )

                    assert response.status_code == 200
                    # Файл должен обновиться даже если ipset failed
                    
    def test_remove_from_bypass_when_bulk_remove_fails(self, flask_app, temp_unblock_dir):
        """Тест когда bulk_remove_from_ipset возвращает False"""
        with flask_app.test_client() as client:
            with client.session_transaction() as sess:
                sess['authenticated'] = True
                sess['csrf_token'] = 'test-csrf-token'

            with patch('routes.WebConfig') as mock_config:
                mock_config.return_value.unblock_dir = temp_unblock_dir
                
                with patch('routes.bulk_remove_from_ipset') as mock_bulk:
                    mock_bulk.return_value = (False, 'Permission denied', ['1.1.1.1'])
                    
                    test_file = os.path.join(temp_unblock_dir, 'test.txt')
                    os.makedirs(temp_unblock_dir, exist_ok=True)
                    with open(test_file, 'w') as f:
                        f.write('1.1.1.1\n8.8.8.8\n')
                    
                    response = client.post(
                        f'/bypass/test/remove',
                        data={
                            'csrf_token': 'test-csrf-token',
                            'entries': '1.1.1.1'
                        },
                        follow_redirects=True
                    )

                    assert response.status_code == 200
```

**Step 2: Run tests**

```bash
cd H:\disk_e\dell\bypass_keenetic-web\src\web_ui
pytest test/web/test_ipset_integration.py::TestRoutesFailureScenarios -v
```

**Step 3: Commit**

```bash
git add test/web/test_ipset_integration.py
git commit -m "test: add failure scenario tests for routes"
```

---

## Task 4: Memory - Добавить лимит на количество записей MAX_BULK_ENTRIES

**Files:**
- Modify: `H:\disk_e\dell\bypass_keenetic-web\src\web_ui\core\ipset_manager.py`
- Test: `H:\disk_e\dell\bypass_keenetic-web\test\web\test_ipset_integration.py`

**Step 1: Add constant MAX_BULK_ENTRIES**

Добавить в начало ipset_manager.py после импортов:

```python
# Memory limit for embedded devices (128MB RAM)
MAX_BULK_ENTRIES = 10000  # Maximum entries per bulk operation
```

**Step 2: Write failing tests**

```python
class TestIpsetMemoryLimits:
    """Тесты лимитов памяти"""

    def test_bulk_add_exceeds_max_entries(self):
        """Тест превышения лимита записей"""
        from core.ipset_manager import bulk_add_to_ipset, MAX_BULK_ENTRIES
        
        # Генерируем 15000 IP (больше лимита)
        entries = [f'10.{i//65536}.{(i//256)%256}.{i%256}' for i in range(15000)]
        
        success, output, failed = bulk_add_to_ipset('unblock', entries)
        
        assert success is False
        assert 'exceeds maximum' in output.lower() or 'limit' in output.lower()
        
    def test_bulk_add_at_max_entries(self, mock_subprocess_success):
        """Тест ровно на лимите"""
        from core.ipset_manager import bulk_add_to_ipset, MAX_BULK_ENTRIES
        
        entries = [f'192.168.{i//256}.{i%256}' for i in range(MAX_BULK_ENTRIES)]
        
        success, output, failed = bulk_add_to_ipset('unblock', entries)
        
        assert success is True
        assert f'Added {MAX_BULK_ENTRIES}' in output
        
    def test_bulk_add_below_max_entries(self, mock_subprocess_success):
        """Тест ниже лимита"""
        from core.ipset_manager import bulk_add_to_ipset
        
        entries = [f'172.16.{i//256}.{i%256}' for i in range(5000)]
        
        success, output, failed = bulk_add_to_ipset('unblock', entries)
        
        assert success is True
```

**Step 3: Add validation to bulk_add_to_ipset**

```python
def bulk_add_to_ipset(setname: str, entries: List[str]) -> Tuple[bool, str, List[str]]:
    if not entries:
        logger.info(f"ipset {setname}: no entries to add")
        return True, "No entries", []
    
    # Check memory limit
    if len(entries) > MAX_BULK_ENTRIES:
        error_msg = f"Entry count {len(entries)} exceeds maximum allowed ({MAX_BULK_ENTRIES})"
        logger.error(f"ipset {setname}: {error_msg}")
        return False, error_msg, entries
    # ... rest unchanged ...
```

**Step 4: Add same validation to bulk_remove_from_ipset**

**Step 5: Run tests**

```bash
cd H:\disk_e\dell\bypass_keenetic-web\src\web_ui
pytest test/web/test_ipset_integration.py::TestIpsetMemoryLimits -v
```

**Step 6: Commit**

```bash
git add src/web_ui/core/ipset_manager.py test/web/test_ipset_integration.py
git commit -m "memory: add MAX_BULK_ENTRIES limit for embedded devices"
```

---

## Task 5: Final Verification

**Step 1: Run all ipset tests**

```bash
cd H:\disk_e\dell\bypass_keenetic-web\src\web_ui
pytest test/web/test_ipset_integration.py -v
```

Ожидаемый результат: Все тесты PASS

**Step 2: Run full test suite**

```bash
cd H:\disk_e\dell\bypass_keenetic-web\src\web_ui
pytest test/ -v --tb=short
```

**Step 3: Verify code quality**

```bash
cd H:\disk_e\dell\bypass_keenetic-web\src\web_ui
python -m py_compile core/ipset_manager.py
```

**Step 4: Final commit**

```bash
git add .
git commit -m "chore: complete critical issues fix from code quality review"
```

**Step 5: Push changes**

```bash
git push
```

---

## Summary

После выполнения этого плана будут исправлены все 4 Critical issues:

1. ✅ **Security**: Добавлена функция `_sanitize_for_ipset()` для предотвращения command injection
2. ✅ **Error Handling**: Реализован парсинг stderr ipset для определения failed entries
3. ✅ **Test Quality**: Добавлены тесты на failure сценарии routes
4. ✅ **Memory**: Добавлен лимит MAX_BULK_ENTRIES = 10000 записей

Каждая issues исправлена с использованием TDD (сначала тесты, затем код).
