# Rename to FlyMyByte Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rename project from "bypass_keenetic-web" to "FlyMyByte" including local directory, remote repository, and all code references.

**Architecture:** Systematic search-and-replace approach across all project files, followed by directory rename and remote repository update. Changes will be made in logical batches with verification steps between each.

**Tech Stack:** Git, Python, Bash, Markdown

---

### Task 1: Create comprehensive list of files containing old project name

**Files:**
- Create: `docs/plans/rename-scan-results.txt`
- Modify: None

**Step 1: Search for all occurrences of project name variations**

Run these commands to find all files containing the old project name:
```bash
# Search for bypass_keenetic_web (with underscore)
grep -r "bypass_keenetic_web" . --include="*.py" --include="*.sh" --include="*.md" --include="*.txt" --include="*.yml" --include="*.yaml" --include="*.json" --include="*.env" --include="*.html" --include="*.css" > docs/plans/rename-scan-results.txt

# Search for bypass_keenetic-web (with dash)
grep -r "bypass_keenetic-web" . --include="*.py" --include="*.sh" --include="*.md" --include="*.txt" --include="*.yml" --include="*.yaml" --include="*.json" --include="*.env" --include="*.html" --include="*.css" >> docs/plans/rename-scan-results.txt

# Search for bypass_keenetic (general)
grep -r "bypass_keenetic" . --include="*.py" --include="*.sh" --include="*.md" --include="*.txt" --include="*.yml" --include="*.yaml" --include="*.json" --include="*.env" --include="*.html" --include="*.css" >> docs/plans/rename-scan-results.txt
```

**Step 2: Review the scan results**

Read the scan results to understand the scope:
```bash
cat docs/plans/rename-scan-results.txt
```

**Step 3: Commit the scan results**

```bash
git add docs/plans/rename-scan-results.txt
git commit -m "docs: add scan results for project rename preparation"
```

---

### Task 2: Update Python files (core modules)

**Files:**
- Modify: `src/web_ui/core/constants.py:151` - Update GITHUB_REPO
- Modify: `src/web_ui/core/app_config.py:4` - Update module description
- Modify: `src/web_ui/core/web_config.py:5,8` - Update comments and URLs
- Modify: `src/web_ui/core/services.py:988,1068` - Update comments and URLs
- Modify: `src/web_ui/routes.py:1208,1591` - Update GitHub repo references
- Modify: `src/web_ui/app.py:1-5` - Update module docstring

**Step 1: Update constants.py**

Replace `bypass_keenetic_web` with `FlyMyByte` in constants.py:
```python
# In src/web_ui/core/constants.py:151
# OLD: GITHUB_REPO = 'royfincher25-source/bypass_keenetic_web'
# NEW: GITHUB_REPO = 'royfincher25-source/FlyMyByte'
```

**Step 2: Update app_config.py**

Update module description:
```python
# In src/web_ui/core/app_config.py:4
# OLD: # Модуль конфигурации для web-приложения bypass_keenetic
# NEW: # Модуль конфигурации для web-приложения FlyMyByte
```

**Step 3: Update web_config.py**

Update base_url and comments:
```python
# In src/web_ui/core/web_config.py:5,8
# OLD: # Генерируется web_ui при установке bypass_keenetic
# OLD: base_url = "https://raw.githubusercontent.com/royfincher25-source/bypass_keenetic_web/master"
# NEW: # Генерируется web_ui при установке FlyMyByte
# NEW: base_url = "https://raw.githubusercontent.com/royfincher25-source/FlyMyByte/master"
```

**Step 4: Update services.py**

Update comments and URLs:
```python
# In src/web_ui/core/services.py:988
# OLD: Create backup of all bypass_keenetic files.
# NEW: Create backup of all FlyMyByte files.

# In src/web_ui/core/services.py:1068
# OLD: github_repo = 'royfincher25-source/bypass_keenetic_web'
# NEW: github_repo = 'royfincher25-source/FlyMyByte'
```

**Step 5: Update routes.py**

Update GitHub repo references:
```python
# In src/web_ui/routes.py:1208
# OLD: github_repo = 'royfincher25-source/bypass_keenetic_web'
# NEW: github_repo = 'royfincher25-source/FlyMyByte'

# In src/web_ui/routes.py:1591
# OLD: flash('✅ Установка bypass_keenetic_web завершена', 'success')
# NEW: flash('✅ Установка FlyMyByte завершена', 'success')
```

