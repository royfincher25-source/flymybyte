# Script.sh Integration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Создать локальную копию script.sh в проекте web_ui, исправить URL для загрузки обновлений и интегрировать с routes.py для устранения ошибки 404.

**Architecture:** Скрипт script.sh будет храниться в новой папке `scripts/` внутри `src/web_ui/`. При установке скрипт будет копироваться с локальной копии (а не загружаться с GitHub), что устранит ошибку 404 и ускорит установку.

**Tech Stack:** Bash shell script, Python Flask, requests library

---

### Task 1: Создать папку для скриптов

**Files:**
- Create: `H:\disk_e\dell\bypass_keenetic-web\src\web_ui\scripts\` (directory)

**Step 1: Создать директорию scripts**

```powershell
New-Item -ItemType Directory -Path "H:\disk_e\dell\bypass_keenetic-web\src\web_ui\scripts" -Force
```

Expected: Directory created successfully

**Step 2: Проверить создание**

```powershell
Test-Path "H:\disk_e\dell\bypass_keenetic-web\src\web_ui\scripts"
```

Expected: True

**Step 3: Commit**

```bash
git add src/web_ui/scripts/
git commit -m "feat: добавить директорию для скриптов"
```

---

### Task 2: Скопировать script.sh из проекта-донора

**Files:**
- Copy from: `H:\disk_e\dell\bypass_keenetic-web\test\src\bot3\script.sh`
- Copy to: `H:\disk_e\dell\bypass_keenetic-web\src\web_ui\scripts\script.sh`

**Step 1: Скопировать файл**

```powershell
Copy-Item "H:\disk_e\dell\bypass_keenetic-web\test\src\bot3\script.sh" "H:\disk_e\dell\bypass_keenetic-web\src\web_ui\scripts\script.sh"
```

Expected: File copied successfully

**Step 2: Проверить наличие файла**

```powershell
Test-Path "H:\disk_e\dell\bypass_keenetic-web\src\web_ui\scripts\script.sh"
```

Expected: True

**Step 3: Проверить размер файла**

```powershell
(Get-Item "H:\disk_e\dell\bypass_keenetic-web\src\web_ui\scripts\script.sh").Length
```

Expected: ~15000-20000 bytes (script should be substantial)

**Step 4: Commit**

```bash
git add src/web_ui/scripts/script.sh
git commit -m "feat: скопировать script.sh из проекта-донора"
```

---

### Task 3: Проанализировать script.sh для выявления URL

**Files:**
- Read: `H:\disk_e\dell\bypass_keenetic-web\src\web_ui\scripts\script.sh`

**Step 1: Найти все URL в скрипте**

```powershell
Select-String -Pattern "raw\.githubusercontent\.com" -Path "H:\disk_e\dell\bypass_keenetic-web\src\web_ui\scripts\script.sh"
```

Expected: List of URLs with line numbers

**Step 2: Прочитать первые 50 строк для понимания структуры**

```powershell
Get-Content "H:\disk_e\dell\bypass_keenetic-web\src\web_ui\scripts\script.sh" -Head 50
```

Expected: Script header with shebang and configuration reading

**Step 3: Задокументировать найденные URL**

Create temporary notes with:
- Line numbers of URLs
- Current repository names
- Required changes

---

### Task 4: Исправить URL в script.sh (заменить bypass_keenetic_web на bypass_keenetic)

**Files:**
- Modify: `H:\disk_e\dell\bypass_keenetic-web\src\web_ui\scripts\script.sh`

**Context:** Скрипт содержит URL для загрузки файлов бота. Необходимо заменить неправильный URL `bypass_keenetic_web` на правильный `bypass_keenetic`.

**Step 1: Найти все вхождения bypass_keenetic_web**

```powershell
Select-String -Pattern "bypass_keenetic_web" -Path "H:\disk_e\dell\bypass_keenetic-web\src\web_ui\scripts\script.sh"
```

Expected: List of lines containing the incorrect URL

**Step 2: Исправить URL (если найдены)**

Если найдены вхождения, заменить:

```powershell
(Get-Content "H:\disk_e\dell\bypass_keenetic-web\src\web_ui\scripts\script.sh") -replace 'bypass_keenetic_web', 'bypass_keenetic' | Set-Content "H:\disk_e\dell\bypass_keenetic-web\src\web_ui\scripts\script.sh"
```

Expected: URL исправлены

**Step 3: Проверить исправления**

```powershell
Select-String -Pattern "raw\.githubusercontent\.com.*bypass_keenetic" -Path "H:\disk_e\dell\bypass_keenetic-web\src\web_ui\scripts\script.sh"
```

Expected: Все URL содержат `bypass_keenetic` (не `bypass_keenetic_web`)

**Step 4: Commit**

```bash
git add src/web_ui/scripts/script.sh
git commit -m "fix: исправить URL в script.sh (bypass_keenetic_web → bypass_keenetic)"
```

---

### Task 5: Добавить проверку целостности script.sh

**Files:**
- Create: `H:\disk_e\dell\bypass_keenetic-web\src\web_ui\scripts\script.sh.md5`

**Step 1: Создать MD5 хэш файла**

```powershell
$hash = Get-FileHash "H:\disk_e\dell\bypass_keenetic-web\src\web_ui\scripts\script.sh" -Algorithm MD5
$hash.Hash | Out-File -FilePath "H:\disk_e\dell\bypass_keenetic-web\src\web_ui\scripts\script.sh.md5" -Encoding ascii -NoNewline
```

Expected: MD5 hash file created

**Step 2: Проверить содержимое**

```powershell
Get-Content "H:\disk_e\dell\bypass_keenetic-web\src\web_ui\scripts\script.sh.md5"
```

Expected: 32-character hex string

**Step 3: Commit**

```bash
git add src/web_ui/scripts/script.sh.md5
git commit -m "chore: добавить MD5 хэш для проверки целостности script.sh"
```

---

### Task 6: Обновить routes.py для использования локального script.sh

**Files:**
- Modify: `H:\disk_e\dell\bypass_keenetic-web\src\web_ui\routes.py:960-1020`

**Context:** Функция `service_install()` сейчас загружает script.sh с GitHub. Нужно изменить на использование локальной копии.

**Step 1: Прочитать текущий код**

```python
# Current code in routes.py (lines ~967-985):
@bp.route('/install', methods=['GET', 'POST'])
@login_required
@csrf_required
def service_install():
    if request.method == 'POST':
        script_path = '/opt/root/script.sh'
        script_url = 'https://raw.githubusercontent.com/royfincher25-source/bypass_keenetic_web/main/src/bot3/script.sh'
        
        try:
            flash('⏳ Загрузка скрипта установки...', 'info')
            response = requests.get(script_url, timeout=15)
            # ... download logic
