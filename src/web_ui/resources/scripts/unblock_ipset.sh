#!/bin/sh
# unblock_ipset.sh - Optimized version with parallel DNS resolution
# Optimized for KN-1212 (128MB RAM)

mkdir -p /opt/var/log
LOGFILE="/opt/var/log/unblock_ipset.log"
TAG="unblock_ipset"

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') [$TAG] $1" >> "$LOGFILE"
}

log_error() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') [$TAG] ERROR: $1" >> "$LOGFILE"
}

log "=== Script started ==="

# Function to check available memory
get_free_memory() {
    free_kB=$(grep MemFree /proc/meminfo | awk '{print $2}')
    free_MB=$((free_kB / 1024))
    echo $free_MB
}

# Function to determine thread count based on memory
get_thread_count() {
    free_MB=$(get_free_memory)
    
    if [ $free_MB -lt 20 ]; then
        echo 1
    elif [ $free_MB -lt 50 ]; then
        echo 2
    elif [ $free_MB -lt 100 ]; then
        echo 3
    else
        echo 4
    fi
}

# Get thread count
THREAD_COUNT=$(get_thread_count)
FREE_MEM=$(get_free_memory)
log "Memory: ${FREE_MEM}MB free, using $THREAD_COUNT threads"

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
log "Checking DNS availability..."
if ! check_dns_ready; then
    log_error "DNS not available after 30 seconds"
    echo "ERROR: DNS not available after 30 seconds" | tee -a "$LOGFILE"
    exit 1
fi
log "DNS is available"

# Function to process a single file
process_file() {
    local file="$1"
    local setname="$2"
    local thread_id="$3"
    local thread_log="/tmp/ipset_thread_${thread_id}.log"
    
    echo "$(date '+%Y-%m-%d %H:%M:%S') [thread-$thread_id] Processing: $file -> $setname" >> "$LOGFILE"
    
    if [ ! -f "$file" ]; then
        log_error "File not found: $file (thread $thread_id)"
        return
    fi
    
    # Count lines in source file
    line_count=$(wc -l < "$file")
    echo "$(date '+%Y-%m-%d %H:%M:%S') [thread-$thread_id] File has $line_count lines" >> "$LOGFILE"
    
    # Create temp file for ipset commands
    temp_file="/tmp/ipset_commands_$thread_id.txt"
    > "$temp_file"
    
    local resolved=0
    local direct_ip=0
    local skipped=0
    
    # Process file line by line
    while read -r line || [ -n "$line" ]; do
        [ -z "$line" ] && { skipped=$((skipped + 1)); continue; }
        [ "${line#?}" = "#" ] && { skipped=$((skipped + 1)); continue; }
        
        # Check for CIDR
        cidr=$(echo "$line" | grep -Eo '[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}/[0-9]{1,2}')
        if [ -n "$cidr" ]; then
            echo "add $setname $cidr" >> "$temp_file"
            direct_ip=$((direct_ip + 1))
            continue
        fi
        
        # Check for IP range
        range=$(echo "$line" | grep -Eo '[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}-[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}')
        if [ -n "$range" ]; then
            echo "add $setname $range" >> "$temp_file"
            direct_ip=$((direct_ip + 1))
            continue
        fi
        
        # Check for single IP
        addr=$(echo "$line" | grep -Eo '[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}')
        if [ -n "$addr" ]; then
            echo "add $setname $addr" >> "$temp_file"
            direct_ip=$((direct_ip + 1))
            continue
        fi
        
        # Resolve domain
        if [ -n "$line" ] && echo "$line" | grep -qv '^[[:space:]]*#'; then
            ips=$(nslookup "$line" 8.8.8.8 2>/dev/null | grep -oE '[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}' | grep -v '8\.8\.8\.8')
            if [ -n "$ips" ]; then
                for ip in $ips; do
                    echo "add $setname $ip" >> "$temp_file"
                done
                resolved=$((resolved + 1))
            else
                echo "$(date '+%Y-%m-%d %H:%M:%S') [thread-$thread_id] WARNING: Could not resolve $line" >> "$LOGFILE"
            fi
        fi
    done < "$file"
    
    # Apply ipset commands if file has content
    if [ -s "$temp_file" ]; then
        # Deduplicate to avoid "already added" errors
        dedup_file="${temp_file}.dedup"
        sort -u "$temp_file" > "$dedup_file"
        cmd_count=$(wc -l < "$dedup_file")
        # Flush before restore to start clean
        ipset flush "$setname" 2>/dev/null
        # Use restore; ignore errors for individual entries (partial success is OK)
        ipset restore < "$dedup_file" 2>> "$thread_log" || true
        actual_count=$(ipset list "$setname" 2>/dev/null | tail -n +7 | grep -c "^[0-9]" 2>/dev/null)
        actual_count=${actual_count:-0}
        echo "$(date '+%Y-%m-%d %H:%M:%S') [thread-$thread_id] Applied $actual_count/$cmd_count entries to $setname (resolved=$resolved, direct=$direct_ip, skipped=$skipped)" >> "$LOGFILE"
        rm -f "$dedup_file"
    else
        echo "$(date '+%Y-%m-%d %H:%M:%S') [thread-$thread_id] No entries to add for $setname" >> "$LOGFILE"
    fi
    
    # Cleanup
    rm -f "$temp_file" "$thread_log"
}

