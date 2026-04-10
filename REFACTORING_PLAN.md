# FlyMyByte Web UI — План рефакторинга

## Дата: 2026-04-10
## Версия: 1.0

---

## 1. Текущее состояние

### Структура проекта
```
src/web_ui/
├── app.py                    # 131 строка — создание Flask app
├── routes_core.py            # 63  — авторизация, базовые страницы
├── routes_bypass.py          # 411 — списки обхода, DNS спуфинг
├── routes_system.py          # 981 — сервисы, бэкап, логи, статистика
├── routes_vpn.py            # 411 — управление ключами VPN
├── routes_updates.py        # --- — обновления
├── core/
│   ├── decorators.py        # 63  — @login_required, @csrf_required
│   ├── constants.py        # 298 — константы и пути
│   ├── utils.py           # 462 — утилиты, кэш, memory manager
│   ├── services.py        # 1500+ — парсеры, service management
│   ├── dns_ops.py        # ---  — DNS мониторинг
│   ├── ipset_ops.py      # ---  — ipset операции
│   ├── dnsmasq_manager.py # ---  — dnsmasq management
│   ├── iptables_manager.py # ---  — iptables management
│   ├── app_config.py    # ---  — конфигурация
│   └── emergency_restore.py
└── templates/, static/
```

### Метрики
- **Общее количество строк:** ~3500+
- **Количество Python файлов:** 15
- **Количество blueprints:** 5
- **Дублирование кода:** 3+ места

---

## 2. Выявленные проблемы

### 🔴 Критические (влияют на поддержку)

| # | Проблема | Файл(ы) | Сimpact |
|---|----------|---------|--------|
| 1 | Глобальное состояние `_RESTORE_STATUS` | routes_system.py:112 | Race conditions, непредсказуемое поведение |
| 2 | Дублирование backup функций | routes_system.py:38-105 | Дублирование логики, сложность изменений |
| 3 | Огромные файлы роутеров (>400 строк) | routes_system.py (981), routes_vpn.py (411) | Сложность навигации, review |
| 4 | Циклические импорты через `from .X import` | services.py, ipset_ops.py, dns_ops.py | Нестабильная загрузка |

### 🟠 Средние (влияют на разработку)

