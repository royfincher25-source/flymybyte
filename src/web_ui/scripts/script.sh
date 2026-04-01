#!/bin/sh
# =============================================================================
# SCRIPT.SH ДЛЯ WEB_UI - LIGHT VERSION
# Загружает ресурсы динамически при установке
# =============================================================================

# Путь к конфигурации веб-интерфейса
WEB_CONFIG="/opt/etc/web_ui/core/web_config.py"
if [ ! -f "$WEB_CONFIG" ]; then
    echo "❌ Ошибка: Файл конфигурации $WEB_CONFIG не найден!" >&2
    echo "Запустите установку через веб-интерфейс." >&2
    exit 1
fi

# Чтение URL из конфигурации
BASE_URL=$(grep "^base_url" "$WEB_CONFIG" | awk -F'"' '{print $2}')
WEB_URL="$BASE_URL/src/web_ui"

# Чтение IP и портов (формат: key = value)
lanip=$(grep "^routerip" "$WEB_CONFIG" | awk -F'=' '{print $2}' | tr -d ' "')
localportsh=$(grep "^localportsh" "$WEB_CONFIG" | awk -F'=' '{print $2}' | tr -d ' ')
dnsporttor=$(grep "^dnsporttor" "$WEB_CONFIG" | awk -F'=' '{print $2}' | tr -d ' ')
localporttor=$(grep "^localporttor" "$WEB_CONFIG" | awk -F'=' '{print $2}' | tr -d ' ')
localportvless=$(grep "^localportvless" "$WEB_CONFIG" | awk -F'=' '{print $2}' | tr -d ' ')
localporttrojan=$(grep "^localporttrojan" "$WEB_CONFIG" | awk -F'=' '{print $2}' | tr -d ' ')
dnsovertlsport=$(grep "^dnsovertlsport" "$WEB_CONFIG" | awk -F'=' '{print $2}' | tr -d ' ')
dnsoverhttpsport=$(grep "^dnsoverhttpsport" "$WEB_CONFIG" | awk -F'=' '{print $2}' | tr -d ' ')

# Чтение версии прошивки
if [ -f /proc/version ]; then
    keen_os_full=$(cat /proc/version | awk '{print $3}')
    keen_os_short=$(echo "$keen_os_full" | cut -d'.' -f1)
else
    echo "❌ Ошибка: файл /proc/version не найден." >&2
    exit 1
fi

# Функция для чтения путей из конфига (формат: key = "value")
read_path() {
    grep "^$1" "$WEB_CONFIG" | awk -F'"' '{print $2}'
}

# Чтение путей из paths
UNBLOCK_DIR=$(read_path "unblock_dir")
TOR_CONFIG=$(read_path "tor_config")
SHADOWSOCKS_CONFIG=$(read_path "shadowsocks_config")
TROJAN_CONFIG=$(read_path "trojan_config")
VLESS_CONFIG=$(read_path "vless_config")
TEMPLATES_DIR=$(read_path "templates_dir")
DNSMASQ_CONF=$(read_path "dnsmasq_conf")
CRONTAB=$(read_path "crontab")
REDIRECT_SCRIPT=$(read_path "redirect_script")
VPN_SCRIPT=$(read_path "vpn_script")
IPSET_SCRIPT=$(read_path "ipset_script")
UNBLOCK_IPSET=$(read_path "unblock_ipset")
UNBLOCK_DNSMASQ=$(read_path "unblock_dnsmasq")
UNBLOCK_UPDATE=$(read_path "unblock_update")
KEENSNAP_DIR=$(read_path "keensnap_dir")
SCRIPT_BU=$(read_path "script_bu")
WEB_DIR=$(read_path "web_dir")
TOR_TMP_DIR=$(read_path "tor_tmp_dir")
TOR_DIR=$(read_path "tor_dir")
XRAY_DIR=$(read_path "xray_dir")
TROJAN_DIR=$(read_path "trojan_dir")
INIT_SHADOWSOCKS=$(read_path "init_shadowsocks")
INIT_TROJAN=$(read_path "init_trojan")
INIT_XRAY=$(read_path "init_xray")
INIT_TOR=$(read_path "init_tor")
INIT_DNSMASQ=$(read_path "init_dnsmasq")
INIT_UNBLOCK=$(read_path "init_unblock")
INIT_WEB=$(read_path "init_web")
HOSTS_FILE=$(read_path "hosts_file")

