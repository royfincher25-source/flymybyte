#!/bin/sh
# 100-redirect.sh - Настройка перенаправления трафика
# Вызывается из системы Keenetic (с переменными $type и $table) или вручную

# Выход для IPv6
[ "$type" = "ip6tables" ] && exit 0

# Ensure all required ipsets exist
for ipset_name in unblocksh unblockhysteria2 unblocktor unblockvless unblocktroj; do
    ipset create "$ipset_name" hash:net -exist 2>/dev/null
done
echo "IPsets ready"

# При ручном запуске (без переменных) — выполняем настройку
if [ -z "$table" ]; then
    # Ручной запуск — применяем правила для NAT
    :
elif [ "$table" != "mangle" ] && [ "$table" != "nat" ]; then
    exit 0
fi

ip4t() {
    if ! iptables -C "$@" &>/dev/null; then
        iptables -A "$@" || exit 0
    fi
}

local_ip=$(ip -4 addr show br0 | awk '/inet /{print $2}' | cut -d/ -f1 | grep -E '^(192\.168\.|10\.|172\.(1[6-9]|2[0-9]|3[0-1])\.)' | head -n1)

RULES=$(iptables-save 2>/dev/null)
IPSETS=$(ipset list -n 2>/dev/null)

for protocol in udp tcp; do
    if [ -z "$(echo "$RULES" | grep "$protocol --dport 53 -j DNAT")" ]; then
        iptables -I PREROUTING -w -t nat -p "$protocol" --dport 53 -j DNAT --to "$local_ip"
    fi
done

add_redirect() {
    name="$1"
    port="$2"

    if echo "$IPSETS" | grep -q "^${name}$"; then
        [ -z "$(echo "$RULES" | grep "$name")" ] || return 0
    else
        ipset create "$name" hash:net -exist 2>/dev/null
    fi

    iptables -I PREROUTING -w -t nat -p tcp -m set --match-set "$name" dst -j REDIRECT --to-port "$port"
    iptables -I PREROUTING -w -t nat -p udp -m set --match-set "$name" dst -j REDIRECT --to-port "$port"
}

add_redirect unblocksh 1082
add_redirect unblocktor 9141
add_redirect unblockvless 10810
add_redirect unblocktroj 10829

TAG="100-redirect.sh"

if ls -d /opt/etc/unblock/vpn-*.txt >/dev/null 2>&1; then
    for vpn_file_name in /opt/etc/unblock/vpn*; do
        vpn_unblock_name=$(echo $vpn_file_name | awk -F '/' '{print $5}' | sed 's/.txt//')
        unblockvpn=$(echo unblock"$vpn_unblock_name")

        vpn_type=$(echo "$unblockvpn" | sed 's/-/ /g' | awk '{print $NF}')
        vpn_link_up=$(curl -s localhost:79/rci/show/interface/"$vpn_type"/link | tr -d '"')
        if [ "$vpn_link_up" = "up" ]; then
            vpn_type_lower=$(echo "$vpn_type" | tr [:upper:] [:lower:])
            get_vpn_fwmark_id=$(grep "$vpn_type_lower" /opt/etc/iproute2/rt_tables | awk '{print $1}')

            if [ -n "${get_vpn_fwmark_id}" ]; then
                vpn_table_id=$get_vpn_fwmark_id
            else
                break
            fi
            vpn_mark_id=$(echo 0xd"$vpn_table_id")

            if echo "$RULES" | grep -q "$unblockvpn"; then
                vpn_rule_ok=$(echo Правила для "$unblockvpn" уже есть.)
                echo "$vpn_rule_ok"
            else
                info_vpn_rule=$(echo ipset: "$unblockvpn", mark_id: "$vpn_mark_id")
                logger -t "$TAG" "$info_vpn_rule"

                ipset create "$unblockvpn" hash:net -exist 2>/dev/null

                fastnat=$(curl -s localhost:79/rci/show/version | grep ppe)
                software=$(curl -s localhost:79/rci/show/rc/p lobes | grep software -C1  | head -1 | awk '{print $2}' | tr -d ",")
                hardware=$(curl -s localhost:79/rci/show/rc/ppe | grep hardware -C1  | head -1 | awk '{print $2}' | tr -d ",")
                if [ -z "$fastnat" ] && [ "$software" = "false" ] && [ "$hardware" = "false" ]; then
                    info=$(echo "VPN: fastnat, swnat и hwnat ВЫКЛЮЧЕНЫ, правила добавлены")
                    logger -t "$TAG" "$info"
                    iptables -A PREROUTING -w -t mangle -p tcp -m set --match-set "$unblockvpn" dst -j MARK --set-mark "$vpn_mark_id"
                    iptables -A PREROUTING -w -t mangle -p udp -m set --match-set "$unblockvpn" dst -j MARK --set-mark "$vpn_mark_id"
                else
                    info=$(echo "VPN: fastnat, swnat и hwnat ВКЛЮЧЕНЫ, правила добавлены")
                    logger -t "$TAG" "$info"
                    iptables -A PREROUTING -w -t mangle -m conntrack --ctstate NEW -m set --match-set "$unblockvpn" dst -j CONNMARK --set-mark "$vpn_mark_id"
                    iptables -A PREROUTING -w -t mangle -j CONNMARK --restore-mark
                fi
            fi
        fi
    done
fi

# =============================================================================
# ПРИМЕНЕНИЕ ПРАВИЛ ПРИ РУЧНОМ ЗАПУСКЕ
# =============================================================================
# Если скрипт запущен вручную (без переменных $type и $table),
# применяем правила перенаправления трафика