| # | Проблема | Файл(ы) | Impact |
|---|----------|---------|--------|
| 5 | Magic numbers | routes_bypass.py, routes_vpn.py | Хрупкий код, сложность тюнинга |
| 6 | Нет единой точки доступа к сервисам | ipset_ops, dns_ops, dnsmasq, iptables | Инверсия зависимостей |
| 7 | Разные стили обработки ошибок | routes/*.py | Нет консистентности |
| 8 | Нет type hints | Большинство функций | Сложность понимания API |

### 🟢 Низкие (косметика)

| # | Проблема | Файл(ы) | Impact |
|---|----------|---------|--------|
| 9 | Смешанные языки комментариев | Все файлы | Нечитаемость |
| 10 | Нет документации API | routes/*.py | Сложность интеграции |

---

## 3. Цели рефакторинга

### Главные цели
1. **Упрощение поддержки** — каждый модуль отвечает за одну вещь
2. **Улучшение тестируемости** — вынесение зависимостей
3. **Снижение coupling** — слабые связи между модулями
4. **Повышение читаемости** — понятный код без пояснений

### Нецели
1. Изменение функционала
2. Исправление багов
3. Изменение API endpoints

---

## 4. План выполнения

### Этап 1: Инфраструктура (базовый фундамент)

#### 1.1 Создать `core/config.py`
- Вынести все константы из `constants.py`
- Добавить Configuration dataclass
- Централизовать timeouts, limits

```python
# Целевой файл: src/web_ui/core/config.py
from dataclasses import dataclass
from typing import Final

@dataclass
class AppConfig:
    """Конфигурация приложения."""
    
    # Timeouts
    TIMEOUT_SERVICE_RESTART: int = 180  # seconds
    TIMEOUT_SCRIPT: int = 120
    TIMEOUT_BACKUP_RESTART: int = 600
    
    # Cache TTLs
    DEFAULT_CACHE_TTL: int = 60
    DNS_CACHE_TTL: int = 86400
    STATUS_CACHE_TTL: int = 60
    
    # Limits
    MAX_ENTRIES_PER_REQUEST: int = 100
    MAX_ENTRY_LENGTH: int = 253
    IP_BULK_SIZE: int = 5000
```

**Зависимости:** Нет
**Риск:** Низкий

---

#### 1.2 Создать `core/exceptions.py`
- Единые исключения для приложения
- Базовый класс `FlyMyByteException`

```python
# Целевой файл: src/web_ui/core/exceptions.py

class FlyMyByteError(Exception):
    """Базовый класс ошибок."""
    pass

class ServiceError(FlyMyByteError):
    """Ошибка сервиса."""
    pass

class ConfigError(FlyMyByteError):
    """Ошибка конфигурации."""
    pass
```

**Зависимости:** Нет
**Риск:** Низкий

---

#### 1.3 Создать `core/service_locator.py`
- Единая точка доступа ко всем сервисам
- Lazy loading с кэшированием

```python
# Целевой файл: src/web_ui/core/service_locator.py

class ServiceLocator:
    """Локатор сервисов — единая точка доступа."""
    
    _managers = {}
    
    @classmethod
    def ipset(cls):
        if 'ipset' not in cls._managers:
            from .ipset_ops import IptablesManager
            cls._managers['ipset'] = IptablesManager()
        return cls._managers['ipset']
    
    @classmethod
    def dnsmasq(cls):
        if 'dnsmasq' not in cls._managers:
            from .dnsmasq_manager import DnsmasqManager
            cls._managers['dnsmasq'] = DnsmasqManager()
        return cls._managers['dnsmasq']
    
    @classmethod
    def dns(cls):
        if 'dns' not in cls._managers:
            from .dns_ops import DNSMonitor
            cls._managers['dns'] = DNSMonitor()
        return cls._managers['dns']
    
    @classmethod
    def iptables(cls):
        if 'iptables' not in cls._managers:
            from .iptables_manager import IptablesManager
            cls._managers['iptables'] = IptablesManager()
        return cls._managers['iptables']
```

**Зависимости:** 1.1
**Риск:** Низкий
**Примечание:** Это замена текущих `get_dnsmasq_manager()`, `get_iptables_manager()` вызовов

---

#### 1.4 Создать декоратор `@handle_errors`
- Единая обработка ошибок во всех routes

```python
# Целевой файл: src/web_ui/core/handlers.py

def handle_errors(f):
    """Декоратор для единой обработки ошибок."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except FlyMyByteError as e:
            logger.warning(f"Expected error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 400
        except Exception as e:
            logger.exception("Unexpected error")
            return jsonify({'success': False, 'error': 'Internal error'}), 500
    return decorated_function
```

**Зависимости:** 1.2
**Риск:** Низкий

---

### Этап 2: Вынос бизнес-логики из routes

#### 2.1 Создать `core/backup_manager.py`
- Вынести функции backup/restore из routes_system.py

```python
# Целевой файл: src/web_ui/core/backup_manager.py
from typing import Tuple, List, Dict
from datetime import datetime
import tarfile
import os
import logging
from .constants import BACKUP_DIR, BACKUP_FILES
from .config import AppConfig

logger = logging.getLogger(__name__)


class BackupManager:
    """Менеджер резервного копирования."""
    
    def __init__(self, backup_dir: str = BACKUP_DIR):
        self.backup_dir = backup_dir
    
    def create(self, backup_type: str = 'full') -> Tuple[bool, str]:
        """Создать бэкап."""
        os.makedirs(self.backup_dir, exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_file = f'{self.backup_dir}/backup_{timestamp}.tar.gz'
        
        existing_files = [f for f in BACKUP_FILES if os.path.exists(f)]
        if not existing_files:
            return False, 'Нет файлов для бэкапа'
        
        with tarfile.open(backup_file, 'w:gz') as tar:
            for f in existing_files:
                tar.add(f, arcname=self._arcname(f))
        
        size_mb = os.path.getsize(backup_file) / 1024 / 1024
        return True, f'Бэкап создан: {backup_file} ({size_mb:.1f} МБ)'
    
    def list(self) -> List[Dict]:
        """Список бэкапов."""
        ...
    
    def delete(self, name: str) -> Tuple[bool, str]:
        """Удалить бэкап."""
        ...
    
    def restore_async(self, name: str) -> Tuple[bool, str]:
        """Восстановить из бэкапа (async)."""
        ...
    
    def _arcname(self, path: str) -> str:
        """Нормализовать путь для архива."""
        ...


# Singleton instance
_backup_manager = None

def get_backup_manager() -> BackupManager:
    global _backup_manager
    if _backup_manager is None:
        _backup_manager = BackupManager()
    return _backup_manager
```

**Изменяемые файлы:** routes_system.py (удалить дубликаты)
**Зависимости:** 1.1
**Риск:** Средний (изменение API)

---

#### 2.2 Создать `core/vpn_manager.py`
- Вынести логику toggle из routes_vpn.py

```python
# Целевой файл: src/web_ui/core/vpn_manager.py
from typing import Tuple, Optional
import subprocess
import time
import logging
from .constants import SERVICE_TOGGLE_CONFIG, INIT_SCRIPTS
from .config import AppConfig

logger = logging.getLogger(__name__)


class VPNManager:
    """Менеджер VPN сервисов."""
    
    def __init__(self, service_name: str):
        self.service_name = service_name
        self.config = SERVICE_TOGGLE_CONFIG.get(service_name, {})
        self.init_script = INIT_SCRIPTS.get(service_name)
    
    def start(self) -> Tuple[bool, str]:
        """Запустить сервис."""
        ...
    
    def stop(self) -> Tuple[bool, str]:
        """Остановить сервис."""
        ...
    
    def restart(self) -> Tuple[bool, str]:
        """Перезапустить сервис."""
        ...
    
    def get_status(self) -> str:
        """Получить статус."""
        ...
    
    def is_running(self) -> bool:
        """Проверить запущен ли."""
        ...
    
    def toggle(self) -> Tuple[bool, str]:
        """Toggle (start/stop)."""
        if self.is_running():
            return self.stop()
        return self.start()
```

**Изменяемые файлы:** routes_vpn.py (упростить)
**Зависимости:** 1.1
**Риск:** Средний

---

#### 2.3 Создать `core/key_manager.py`
- Управление ключами VPN

```python
# Целевой файл: src/web_ui/core/key_manager.py
from typing import Dict, Optional
from .services import parse_vless_key, parse_shadowsocks_key, parse_trojan_key
from .config import AppConfig

class KeyManager:
    """Менеджер ключей VPN."""
    
    PARSERS = {
        'vless': parse_vless_key,
        'shadowsocks': parse_shadowsocks_key,
        'trojan': parse_trojan_key,
    }
    
    def validate(self, key: str, service: str) -> Dict:
        """Валидировать ключ."""
        parser = self.PARSERS.get(service)
        if not parser:
            raise ValueError(f'Unknown service: {service}')
        return parser(key)
    
    def save_config(self, key: str, service: str, config_path: str) -> bool:
        """Сохранить конфиг и перезапустить."""
        ...
```

---

#### 2.4 Создать `core/error_handler.py`
- Единый обработчик HTTP ошибок

```python
# Целевой файл: src/web_ui/core/error_handler.py
from flask import jsonify
from functools import wraps
import logging

logger = logging.getLogger(__name__)

def api_error(f):
    """ Декоратор для обработки ошибок API."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except ValueError as e:
            logger.warning(f"Validation error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 400
        except Exception as e:
            logger.exception("API error")
            return jsonify({'success': False, 'error': 'Internal error'}), 500
    return wrapper
```

---

### Этап 3: Рефакторинг routes

#### 3.1 Разделить routes_system.py

**Текущее:** 981 строка, 20+ routes
**Целевое:**
- `routes_system.py` — только /service/* основные операции (~200 строк)
- `routes_backup.py` — /service/backup/* (~100 строк)
- `routes_stats.py` — /stats/* (~100 строк)
- `routes_logs.py` — /logs/* (~50 строк)

```python
# routes_backup.py — новый файл
from flask import Blueprint, render_template, request, flash, redirect, url_for
from core.decorators import login_required, csrf_required
from core.backup_manager import get_backup_manager

bp = Blueprint('backup', __name__, url_prefix='/service/backup')

@bp.route('/', methods=['GET', 'POST'])
@login_required
def index():
    manager = get_backup_manager()
    backups = manager.list()
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'create':
            success, msg = manager.create()
            flash(msg, 'success' if success else 'danger')
        elif action == 'delete':
            name = request.form.get('backup_name')
            success, msg = manager.delete(name)
            flash(msg, 'success' if success else 'danger')
        return redirect(url_for('backup.index'))
    return render_template('backup.html', backups=backups)
```

**Изменяемые файлы:** routes_system.py, templates/backup.html
**Зависимости:** 2.1
**Риск:** Средний

---

#### 3.2 Упростить routes_vpn.py

**Текущее:** 411 строк
**Целевое:** ~150 строк (только route декораторы)

```python
# routes_vpn.py — после рефакторинга
from flask import Blueprint, render_template, redirect, url_for, request, flash
from core.decorators import login_required, csrf_required
from core.vpn_manager import VPNManager
from core.key_manager import KeyManager

bp = Blueprint('vpn', __name__)

@bp.route('/keys')
@login_required
def keys():
    # Только получение данных для рендера
    services = {name: VPNManager(name).get_status() for name in ['vless', 'shadowsocks', 'trojan']}
    return render_template('keys.html', services=services)

@bp.route('/keys/<service>', methods=['GET', 'POST'])
@login_required
@csrf_required
def key_config(service: str):
    manager = VPNManager(service)
    if request.method == 'POST':
        key = request.form.get('key', '').strip()
        if not key:
            flash('Введите ключ', 'warning')
            return redirect(url_for('vpn.key_config', service=service))
        
        km = KeyManager()
        parsed = km.validate(key, service)
        ok = km.save_config(key, service, manager.config_path)
        
        if ok:
            flash(f'✅ {service} настроен', 'success')
        else:
            flash(f'❌ Ошибка сохранения', 'danger')
        return redirect(url_for('vpn.keys'))
    
    return render_template('key_generic.html', service=service)
```

**Изменяемые файлы:** routes_vpn.py
**Зависимости:** 2.2, 2.3
**Риск:** Средний

---

#### 3.3 Упрос��ит�� routes_bypass.py

**Целевое:** ~200 строк

```python
# routes_bypass.py — после рефакторинга
from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify
from core.decorators import login_required, csrf_required
from core.bypass_manager import BypassManager  # Новый модуль

bp = Blueprint('bypass', __name__)

@bp.route('/bypass')
@login_required
def list():
    manager = BypassManager()
    available_files = manager.list_files()
    return render_template('bypass.html', files=available_files)

@bp.route('/bypass//add', methods=['GET', 'POST'])
@login_required
@csrf_required
def add(filename: str):
    manager = BypassManager()
    if request.method == 'POST':
        entries = request.form.get('entries', '').split('\n')
        count = manager.add_entries(filename, entries)
        manager.apply_changes()
        flash(f'Добавлено {count} записей', 'success')
        return redirect(url_for('bypass.view', filename=filename))
    return render_template('bypass_add.html', filename=filename)
```

**Изменяемые файлы:** routes_bypass.py
**Зависимости:** 2.x (новые manager модули)
**Риск:** Средний

---

### Этап 4: Улучшение кода

#### 4.1 Добавить type hints

```python
# До
def load_bypass_list(filepath):
    if not os.path.exists(filepath):
        return []
    with open(filepath) as f:
        return [line.strip() for line in f]

# После
def load_bypass_list(filepath: str) -> List[str]:
    """Load bypass list from file.
    
    Args:
        filepath: Path to bypass list file.
        
    Returns:
        List of entries (domains or IPs), excluding comments.
    """
    if not os.path.exists(filepath):
        logger.warning(f"Bypass file not found: {filepath}")
        return []
    with open(filepath, encoding='utf-8') as f:
        return [line.strip() for line in f if line.strip() and not line.startswith('#')]
```

#### 4.2 Вынести константы из app.py в config

```python
# app.py — до
from core.constants import WebConfig

# app.py — после  
from core.config import AppConfig, Settings

config = Settings.load()  # Читает .env или defaults
```

---

## 5. График выполнения

| Этап | Задачи | Оценка | Зависимости |
|------|--------|--------|------------|
| 1. Инфраструктура | 1.1–1.4 | 2 часа | — |
| 2. Business Logic | 2.1–2.4 | 4 часа | 1.x |
| 3. Routes | 3.1–3.3 | 3 часа | 2.x |
| 4. Улучшения | 4.1–4.2 | 1 час | 3.x |

**Общая оценка:** 10 часов

---

## 6. Критерии успеха

### Метрики до/после

| Метрика | До | После |
|---------|-----|-------|
| Строк в routes_system.py | 981 | ~200 |
| Строк в routes_vpn.py | 411 | ~150 |
| Дублирующихся функций | 3+ | 0 |
| Файлов в core/ | 10 | 15+ |
| Type hints覆盖率 | ~30% | ~80% |

### Качественные критерии
- [ ] Каждый модуль отвечает за одну вещь
- [ ] Зависимости явно указаны в imports
- [ ] Ошибки обрабатываются централизованно
- [ ] Конфигурация в одном месте

---

## 7. Откат (rollback)

Если рефакторинг неудачен:
```bash
git checkout HEAD~1 -- src/web_ui/
```

---

## 8. Notes

- Без изменения функционала
- Без изменения API endpoints
- Сохранить обратную совместимость
- Все тесты должны проходить
- Минимальные изменения за ра��