```

**Step 2: Изменить логику на использование локального файла**

```python
# New code:
@bp.route('/install', methods=['GET', 'POST'])
@login_required
@csrf_required
def service_install():
    """
    Run installation script.

    Requires authentication.
    """
    if request.method == 'POST':
        script_path = '/opt/root/script.sh'
        local_script_path = os.path.join(os.path.dirname(__file__), 'scripts', 'script.sh')

        try:
            flash('⏳ Копирование скрипта установки...', 'info')
            
            # Проверка наличия локального скрипта
            if not os.path.exists(local_script_path):
                flash('❌ Ошибка: локальный скрипт не найден', 'danger')
                logger.error(f"Local script not found: {local_script_path}")
                return redirect(url_for('main.service_install'))

            # Чтение локального скрипта
            with open(local_script_path, 'r', encoding='utf-8') as f:
                script_content = f.read()

            # Создание директории назначения
            os.makedirs(os.path.dirname(script_path), exist_ok=True)

            # Запись скрипта на роутер
            with open(script_path, 'w', encoding='utf-8') as f:
                f.write(script_content)
            os.chmod(script_path, 0o755)
            
            flash('✅ Скрипт скопирован', 'success')
            logger.info(f"Script copied to {script_path}")

        except Exception as e:
            flash(f'❌ Ошибка копирования скрипта: {str(e)}', 'danger')
            logger.error(f"service_install copy Exception: {e}")
            return redirect(url_for('main.service_install'))

        # ... rest of installation logic remains the same
```

**Step 3: Применить изменения через edit tool**

Использовать edit для замены кода в routes.py (lines 967-995)

**Step 4: Проверить синтаксис Python**

```bash
python -m py_compile H:\disk_e\dell\bypass_keenetic-web\src\web_ui\routes.py
```

Expected: No syntax errors

**Step 5: Commit**

```bash
git add src/web_ui/routes.py
git commit -m "feat: использовать локальный script.sh вместо загрузки с GitHub"
```

---

### Task 7: Обновить routes.py для service_remove() аналогично

**Files:**
- Modify: `H:\disk_e\dell\bypass_keenetic-web\src\web_ui\routes.py:1020-1070`

**Context:** Функция `service_remove()` также загружает script.sh с GitHub. Нужно изменить на использование локальной копии.

**Step 1: Прочитать текущий код**

```python
# Current code in routes.py (lines ~1024-1045):
@bp.route('/remove', methods=['GET', 'POST'])
@login_required
@csrf_required
def service_remove():
    if request.method == 'POST':
        script_path = '/opt/root/script.sh'
        script_url = 'https://raw.githubusercontent.com/royfincher25-source/bypass_keenetic_web/main/src/bot3/script.sh'
        
        if not os.path.exists(script_path):
            try:
                flash('⏳ Загрузка скрипта...', 'info')
                response = requests.get(script_url, timeout=30)
                # ... download logic