# Чтение пакетов
installed_packages=$(opkg list-installed | awk '{print $1}')
PACKAGES=$(awk '/^packages = \[/,/\]/ {
    if ($0 ~ /".*"/) {
        gsub(/^[[:space:]]*"|".*$/, "")
        printf "%s ", $0
    }
}' "$WEB_CONFIG")

# =============================================================================
# УДАЛЕНИЕ (-remove)
# =============================================================================
if [ "$1" = "-remove" ]; then
    echo "=== Удаление flymybyte ==="

    # Удаление пакетов
    for pkg in $PACKAGES; do
        if echo "$installed_packages" | grep -q "^$pkg$"; then
            echo "Удаляем пакет: $pkg"
            opkg remove "$pkg" --force-removal-of-dependent-packages
        else
            echo "❕Пакет $pkg не установлен, пропускаем..."
        fi
    done
    echo "Все пакеты удалены. Начинаем удаление папок, файлов и настроек"

    # Очистка ipset
    ipset flush unblocktor 2>/dev/null || true
    ipset flush unblocksh 2>/dev/null || true
    ipset flush unblockvless 2>/dev/null || true
    ipset flush unblocktroj 2>/dev/null || true

    # Список для удаления
    for file in \
        "$CRONTAB" \
        "$INIT_SHADOWSOCKS" \
        "$INIT_TROJAN" \
        "$INIT_XRAY" \
        "$INIT_TOR" \
        "$INIT_DNSMASQ" \
        "$INIT_UNBLOCK" \
        "$REDIRECT_SCRIPT" \
        "$VPN_SCRIPT" \
        "$IPSET_SCRIPT" \
        "$UNBLOCK_IPSET" \
        "$UNBLOCK_DNSMASQ" \
        "$UNBLOCK_UPDATE" \
        "$DNSMASQ_CONF" \
        "$TOR_TMP_DIR" \
        "$TOR_DIR" \
        "$XRAY_DIR" \
        "$TEMPLATES_DIR" \
        "$TROJAN_DIR" \
        "/opt/etc/unblock-ai.dnsmasq" \
        "/opt/etc/unblock/ai-domains.txt"
    do
        [ -e "$file" ] && rm -rf "$file" && echo "Удалён файл или директория: \"$file\""
    done

    # Удаление веб-интерфейса
    if [ -n "$WEB_DIR" ] && [ -d "$WEB_DIR" ]; then
        rm -rf "$WEB_DIR"
        echo "Удалена директория веб-интерфейса: $WEB_DIR"
    fi

    echo "✅ Созданные папки, файлы и настройки удалены"
    exit 0
fi

