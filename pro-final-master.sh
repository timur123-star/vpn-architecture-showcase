#!/bin/bash
set -euo pipefail
cd /root
sed -i 's/\r$//' *.sh *.py 2>/dev/null || true

echo "========== PRO FINAL MASTER =========="
# sysctl / BBR
[ -f /etc/sysctl.d/99-vpn-pro.conf ] || cat >/etc/sysctl.d/99-vpn-pro.conf <<'EOF'
net.ipv4.ip_forward = 1
net.ipv4.tcp_congestion_control = bbr
net.core.default_qdisc = fq
net.ipv4.conf.all.rp_filter = 0
net.ipv4.conf.default.rp_filter = 0
EOF
sysctl --system >/dev/null 2>&1 || true

ufw allow 80/tcp comment 'subscription' 2>/dev/null || true
ufw allow 443/tcp 8442/tcp 8443/udp 51820/udp 2>/dev/null || true
ufw reload 2>/dev/null || true

# backup cron
mkdir -p /root/backups/x-ui
[ -f /etc/cron.d/x-ui-backup ] || echo '17 3 * * * root cp -a /etc/x-ui/x-ui.db /root/backups/x-ui/x-ui.db.$(date +\%Y\%m\%d); find /root/backups/x-ui -mtime +14 -delete' >/etc/cron.d/x-ui-backup

systemctl enable wg-fr wg-fr-443 x-ui-sub-proxy 2>/dev/null || true
systemctl restart wg-fr wg-fr-443 2>/dev/null || true

# sub on :80
cp -f /root/sub-proxy-standalone.py /root/sub-proxy.py 2>/dev/null || true
python3 /root/setup-sub-port80.py 2>/dev/null || true
systemctl restart x-ui-sub-proxy

python3 /root/fix-hiddify-connect.py 2>/dev/null || true
python3 /root/fix-routing-paris.py
python3 /root/sync-fr-paris.py || true

x-ui restart
sleep 5
systemctl restart x-ui-sub-proxy

# watchdog
[ -f /root/vpn-watchdog.sh ] && chmod +x /root/vpn-watchdog.sh
[ -f /root/vpn-watchdog.sh ] && grep -q vpn-watchdog /etc/cron.d/vpn-watchdog 2>/dev/null || \
  echo '*/5 * * * * root /root/vpn-watchdog.sh >> /var/log/vpn-watchdog.log 2>&1' >/etc/cron.d/vpn-watchdog 2>/dev/null || true

bash /root/test-reality.sh && echo "Reality OK"

# FR over WG
export SSHPASS="${SSHPASS:?}"
export SSHPASS
if [ -n "${SSHPASS:-}" ]; then
  sshpass -e ssh -o StrictHostKeyChecking=no -o ConnectTimeout=20 root@<FR_WG_IP> 'bash -s' <<'FR' || echo "FR SSH via WG failed"
set -uo pipefail
systemctl enable x-ui wg-ru wg-ru-443 wireproxy 2>/dev/null || true
systemctl restart wireproxy wg-ru wg-ru-443 2>/dev/null || true
for s in x-ui wireproxy wg-ru; do systemctl is-active --quiet $s && echo "OK $s" || echo "FAIL $s"; done
/usr/local/x-ui/bin/xray-linux-amd64 -test -config /usr/local/x-ui/bin/config.json 2>&1 | tail -1
ss -tln | grep -q ':40000' && echo "OK wireproxy 40000" || echo "FAIL wireproxy port"
curl -s --max-time 8 --socks5-hostname 127.0.0.1:40000 https://ipinfo.io/country 2>/dev/null || echo "WARP check skip"
wg show wg-ru 2>/dev/null | grep handshake || true
FR
fi

python3 /root/pro-final-audit.py
echo "========== DONE =========="
