# KN-1212 Optimization Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan.

**Goal:** Оптимизировать web-интерфейс для роутера Keenetic KN-1212 с ограниченными ресурсами (128MB RAM)

**Architecture:** Снижение потребления RAM и CPU, добавление memory management функций

**Tech Stack:** Python/Flask, Shell scripts

---

## Task 1: Уменьшить потребление RAM

**Files:**
- Modify: `src/web_ui/app.py:108`
- Modify: `src/web_ui/routes.py:21`
- Modify: `src/web_ui/core/utils.py:85`

**Step 1: Уменьшить Waitress threads (4 → 2)**
**Step 2: Уменьшить ThreadPoolExecutor workers (4 → 2)**
**Step 3: Уменьшить LRU Cache (50 → 30)**

**Verification:**
```bash
python3 -m py_compile src/web_ui/app.py
python3 -m py_compile src/web_ui/routes.py
python3 -m py_compile src/web_ui/core/utils.py
```

**Commit:** `git commit -m "perf: reduce memory footprint for KN-1212"`

---

## Task 2: Оптимизировать CPU нагрузку

**Files:**
- Modify: `src/web_ui/core/dns_monitor.py:32-34`

**Step 1: Увеличить интервал проверки DNS (30 → 60 сек)**
**Step 2: Увеличить timeout проверки (2 → 3 сек)**

**Verification:**
```bash
python3 -m py_compile src/web_ui/core/dns_monitor.py
```

**Commit:** `git commit -m "perf: reduce CPU usage - longer DNS check interval"`

---

## Task 3A: Статус RAM на странице Сервис

**Files:**
- Modify: `src/web_ui/core/utils.py` - добавить функцию get_memory_stats()
- Modify: `src/web_ui/routes.py` - добавить эндпоинт /api/system/stats
- Modify: `src/web_ui/templates/service.html` - вывести статус RAM

**Step 1: Добавить функцию get_memory_stats() в utils.py**
**Step 2: Добавить API эндпоинт в routes.py**
**Step 3: Добавить отображение в service.html**

**Commit:** `git commit -m "feat: add RAM status display on service page"`

---

## Task 3B: Авто-снижение при low memory с тумблером

**Files:**
- Modify: `src/web_ui/core/utils.py` - добавить MemoryManager class
- Modify: `src/web_ui/core/app_config.py` - добавить настройку
- Modify: `src/web_ui/routes.py` - добавить API для тумблера
- Modify: `src/web_ui/templates/service.html` - добавить тумблер

**Step 1: Создать MemoryManager class с auto-optimization**
**Step 2: Добавить настройку в WebConfig**
**Step 3: Добавить API endpoints (enable/disable, status)**
**Step 4: Добавить UI тумблер**

**Commit:** `git commit -m "feat: add auto memory optimization with toggle"`

---

## Task 3C: Кнопка ручной оптимизации

**Files:**
- Modify: `src/web_ui/routes.py` - добавить эндпоинт /api/system/optimize
- Modify: `src/web_ui/templates/service.html` - добавить кнопку

**Step 1: Добавить API эндпоинт для оптимизации**
**Step 2: Добавить кнопку в UI**

**Commit:** `git commit -m "feat: add manual memory optimization button"`

---

## Task 4: Верификация

**Step 1: Проверить все файлы**
```bash
python3 -m py_compile src/web_ui/app.py
python3 -m py_compile src/web_ui/routes.py
python3 -m py_compile src/web_ui/core/dns_monitor.py
python3 -m py_compile src/web_ui/core/utils.py
```

**Step 2: Финальный commit**
```bash
git add -A
git commit -m "perf: KN-1212 optimization complete"
```
