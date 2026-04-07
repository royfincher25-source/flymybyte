# FlyMyByte — Project Notes

## Environment

- **Device**: Keenetic KN-1212, 128MB RAM
- **OS**: Keenetic OS + Entware
- **Shell**: BusyBox ash
- **Architecture**: mipsel

## Unsupported Commands / Features

### DNS tools
- `dig` — NOT installed on router
- `nslookup host server port` — BusyBox nslookup doesn't support port argument
- `nc -u` / `nc -w` — BusyBox nc only supports `nc IP PORT` (TCP, no flags)
- `hexdump` — NOT available

### dnsmasq
- `filter-aaaa` — NOT supported in this dnsmasq build
- `filter-aaaa-on-local` — NOT supported in this dnsmasq build

### ipset / iptables
- `ipset restore` without dedup — fails on duplicate IPs (different domains → same IP). Always use `sort -u` before restore
- `grep -c` on non-existent ipset — returns empty string, not "0". Always use `${count:-0}`
- PREROUTING chain does NOT apply to loopback traffic — testing DNS via `nslookup host 127.0.0.1` bypasses PREROUTING

### Shell
- `&&` chaining — PowerShell on dev machine doesn't support it; on router BusyBox ash does, but be consistent
- Empty arithmetic — `$((TOTAL_ENTRIES + ))` causes syntax error. Always default: `${var:-0}`

## Supported Alternatives

| Need | Supported approach |
|------|-------------------|
| DNS query to specific port | `python3` with socket, or `nslookup` (port 53 only) |
| Raw DNS packet | `python3` with `struct` + `socket` |
| Check listening ports | `netstat -lnp \| grep PORT` |
| Test DNS from LAN | `nslookup host 192.168.1.1` from PC |
| DNS via dnsmasq:5353 | `nslookup host 192.168.1.1` (DNAT redirects to 5353) |
| Check ipset entries | `ipset list NAME \| grep -c` with `${count:-0}` |
| Check service status | `netstat -lnp \| grep PORT` or `ps \| grep NAME` |

## Logging Conventions

- Shell scripts: `/opt/var/log/<script_name>.log`
- Python modules: `/opt/var/log/web_ui.log`

## Safety

- Backup: `/opt/root/backup/update_backup_*.tar.gz`
- Emergency restore: `/opt/bin/emergency_restore.sh`
- Rollback: `/opt/bin/rollback.sh`
- Post-update test: `/opt/bin/test_bypass.sh`

## DNS Chain

```
Client → dnsmasq:5353 (via DNAT) → stubby:40500 (DNS-over-TLS) → ss-redir:1082 (proxy)
```

## Current Version

- Version: 2.0.4
- Branch: origin/master