# Process files in parallel
i=0

log "Processing predefined files..."

# Map ipset names to service check commands
# Only populate ipset if the corresponding service is running
# OPTIMIZATION: Check /proc instead of netstat/ps to reduce CPU usage
check_service() {
    local setname="$1"
    local pattern=""
    
    case "$setname" in
        unblocksh)        pattern="ss-redir" ;;
        unblockhysteria2) pattern="hysteria" ;;
        unblocktor)       pattern="tor" ;;
        unblockvless)     pattern="xray" ;;
        unblocktroj)      pattern="trojan" ;;
        *)                return 0 ;;
    esac
    
    # Check /proc for process cmdline
    for pid_dir in /proc/[0-9]*; do
        if [ -r "$pid_dir/cmdline" ] && grep -q "$pattern" "$pid_dir/cmdline" 2>/dev/null; then
            return 0  # Service is running
        fi
    done
    return 1  # Service not running
}

# Process predefined files
for entry in "/opt/etc/unblock/shadowsocks.txt:unblocksh" "/opt/etc/unblock/hysteria2.txt:unblockhysteria2" "/opt/etc/unblock/tor.txt:unblocktor" "/opt/etc/unblock/vless.txt:unblockvless" "/opt/etc/unblock/trojan.txt:unblocktroj"; do
    file=$(echo "$entry" | cut -d: -f1)
    setname=$(echo "$entry" | cut -d: -f2)

    # Ensure ipset exists
    ipset create "$setname" hash:ip 2>/dev/null && log "  Created ipset: $setname" || log "  Ipset exists: $setname"

    # Check if corresponding service is running
    if ! check_service "$setname"; then
        log "  SKIP: $setname (service not running) - flushing ipset"
        ipset flush "$setname" 2>/dev/null
        continue
    fi

    # Run in background
    process_file "$file" "$setname" $i &
    log "  Started thread $i: $file -> $setname"
    i=$((i + 1))

    # Limit concurrent processes to thread count
    if [ $i -ge $THREAD_COUNT ]; then
        log "  Waiting for batch of $THREAD_COUNT threads..."
        wait
        i=0
    fi
done

# Add and process VPN files
if ls /opt/etc/unblock/vpn-*.txt >/dev/null 2>&1; then
    log "Processing VPN files..."
    for vpn_file in /opt/etc/unblock/vpn-*.txt; do
        if [ -f "$vpn_file" ]; then
            vpn_name=$(basename "$vpn_file" .txt)
            setname="unblock$vpn_name"
            
            ipset create "$setname" hash:ip 2>/dev/null && log "  Created ipset: $setname" || log "  Ipset exists: $setname"
            
            process_file "$vpn_file" "$setname" $i &
            log "  Started thread $i: $vpn_file -> $setname"
            i=$((i + 1))
            
            if [ $i -ge $THREAD_COUNT ]; then
                log "  Waiting for batch of $THREAD_COUNT threads..."
                wait
                i=0
            fi
        fi
    done
else
    log "No VPN files found"
fi

# Wait for all background jobs
log "Waiting for all threads to complete..."
wait

# Summary
log "=== Summary ==="
for setname in unblocksh unblockhysteria2 unblocktor unblockvless unblocktroj; do
    if ipset list "$setname" -n 2>/dev/null | grep -q "^${setname}$"; then
        count=$(ipset list "$setname" 2>/dev/null | tail -n +7 | grep -c "^[0-9]")
        count=${count:-0}
        log "  $setname: $count entries"
    else
        log "  $setname: NOT FOUND"
    fi
done

# Check VPN ipsets
for vpn_file in /opt/etc/unblock/vpn-*.txt; do
    if [ -f "$vpn_file" ]; then
        vpn_name=$(basename "$vpn_file" .txt)
        setname="unblock$vpn_name"
        if ipset list "$setname" -n 2>/dev/null | grep -q "^${setname}$"; then
            count=$(ipset list "$setname" 2>/dev/null | tail -n +7 | grep -c "^[0-9]")
            count=${count:-0}
            log "  $setname: $count entries"
        else
            log "  $setname: NOT FOUND"
        fi
    fi
done

log "=== Script completed ==="
echo "✅ IPSET заполнен" | tee -a "$LOGFILE"
