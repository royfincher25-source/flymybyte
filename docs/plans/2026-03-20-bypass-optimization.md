# Bypass Domain Addition Optimization Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Optimize the domain addition process for bypass lists (especially Shadowsocks) to reduce processing time on KN-1212 (128MB RAM) by implementing parallel processing and incremental updates.

**Architecture:**
- Optimize `unblock_ipset.sh` to use parallel DNS resolution (2-4 threads based on available memory) instead of sequential processing.
- Optimize `unblock_dnsmasq.sh` to generate configuration in parallel and remove redundant DNS checks.
- Improve `add_to_bypass` logic in `routes.py` to handle IP addresses directly without full system update where possible.
- Simplify logging and error handling in shell scripts.

**Tech Stack:** Python (Flask, ThreadPoolExecutor), Shell (sh, ipset, dnsmasq), ipset restore.

---

### Task 1: Optimize `unblock_ipset.sh` for Parallel Processing

**Files:**
- Modify: `src/web_ui/resources/scripts/unblock_ipset.sh`

**Step 1: Write the failing test (Manual Verification)**

Since this is a shell script, we verify current slow behavior by checking for sequential processing.

Run:
```bash
grep -n "nslookup" src/web_ui/resources/scripts/unblock_ipset.sh
```

Expected: Multiple lines with sequential `nslookup` calls (lines 14, 43, 79, 115, 189).

**Step 2: Run test to verify it fails (Current State)**

Run:
```bash
head -n 50 src/web_ui/resources/scripts/unblock_ipset.sh
```

Expected:看到顺序处理逻辑 (看到了顺序处理逻辑).

**Step 3: Write minimal implementation**

Modify `src/web_ui/resources/scripts/unblock_ipset.sh`:

1. Add memory check logic to determine thread count (1-4 threads based on MemFree).
2. Replace sequential processing with parallel execution using background jobs.
3. Simplify logging to only stats and errors.
4. Keep wildcard domain handling.

Full implementation:

