# =============================================================================
# WEB CONFIGURATION MODULE
# =============================================================================
# Модуль конфигурации для web-приложения flymybyte
# Использует env_parser для загрузки .env файлов
# =============================================================================

import os
import re
import sys
import threading
from pathlib import Path
from typing import Any, Dict, Optional

# Импортируем константы из централизованного хранилища
from .constants import (
    DEFAULT_WEB_HOST,
    DEFAULT_WEB_PORT,
    DEFAULT_WEB_PASSWORD,
    DEFAULT_ROUTER_IP,
    DEFAULT_UNBLOCK_DIR,
    MIN_PORT,
    MAX_PORT,
)


# =============================================================================
# ИМПОРТ ENV PARSER
# =============================================================================

# Добавляем путь к директории web/ для импорта env_parser
WEB_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(WEB_ROOT))

# Пробуем импорт env_parser из той же директории
try:
    from env_parser import load_env_file, get_env, get_env_int
except ImportError:
    # Fallback: простой парсер
    def load_env_file(filepath):
        import re
        env = {}
        if os.path.exists(filepath):
            with open(filepath, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        match = re.match(r'^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$', line)
                        if match:
                            key, value = match.group(1), match.group(2)
                            if (value.startswith('"') and value.endswith('"')) or \
                               (value.startswith("'") and value.endswith("'")):
                                value = value[1:-1]
                            env[key] = value
        return env

    def get_env(key, default=None):
        return os.environ.get(key, default)

    def get_env_int(key, default=0):
        try:
            return int(get_env(key, default))
        except (ValueError, TypeError):
            return default


# =============================================================================
# КОНСТАНТЫ (импортируются из constants.py для единообразия)
# =============================================================================

from .constants import (
    DEFAULT_WEB_HOST,
    DEFAULT_WEB_PORT,
    DEFAULT_WEB_PASSWORD,
    DEFAULT_ROUTER_IP,
    DEFAULT_UNBLOCK_DIR,
    MIN_PORT,
    MAX_PORT,
)


# =============================================================================
# WEB CONFIG CLASS
# =============================================================================

class WebConfig:
    """
    Singleton класс для управления конфигурацией web-приложения.

    Использует env_parser для загрузки .env файлов, кэширует значения
    для уменьшения количества обращений к файлу.

    Attributes:
        web_host: Хост для web-сервера (default: 0.0.0.0)
        web_port: Порт для web-сервера (default: 8080)
        web_password: Пароль для доступа к web-интерфейсу (default: changeme)
        router_ip: IP-адрес роутера (default: 192.168.1.1)

    Example:
        >>> config = WebConfig()
        >>> config.web_port
        8080
        >>> config.is_valid()
        True
        >>> config.to_dict()
        {'web_host': '0.0.0.0', 'web_port': 8080, ...}
    """

    _instance: Optional['WebConfig'] = None
    _cache: Dict[str, Any] = {}
    _loaded: bool = False
    _env_file: Optional[str] = None
    _lock: threading.Lock = threading.Lock()

    def __new__(cls, env_file: Optional[str] = None) -> 'WebConfig':
        """
        Создание экземпляра (Singleton pattern с thread-safe блокировкой).

        Args:
            env_file: Путь к .env файлу. Если None, используется .env
                     в корневой директории проекта.

        Returns:
            Экземпляр WebConfig
        """
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:  # Double-check locking
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self, env_file: Optional[str] = None):
        """
        Инициализация конфигурации.
        
        Args:
            env_file: Путь к .env файлу
        """
        # Инициализация только при первом создании
        if not self._loaded:
            self._env_file = env_file
            self._load_config()
            self._loaded = True
    
    def _load_config(self) -> None:
        """Загрузка конфигурации из .env файла и переменных окружения."""
        if self._env_file is None:
            # Поиск .env в директории, где лежит app.py
            # Используем __file__ для определения пути к этому модулю
            # config.py находится в core/, поэтому идём на уровень вверх (web/)
            module_dir = os.path.dirname(os.path.abspath(__file__))
            parent_dir = os.path.dirname(module_dir)  # src/web/
            self._env_file = os.path.join(parent_dir, '.env')

            # Если не найден, пробуем WEB_ROOT
            if not os.path.exists(self._env_file):
                self._env_file = str(WEB_ROOT / '.env')

        # Загружаем .env файл
        file_config = load_env_file(self._env_file)

        self._cache = {
            'WEB_HOST': os.environ.get('WEB_HOST', file_config.get('WEB_HOST', DEFAULT_WEB_HOST)),
            'WEB_PORT': os.environ.get('WEB_PORT', file_config.get('WEB_PORT', str(DEFAULT_WEB_PORT))),
            'WEB_PASSWORD': os.environ.get('WEB_PASSWORD', file_config.get('WEB_PASSWORD', DEFAULT_WEB_PASSWORD)),
            'ROUTER_IP': os.environ.get('ROUTER_IP', file_config.get('ROUTER_IP', DEFAULT_ROUTER_IP)),
            'UNBLOCK_DIR': os.environ.get('UNBLOCK_DIR', file_config.get('UNBLOCK_DIR', DEFAULT_UNBLOCK_DIR)),
        }
    
    # =============================================================================
    # СВОЙСТВА
    # =============================================================================
    
    @property
    def web_host(self) -> str:
        """Хост для web-сервера"""
        return self._get_value('WEB_HOST', DEFAULT_WEB_HOST)
    
    @property
    def web_port(self) -> int:
        """Порт для web-сервера"""
        value = self._get_value('WEB_PORT', str(DEFAULT_WEB_PORT))
        try:
            port = int(value)
            # Проверка диапазона порта
            if not (MIN_PORT <= port <= MAX_PORT):
                return DEFAULT_WEB_PORT
            return port
        except (ValueError, TypeError):
            return DEFAULT_WEB_PORT
    
    @property
    def web_password(self) -> str:
        """Пароль для доступа к web-интерфейсу"""
        return self._get_value('WEB_PASSWORD', DEFAULT_WEB_PASSWORD)
    
    @property
    def router_ip(self) -> str:
        """IP-адрес роутера"""
        return self._get_value('ROUTER_IP', DEFAULT_ROUTER_IP)

    @property
    def unblock_dir(self) -> str:
        """Директория для списков обхода"""
        return self._get_value('UNBLOCK_DIR', DEFAULT_UNBLOCK_DIR)

    def _get_value(self, key: str, default: str) -> Any:
        """
        Получение значения из кэша.
        
        Args:
            key: Ключ конфигурации
            default: Значение по умолчанию
        
        Returns:
            Значение конфигурации
        """
        if not self._loaded:
            self._load_config()
        return self._cache.get(key, default)
    
    # =============================================================================
    # МЕТОДЫ ВАЛИДАЦИИ
    # =============================================================================
    
    def is_valid(self) -> bool:
        """
        Проверка валидности конфигурации.
        
        Returns:
            True если конфигурация валидна, False иначе
        
        Example:
            >>> config.is_valid()
            True
        """
        # Проверка пароля (не должен быть пустым)
        if not self.web_password or len(self.web_password.strip()) == 0:
            return False
        
        # Проверка порта
        if not (MIN_PORT <= self.web_port <= MAX_PORT):
            return False
        
        # Проверка IP адреса роутера
        if not self._is_valid_ip(self.router_ip):
            return False
        
        # Проверка хоста
        if not self._is_valid_host(self.web_host):
            return False
        
        return True
    
    def validate(self) -> bool:
        """
        Валидация конфигурации с выбрасыванием исключения.
        
        Returns:
            True если конфигурация валидна
        
        Raises:
            ValueError: Если конфигурация невалидна
        
        Example:
            >>> config.validate()
            True
            >>> # Raises ValueError if invalid
        """
        if not self.is_valid():
            errors = []
            
            if not self.web_password or len(self.web_password.strip()) == 0:
                errors.append("WEB_PASSWORD не может быть пустым")
            
            if not (MIN_PORT <= self.web_port <= MAX_PORT):
                errors.append(f"WEB_PORT должен быть в диапазоне {MIN_PORT}-{MAX_PORT}")
            
            if not self._is_valid_ip(self.router_ip):
                errors.append(f"ROUTER_IP '{self.router_ip}' невалиден")
            
            if not self._is_valid_host(self.web_host):
                errors.append(f"WEB_HOST '{self.web_host}' невалиден")
            
            raise ValueError("; ".join(errors))
        
        return True
    
    def _is_valid_ip(self, ip: str) -> bool:
        """
        Проверка валидности IPv4 адреса.
        
        Args:
            ip: IP адрес для проверки
        
        Returns:
            True если IP валиден
        """
        if not ip:
            return False
        
        # Простая проверка формата IPv4
        pattern = r'^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$'
        match = re.match(pattern, ip)
        
        if not match:
            return False
        
        # Проверка каждой части на диапазон 0-255
        for group in match.groups():
            if not (0 <= int(group) <= 255):
                return False
        
        return True
    
    def _is_valid_host(self, host: str) -> bool:
        """
        Проверка валидности хоста.
        
        Args:
            host: Хост для проверки
        
        Returns:
            True если хост валиден
        """
        if not host:
            return False
        
        # Разрешаем 0.0.0.0 и localhost
        if host in ('0.0.0.0', 'localhost', '127.0.0.1'):
            return True
        
        # Проверка IPv4
        if self._is_valid_ip(host):
            return True
        
        # Простая проверка доменного имени
        pattern = r'^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*$'
        return bool(re.match(pattern, host))
    
    # =============================================================================
    # МЕТОДЫ ЭКСПОРТА
    # =============================================================================
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Экспорт конфигурации в словарь.

        Returns:
            Словарь с конфигурацией

        Example:
            >>> config.to_dict()
            {
                'web_host': '0.0.0.0',
                'web_port': 8080,
                'web_password': 'changeme',
                'router_ip': '192.168.1.1',
                'unblock_dir': '/opt/etc/unblock/'
            }
        """
        return {
            'web_host': self.web_host,
            'web_port': self.web_port,
            'web_password': self.web_password,
            'router_ip': self.router_ip,
            'unblock_dir': self.unblock_dir,
        }
    
    def __repr__(self) -> str:
        """Строковое представление конфигурации"""
        return (
            f"WebConfig(web_host='{self.web_host}', "
            f"web_port={self.web_port}, "
            f"web_password='***', "
            f"router_ip='{self.router_ip}', "
            f"unblock_dir='{self.unblock_dir}')"
        )
    
    # =============================================================================
    # МЕТОДЫ УПРАВЛЕНИЯ КЭШЕМ
    # =============================================================================
    
    def clear_cache(self) -> None:
        """
        Очистка кэша конфигурации.
        
        Позволяет перезагрузить конфигурацию из файла.

        Example:
            >>> config.clear_cache()
            >>> config._loaded = False  # Для принудительной перезагрузки
        """
        self._cache = {}
        self._loaded = False
        # Не сбрасываем _instance здесь — это не имеет смысла внутри экземпляра

    def reload(self) -> None:
        """
        Перезагрузка конфигурации из файла.

        Example:
            >>> config.reload()
        """
        with self._lock:
            self.clear_cache()
            self._load_config()
            self._loaded = True


# =============================================================================
# УДОБНЫЙ ДОСТУП
# =============================================================================

def get_config(env_file: Optional[str] = None) -> WebConfig:
    """
    Получение экземпляра конфигурации.
    
    Args:
        env_file: Путь к .env файлу
    
    Returns:
        Экземпляр WebConfig
    
    Example:
        >>> config = get_config()
        >>> config.web_port
        8080
    """
    return WebConfig(env_file=env_file)
