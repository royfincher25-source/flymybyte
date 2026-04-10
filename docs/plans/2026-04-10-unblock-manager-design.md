# Plan: Переход на Python менеджеры

**Дата:** 10 апреля 2026  
**Версия:** 1.0

---

## Цель

Заменить shell скрипты на Python менеджеры для:
- Упрощения отладки и тестирования
- Добавления type hints
- Единого API для управления bypass
- Постепенного ухода от shell

---

## Анализ текущего состояния

### Shell скрипты:
| Скрипт | Строк | Функция | Python аналог |
|--------|-------|---------|----------------|
| unblock_dnsmasq.sh | 189 | Генерация dnsmasq конфигов | ✅ `DnsmasqManager` (уже есть!) |
| unblock_ipset.sh | 272 | Заполнение ipsets из доменов | ⚠️ `refresh_ipset_from_file()` (частично) |
| unblock_update.sh | 28 | Оркестрация обоих | ❌ Нужно создать |
| S99unblock | 111 | Init скрипт при загрузке | ⚠️ Может вызывать Python |

### Что уже есть в Python:
- `DnsmasqManager` — полностью заменяет `unblock_dnsmasq.sh`
- `refresh_ipset_from_file()` — заменяет основную логику `unblock_ipset.sh`
- `bulk_add_to_ipset()` — добавление IP в ipset
- `ensure_ipset_exists()` — создание ipset

### Что нужно создать:
1. **UnblockManager** — единая точка входа для всех unblock операций
2. Python-версия `unblock_ipset` логики (расширение `refresh_ipset_from_file`)
3. Гибридный режим: S99unblock может вызывать Python, но shell остаётся как fallback

---

## Дизайн решения

### 1. UnblockManager — единый API

```python
# core/unblock_manager.py

class UnblockManager:
    """Единый интерфейс для всех bypass операций."""

    def __init__(self):
        self._dnsmasq = DnsmasqManager()
    
    def update_all(self, timeout: int = 600) -> Tuple[bool, str]:
        """Полное обновление: dnsmasq + ipset."""
    
    def update_dnsmasq(self) -> Tuple[bool, str]:
        """Только обновить dnsmasq конфиги."""
    
    def update_ipsets(self, max_workers: int = None) -> Tuple[bool, str]:
        """Только обновить ipset из доменов."""
    
    def get_status(self) -> Dict:
        """Получить статус всех компонентов."""
    
    def flush_ipsets(self) -> Tuple[bool, str]:
        """Очистить все ipsets."""
```

### 2. Интеграция с S99unblock

**Вариант А: Гибридный (рекомендуется)**
```bash
# S99unblock будет пытаться вызвать Python, 
# если не работает — fallback на shell

if [ -x "/opt/bin/unblock.py" ]; then
    /opt/bin/unblock.py update >> "$LOGFILE" 2>&1
else
    /opt/bin/unblock_dnsmasq.sh
    /opt/bin/unblock_ipset.sh
fi
```

**Вариант Б: Полный переход**
```bash
# S99unblock только вызывает Python
/opt/bin/unblock.py start >> "$LOGFILE" 2>&1
```

### 3. Обновление routes_updates.py

```python
@blueprint.route('/update-bypass', methods=['POST'])
def update_bypass():
    # Вместо shell вызова — Python
    mgr = get_unblock_manager()
    ok, msg = mgr.update_all()
    return jsonify({'success': ok, 'message': msg})
```

---

## Реализация (этапы)

### Этап 1: Создание UnblockManager (Python)
- [ ] Создать `core/unblock_manager.py`
- [ ] Интегрировать `DnsmasqManager`
- [ ] Добавить `update_ipsets()` с логикой из shell
- [ ] Добавить в `ServiceLocator`

### Этап 2: Обновление routes_updates.py
- [ ] Заменить shell-вызовы на Python API
- [ ] Сохранить backward compatibility (try Python, fallback shell)

### Этап 3: Обновление S99unblock (гибрид)
- [ ] Добавить вызов Python скрипта
- [ ] Сохранить shell fallback
- [ ] Добавить логирование

### Этап 4: Тестирование
- [ ] Тест на роутере: полное обновление bypass
- [ ] Тест: S99unblock start/stop
- [ ] Тест: веб-интерфейс "Обновить"

### Этап 5: Удаление shell (опционально)
- [ ] После стабилизации удалить shell скрипты
- [ ] Обновить S99unblock только на Python

---

## Критерии приёмки

1. ✅ `UnblockManager.update_all()` работает как `unblock_update.sh`
2. ✅ `S99unblock start` работает через Python
3. ✅routes_updates.py `/update-bypass` работает
4. ✅ Если Python не работает — fallback на shell
5. ✅ Логирование: понятно где ошибка
6. ✅ Все текущие функции работают без изменений

---

## Риски и mitigation

| Риск | Mitigation |
|------|-------------|
| Python не работает на роутере | Оставить shell fallback |
| Потеря функциональности | Тестировать каждый этап |
| Реgrессия в bypass | Сравнивать результаты до/после |

---

## Время оценка

- Этап 1: 1-2 часа
- Этап 2: 30 минут
- Этап 3: 30 минут
- Этап 4: 1 час (на роутере)
- **Всего: 3-4 часа**