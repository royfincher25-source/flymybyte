# Critical Issues Fix Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Исправить 3 critical issues из code quality review (дублирование функций, memory leak, отсутствие импорта)

**Architecture:** Рефакторинг кода с удалением дублирования, оптимизация памяти через batch processing, централизация утилитарных функций

**Tech Stack:** Python 3, ThreadPoolExecutor, ipset, pytest

---

## Task 1: Удаление дублирования функции _sanitize_for_ipset() в ipset_manager.py

**Files:**
- Modify: `H:\disk_e\dell\bypass_keenetic-web\src\web_ui\core\ipset_manager.py:240-262`
- Test: `H:\disk_e\dell\bypass_keenetic-web\test\web\test_ipset_manager.py`

**Проблема:** Функция `_sanitize_for_ipset()` определена дважды (строки 240-262 и 280-304). Первое определение нужно удалить.

**Step 1: Прочитать файл и точно определить границы дубликата**

Прочитать строки 235-310 из `ipset_manager.py` для точного определения удаляемого кода.

**Step 2: Удалить первое определение функции (строки 240-262)**

Удалить блок:
```python
def _sanitize_for_ipset(text: str) -> str:
    """
    Sanitize text for safe use in ipset commands.
    ...
    """
    # Remove dangerous characters
    return re.sub(r'[\n\r\t;|&$`]', '', text)
```

**Step 3: Проверить, что осталось только второе определение (строки 280-304)**

Убедиться, что функция определена один раз с улучшенной версией (с проверкой на пустую строку и более полным набором опасных символов).

**Step 4: Запустить тесты**

Run: `pytest test/web/test_ipset_manager.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/web_ui/core/ipset_manager.py
git commit -m "refactor: remove duplicate _sanitize_for_ipset() function"
```

---

## Task 2: Исправление memory leak в dns_resolver.py через batch processing

**Files:**
- Modify: `H:\disk_e\dell\bypass_keenetic-web\src\web_ui\core\dns_resolver.py:125-133`
- Test: `H:\disk_e\dell\bypass_keenetic-web\test\web\test_dns_resolver.py`

**Проблема:** В функции `resolve_domains_for_ipset()` все IP собираются в список `all_ips`, что вызывает memory leak при большом количестве доменов.

**Текущий код (строки 125-133):**
```python
# Collect all IPs
all_ips = []
for domain, ips in resolved.items():
    all_ips.extend(ips)

# Remove duplicates
all_ips = list(set(all_ips))

# Bulk add to ipset
if all_ips:
```

**Step 1: Написать тест на batch processing**

Добавить в `test_dns_resolver.py`:
```python
def test_resolve_domains_batch_processing():
    """Test that large domain lists are processed in batches"""
    from core.dns_resolver import resolve_domains_for_ipset
    from unittest.mock import patch, MagicMock
    
    # Mock 1000 domains
    with patch('core.dns_resolver.load_bypass_list') as mock_load:
        mock_load.return_value = [f'domain{i}.com' for i in range(1000)]
        
        with patch('core.dns_resolver.parallel_resolve') as mock_resolve:
            mock_resolve.return_value = {
                f'domain{i}.com': [f'192.168.1.{i % 256}']
                for i in range(1000)
            }
            
            with patch('core.dns_resolver.bulk_add_to_ipset') as mock_bulk:
                mock_bulk.return_value = (True, 'Success')
                
                # Should process in batches, not collect all IPs
                result = resolve_domains_for_ipset('/tmp/test.txt')
                assert result > 0
