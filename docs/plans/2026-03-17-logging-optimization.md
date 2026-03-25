# Оптимизация логирования

**Дата создания:** 17 марта 2026 г.  
**Приоритет:** Низкий  
**Статус:** Отложено (логирование работает, можно оптимизировать позже)

---

## Контекст

В ходе отладки проблемы с deadlock в `Cache.get()` (17 марта 2026) было добавлено подробное диагностическое логирование для всех этапов обработки ключей.

**Проблема:** Страница `/keys` зависала после `Shadowsocks cache hit`.

**Причина:** Deadlock в `Cache.get()` — метод захватывал `threading.Lock` и вызывал `is_valid()`, который тоже захватывал тот же lock.

**Решение:** Исправлено в `utils.py` — убран вызов `is_valid()` из `get()`, проверка делается inline.

---

## Текущее состояние логирования

### Добавленные логи (требуют оптимизации):

#### `routes.py` — обработка ключей:

```python
# VLESS
logger.info("Parsing VLESS key")
logger.info(f"VLESS key parsed: {list(parsed.keys())}")
# Проверка успешности парсинга
if not parsed.get('server') or not parsed.get('port'):
    logger.error(f"VLESS parse failed: missing server/port")
    raise ValueError(...)
logger.info(f"VLESS parse OK: server={parsed['server']}, port={parsed['port']}")
logger.info("Generating VLESS config")
logger.info(f"VLESS config generated with {len(cfg)} keys")
logger.info(f"About to write VLESS config to {svc['config_path']}")
# write_json_config логирует внутри себя
logger.info(f"VLESS config written successfully")

# Аналогично для Shadowsocks, Trojan, Tor
```

#### `services.py` — write_json_config:

```python
logger.info(f"write_json_config: writing to {filepath}")
logger.info(f"write_json_config: creating directory {os.path.dirname(filepath)}")
logger.info(f"write_json_config: opening temp file {temp_path}")
logger.debug(f"Writing config to {temp_path}")
logger.info(f"write_json_config: config written to {temp_path}")
logger.info(f"write_json_config: replacing {temp_path} with {filepath}")
logger.info(f"write_json_config: config written to {filepath} successfully")
```

#### `services.py` — restart_service:

```python
logger.info(f"restart_service: {service_name} via {init_script}")
logger.info(f"restart_service: running ['sh', {init_script}, 'restart']")
# ...
logger.info(f"restart_service: {service_name} completed with returncode={result.returncode}")
```

#### `services.py` — shadowsocks_config:

```python
logger.info(f"shadowsocks_config: вызов с ключом {key[:20]}...")
# В parse_shadowsocks_key:
logger.info(f"Shadowsocks cache hit: {cache_key[:20]}...")
logger.info(f"Shadowsocks cache get вернул: {type(cached_result)}")
logger.info(f"shadowsocks_config: parse_shadowsocks_key вернул результат")
logger.info(f"shadowsocks_config: конфигурация сгенерирована")
```

---

## Задачи на оптимизацию

### 1. Удалить избыточное логирование

**Удалить (отладочные):**
- [ ] `Shadowsocks cache get вернул: {type(cached_result)}` — достаточно `cache hit`
- [ ] `shadowsocks_config: parse_shadowsocks_key вернул результат` — подразумевается
- [ ] `shadowsocks_config: конфигурация сгенерирована` — дублирует `config generated with N keys`
- [ ] `write_json_config: creating directory ...` — достаточно `writing to`
- [ ] `write_json_config: opening temp file ...` — деталь реализации
- [ ] `write_json_config: config written to ...tmp` — промежуточный этап
- [ ] `write_json_config: replacing ...` — деталь реализации
- [ ] `restart_service: running ['sh', ...]` — достаточно `restart_service: Shadowsocks via ...`

**Оставить (критические):**
- ✅ `parse OK: server=..., port=...` — подтверждение успешного парсинга
- ✅ `parse failed: missing server/port` — ошибка валидации
- ✅ `config generated with N keys` — подтверждение генерации
- ✅ `writing to {filepath}` — начало записи
- ✅ `config written to {filepath} successfully` — успешная запись
- ✅ `restart_service: {name} via {script}` — начало перезапуска
- ✅ `{name} restarted successfully` / `completed with returncode=0` — результат

### 2. Унифицировать формат сообщений

**Текущая проблема:** Смесь русских и английских сообщений.

**Задача:**
- [ ] Привести все сообщения к единому языку (английский для консистентности)
- [ ] Использовать единый формат: `{operation}: {status} — {details}`

**Пример:**
```python
# Было
logger.info(f"Shadowsocks parse OK: server={parsed['server']}, port={parsed['port']}")

# Станет
logger.info(f"Shadowsocks parsing: SUCCESS — server={parsed['server']}, port={parsed['port']}")
```

### 3. Добавить уровни логирования

**Сейчас:** Все сообщения на уровне `INFO`.

**Задача:**
- [ ] `DEBUG` — детали реализации (открытие файлов, временные пути)
- [ ] `INFO` — ключевые этапы (парсинг, генерация, запись, перезапуск)
- [ ] `WARNING` — не критические проблемы (кэш не найден, файл создан заново)
- [ ] `ERROR` — ошибки (парсинг не удался, запись не удалась, перезапуск провален)

---

## Пример рефакторинга

### До:
```python
logger.info(f"write_json_config: writing to {filepath}")
logger.info(f"write_json_config: creating directory {os.path.dirname(filepath)}")
logger.info(f"write_json_config: opening temp file {temp_path}")
logger.info(f"write_json_config: config written to {temp_path}")
logger.info(f"write_json_config: replacing {temp_path} with {filepath}")
logger.info(f"write_json_config: config written to {filepath} successfully")
```

### После:
```python
logger.info(f"Writing config to {filepath}")
# ... атомарная запись ...
logger.info(f"Config written successfully: {filepath}")
```

---

## Критерии завершения

- [ ] Удалено ~15 отладочных сообщений
- [ ] Оставлено ~8 критических сообщений на полный цикл обработки ключа
- [ ] Все сообщения на английском языке
- [ ] Использованы соответствующие уровни логирования (DEBUG/INFO/WARNING/ERROR)
- [ ] Логи читаемы для пользователя (не только для разработчика)

---

## Приоритизация

**Текущий статус:** Логирование работает, проблема с deadlock исправлена.

**Когда выполнять:**
- Не в релизном цикле
- После стабилизации всех функций
- При следующей работе над производительностью или читаемостью логов

**Ожидаемое время:** 30-45 минут

---

## Связанные файлы

- `src/web_ui/routes.py` — обработка ключей
- `src/web_ui/core/services.py` — парсеры, запись конфигов, перезапуск
- `src/web_ui/core/utils.py` — Cache, write_json_config
