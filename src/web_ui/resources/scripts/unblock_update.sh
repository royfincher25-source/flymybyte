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
