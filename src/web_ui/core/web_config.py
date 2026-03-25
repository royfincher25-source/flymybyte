# =============================================================================
# WEB CONFIG FOR SCRIPT.SH
# =============================================================================
# Shell-совместимый конфиг для script.sh
# Генерируется web_ui при установке flymybyte
# =============================================================================

base_url = "https://raw.githubusercontent.com/royfincher25-source/flymybyte/master"
routerip = "192.168.1.1"

localportsh = 8388
dnsporttor = 5300
localporttor = 9080
localportvless = 10000
localporttrojan = 10001
dnsovertlsport = 10002
dnsoverhttpsport = 10003

unblock_dir = "/opt/etc/unblock/"
tor_config = "/opt/etc/tor/torrc"
shadowsocks_config = "/opt/etc/shadowsocks.json"
trojan_config = "/opt/etc/trojan/config.json"
vless_config = "/opt/etc/xray/config.json"
templates_dir = "/opt/etc/web_ui/templates/"
dnsmasq_conf = "/opt/etc/dnsmasq.conf"
crontab = "/opt/etc/crontab"
redirect_script = "/opt/etc/ndm/netfilter.d/100-redirect.sh"
vpn_script = "/opt/etc/ndm/ifstatechanged.d/100-unblock-vpn.sh"
ipset_script = "/opt/etc/ndm/fs.d/100-ipset.sh"
unblock_ipset = "/opt/bin/unblock_ipset.sh"
unblock_dnsmasq = "/opt/bin/unblock_dnsmasq.sh"
unblock_update = "/opt/bin/unblock_update.sh"
script_sh = "/opt/root/script.sh"
init_shadowsocks = "/opt/etc/init.d/S22shadowsocks"
init_trojan = "/opt/etc/init.d/S22trojan"
init_xray = "/opt/etc/init.d/S24xray"
init_tor = "/opt/etc/init.d/S35tor"
init_dnsmasq = "/opt/etc/init.d/S56dnsmasq"
init_unblock = "/opt/etc/init.d/S99unblock"
init_web = "/opt/etc/init.d/S99web_ui"
hosts_file = "/opt/etc/hosts"
web_ui_dir = "/opt/etc/web_ui"
