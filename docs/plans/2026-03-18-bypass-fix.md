# Bypass Mechanism Fix and Installation Enhancement Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix bypass mechanism (ipset, dnsmasq, iptables) and enhance installation process for Keenetic KN-1212 router with 128MB RAM.

**Architecture:** Two-part fix: (1) Critical bypass mechanism bugs - unblock_update.sh runs in background causing ipset to never populate, DNS servers pointing to non-working local ports, missing file checks. (2) Installation enhancements - add missing files (dnsmasq.conf, crontab, lists) to install process.

**Tech Stack:** Shell scripts (sh), Python Flask web interface, iptables, ipset, dnsmasq, Keenetic Entware

---

## Part A: Critical Bypass Mechanism Fixes

### Task A1: Fix unblock_update.sh (blocking execution)

**Files:**
- Modify: `src/web_ui/resources/scripts/unblock_update.sh`

**Step 1: Create backup**

```bash
cp src/web_ui/resources/scripts/unblock_update.sh src/web_ui/resources/scripts/unblock_update.sh.bak
```

**Step 2: Edit file to fix background execution**

Find line 17:
```bash
/opt/bin/unblock_ipset.sh &
```

Replace with:
```bash
# Block until ipset is filled, with logging
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

**Step 3: Commit**

```bash
git add src/web_ui/resources/scripts/unblock_update.sh
git commit -m "fix: block ipset execution, add logging"
```

---

### Task A2: Fix dnsmasq.conf DNS servers

**Files:**
- Modify: `src/web_ui/resources/config/dnsmasq.conf`

**Step 1: Backup original**

```bash
cp src/web_ui/resources/config/dnsmasq.conf src/web_ui/resources/config/dnsmasq.conf.bak
```

**Step 2: Edit file - replace DNS servers**

Find lines 32-33:
```bash
server=127.0.0.1#40500
server=127.0.0.1#40508
```

Replace with:
```bash
# Direct DNS with fallback (no local DoT/DoH required)
# Primary: Google, Secondary: Cloudflare
server=8.8.8.8
server=1.1.1.1

# Optional: Uncomment if cloudflored is installed and running
# server=127.0.0.1#40500
# server=127.0.0.1#40508
```

**Step 3: Commit**

```bash
git add src/web_ui/resources/config/dnsmasq.conf
git commit -m "fix: use direct DNS servers as fallback"
```

---

### Task A3: Add file existence checks to unblock_dnsmasq.sh

**Files:**
- Modify: `src/web_ui/resources/scripts/unblock_dnsmasq.sh`

**Step 1: Add checks before each file read**

After line 6 (cut_local function), add:

```bash
# Ensure log directory exists
mkdir -p /opt/var/log
LOGFILE="/opt/var/log/unblock_dnsmasq.log"
echo "=== $(date '+%Y-%m-%d %H:%M:%S') ===" >> "$LOGFILE"
```

**Step 2: Add file check before shadowsocks.txt loop (around line 8)**

Find:
```bash
while read -r line || [ -n "$line" ]; do
```

Replace with:
```bash
# Check file exists
if [ ! -f "/opt/etc/unblock/shadowsocks.txt" ]; then
    echo "Warning: /opt/etc/unblock/shadowsocks.txt not found, skipping" >> "$LOGFILE"
else
while read -r line || [ -n "$line" ]; do
```

And close the if block after the first done (line 24):
```bash
done < /opt/etc/unblock/shadowsocks.txt
fi
```

**Step 3: Repeat for tor.txt, vless.txt, trojan.txt, vpn-*.txt loops**

**Step 4: Commit**

```bash
git add src/web_ui/resources/scripts/unblock_dnsmasq.sh
git commit -m "fix: add file existence checks before reading"
```

---

### Task A4: Ensure ipset creation in 100-redirect.sh

**Files:**
- Modify: `src/web_ui/resources/scripts/100-redirect.sh`

**Step 1: Add ipset creation at script start (after line 6)**

Add:
```bash
# Ensure all required ipsets exist
for ipset_name in unblocksh unblocktor unblockvless unblocktroj; do
    ipset create "$ipset_name" hash:net -exist 2>/dev/null