**Step 6: Update app.py docstring**

```python
# In src/web_ui/app.py:1-5
# OLD: Bypass Keenetic Web Interface - Main Application
# NEW: FlyMyByte Web Interface - Main Application
```

**Step 7: Run tests to verify no breaking changes**

```bash
python -m py_compile src/web_ui/app.py
python -m py_compile src/web_ui/routes.py
python -m py_compile src/web_ui/core/constants.py
python -m py_compile src/web_ui/core/app_config.py
python -m py_compile src/web_ui/core/web_config.py
python -m py_compile src/web_ui/core/services.py
```

**Step 8: Commit changes**

```bash
git add src/web_ui/
git commit -m "refactor: update Python files for FlyMyByte rename"
```

---

### Task 3: Update shell scripts

**Files:**
- Modify: `src/web_ui/scripts/install_web.sh` - Update GitHub repo references
- Modify: `src/web_ui/scripts/script.sh` - Update comments and messages

**Step 1: Update install_web.sh**

Replace all occurrences of `bypass_keenetic_web` with `FlyMyByte`:
```bash
# In install_web.sh:6,12,14
# OLD: curl -sL https://raw.githubusercontent.com/royfincher25-source/bypass_keenetic_web/master/src/web_ui/install_web.sh | sh
# OLD: GITHUB_REPO="royfincher25-source/bypass_keenetic_web"
# NEW: curl -sL https://raw.githubusercontent.com/royfincher25-source/FlyMyByte/master/src/web_ui/install_web.sh | sh
# NEW: GITHUB_REPO="royfincher25-source/FlyMyByte"
```

Also update comments:
```bash
# In install_web.sh:3-4
# OLD: # BYPASS KEENETIC WEB UI - MINIMAL INSTALLER
# NEW: # FLYMYBYTE WEB UI - MINIMAL INSTALLER
```

**Step 2: Update script.sh**

Update comments and messages:
```bash
# In script.sh:87,147,343,365,366
# Replace "bypass_keenetic" with "FlyMyByte" in echo statements
```

**Step 3: Test script compilation**

```bash
bash -n src/web_ui/scripts/install_web.sh
bash -n src/web_ui/scripts/script.sh
```

**Step 4: Commit changes**

```bash
git add src/web_ui/scripts/
git commit -m "refactor: update shell scripts for FlyMyByte rename"
```

---

### Task 4: Update documentation files

**Files:**
- Modify: `README.md` - Update all references
- Modify: `docs/INSTALL-manual.md` - Update references
- Modify: `docs/OBSIDIAN_INSTRUCTION.md` - Update project name
- Modify: `docs/DNS_SPOOFING_INSTRUCTION.md` - Update URLs
- Modify: `docs/DNS_SPOOFING_DESIGN.md` - Update project name
- Modify: `docs/INSTRUCTION_MANUAL_UPDATE.md` - Update references
- Modify: `docs/CHECK_BYPASS_INSTRUCTION.md` - Update path references
- Modify: `CHANGELOG.md` - Update URLs

**Step 1: Update README.md**

Replace all references to `bypass_keenetic-web` and `bypass_keenetic_web` with `FlyMyByte`:
- Update title: `# Bypass Keenetic Web` → `# FlyMyByte`
- Update description: `Web-интерфейс для управления bypass_keenetic` → `Web-интерфейс для управления FlyMyByte`
- Update GitHub URLs: `royfincher25-source/bypass_keenetic_web` → `royfincher25-source/FlyMyByte`
- Update directory names: `bypass_keenetic-web/` → `FlyMyByte/`

**Step 2: Update documentation files**

Perform similar replacements in all documentation files:
- Replace `bypass_keenetic-web` with `FlyMyByte`
- Replace `bypass_keenetic_web` with `FlyMyByte`
- Update GitHub URLs to point to new repository

**Step 3: Verify no old references remain**

```bash
grep -r "bypass_keenetic" . --include="*.md" | grep -v "docs/plans/rename-scan-results.txt"
```

**Step 4: Commit changes**

```bash
git add README.md docs/
git commit -m "docs: update documentation for FlyMyByte rename"
```

---

### Task 5: Rename local directory and update Git configuration

**Files:**
- Modify: `.git/config` - Update remote URL
- Create: `H:\disk_e\dell\FlyMyByte` (new directory)
- Delete: `H:\disk_e\dell\bypass_keenetic-web` (old directory)

**Step 1: Update Git remote URL**

