# =============================================================================
# ЛЁГКИЙ ПАРСЕР .ENV ФАЙЛОВ
# =============================================================================
# Минималистичная замена python-dotenv для embedded-устройств
# Потребление памяти: < 1MB vs ~5MB у python-dotenv
# =============================================================================

import os
import re


def parse_env_line(line):
    """
    Парсинг одной строки .env файла.
    
    Args:
        line: Строка для парсинга
        
    Returns:
        (key, value) или (None, None)
    """
    line = line.strip()
    
    # Пропуск пустых строк и комментариев
    if not line or line.startswith('#'):
        return None, None
    
    # Разделение на ключ и значение
    match = re.match(r'^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$', line)
    if not match:
        return None, None
    
    key = match.group(1)
    value = match.group(2)
    
    # Удаление кавычек
    if (value.startswith('"') and value.endswith('"')) or \
       (value.startswith("'") and value.endswith("'")):
        value = value[1:-1]
    
    return key, value


def load_env_file(filepath):
    """
    Загрузка .env файла в словарь.
    
    Args:
        filepath: Путь к файлу
        
    Returns:
        Dict с переменными
    """
    env_vars = {}
    
    try:
        with open(filepath, 'r') as f:
            for line in f:
                key, value = parse_env_line(line)
                if key is not None:
                    env_vars[key] = value
    except FileNotFoundError:
        pass
    except IOError:
        pass
    
    return env_vars


def load_env(filepath=None):
    """
    Загрузка .env и установка в os.environ.
    
    Args:
        filepath: Путь к файлу. Если None, ищется .env в директории скрипта.
    """
    if filepath is None:
        # Поиск .env в директории текущего модуля
        import sys
        script_dir = os.path.dirname(os.path.abspath(sys.modules['__main__'].__file__))
        filepath = os.path.join(script_dir, '.env')
    
    env_vars = load_env_file(filepath)
    
    # Установка только отсутствующих переменных
    for key, value in env_vars.items():
        if key not in os.environ:
            os.environ[key] = value
    
    return env_vars


def get_env(key, default=None):
    """
    Получение переменной окружения.
    
    Args:
        key: Имя переменной
        default: Значение по умолчанию
        
    Returns:
        Значение переменной или default
    """
    return os.environ.get(key, default)


def get_env_int(key, default=0):
    """Получение целочисленной переменной"""
    try:
        return int(os.environ.get(key, default))
    except (ValueError, TypeError):
        return default


def get_env_bool(key, default=False):
    """Получение булевой переменной"""
    value = os.environ.get(key, '').lower()
    if value in ('true', '1', 'yes', 'on'):
        return True
    return default


# =============================================================================
# БЫСТРЫЙ ДОСТУП (singleton pattern)
# =============================================================================

class EnvConfig:
    """
    Singleton для быстрого доступа к конфигурации.
    Кэширует значения для уменьшения количества обращений к файлу.
    """
    
    _instance = None
    _cache = {}
    _loaded = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def load(self, filepath=None):
        """Загрузка конфигурации"""
        if not self._loaded:
            # Если путь не указан, используем путь по умолчанию
            if filepath is None:
                filepath = '/opt/etc/web_ui/.env'
            self._cache = load_env_file(filepath)
            self._loaded = True
        return self._cache
    
    def get(self, key, default=None):
        """Получение значения"""
        if not self._loaded:
            self.load()
        return self._cache.get(key, os.environ.get(key, default))
    
    def get_int(self, key, default=0):
        """Получение целого числа"""
        if not self._loaded:
            self.load()
        value = self._cache.get(key, os.environ.get(key))
        try:
            return int(value) if value else default
        except (ValueError, TypeError):
            return default
    
    def get_bool(self, key, default=False):
        """Получение булевого значения"""
        if not self._loaded:
            self.load()
        value = self._cache.get(key, os.environ.get(key, ''))
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ('true', '1', 'yes', 'on')
        return default
    
    def clear_cache(self):
        """Очистка кэша (для перезагрузки конфигурации)"""
        self._cache = {}
        self._loaded = False


# Глобальный экземпляр для быстрого доступа
env = EnvConfig()