```

**Step 2: Run test to verify it fails**

Run: `pytest test/web/test_dns_resolver.py::test_resolve_domains_batch_processing -v`
Expected: FAIL (test not exists yet)

**Step 3: Реализовать batch processing в resolve_domains_for_ipset()**

Заменить код на:
```python
def resolve_domains_for_ipset(filepath: str, max_workers: int = MAX_WORKERS) -> int:
    """
    Resolve domains from bypass list file and add to ipset.
    Uses batch processing to prevent memory issues with large domain lists.
    """
    from .utils import load_bypass_list
    from .ipset_manager import bulk_add_to_ipset, ensure_ipset_exists

    # Load domains from file
    entries = load_bypass_list(filepath)

    # Filter only domains (not IPs)
    domains = [e for e in entries if not _is_ip_address(e)]

    if not domains:
        logger.info(f"No domains to resolve in {filepath}")
        return 0

    # Process in batches to prevent memory issues
    BATCH_SIZE = 500  # Process 500 domains at a time
    total_ips_added = 0

    for i in range(0, len(domains), BATCH_SIZE):
        batch_domains = domains[i:i + BATCH_SIZE]
        
        # Resolve batch in parallel
        resolved = parallel_resolve(batch_domains, max_workers)
        
        # Collect IPs from this batch
        batch_ips = set()
        for domain, ips in resolved.items():
            batch_ips.update(ips)
        
        # Bulk add batch IPs to ipset
        if batch_ips:
            ensure_ipset_exists('unblock_domains')
            success, msg = bulk_add_to_ipset('unblock_domains', list(batch_ips))
            if success:
                total_ips_added += len(batch_ips)
                logger.info(f"Batch {i // BATCH_SIZE + 1}: added {len(batch_ips)} IPs")
            else:
                logger.error(f"Failed to add batch IPs: {msg}")

    logger.info(f"Total: added {total_ips_added} resolved IPs to ipset")
    return total_ips_added
```

**Step 4: Run test to verify it passes**

Run: `pytest test/web/test_dns_resolver.py::test_resolve_domains_batch_processing -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/web_ui/core/dns_resolver.py test/web/test_dns_resolver.py
git commit -m "fix: use batch processing in resolve_domains_for_ipset to prevent memory leak"
```

---

## Task 3: Удаление дублирования функции _is_ip_address() в dns_resolver.py

**Files:**
- Modify: `H:\disk_e\dell\bypass_keenetic-web\src\web_ui\core\dns_resolver.py:1-20,167-199`
- Test: `H:\disk_e\dell\bypass_keenetic-web\test\web\test_dns_resolver.py`

**Проблема:** Функция `_is_ip_address()` дублирует `is_ip_address()` из `core.utils`. Нужно импортировать и удалить локальную.

**Step 1: Добавить импорт в начало файла**

Изменить импорты (после строки 15):
```python
from .utils import load_bypass_list, is_ip_address
```

**Step 2: Удалить локальную функцию _is_ip_address() (строки 167-199)**

Удалить весь блок функции `_is_ip_address()`.

**Step 3: Заменить вызовы _is_ip_address() на is_ip_address()**

В строке 118 заменить:
```python
domains = [e for e in entries if not is_ip_address(e)]
```

**Step 4: Run tests**

Run: `pytest test/web/test_dns_resolver.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/web_ui/core/dns_resolver.py
git commit -m "refactor: import is_ip_address from utils instead of duplicating"
```

---

## Task 4: Добавление валидации входных данных в parallel_resolve()

**Files:**
- Modify: `H:\disk_e\dell\bypass_keenetic-web\src\web_ui\core\dns_resolver.py:74-99`
- Test: `H:\disk_e\dell\bypass_keenetic-web\test\web\test_dns_resolver.py`

**Проблема:** Функция `parallel_resolve()` не фильтрует None, пустые строки и дубликаты.

**Step 1: Написать тест на валидацию**

Добавить в `test_dns_resolver.py`:
```python
def test_parallel_resolve_with_invalid_inputs():
    """Test filtering of None, empty strings, and duplicates"""
    from core.dns_resolver import parallel_resolve
    
    # Test with None, empty strings, duplicates
    domains = ['google.com', None, '', 'google.com', 'facebook.com', '', None]
    results = parallel_resolve(domains, max_workers=2)
    
    # Should only resolve valid unique domains
    assert 'google.com' in results
    assert 'facebook.com' in results
    assert len(results) == 2  # No duplicates
