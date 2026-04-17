#!/bin/sh
# refactoring-update.sh - Update FlyMyByte to refactoring branch
# Usage: curl -sL https://raw.githubusercontent.com/royfincher25-source/flymybyte/refactoring/scripts/refactoring-update.sh | sh

set -e

REPO="royfincher25-source/flymybyte"
BRANCH="refactoring"
BASE_URL="https://raw.githubusercontent.com/$REPO/$BRANCH"
WEB_UI_DIR="/opt/etc/web_ui"

echo "=== FlyMyByte Refactoring Update ==="
echo "Branch: $BRANCH"
echo ""

# Phase 1: Create new files
echo "[1/3] Creating new modules..."

curl -sL -o "$WEB_UI_DIR/core/bypass_utils.py" "$BASE_URL/src/web_ui/core/bypass_utils.py"
curl -sL -o "$WEB_UI_DIR/core/system_utils.py" "$BASE_URL/src/web_ui/core/system_utils.py"

chmod 644 "$WEB_UI_DIR/core/bypass_utils.py"
chmod 644 "$WEB_UI_DIR/core/system_utils.py"

echo "  ✅ bypass_utils.py"
echo "  ✅ system_utils.py"

# Phase 2: Update core files
echo "[2/3] Updating core modules..."

curl -sL -o "$WEB_UI_DIR/core/__init__.py" "$BASE_URL/src/web_ui/core/__init__.py"
curl -sL -o "$WEB_UI_DIR/core/utils.py" "$BASE_URL/src/web_ui/core/utils.py"
curl -sL -o "$WEB_UI_DIR/core/dnsmasq_manager.py" "$BASE_URL/src/web_ui/core/dnsmasq_manager.py"
curl -sL -o "$WEB_UI_DIR/core/dns_ops.py" "$BASE_URL/src/web_ui/core/dns_ops.py"
curl -sL -o "$WEB_UI_DIR/core/iptables_manager.py" "$BASE_URL/src/web_ui/core/iptables_manager.py"

echo "  ✅ __init__.py"
echo "  ✅ utils.py"
echo "  ✅ dnsmasq_manager.py"
echo "  ✅ dns_ops.py"
echo "  ✅ iptables_manager.py"

# Phase 3: Update app.py (critical - add_dns_redirect)
echo "[3/3] Updating app.py..."
curl -sL -o "$WEB_UI_DIR/app.py" "$BASE_URL/src/web_ui/app.py"
echo "  ✅ app.py"

# Restart Web UI
echo ""
echo "Restarting Web UI..."
killall python3 2>/dev/null || true
sleep 1
cd "$WEB_UI_DIR" && python3 app.py > /dev/null 2>&1 &
sleep 2

# Verify
echo ""
echo "=== Verification ==="
if curl -s http://127.0.0.1:80/ > /dev/null 2>&1; then
    echo "✅ Web UI is running"
else
    echo "⚠️ Web UI may not be running - check manually"
fi

echo ""
echo "Update complete!"
echo "Check logs: tail -f /opt/var/log/web_ui.log"