done
echo "IPsets ready"
```

**Step 2: Commit**

```bash
git add src/web_ui/resources/scripts/100-redirect.sh
git commit -m "fix: create ipsets on script start"
```

---

### Task A5: Add logging to unblock_ipset.sh

**Files:**
- Modify: `src/web_ui/resources/scripts/unblock_ipset.sh`

**Step 1: Add log file creation at start**

After line 3 (comment), add:
```bash
mkdir -p /opt/var/log
LOGFILE="/opt/var/log/unblock_ipset.log"
echo "=== $(date '+%Y-%m-%d %H:%M:%S') ===" >> "$LOGFILE"
```

**Step 2: Add entry counts at end**

After line 195 (echo "✅ IPSET заполнен"), add:
```bash
echo "Final counts:" >> "$LOGFILE"
for name in unblocksh unblocktor unblockvless unblocktroj; do
    cnt=$(ipset list "$name" 2>/dev/null | grep -c "^[0-9]" || echo 0)
    echo "  $name: $cnt" >> "$LOGFILE"
done
```

**Step 3: Commit**

```bash
git add src/web_ui/resources/scripts/unblock_ipset.sh
git commit -m "fix: add logging to ipset script"
```

---

## Part B: Installation Enhancement

### Task B1: Add missing resources (crontab and lists)

**Files:**
- Create: `src/web_ui/resources/config/crontab`
- Create: `src/web_ui/resources/lists/unblockvless.txt`
- Create: `src/web_ui/resources/lists/unblocktor.txt`

**Step 1: Create crontab file**

```bash
mkdir -p src/web_ui/resources/config
mkdir -p src/web_ui/resources/lists

cat > src/web_ui/resources/config/crontab << 'EOF'
# Bypass Keenetic - Cron schedule
# Update ipset every 6 hours
0 */6 * * * /opt/bin/unblock_update.sh
EOF
```

**Step 2: Create list files (minimal starter lists)**

```bash
cat > src/web_ui/resources/lists/unblockvless.txt << 'EOF'
# Minimal VLESS bypass list - add your domains
youtube.com
googlevideo.com
ytimg.com
googleusercontent.com
EOF

cat > src/web_ui/resources/lists/unblocktor.txt << 'EOF'
# Minimal Tor bypass list - add your domains
facebook.com
instagram.com
twitter.com
telegram.org
EOF
```

**Step 3: Commit**

```bash
git add src/web_ui/resources/config/crontab src/web_ui/resources/lists/
git commit -m "feat: add crontab and starter lists"
```

---

### Task B2: Enhance script.sh with full installation

**Files:**
- Modify: `src/web_ui/scripts/script.sh`

**Step 1: Find installation section around line 170**

After loading scripts, add new section for config files:

```bash
# === NEW: Install dnsmasq.conf ===
echo "Installing dnsmasq.conf..."
curl -sL -o "$DNSMASQ_CONF" "$RESOURCES_URL/config/dnsmasq.conf" && \
    sed -i -e "s/192.168.1.1/${lanip}/g" \
           -e "s/40500/${dnsovertlsport}/g" \
           -e "s/40508/${dnsoverhttpsport}/g" "$DNSMASQ_CONF" && \
    echo "  ✅ dnsmasq.conf" || echo "  ⚠️ dnsmasq.conf"

# === NEW: Install crontab ===
echo "Installing crontab..."
curl -sL -o "$CRONTAB" "$RESOURCES_URL/config/crontab" && \
    echo "  ✅ crontab" || echo "  ⚠️ crontab"

# === NEW: Install templates ===
echo "Installing templates..."
mkdir -p "$TEMPLATES_DIR"
for template in tor_template.torrc vless_template.json trojan_template.json shadowsocks_template.json; do
    curl -sL -o "$TEMPLATES_DIR/$template" "$RESOURCES_URL/config/$template" && \
        echo "  ✅ $template" || echo "  ⚠️ $template"
done

# === NEW: Install init scripts ===
echo "Installing init scripts..."
curl -sL -o "$INIT_UNBLOCK" "$RESOURCES_URL/scripts/S99unblock" && \
    chmod 755 "$INIT_UNBLOCK" && \
    echo "  ✅ S99unblock" || echo "  ⚠️ S99unblock"

curl -sL -o "$INIT_WEB" "$RESOURCES_URL/scripts/S99web_ui" && \
    chmod 755 "$INIT_WEB" && \
    echo "  ✅ S99web_ui" || echo "  ⚠️ S99web_ui"