# =============================================================================
# УСТАНОВКА (-install)
# =============================================================================
if [ "$1" = "-install" ]; then
    echo "=== Установка flymybyte ==="
    echo "ℹ️ Ваша версия KeenOS: ${keen_os_full}"
    echo ""

    # Установка пакетов
    echo "📦 Установка пакетов..."
    for pkg in $PACKAGES; do
        if echo "$installed_packages" | grep -q "^$pkg$"; then
            echo "  ❕$pkg уже установлен"
        else
            echo "  → $pkg"
            if ! opkg install "$pkg" >/dev/null 2>&1; then
                echo "❌ Ошибка при установке $pkg" >&2
                exit 1
            fi
        fi
    done
    echo "✅ Пакеты установлены"
    echo ""

    # Проверка hash:net
    set_type=$(ipset --help 2>/dev/null | grep -q "hash:net" && echo "hash:net" || echo "hash:ip")
    echo "ℹ️ Тип ipset: $set_type"
    echo ""

    # Загрузка скриптов с GitHub
    RESOURCES_URL="$BASE_URL/src/web_ui/resources"

    echo "⏳ Загрузка скриптов..."
    mkdir -p "$(dirname "$IPSET_SCRIPT")"
    curl -sL -o "$IPSET_SCRIPT" "$RESOURCES_URL/scripts/100-ipset.sh" && \
        sed -i "s/hash:net/${set_type}/g" "$IPSET_SCRIPT" && \
        chmod 755 "$IPSET_SCRIPT" && \
        "$IPSET_SCRIPT" start && \
        echo "  ✅ 100-ipset.sh" || echo "  ❌ 100-ipset.sh"

    curl -sL -o "$UNBLOCK_IPSET" "$RESOURCES_URL/scripts/unblock_ipset.sh" && \
        sed -i "s/40500/${dnsovertlsport}/g" "$UNBLOCK_IPSET" && \
        chmod 755 "$UNBLOCK_IPSET" && \
        echo "  ✅ unblock_ipset.sh" || echo "  ❌ unblock_ipset.sh"

    curl -sL -o "$UNBLOCK_DNSMASQ" "$RESOURCES_URL/scripts/unblock_dnsmasq.sh" && \
        sed -i "s/40500/${dnsovertlsport}/g" "$UNBLOCK_DNSMASQ" && \
        chmod 755 "$UNBLOCK_DNSMASQ" && \
        echo "  ✅ unblock_dnsmasq.sh" || echo "  ❌ unblock_dnsmasq.sh"

    curl -sL -o "$UNBLOCK_UPDATE" "$RESOURCES_URL/scripts/unblock_update.sh" && \
        chmod 755 "$UNBLOCK_UPDATE" && \
        echo "  ✅ unblock_update.sh" || echo "  ❌ unblock_update.sh"

    curl -sL -o "$REDIRECT_SCRIPT" "$RESOURCES_URL/scripts/100-redirect.sh" && \
        sed -i -e "s/hash:net/${set_type}/g" -e "s/192.168.1.1/${lanip}/g" \
               -e "s/1082/${localportsh}/g" -e "s/9141/${localporttor}/g" \
               -e "s/10810/${localportvless}/g" -e "s/10829/${localporttrojan}/g" \
               "$REDIRECT_SCRIPT" && \
        chmod 755 "$REDIRECT_SCRIPT" && \
        echo "  ✅ 100-redirect.sh" || echo "  ❌ 100-redirect.sh"

    # VPN скрипт
    if [ "${keen_os_short}" = "4" ]; then
        curl -sL -o "$VPN_SCRIPT" "$RESOURCES_URL/scripts/100-unblock-vpn-v4.sh" && \
            chmod 755 "$VPN_SCRIPT" && \
            echo "  ✅ 100-unblock-vpn-v4.sh" || echo "  ❌ 100-unblock-vpn-v4.sh"
    else
        curl -sL -o "$VPN_SCRIPT" "$RESOURCES_URL/scripts/100-unblock-vpn.sh" && \
            chmod 755 "$VPN_SCRIPT" && \
            echo "  ✅ 100-unblock-vpn.sh" || echo "  ❌ 100-unblock-vpn.sh"
    fi

    # S99 скрипты
    mkdir -p /opt/etc/init.d
    curl -sL -o "$INIT_UNBLOCK" "$RESOURCES_URL/scripts/S99unblock" && \
        chmod 755 "$INIT_UNBLOCK" && \
        echo "  ✅ S99unblock" || echo "  ❌ S99unblock"

    curl -sL -o "$INIT_WEB" "$RESOURCES_URL/scripts/S99web_ui" && \
        chmod 755 "$INIT_WEB" && \
        echo "  ✅ S99web_ui" || echo "  ❌ S99web_ui"

    echo ""
    echo "⏳ Загрузка шаблонов конфигураций..."
    mkdir -p "$TEMPLATES_DIR"
    for template in tor_template.torrc vless_template.json trojan_template.json shadowsocks_template.json; do
        curl -sL -o "$TEMPLATES_DIR/$template" "$RESOURCES_URL/templates/$template" && \
            echo "  ✅ $template" || echo "  ❌ $template"
    done

    echo ""
    echo "⏳ Настройка конфигураций..."
    mkdir -p "$TOR_TMP_DIR"
    
    # Конфиги - НЕ перезаписывать если существуют (сохраняем ключи)
    [ ! -f "$TOR_CONFIG" ] && cp "$TEMPLATES_DIR/tor_template.torrc" "$TOR_CONFIG" 2>/dev/null && echo "  ✅ Tor config created" || echo "  ℹ️ Tor config preserved"
    [ ! -f "$SHADOWSOCKS_CONFIG" ] && cp "$TEMPLATES_DIR/shadowsocks_template.json" "$SHADOWSOCKS_CONFIG" 2>/dev/null && echo "  ✅ Shadowsocks config created" || echo "  ℹ️ Shadowsocks config preserved"
    [ ! -f "$TROJAN_CONFIG" ] && cp "$TEMPLATES_DIR/trojan_template.json" "$TROJAN_CONFIG" 2>/dev/null && echo "  ✅ Trojan config created" || echo "  ℹ️ Trojan config preserved"
    [ ! -f "$VLESS_CONFIG" ] && cp "$TEMPLATES_DIR/vless_template.json" "$VLESS_CONFIG" 2>/dev/null && echo "  ✅ VLESS config created" || echo "  ℹ️ VLESS config preserved"

    # dnsmasq.conf - ВСЕГДА обновляем (содержит актуальные настройки)
    # NOTE: 127.0.0.1#40500 intentionally removed from main dnsmasq.conf
    # to prevent total DNS failure when proxy key expires.
    # Port 40500 is used ONLY for bypass domains via unblock.dnsmasq.
    curl -sL -o "$DNSMASQ_CONF" "$RESOURCES_URL/config/dnsmasq.conf" && \
        sed -i "s/192.168.1.1/${lanip}/g" "$DNSMASQ_CONF" && \
        echo "  ✅ dnsmasq.conf updated" || echo "  ❌ dnsmasq.conf"

    # Перезапустить dnsmasq после обновления конфига
    if [ -x "$INIT_DNSMASQ" ]; then
        "$INIT_DNSMASQ" restart >/dev/null 2>&1 && echo "  ✅ dnsmasq restarted" || echo "  ⚠️ dnsmasq restart failed"
    elif [ -x /opt/etc/init.d/S56dnsmasq ]; then
        /opt/etc/init.d/S56dnsmasq restart >/dev/null 2>&1 && echo "  ✅ dnsmasq restarted" || echo "  ⚠️ dnsmasq restart failed"
    fi

    # crontab - ВСЕГДА обновляем
    curl -sL -o "$CRONTAB" "$RESOURCES_URL/config/crontab" && \
        echo "  ✅ crontab updated" || echo "  ❌ crontab"

    echo ""
    echo "⏳ Загрузка списков обхода..."
    mkdir -p "$UNBLOCK_DIR"
    
    # Списки - НЕ перезаписывать если существуют (сохраняем пользовательские данные)
    [ ! -f "${UNBLOCK_DIR}vless.txt" ] && curl -sL -o "${UNBLOCK_DIR}vless.txt" "$RESOURCES_URL/lists/unblockvless.txt" && \
        echo "  ✅ unblockvless.txt created" || echo "  ℹ️ unblockvless.txt preserved"
    [ ! -f "${UNBLOCK_DIR}tor.txt" ] && curl -sL -o "${UNBLOCK_DIR}tor.txt" "$RESOURCES_URL/lists/unblocktor.txt" && \
        echo "  ✅ unblocktor.txt created" || echo "  ℹ️ unblocktor.txt preserved"

    # Пустые файлы - только создать если не существуют
    for file in "${UNBLOCK_DIR}shadowsocks.txt" "${UNBLOCK_DIR}hysteria2.txt" "${UNBLOCK_DIR}trojan.txt" "${UNBLOCK_DIR}vpn.txt"; do
        [ ! -f "$file" ] && touch "$file" && chmod 644 "$file" && echo "  ✅ $(basename $file) created"
    done
    echo "  ℹ️ Existing lists preserved"

    # AI domains DNS spoofing - загрузка и настройка
    echo ""
    echo "⏳ Настройка DNS-обхода AI-доменов..."
    mkdir -p /opt/etc/unblock
    curl -sL -o "/opt/etc/unblock/ai-domains.txt" "$RESOURCES_URL/lists/unblock-ai-domains.txt" && \
        echo "  ✅ AI domains list created" || echo "  ℹ️ AI domains list preserved"
    
    curl -sL -o "/opt/etc/unblock-ai.dnsmasq" "$RESOURCES_URL/config/unblock-ai.dnsmasq.template" && \
        sed -i "s/40500/${dnsovertlsport}/g" "/opt/etc/unblock-ai.dnsmasq" && \
        echo "  ✅ AI dnsmasq config created" || echo "  ❌ AI dnsmasq config"

    echo ""
    echo "⏳ Загрузка дополнительных файлов..."
    # keensnap.sh
    mkdir -p "$KEENSNAP_DIR"
    curl -sL -o "$SCRIPT_BU" "$RESOURCES_URL/scripts/keensnap.sh" && \
        chmod 755 "$SCRIPT_BU" && \
        echo "  ✅ keensnap.sh" || echo "  ❌ keensnap.sh"

    # Применение настроек
    echo ""
    echo "⏳ Применение настроек..."
    "$UNBLOCK_UPDATE" >/dev/null 2>&1 && echo "  ✅ unblock_update применён" || echo "  ⚠️ unblock_update"
    "$UNBLOCK_DNSMASQ" >/dev/null 2>&1 && echo "  ✅ unblock_dnsmasq применён" || echo "  ⚠️ unblock_dnsmasq"
    
    # Применение правил маршрутизации (iptables)
    echo ""
    echo "🔥 Применение правил маршрутизации (iptables)..."
    "$REDIRECT_SCRIPT" >/dev/null 2>&1 && echo "  ✅ 100-redirect.sh применён" || echo "  ⚠️ 100-redirect.sh"
    
    # Проверка правил
    if iptables-save -t nat 2>/dev/null | grep -q "1082"; then
        echo "  ✅ iptables правила: активны"
    else
        echo "  ⚠️  iptables правила: не применены"
    fi

    # Запуск веб-интерфейса
    echo ""
    echo "🚀 Запуск веб-интерфейса..."
    "$INIT_WEB" start
    sleep 2

    if pgrep -f "python.*app.py" >/dev/null; then
        echo "  ✅ Веб-интерфейс запущен"
    else
        echo "  ⚠️ Не удалось запустить веб-интерфейс"
    fi

    echo ""
    echo "✅ === Установка завершена! ==="
    echo ""
    echo "🌐 Откройте: http://${lanip}:8080"
    echo ""
    echo "📋 Следующие шаги:"
    echo "   1. Откройте веб-интерфейс"
    echo "   2. Добавьте VPN ключи (🔑 Ключи и мосты)"
    echo "   3. Добавьте списки обхода (📑 Списки обхода)"
    echo "   4. Включите DNS Override (⚙️ Сервис → ⁉️ DNS Override → ✅ ВКЛ)"
    echo ""
    exit 0
fi

# =============================================================================
# ОБНОВЛЕНИЕ (-update)
# =============================================================================
if [ "$1" = "-update" ]; then
    echo "=== Обновление flymybyte ==="

    opkg update >/dev/null 2>&1 && echo "✅ Пакеты обновлены" || echo "⚠️ Не удалось обновить пакеты"

    # Перезапуск веб-интерфейса
    "$INIT_WEB" restart
    sleep 2

    if pgrep -f "python.*app.py" >/dev/null; then
        echo "✅ Веб-интерфейс перезапущен"
    else
        echo "⚠️ Не удалось перезапустить веб-интерфейс"
    fi

    exit 0
fi

# =============================================================================
# СПРАВКА
# =============================================================================
if [ "$1" = "-help" ] || [ -z "$1" ]; then
    echo "Доступные аргументы:"
    echo "  -install  - установка flymybyte"
    echo "  -remove   - удаление flymybyte"
    echo "  -update   - обновление"
    echo "  -help     - эта справка"
fi