if [ -z "$table" ]; then
    echo "Применение правил перенаправления трафика..."
    
    # Получение локального IP
    local_ip=$(ip -4 addr show br0 | awk '/inet /{print $2}' | cut -d/ -f1 | grep -E '^(192\.168\.|10\.|172\.(1[6-9]|2[0-9]|3[0-1])\.)' | head -n1)
    
    # Проверка ipset (IPv4)
    for ipset_name in unblocksh unblocktor unblockvless unblocktroj; do
        if ipset list "$ipset_name" -n 2>/dev/null | grep -q "^${ipset_name}$"; then
            count=$(ipset list "$ipset_name" 2>/dev/null | grep -c "^[0-9]" || echo 0)
            echo "  ✅ $ipset_name: $count записей"
        else
            echo "  ⚠️  $ipset_name: не создан"
        fi
    done
    
    # Проверка ipset (IPv6)
    for ipset_name in unblocksh6 unblocktor6 unblockvless6 unblocktroj6; do
        if ipset list "$ipset_name" -n 2>/dev/null | grep -q "^${ipset_name}$"; then
            count=$(ipset list "$ipset_name" 2>/dev/null | grep -c "^[0-9a-f]" || echo 0)
            echo "  ✅ $ipset_name: $count записей"
        else
            echo "  ⚠️  $ipset_name: не создан"
        fi
    done
    
    # Применение правил для Shadowsocks
    echo "  → Добавление правил для Shadowsocks (порт 1082)..."
    iptables -I PREROUTING -w -t nat -p tcp -m set --match-set unblocksh dst -j REDIRECT --to-ports 1082 2>/dev/null && \
        echo "    ✅ TCP правило добавлено" || echo "    ⚠️  TCP правило не добавлено"
    iptables -I PREROUTING -w -t nat -p udp -m set --match-set unblocksh dst -j REDIRECT --to-ports 1082 2>/dev/null && \
        echo "    ✅ UDP правило добавлено" || echo "    ⚠️  UDP правило не добавлено"
    
    # Применение правил для Tor
    echo "  → Добавление правил для Tor (порт 9141)..."
    iptables -I PREROUTING -w -t nat -p tcp -m set --match-set unblocktor dst -j REDIRECT --to-ports 9141 2>/dev/null && \
        echo "    ✅ TCP правило добавлено" || echo "    ⚠️  TCP правило не добавлено"
    iptables -I PREROUTING -w -t nat -p udp -m set --match-set unblocktor dst -j REDIRECT --to-ports 9141 2>/dev/null && \
        echo "    ✅ UDP правило добавлено" || echo "    ⚠️  UDP правило не добавлено"
    
    # Применение правил для VLESS
    echo "  → Добавление правил для VLESS (порт 10810)..."
    iptables -I PREROUTING -w -t nat -p tcp -m set --match-set unblockvless dst -j REDIRECT --to-ports 10810 2>/dev/null && \
        echo "    ✅ TCP правило добавлено" || echo "    ⚠️  TCP правило не добавлено"
    iptables -I PREROUTING -w -t nat -p udp -m set --match-set unblockvless dst -j REDIRECT --to-ports 10810 2>/dev/null && \
        echo "    ✅ UDP правило добавлено" || echo "    ⚠️  UDP правило не добавлено"
    
    # Применение правил для Trojan
    echo "  → Добавление правил для Trojan (порт 10829)..."
    iptables -I PREROUTING -w -t nat -p tcp -m set --match-set unblocktroj dst -j REDIRECT --to-ports 10829 2>/dev/null && \
        echo "    ✅ TCP правило добавлено" || echo "    ⚠️  TCP правило не добавлено"
    iptables -I PREROUTING -w -t nat -p udp -m set --match-set unblocktroj dst -j REDIRECT --to-ports 10829 2>/dev/null && \
        echo "    ✅ UDP правило добавлено" || echo "    ⚠️  UDP правило не добавлено"
    
    # =============================================================================
    # IPv6 ПРАВИЛА
    # =============================================================================
    echo ""
    echo "🔥 Применение IPv6 правил..."
    
    # Создание IPv6 ipset
    ipset create unblocksh6 hash:net family inet6 -exist 2>/dev/null
    ipset create unblocktor6 hash:net family inet6 -exist 2>/dev/null
    ipset create unblockvless6 hash:net family inet6 -exist 2>/dev/null
    ipset create unblocktroj6 hash:net family inet6 -exist 2>/dev/null
    
    # Добавление IPv6 диапазонов для популярных сервисов
    ipset add unblocksh6 2a00:1450::/32 2>/dev/null  # Google/YouTube
    ipset add unblocksh6 2600:1900::/32 2>/dev/null  # Google Cloud
    ipset add unblocksh6 2a00:1450:4001::/48 2>/dev/null
    ipset add unblocksh6 2a00:1450:4010::/48 2>/dev/null
    
    # IPv6 правила для Shadowsocks
    ip6tables -I PREROUTING -w -t nat -p tcp -m set --match-set unblocksh6 dst -j REDIRECT --to-ports 1082 2>/dev/null && \
        echo "  ✅ IPv6 Shadowsocks правила добавлены" || echo "  ⚠️  IPv6 Shadowsocks правила не добавлены"
    ip6tables -I PREROUTING -w -t nat -p udp -m set --match-set unblocksh6 dst -j REDIRECT --to-ports 1082 2>/dev/null
    
    echo "✅ IPv6 правила применены"
    
    echo "✅ Правила маршрутизации применены"
fi

exit 0
