#!/bin/sh
# 100-redirect.sh - Настройка перенаправления трафика
# Вызывается из системы Keenetic (с переменными $type и $table) или вручную

mkdir -p /opt/var/log
LOGFILE="/opt/var/log/100-redirect.log"
TAG="100-redirect.sh"

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') [$TAG] $1" >> "$LOGFILE"
}

log_error() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') [$TAG] ERROR: $1" >> "$LOGFILE"
}

log "=== Script started (type=$type, table=$table) ==="

# Выход для IPv6
[ "$type" = "ip6tables" ] && { log "IPv6 call, exiting"; exit 0; }

# Ensure all required ipsets exist
log "Ensuring base ipsets exist..."
for ipset_name in unblocksh unblockhysteria2 unblocktor unblockvless unblocktroj; do
    if ipset create "$ipset_name" hash:net -exist 2>/dev/null; then
        log "  Created ipset: $ipset_name"
    else
        log "  Ipset already exists: $ipset_name"
    fi
done
log "IPsets ready"

# При ручном запуске (без переменных) — выполняем настройку
if [ -z "$table" ]; then
    log "Manual invocation — will apply NAT rules"
elif [ "$table" != "mangle" ] && [ "$table" != "nat" ]; then
    log "Table '$table' not supported, exiting"
    exit 0
fi

ip4t() {
    if ! iptables -C "$@" &>/dev/null; then
        iptables -A "$@" || { log_error "iptables -A $* failed"; exit 0; }
    fi
}

# Detect local IP
local_ip=$(ip -4 addr show br0 | awk '/inet /{print $2}' | cut -d/ -f1 | grep -E '^(192\.168\.|10\.|172\.(1[6-9]|2[0-9]|3[0-1])\.)' | head -n1)
if [ -z "$local_ip" ]; then
    log_error "Could not detect local IP on br0"
    local_ip="192.168.1.1"
    log "  Using fallback IP: $local_ip"
else
    log "Detected local IP: $local_ip"
fi

# Capture current iptables and ipset state
RULES=$(iptables-save 2>/dev/null)
IPSETS=$(ipset list -n 2>/dev/null)
log "Captured iptables rules ($(echo "$RULES" | wc -l) lines) and ipsets ($(echo "$IPSETS" | wc -l) sets)"

# DNS redirect to dnsmasq:5353 (only if dnsmasq is listening on 5353)
# OPTIMIZATION: Check /proc for dnsmasq instead of netstat
log "Checking if dnsmasq is running..."
DNS_REDIRECT_OK=false
dnsmasq_running=false

for pid_dir in /proc/[0-9]*; do
    if [ -r "$pid_dir/cmdline" ] && grep -q "dnsmasq" "$pid_dir/cmdline" 2>/dev/null; then
        dnsmasq_running=true
        break
    fi
done

if [ "$dnsmasq_running" = "true" ]; then
    log "  dnsmasq process found, enabling DNS redirect"
    DNS_REDIRECT_OK=true
else
    # Try starting dnsmasq and wait briefly
    log "  dnsmasq NOT running, attempting to start..."
    /opt/etc/init.d/S56dnsmasq restart >> "$LOGFILE" 2>&1
    sleep 2
    
    for pid_dir in /proc/[0-9]*; do
        if [ -r "$pid_dir/cmdline" ] && grep -q "dnsmasq" "$pid_dir/cmdline" 2>/dev/null; then
            dnsmasq_running=true
            break
        fi
    done
    
    if [ "$dnsmasq_running" = "true" ]; then
        log "  dnsmasq started successfully, enabling DNS redirect"
        DNS_REDIRECT_OK=true
    else
        log_error "  dnsmasq still not running, SKIPPING DNS redirect to prevent internet loss"
    fi
fi

if [ "$DNS_REDIRECT_OK" = "true" ]; then
    for protocol in udp tcp; do
        if [ -z "$(echo "$RULES" | grep "$protocol --dport 53 -j DNAT")" ]; then
            log "Adding DNS redirect: $protocol dport 53 -> $local_ip:5353"
            if iptables -I PREROUTING -w -t nat -p "$protocol" --dport 53 -j DNAT --to "$local_ip:5353" 2>&1; then
                log "  DNS redirect added for $protocol"
            else
                log_error "Failed to add DNS redirect for $protocol"
            fi
        else
            log "DNS redirect for $protocol already exists"
        fi
    done
else
    log "WARNING: DNS redirect NOT applied — dnsmasq:5353 not available"
fi

# Check if a service is running for a given ipset
# OPTIMIZATION: Check /proc directly instead of netstat/ps to reduce CPU usage
service_running() {
    local name="$1"
    local port="$2"
    local pattern=""
    
    case "$name" in
        unblocksh)        pattern="ss-redir" ;;
        unblockhysteria2) pattern="hysteria" ;;
        unblocktor)       pattern="tor" ;;
        unblockvless)     pattern="xray" ;;
        unblocktroj)      pattern="trojan" ;;
        *)                return 1 ;;
    esac
    
    # Check /proc for process cmdline
    for pid_dir in /proc/[0-9]*; do
        pid="${pid_dir##*/}"
        if [ -r "$pid_dir/cmdline" ] && grep -q "$pattern" "$pid_dir/cmdline" 2>/dev/null; then
            return 0
        fi
    done
    return 1
}