```bash
git remote set-url origin https://github.com/royfincher25-source/FlyMyByte.git
```

**Step 2: Verify remote URL**

```bash
git remote -v
```

**Step 3: Rename local directory**

Since we're on Windows, use PowerShell or manually rename:
```powershell
# In PowerShell
Rename-Item -Path "H:\disk_e\dell\bypass_keenetic-web" -NewName "FlyMyByte"
```

**Step 4: Change to new directory and verify Git still works**

```bash
cd H:\disk_e\dell\FlyMyByte
git status
```

**Step 5: Commit Git config change**

```bash
git add .git/config
git commit -m "chore: update remote URL to FlyMyByte repository"
```

---

### Task 6: Final verification and cleanup

**Files:**
- Modify: None (verification only)

**Step 1: Comprehensive search for old names**

```bash
# Search in all files
grep -r "bypass_keenetic" . --include="*.py" --include="*.sh" --include="*.md" --include="*.txt" --include="*.yml" --include="*.yaml" --include="*.json" --include="*.env" --include="*.html" --include="*.css" | grep -v "docs/plans/rename-scan-results.txt"
```

**Step 2: Verify Python files compile**

```bash
python -m py_compile src/web_ui/*.py
python -m py_compile src/web_ui/core/*.py
```

**Step 3: Verify shell scripts**

```bash
bash -n src/web_ui/scripts/*.sh
```

**Step 4: Create final verification report**

```bash
echo "=== Rename Verification Report ===" > docs/plans/rename-verification.txt
echo "Date: $(date)" >> docs/plans/rename-verification.txt
echo "Directory: $(pwd)" >> docs/plans/rename-verification.txt
echo "" >> docs/plans/rename-verification.txt
echo "Remaining old references:" >> docs/plans/rename-verification.txt
grep -r "bypass_keenetic" . --include="*.py" --include="*.sh" --include="*.md" --include="*.txt" --include="*.yml" --include="*.yaml" --include="*.json" --include="*.env" --include="*.html" --include="*.css" | grep -v "docs/plans/rename" >> docs/plans/rename-verification.txt || echo "None found" >> docs/plans/rename-verification.txt
```

**Step 5: Commit verification report**

```bash
git add docs/plans/rename-verification.txt
git commit -m "docs: add rename verification report"
```

**Step 6: Push to remote repository**

```bash
git push -u origin master
```

---

### Task 7: Update remote repository on GitHub

**Note:** This task requires manual action on GitHub website

**Step 1: Create new repository on GitHub**

1. Go to https://github.com/royfincher25-source
2. Click "New" to create repository
3. Name: `FlyMyByte`
4. Description: "Web-интерфейс для управления обходом блокировок на роутерах Keenetic"
5. Make it public
6. Initialize with README (optional)

**Step 2: Push local repository to new remote**

```bash
git push -u origin master
```

**Step 3: Update installation script URLs if needed**

If the repository was created with a different name or under a different organization, update the URLs in:
- `src/web_ui/scripts/install_web.sh`
- `src/web_ui/core/constants.py`
- `src/web_ui/core/web_config.py`

---

### Task 8: Final cleanup

**Files:**
- Modify: None

**Step 1: Remove temporary scan files**

```bash
git rm docs/plans/rename-scan-results.txt
git commit -m "chore: remove temporary scan files"
```

**Step 2: Verify final state**

```bash
# Check Git status
git status

# Check remote URL
git remote -v

# Verify no pending changes
git diff --name-only
```

**Step 3: Create final summary**

```bash
echo "=== FlyMyByte Rename Complete ===" > docs/plans/rename-summary.txt
echo "Local directory: H:\\disk_e\\dell\\FlyMyByte" >> docs/plans/rename-summary.txt
echo "Remote repository: https://github.com/royfincher25-source/FlyMyByte" >> docs/plans/rename-summary.txt
echo "All references updated from bypass_keenetic-web to FlyMyByte" >> docs/plans/rename-summary.txt
```

**Step 4: Commit summary**

```bash
git add docs/plans/rename-summary.txt
git commit -m "docs: add rename completion summary"
```

---

## Execution Handoff

**Plan complete and saved to `docs/plans/2026-03-25-rename-to-flymybyte.md`. Two execution options:**

**1. Subagent-Driven (this session)** - I dispatch fresh subagent per task, review between tasks, fast iteration

**2. Parallel Session (separate)** - Open new session with executing-plans, batch execution with checkpoints

**Which approach?**