```

**Step 2: Изменить логику (аналогично Task 6)**

```python
# New code:
@bp.route('/remove', methods=['GET', 'POST'])
@login_required
@csrf_required
def service_remove():
    """
    Run removal script.

    Requires authentication.
    """
    if request.method == 'POST':
        script_path = '/opt/root/script.sh'
        local_script_path = os.path.join(os.path.dirname(__file__), 'scripts', 'script.sh')

        if not os.path.exists(script_path):
            try:
                flash('⏳ Копирование скрипта...', 'info')
                
                # Проверка наличия локального скрипта
                if not os.path.exists(local_script_path):
                    flash('❌ Ошибка: локальный скрипт не найден', 'danger')
                    logger.error(f"Local script not found: {local_script_path}")
                    return redirect(url_for('main.service_remove'))

                # Чтение локального скрипта
                with open(local_script_path, 'r', encoding='utf-8') as f:
                    script_content = f.read()

                # Создание директории назначения
                os.makedirs(os.path.dirname(script_path), exist_ok=True)

                # Запись скрипта на роутер
                with open(script_path, 'w', encoding='utf-8') as f:
                    f.write(script_content)
                os.chmod(script_path, 0o755)
                
                flash('✅ Скрипт скопирован', 'success')
                logger.info(f"Script copied to {script_path}")

            except Exception as e:
                flash(f'❌ Ошибка копирования скрипта: {str(e)}', 'danger')
                logger.error(f"service_remove copy Exception: {e}")
                return redirect(url_for('main.service_remove'))

        # ... rest of removal logic remains the same
```

**Step 3: Применить изменения через edit tool**

**Step 4: Проверить синтаксис Python**

```bash
python -m py_compile H:\disk_e\dell\bypass_keenetic-web\src\web_ui\routes.py
```

Expected: No syntax errors

**Step 5: Commit**

```bash
git add src/web_ui/routes.py
git commit -m "fix: использовать локальный script.sh в service_remove()"
```

---

### Task 8: Добавить .gitkeep для пустой директории (если нужно)

**Files:**
- Create: `H:\disk_e\dell\bypass_keenetic-web\src\web_ui\scripts\.gitkeep`

**Step 1: Создать .gitkeep файл**

```python
# Для гарантии отслеживания директории в git
with open("H:\\disk_e\\dell\\bypass_keenetic-web\\src\\web_ui\\scripts\\.gitkeep", "w") as f:
    f.write("# Keep this directory in git\n")
```

**Step 2: Commit**

```bash
git add src/web_ui/scripts/.gitkeep
git commit -m "chore: добавить .gitkeep для директории scripts"
```

---

### Task 9: Проверка интеграции

**Files:**
- Test: `H:\disk_e\dell\bypass_keenetic-web\src\web_ui\`

**Step 1: Проверить структуру файлов**

```powershell
Get-ChildItem -Recurse "H:\disk_e\dell\bypass_keenetic-web\src\web_ui\scripts"
```

Expected: script.sh и script.sh.md5 присутствуют

**Step 2: Проверить импорты в routes.py**

```bash
python -c "import sys; sys.path.insert(0, 'H:/disk_e/dell/bypass_keenetic-web/src/web_ui'); import routes"
```

Expected: No import errors

**Step 3: Проверить путь к скрипту в коде**

```powershell
Select-String -Pattern "local_script_path" -Path "H:\disk_e\dell\bypass_keenetic-web\src\web_ui\routes.py"
```

Expected: Path construction using os.path.join

**Step 4: Запустить тесты (если есть)**

```bash
pytest tests/web/ -v -k install
```

Expected: Tests pass or skip if no tests exist

---

### Task 10: Документирование изменений

**Files:**
- Modify: `H:\disk_e\dell\bypass_keenetic-web\README.md`
- Create: `H:\disk_e\dell\bypass_keenetic-web\src\web_ui\scripts\README.md`

**Step 1: Создать README для scripts/**

```markdown
# Scripts Directory

Эта директория содержит скрипты для установки и удаления bypass_keenetic.

## Файлы

- `script.sh` - основной скрипт установки/удаления
- `script.sh.md5` - MD5 хэш для проверки целостности

## Обновление скрипта

Для обновления script.sh из репозитория-донора:

```bash
cp ../test/src/bot3/script.sh ./script.sh
# Внести необходимые изменения (исправить URL)
md5sum script.sh > script.sh.md5
```

## Использование

Скрипт копируется на роутер при установке через веб-интерфейс:
- Путь на роутере: `/opt/root/script.sh`
- Права: 755 (исполняемый)
```

**Step 2: Обновить основной README**

Добавить секцию в `README.md`:

```markdown
## Scripts

Директория `scripts/` содержит:
- `script.sh` - скрипт установки/удаления bypass_keenetic
- Скрипт копируется на роутер при установке через веб-интерфейс
```

**Step 3: Commit**

```bash
git add src/web_ui/scripts/README.md README.md
git commit -m "docs: добавить документацию для scripts/"
```

---

## Verification Checklist

- [ ] Директория `scripts/` создана
- [ ] `script.sh` скопирован и содержит правильные URL
- [ ] `script.sh.md5` создан
- [ ] `routes.py` использует локальный script.sh
- [ ] `service_remove()` использует локальный script.sh
- [ ] Синтаксис Python валиден
- [ ] Документация добавлена
- [ ] Все изменения закоммичены

---

**Plan complete and saved to `docs/plans/2026-03-16-script-sh-integration.md`. Two execution options:**

**1. Subagent-Driven (this session)** - I dispatch fresh subagent per task, review between tasks, fast iteration

**2. Parallel Session (separate)** - Open new session with executing-plans, batch execution with checkpoints

**Which approach?**