# === NEW: Create domain lists ===
echo "Installing domain lists..."
mkdir -p "$UNBLOCK_DIR"
curl -sL -o "${UNBLOCK_DIR}vless.txt" "$RESOURCES_URL/lists/unblockvless.txt" || touch "${UNBLOCK_DIR}vless.txt"
curl -sL -o "${UNBLOCK_DIR}tor.txt" "$RESOURCES_URL/lists/unblocktor.txt" || touch "${UNBLOCK_DIR}tor.txt"
touch "${UNBLOCK_DIR}shadowsocks.txt"
touch "${UNBLOCK_DIR}trojan.txt"
touch "${UNBLOCK_DIR}vpn.txt"
echo "  ✅ Domain lists created"
```

**Step 2: Add startup commands after installation**

After the curl sections, add:

```bash
# === NEW: Initial startup ===
echo "Starting services..."

# Create ipsets and populate
/opt/bin/unblock_ipset.sh

# Setup iptables rules
/opt/etc/ndm/netfilter.d/100-redirect.sh

# Restart dnsmasq
/opt/etc/init.d/S56dnsmasq restart

echo "✅ Installation complete"
```

**Step 3: Commit**

```bash
git add src/web_ui/scripts/script.sh
git commit -m "feat: enhance installation with all required files"
```

---

### Task B3: Add post-install verification in routes.py

**Files:**
- Modify: `src/web_ui/routes.py` (around line 1130-1140)

**Step 1: Add verification after installation**

After the process.wait() block around line 1130, add:

```python
# Verify installation
try:
    # Check ipset exists
    result = subprocess.run(
        ['sh', '-c', 'ipset list -n'],
        capture_output=True,
        text=True,
        timeout=10
    )
    if 'unblocksh' in result.stdout:
        flash('✅ ipset initialized', 'success')
    else:
        flash('⚠️ ipset not found', 'warning')
        
    # Check init scripts
    for script in ['S99unblock', 'S99web_ui']:
        if os.path.exists(f'/opt/etc/init.d/{script}'):
            flash(f'✅ {script} installed', 'success')
            
except Exception as e:
    logger.error(f"Post-install verification error: {e}")
```

**Step 2: Commit**

```bash
git add src/web_ui/routes.py
git commit -m "feat: add post-install verification"
```

---

## Testing Phase

### Test A1: Verify bypass mechanism works

**Run on router:**

```bash
# Manual test
ssh root@192.168.1.1

# Run ipset script
/opt/bin/unblock_ipset.sh

# Check results
ipset list unblocksh | head -20
ipset list unblocksh | wc -l

# Check iptables
iptables -t nat -L PREROUTING -v -n | head -10

# Check dnsmasq
cat /opt/etc/unblock.dnsmasq | head -10

# Test DNS
nslookup youtube.com
```

**Expected results:**
- ipset has entries (>0)
- iptables rules exist
- dnsmasq.conf has domain rules

---

### Test B1: Verify installation works

**Run on router:**

```bash
# From web interface, click "Install"
# Or manually:
/opt/root/script.sh -install

# Check all files exist
ls -la /opt/etc/init.d/S99*
ls -la /opt/bin/unblock*.sh
ls -la /opt/etc/unblock/*.txt
ls -la /opt/etc/dnsmasq.conf
cat /opt/etc/crontab
```

**Expected results:**
- All init scripts present
- All scripts in /opt/bin/
- All lists in /opt/etc/unblock/
- dnsmasq.conf installed
- crontab installed

---

## Summary Checklist

| Task | Description | Status |
|------|-------------|--------|
| A1 | Fix unblock_update.sh blocking | ⬜ |
| A2 | Fix dnsmasq.conf DNS | ⬜ |
| A3 | Add file checks in unblock_dnsmasq.sh | ⬜ |
| A4 | Ensure ipset creation in 100-redirect.sh | ⬜ |
| A5 | Add logging to unblock_ipset.sh | ⬜ |
| B1 | Add crontab and lists | ⬜ |
| B2 | Enhance script.sh | ⬜ |
| B3 | Add post-install verification | ⬜ |
| TEST | Verify bypass works | ⬜ |
| TEST | Verify installation works | ⬜ |

---

## Notes for Execution

- All tasks are independent and can be done in parallel where applicable
- Test on router after each major change
- Create backups before modifying any file
- Commit after each successful change

**Plan complete and saved to `docs/plans/2026-03-18-bypass-fix.md`.**
