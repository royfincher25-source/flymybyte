#!/bin/sh
# unblock_ipset.sh - Optimized version with parallel DNS resolution
# Optimized for KN-1212 (128MB RAM)

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
        if [ -n "$line" ] && echo "$line" | grep -qv '^[[:space:]]*#'; then
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

# Process files in parallel
i=0

# Process predefined files
for entry in "/opt/etc/unblock/shadowsocks.txt:unblocksh" "/opt/etc/unblock/hysteria2.txt:unblockhysteria2" "/opt/etc/unblock/tor.txt:unblocktor" "/opt/etc/unblock/vless.txt:unblockvless" "/opt/etc/unblock/trojan.txt:unblocktroj"; do
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

# Add and process VPN files
for vpn_file in /opt/etc/unblock/vpn-*.txt; do
    if [ -f "$vpn_file" ]; then
        vpn_name=$(basename "$vpn_file" .txt)
        setname="unblock$vpn_name"
        
        # Ensure ipset exists
        ipset create "$setname" hash:ip 2>/dev/null || true
        
        # Run in background
        process_file "$vpn_file" "$setname" $i &
        i=$((i + 1))
        
        # Limit concurrent processes to thread count
        if [ $i -ge $THREAD_COUNT ]; then
            wait
            i=0
        fi
    fi
done

# Wait for all background jobs
wait

echo "✅ IPSET заполнен" | tee -a "$LOGFILE"