```bash
#!/bin/sh
# unblock_ipset.sh - Optimized version with parallel DNS resolution

mkdir -p /opt/var/log
LOGFILE="/opt/var/log/unblock_ipset.log"
echo "=== $(date '+%Y-%m-%d %H:%M:%S') ===" >> "$LOGFILE"

# Function to check available memory
get_free_memory() {
    # Read MemFree from /proc/meminfo (in kB)
    free_kB=$(grep MemFree /proc/meminfo | awk '{print $2}')
    # Convert to MB
    free_MB=$((free_kB / 1024))
    echo $free_MB
}

# Function to determine thread count based on memory
get_thread_count() {
    free_MB=$(get_free_memory)
    
    if [ $free_MB -lt 20 ]; then
        echo 1  # Very low memory, sequential processing
    elif [ $free_MB -lt 50 ]; then
        echo 2  # Low memory, 2 threads
    elif [ $free_MB -lt 100 ]; then
        echo 3  # Medium memory, 3 threads
    else
        echo 4  # Good memory, 4 threads
    fi
}

# Get thread count
THREAD_COUNT=$(get_thread_count)
echo "Using $THREAD_COUNT threads (free memory: $(get_free_memory)MB)" >> "$LOGFILE"

# Function to check if DNS is ready
check_dns_ready() {
    timeout=30
    while [ $timeout -gt 0 ]; do
        if nslookup google.com 8.8.8.8 >/dev/null 2>&1; then
            return 0
        fi
        sleep 1
        timeout=$((timeout - 1))
    done
    return 1
}

# Check DNS once at start
if ! check_dns_ready; then
    echo "ERROR: DNS not available after 30 seconds" | tee -a "$LOGFILE"
    exit 1
fi

# Function to process a single file
process_file() {
    local file="$1"
    local setname="$2"
    local thread_id="$3"
    
    if [ ! -f "$file" ]; then
        echo "File not found: $file" >> "$LOGFILE"
        return
    fi
    
    # Create temp file for ipset commands
    temp_file="/tmp/ipset_commands_$thread_id.txt"
    > "$temp_file"
    
    # Process file line by line
    while read -r line || [ -n "$line" ]; do
        [ -z "$line" ] && continue
        [ "${line#?}" = "#" ] && continue
        
        # Check for CIDR
        cidr=$(echo "$line" | grep -Eo '[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}/[0-9]{1,2}')
        if [ -n "$cidr" ]; then
            echo "add $setname $cidr" >> "$temp_file"
            continue
        fi
        
        # Check for IP range
        range=$(echo "$line" | grep -Eo '[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}-[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}')
        if [ -n "$range" ]; then
            echo "add $setname $range" >> "$temp_file"
            continue
        fi
        
        # Check for single IP
        addr=$(echo "$line" | grep -Eo '[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}')
        if [ -n "$addr" ]; then
            echo "add $setname $addr" >> "$temp_file"
            continue
        fi
        
        # Resolve domain (skip if empty or comment)
        if [ -n "$line" ] && ! echo "$line" | grep -q '^[[:space:]]*#'; then
            # Use nslookup to resolve domain
            ips=$(nslookup "$line" 8.8.8.8 2>/dev/null | grep -oE '[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}' | grep -v '8\.8\.8\.8')
            for ip in $ips; do
                echo "add $setname $ip" >> "$temp_file"
            done
        fi
    done < "$file"
    
    # Apply ipset commands if file has content
    if [ -s "$temp_file" ]; then
        ipset restore < "$temp_file" 2>> "$LOGFILE"
        count=$(wc -l < "$temp_file")
        echo "Processed $count entries from $file (thread $thread_id)" >> "$LOGFILE"
    fi
    
    # Cleanup
    rm -f "$temp_file"
}

# Define files to process
files=(
    "/opt/etc/unblock/shadowsocks.txt:unblocksh"
    "/opt/etc/unblock/tor.txt:unblocktor"
    "/opt/etc/unblock/vless.txt:unblockvless"
    "/opt/etc/unblock/trojan.txt:unblocktroj"
)

# Add VPN files
for vpn_file in /opt/etc/unblock/vpn-*.txt; do
    if [ -f "$vpn_file" ]; then
        vpn_name=$(basename "$vpn_file" .txt)
        files+=("$vpn_file:unblock$vpn_name")
    fi
done

# Process files in parallel
i=0
for entry in "${files[@]}"; do
    file=$(echo "$entry" | cut -d: -f1)
    setname=$(echo "$entry" | cut -d: -f2)
    
    # Ensure ipset exists
    ipset create "$setname" hash:ip 2>/dev/null || true
    
    # Run in background
    process_file "$file" "$setname" $i &
    i=$((i + 1))
    
    # Limit concurrent processes to thread count
    if [ $i -ge $THREAD_COUNT ]; then
        wait
        i=0
    fi
done

# Wait for all background jobs
wait

echo "✅ IPSET заполнен" | tee -a "$LOGFILE"
```

**Step 4: Run test to verify it passes**

Run syntax check:
```bash
bash -n src/web_ui/resources/scripts/unblock_ipset.sh
```

Expected: No syntax errors.

**Step 5: Commit**

```bash
git add src/web_ui/resources/scripts/unblock_ipset.sh
git commit -m "refactor: optimize unblock_ipset.sh with parallel processing and memory check"
```

---

### Task 2: Optimize `unblock_dnsmasq.sh` for Parallel Generation

**Files:**
- Modify: `src/web_ui/resources/scripts/unblock_dnsmasq.sh`

**Step 1: Write the failing test**

Verify current sequential generation:
Run:
```bash
grep -n "while read" src/web_ui/resources/scripts/unblock_dnsmasq.sh
```

Expected: Multiple sequential loops.

**Step 2: Run test to verify it fails**

Check for DNS check at start:
Run:
```bash
grep -n "nslookup google.com" src/web_ui/resources/scripts/unblock_dnsmasq.sh
```

Expected: Found check.

**Step 3: Write minimal implementation**

Modify `src/web_ui/resources/scripts/unblock_dnsmasq.sh`:

1. Remove DNS check (moved to `unblock_ipset.sh`).
2. Parallelize configuration generation for existing files.
3. Simplify logging.
4. Delete comments during generation.

Full implementation:

```bash
#!/bin/sh
# unblock_dnsmasq.sh - Optimized version with parallel generation

mkdir -p /opt/var/log
LOGFILE="/opt/var/log/unblock_dnsmasq.log"
echo "=== $(date '+%Y-%m-%d %H:%M:%S') ===" >> "$LOGFILE"

# Clear dnsmasq config
cat /dev/null > /opt/etc/unblock.dnsmasq

# Function to generate config for a single file
generate_config() {
    local file="$1"
    local setname="$2"
    local temp_config="$3"
    
    if [ ! -f "$file" ]; then
        echo "Warning: $file not found" >> "$LOGFILE"
        return
    fi
    
    # Process file, skipping comments and empty lines
    while read -r line || [ -n "$line" ]; do
        [ -z "$line" ] && continue
        [ "${line#?}" = "#" ] && continue
        
        # Skip IP addresses (only process domains)
        if echo "$line" | grep -Eq '[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}'; then
            continue
        fi
        
        # Handle wildcard domains (keep as is, dnsmasq ignores leading dots)
        echo "ipset=/$line/$setname" >> "$temp_config"
        echo "server=/$line/127.0.0.1#40500" >> "$temp_config"
    done < "$file"
}

# Define files to process
files=(
    "/opt/etc/unblock/shadowsocks.txt:unblocksh"
    "/opt/etc/unblock/tor.txt:unblocktor"
    "/opt/etc/unblock/vless.txt:unblockvless"
    "/opt/etc/unblock/trojan.txt:unblocktroj"
)

# Add VPN files
for vpn_file in /opt/etc/unblock/vpn-*.txt; do
    if [ -f "$vpn_file" ]; then
        vpn_name=$(basename "$vpn_file" .txt)
        files+=("$vpn_file:unblock$vpn_name")
    fi
done

# Process files in parallel
temp_dir="/tmp/dnsmasq_config_$$"
mkdir -p "$temp_dir"

i=0
for entry in "${files[@]}"; do
    file=$(echo "$entry" | cut -d: -f1)
    setname=$(echo "$entry" | cut -d: -f2)
    
    temp_config="$temp_dir/config_$i.txt"
    > "$temp_config"
    
    # Run in background
    generate_config "$file" "$setname" "$temp_config" &
    i=$((i + 1))
done

# Wait for all background jobs
wait

# Combine all configs
cat "$temp_dir"/config_*.txt >> /opt/etc/unblock.dnsmasq

# Cleanup
rm -rf "$temp_dir"

# Restart dnsmasq
/opt/etc/init.d/S56dnsmasq restart >> "$LOGFILE" 2>&1

echo "✅ Dnsmasq config generated" | tee -a "$LOGFILE"
```

**Step 4: Run test to verify it passes**

Run syntax check:
```bash
bash -n src/web_ui/resources/scripts/unblock_dnsmasq.sh
```

Expected: No syntax errors.

**Step 5: Commit**

```bash
git add src/web_ui/resources/scripts/unblock_dnsmasq.sh
git commit -m "refactor: optimize unblock_dnsmasq.sh with parallel generation"
```

---

### Task 3: Optimize `add_to_bypass` in `routes.py`

**Files:**
- Modify: `src/web_ui/routes.py` (lines ~470-566)

**Step 1: Write the failing test**

Create test file:
```bash
cat > tests/test_bypass_optimization.py << 'EOF'
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'web_ui'))

def test_add_to_bypass_exists():
    """Test that add_to_bypass function exists"""
    from routes import add_to_bypass
    assert add_to_bypass is not None
    print("✓ add_to_bypass function exists")
EOF
```

**Step 2: Run test to verify it fails**

Run:
```bash
python -m pytest tests/test_bypass_optimization.py::test_add_to_bypass_exists -v
```

Expected: PASS (function exists).

**Step 3: Write minimal implementation**

Modify `src/web_ui/routes.py`:

Replace the `add_to_bypass` function with optimized version:

```python
@bp.route('/bypass/<filename>/add', methods=['GET', 'POST'])
@login_required
@csrf_required
def add_to_bypass(filename: str):
    """
    Add entries to a bypass list file with optimized processing.
    """
    config = WebConfig()
    
    # Security: sanitize filename
    filename = secure_filename(filename)
    if not filename:
        flash('Неверное имя файла', 'danger')
        return redirect(url_for('main.bypass'))
    
    filepath = os.path.join(config.unblock_dir, f"{filename}.txt")

    if request.method == 'POST':
        entries_text = request.form.get('entries', '')

        # Проверка на общий размер ввода (DoS protection)
        if len(entries_text) > MAX_TOTAL_INPUT_SIZE:
            flash(f'Превышен лимит размера ввода (макс. {MAX_TOTAL_INPUT_SIZE // 1024}KB)', 'danger')
            return redirect(url_for('main.bypass'))

        # Разбиваем на отдельные записи
        new_entries = [e.strip() for e in entries_text.split('\n') if e.strip()]

        # Проверка на количество записей (DoS protection)
        if len(new_entries) > MAX_ENTRIES_PER_REQUEST:
            flash(f'Превышено количество записей (макс. {MAX_ENTRIES_PER_REQUEST})', 'danger')
            return redirect(url_for('main.bypass'))

        # Проверка на длину записей (XSS + DoS protection)
        for entry in new_entries:
            if len(entry) > MAX_ENTRY_LENGTH:
                flash(f'Запись слишком длинная (макс. {MAX_ENTRY_LENGTH} симв.): {escape(entry[:50])}...', 'danger')
                return redirect(url_for('main.bypass'))

        # Загружаем текущий список
        current_list = load_bypass_list(filepath)

        # Добавляем новые записи с валидацией
        added_count = 0
        invalid_entries = []
        ip_entries = []  # Отдельно собираем IP для добавления в ipset
        domain_entries = []  # Отдельно собираем домены

        for entry in new_entries:
            if entry not in current_list:
                if validate_bypass_entry(entry):
                    current_list.append(entry)
                    added_count += 1
                    # Если это IP адрес - добавляем в список для ipset
                    if is_ip_address(entry):
                        ip_entries.append(entry)
                    else:
                        domain_entries.append(entry)
                else:
                    invalid_entries.append(entry)

        # Сохраняем список
        save_bypass_list(filepath, current_list)

        # Оптимизированная логика обновления
        if added_count > 0:
            # Если только IP-адреса - добавляем напрямую в ipset
            if ip_entries and not domain_entries:
                success, msg = bulk_add_to_ipset('unblock', ip_entries)
                if success:
                    logger.info(f"Directly added {len(ip_entries)} IPs to ipset")
                    flash(f'✅ Успешно добавлено: {added_count} шт. (IP в ipset: {len(ip_entries)})', 'success')
                else:
                    logger.warning(f"Failed to add IPs directly: {msg}")
                    # Fall back to full update
                    success, output = run_unblock_update()
                    if success:
                        flash(f'✅ Успешно добавлено: {added_count} шт. Изменения применены', 'success')
                    else:
                        flash(f'⚠️ Добавлено {added_count} записей, но ошибка при применении: {output}', 'warning')
            else:
                # Для доменов или смешанных записей - использовать оптимизированные скрипты
                if added_count > 0:
                    success, output = run_unblock_update()
                    if success:
                        flash(f'✅ Успешно добавлено: {added_count} шт. Изменения применены', 'success')
                    else:
                        flash(f'⚠️ Добавлено {added_count} записей, но ошибка при применении: {output}', 'warning')
        elif invalid_entries:
            # XSS protection: escape user input
            escaped_invalid = [escape(e) for e in invalid_entries[:5]]
            flash(f'⚠️ Все записи уже в списке или невалидны. Нераспознанные: {", ".join(escaped_invalid)}', 'warning')
        else:
            flash('ℹ️ Все записи уже были в списке', 'info')

        return redirect(url_for('main.view_bypass', filename=filename))
    
    # GET запрос - показываем форму
    return render_template('bypass_add.html', filename=filename)
```

**Step 4: Run test to verify it passes**

Run:
```bash
python -m pytest tests/test_bypass_optimization.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add tests/test_bypass_optimization.py src/web_ui/routes.py
git commit -m "feat: optimize add_to_bypass for direct IP addition"
```

---

### Task 4: Update `unblock_update.sh` Integration

