# FlyMyByte Refactoring Plan

> **Goal:** Упростить архитектуру, улучшить читаемость, упростить отладку при сохранении функциональности (B)
> **Approach:** Средний уровень - упростить текущий код, сохраняя совместимость (B)

## Текущие проблемы

1. **services.py** - лишний агрегатор, делает только import-ы
2. **app.py при старте** - делает слишком много (загрузка ipset, запуск мониторинга)
3. **dns_ops.py** - смешаны мониторинг + резолвинг + DNS manager
4. **dnsmasq_manager.py** - генерирует конфиг + рестартит сервис
5. **utils.py** - 481 строка, смешаны утилиты разного назначения
6. **Дублирование** - IPSET_MAP в constants и app_config

---

## Phase 1: Удалить лишние слои

### Task 1.1: Удалить services.py

**Files:**
- Modify: `src/web_ui/core/__init__.py` - перенести импорты из services.py
- Delete: `src/web_ui/core/services.py`

**Steps:**
- [ ] 1. Добавить импорты из services.py в `__init__.py`
- [ ] 2. Обновить все файлы которые импортируют из services.py
- [ ] 3. Удалить services.py

### Task 1.2: Удалить service_locator.py

**Files:**
- Delete: `src/web_ui/core/service_locator.py`

---

## Phase 2: Разделить смешанные ответственности

**Status:** ✅ Completed

### Task 2.1: Выделить DNS мониторинг

**Status:** ✅ Completed (DNSMonitor остался в dns_ops.py - OK for embedded)

### Task 2.2: Разделить dnsmasq_manager

**Status:** ✅ Completed

---

## Phase 3: Упростить app.py

**Files:**
- Modify: `src/web_ui/app.py`

**Steps:**
- [ ] 1. Убрать загрузку ipset при старте - делать по требованию
- [ ] 2. Упростить startup до минимума
- [ ] 3. Добавить явные логи при старте для отладки

---

## Phase 4: Разделить utils.py

**Status:** ✅ Completed

**Files:**
- Create: `src/web_ui/core/bypass_utils.py`
- Create: `src/web_ui/core/system_utils.py`
- Modify: `src/web_ui/core/utils.py` - оставить только логирование и базовые утилиты

**Steps:**
- [x] 1. Выделить load_bypass_list, save_bypass_list, validate_bypass_entry в bypass_utils.py
- [x] 2. Выделить get_cpu_stats, get_memory_stats в system_utils.py
- [x] 3. Оставить только логирование и базовые утилиты в utils.py

---

## Phase 5: Почистить constants

**Files:**
- Modify: `src/web_ui/core/constants.py`

**Steps:**
- [ ] 1. Удалить неиспользуемые константы
- [ ] 2. Удалить дублирующие маппинги (оставить только в constants)
- [ ] 3. Добавить документацию для ключевых констант

---

## Тестирование после каждого этапа

- [ ] Проверить web UI запускается без ошибок
- [ ] Проверить работают основные функции (bypass, vpn restart)
- [ ] Проверить логирование корректное