add_redirect() {
    name="$1"
    port="$2"

    log "Processing redirect: $name -> port $port"

    # Skip if service is not running
    if ! service_running "$name" "$port"; then
        log "  SKIP: service for $name not running on port $port"
        # Flush ipset to avoid stale entries redirecting traffic
        ipset flush "$name" 2>/dev/null && log "  Flushed $name"
        return 0
    fi

    if echo "$IPSETS" | grep -q "^${name}$"; then
        log "  Ipset $name exists"
        if [ -z "$(echo "$RULES" | grep "$name")" ]; then
            log "  No iptables rule for $name, adding..."
        else
            log "  Rule for $name already exists, skipping"
            return 0
        fi
    else
        log "  Ipset $name NOT found, creating..."
        ipset create "$name" hash:net -exist 2>/dev/null || log_error "Failed to create ipset $name"
    fi

    iptables -I PREROUTING -w -t nat -p tcp -m set --match-set "$name" dst -j REDIRECT --to-port "$port" 2>&1 && \
        log "  TCP redirect added for $name -> $port" || log_error "Failed to add TCP redirect for $name"
    iptables -I PREROUTING -w -t nat -p udp -m set --match-set "$name" dst -j REDIRECT --to-port "$port" 2>&1 && \
        log "  UDP redirect added for $name -> $port" || log_error "Failed to add UDP redirect for $name"
}

add_redirect unblocksh 1082
add_redirect unblockhysteria2 0
add_redirect unblocktor 9141
add_redirect unblockvless 10810
add_redirect unblocktroj 10829

# VPN-specific routing
if ls -d /opt/etc/unblock/vpn-*.txt >/dev/null 2>&1; then
    log "Processing VPN files..."
    for vpn_file_name in /opt/etc/unblock/vpn*; do
        vpn_unblock_name=$(echo $vpn_file_name | awk -F '/' '{print $5}' | sed 's/.txt//')
        unblockvpn=$(echo unblock"$vpn_unblock_name")

        vpn_type=$(echo "$unblockvpn" | sed 's/-/ /g' | awk '{print $NF}')
        vpn_link_up=$(curl -s localhost:79/rci/show/interface/"$vpn_type"/link | tr -d '"')
        if [ "$vpn_link_up" = "up" ]; then
            log "  VPN $vpn_type link is UP"
            vpn_type_lower=$(echo "$vpn_type" | tr [:upper:] [:lower:])
            get_vpn_fwmark_id=$(grep "$vpn_type_lower" /opt/etc/iproute2/rt_tables | awk '{print $1}')

            if [ -n "${get_vpn_fwmark_id}" ]; then
                vpn_table_id=$get_vpn_fwmark_id
            else
                log_error "  No fwmark for $vpn_type_lower in rt_tables"
                break
            fi
            vpn_mark_id=$(echo 0xd"$vpn_table_id")

            if echo "$RULES" | grep -q "$unblockvpn"; then
                log "  Rules for $unblockvpn already exist"
            else
                log "  Adding rules for $unblockvpn (mark=$vpn_mark_id)"

                ipset create "$unblockvpn" hash:net -exist 2>/dev/null

                fastnat=$(curl -s localhost:79/rci/show/version | grep ppe)
                software=$(curl -s localhost:79/rci/show/rc/p lobes | grep software -C1  | head -1 | awk '{print $2}' | tr -d ",")
                hardware=$(curl -s localhost:79/rci/show/rc/ppe | grep hardware -C1  | head -1 | awk '{print $2}' | tr -d ",")
                if [ -z "$fastnat" ] && [ "$software" = "false" ] && [ "$hardware" = "false" ]; then
                    log "  VPN: fastnat/swnat/hwnat DISABLED, using MARK rules"
                    iptables -A PREROUTING -w -t mangle -p tcp -m set --match-set "$unblockvpn" dst -j MARK --set-mark "$vpn_mark_id" 2>&1 && \
                        log "    MARK rule added (tcp)" || log_error "    Failed to add MARK rule (tcp)"
                    iptables -A PREROUTING -w -t mangle -p udp -m set --match-set "$unblockvpn" dst -j MARK --set-mark "$vpn_mark_id" 2>&1 && \
                        log "    MARK rule added (udp)" || log_error "    Failed to add MARK rule (udp)"
                else
                    log "  VPN: fastnat/swnat/hwnat ENABLED, using CONNMARK rules"
                    iptables -A PREROUTING -w -t mangle -m conntrack --ctstate NEW -m set --match-set "$unblockvpn" dst -j CONNMARK --set-mark "$vpn_mark_id" 2>&1 && \
                        log "    CONNMARK rule added" || log_error "    Failed to add CONNMARK rule"
                    iptables -A PREROUTING -w -t mangle -j CONNMARK --restore-mark 2>&1 && \
                        log "    CONNMARK restore added" || log_error "    Failed to add CONNMARK restore"
                fi
            fi
        else
            log "  VPN $vpn_type link is DOWN, skipping"
        fi
    done
else
    log "No VPN files found in /opt/etc/unblock/"
fi

log "=== Script completed ==="
exit 0