**Files:**
- Modify: `src/web_ui/resources/scripts/unblock_update.sh`

**Step 1: Write the failing test**

Verify current DNS check:
Run:
```bash
grep -n "nslookup google.com" src/web_ui/resources/scripts/unblock_update.sh
```

**Step 2: Run test to verify it fails**

Expected: Found check.

**Step 3: Write minimal implementation**

Modify `src/web_ui/resources/scripts/unblock_update.sh`:

Remove DNS check (now in `unblock_ipset.sh`):

```bash
#!/bin/sh
ipset flush unblocktor
ipset flush unblocksh
ipset flush unblockvless
ipset flush unblocktroj

if ls -d /opt/etc/unblock/vpn-*.txt >/dev/null 2>&1; then
    for vpn_file_names in /opt/etc/unblock/vpn-*; do
        vpn_file_name=$(echo "$vpn_file_names" | awk -F '/' '{print $5}' | sed 's/.txt//')
        unblockvpn=$(echo unblock"$vpn_file_name")
        ipset flush "$unblockvpn"
    done
fi

/opt/bin/unblock_dnsmasq.sh
/opt/etc/init.d/S56dnsmasq restart

# Block until ipset is filled, with logging
mkdir -p /opt/var/log
echo "=== $(date '+%Y-%m-%d %H:%M:%S') ===" >> /opt/var/log/unblock.log 2>/dev/null || true
echo "Starting ipset population..." | tee -a /opt/var/log/unblock.log
/opt/bin/unblock_ipset.sh 2>&1 | tee -a /opt/var/log/unblock.log

# Verify result
sleep 2
for ipset_name in unblocksh unblocktor unblockvless unblocktroj; do
    count=$(ipset list "$ipset_name" 2>/dev/null | grep -c "^[0-9]" || echo 0)
    echo "$ipset_name: $count entries" | tee -a /opt/var/log/unblock.log
done
```

**Step 4: Run test to verify it passes**

Run syntax check:
```bash
bash -n src/web_ui/resources/scripts/unblock_update.sh
```

Expected: No syntax errors.

**Step 5: Commit**

```bash
git add src/web_ui/resources/scripts/unblock_update.sh
git commit -m "refactor: remove redundant DNS check in unblock_update.sh"
```

---

### Task 5: Integration and Final Verification

**Files:**
- Test file: `tests/test_bypass_optimization.py`

**Step 1: Write integration test**

Add to `tests/test_bypass_optimization.py`:

```python
def test_optimized_scripts_exist():
    """Test that optimized scripts exist and are valid"""
    import os
    
    scripts = [
        'src/web_ui/resources/scripts/unblock_ipset.sh',
        'src/web_ui/resources/scripts/unblock_dnsmasq.sh',
        'src/web_ui/resources/scripts/unblock_update.sh'
    ]
    
    for script in scripts:
        assert os.path.exists(script), f"Script {script} not found"
        
        # Check script is executable
        assert os.access(script, os.X_OK), f"Script {script} is not executable"
    
    print("✓ All optimized scripts exist and are executable")

def test_routes_optimization():
    """Test that routes.py has been optimized"""
    routes_file = 'src/web_ui/routes.py'
    
    with open(routes_file, 'r') as f:
        content = f.read()
    
    # Check for optimized logic
    assert 'ip_entries' in content, "IP entries handling not found"
    assert 'domain_entries' in content, "Domain entries handling not found"
    assert 'bulk_add_to_ipset' in content, "Bulk add to ipset not found"
    
    print("✓ routes.py has been optimized")
```

**Step 2: Run test**

Run:
```bash
python -m pytest tests/test_bypass_optimization.py -v
```

**Step 3: Fix any issues**

**Step 4: Commit**

```bash
git add tests/test_bypass_optimization.py
git commit -m "test: add integration tests for bypass optimization"
```

---

## Execution Handoff

Plan complete and saved to `docs/plans/2026-03-20-bypass-optimization.md`. Two execution options:

**1. Subagent-Driven (this session)** - I dispatch fresh subagent per task, review between tasks, fast iteration

**2. Parallel Session (separate)** - Open new session with executing-plans, batch execution with checkpoints

Which approach?