```

**Step 2: Run test to verify it fails**

Run: `pytest test/web/test_dns_resolver.py::test_parallel_resolve_with_invalid_inputs -v`
Expected: FAIL (function may crash on None)

**Step 3: Добавить валидацию в parallel_resolve()**

Изменить функцию (после строки 74):
```python
def parallel_resolve(domains: List[str], max_workers: int = MAX_WORKERS) -> Dict[str, List[str]]:
    """
    Resolve multiple domains in parallel.
    Filters out None, empty strings, and duplicates.
    """
    if not domains:
        return {}

    # Filter out None, empty strings, and duplicates
    valid_domains = list(set(
        domain for domain in domains
        if domain and isinstance(domain, str) and domain.strip()
    ))

    if not valid_domains:
        return {}

    # Limit workers for embedded devices
    max_workers = min(max_workers, MAX_WORKERS)

    results = {}
    # ... rest of function
```

**Step 4: Run test to verify it passes**

Run: `pytest test/web/test_dns_resolver.py::test_parallel_resolve_with_invalid_inputs -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/web_ui/core/dns_resolver.py test/web/test_dns_resolver.py
git commit -m "feat: add input validation to parallel_resolve (filter None, empty, duplicates)"
```

---

## Task 5: Добавление моков для тестов DNS resolver

**Files:**
- Modify: `H:\disk_e\dell\bypass_keenetic-web\test\web\test_dns_resolver.py`

**Проблема:** Тесты зависят от реального сети, что делает их ненадёжными.

**Step 1: Добавить моки для socket.getaddrinfo**

Изменить тесты:
```python
import pytest
from unittest.mock import patch, MagicMock
import socket

@patch('core.dns_resolver.socket.getaddrinfo')
def test_resolve_single_domain(mock_getaddrinfo):
    """Test resolving a single domain with mocked DNS"""
    # Mock DNS response
    mock_getaddrinfo.return_value = [
        (socket.AF_INET, socket.SOCK_STREAM, 6, '', ('142.250.185.46', 0)),
        (socket.AF_INET, socket.SOCK_STREAM, 6, '', ('142.250.185.47', 0)),
    ]
    
    from core.dns_resolver import resolve_single
    ips = resolve_single('google.com')
    
    assert len(ips) == 2
    assert '142.250.185.46' in ips
    assert '142.250.185.47' in ips
```

**Step 2: Обновить остальные тесты с моками**

Аналогично обновить `test_parallel_resolve_multiple`, `test_parallel_resolve_with_invalid`, etc.

**Step 3: Run all tests**

Run: `pytest test/web/test_dns_resolver.py -v`
Expected: All PASS (no network dependency)

**Step 4: Commit**

```bash
git add test/web/test_dns_resolver.py
git commit -m "test: add mocks for socket.getaddrinfo to make tests independent of network"
```

---

## Verification

**Step 1: Run full test suite**

Run: `pytest test/web/ -v`
Expected: All tests PASS

**Step 2: Check for code duplication**

Run: `grep -n "_is_ip_address\|_sanitize_for_ipset" src/web_ui/core/*.py`
Expected: Each function defined only once

**Step 3: Verify memory optimization**

Проверить, что batch processing работает:
```python
# В Python console
from core.dns_resolver import resolve_domains_for_ipset
# Should process in batches, not load all IPs into memory
```

---

## Summary

**Critical issues fixed:**
1. ✅ Удалено дублирование `_sanitize_for_ipset()` в `ipset_manager.py`
2. ✅ Исправлен memory leak через batch processing в `dns_resolver.py`
3. ✅ Удалено дублирование `_is_ip_address()` через импорт из `utils`

**Important issues fixed:**
4. ✅ Добавлена валидация входных данных (None, empty, duplicates)
5. ✅ Добавлены моки для независимости тестов от сети

**Files modified:**
- `src/web_ui/core/ipset_manager.py`
- `src/web_ui/core/dns_resolver.py`
- `test/web/test_dns_resolver.py`
