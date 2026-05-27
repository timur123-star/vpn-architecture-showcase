#!/bin/bash
# VPN-only hardening on FR. Does NOT touch SSH keys or passwords.
set -euo pipefail
RU_IP="<RU_SERVER_IP>"
log() { echo "[$(date -Iseconds)] $*"; }

export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq wireguard-tools sqlite3 >/dev/null

log "sysctl"
grep -q '99-vpn-pro' /etc/sysctl.d/99-vpn-pro.conf 2>/dev/null || cat >>/etc/sysctl.d/99-vpn-pro.conf <<'EOF'
net.ipv4.ip_forward = 1
net.ipv4.conf.all.rp_filter = 0
net.ipv4.conf.default.rp_filter = 0
EOF
sysctl --system >/dev/null 2>&1 || true

log "disable failed kernel wgwarp (wireproxy active)"
systemctl disable --now wg-quick@wgwarp.service 2>/dev/null || true
systemctl mask wg-quick@wgwarp.service 2>/dev/null || true

log "WG on UDP/443 for RU"
RU_PUB="${1:-}"
[ -z "$RU_PUB" ] && RU_PUB=$(cat /etc/wireguard/ru-peer.pub 2>/dev/null)
[ -z "$RU_PUB" ] && { log "no RU pubkey"; exit 1; }

if [ ! -f /etc/wireguard/wg-ru-443.key ]; then
  wg genkey | tee /etc/wireguard/wg-ru-443.key | wg pubkey > /etc/wireguard/wg-ru-443.pub
  chmod 600 /etc/wireguard/wg-ru-443.key
fi
FR_PRIV=$(cat /etc/wireguard/wg-ru-443.key)
FR_PUB443=$(cat /etc/wireguard/wg-ru-443.pub)
echo "$FR_PUB443" > /etc/wireguard/fr-peer-443.pub.export

cat >/etc/wireguard/wg-ru-443.conf <<EOF
[Interface]
Address = <FR_WG_IP>/24
ListenPort = 443
PrivateKey = $FR_PRIV
MTU = 1280
PostUp = iptables -t nat -A POSTROUTING -s <WG_443_NET>/24 -o eth0 -j MASQUERADE; iptables -A FORWARD -i wg-ru-443 -j ACCEPT; iptables -A FORWARD -o wg-ru-443 -m state --state RELATED,ESTABLISHED -j ACCEPT
PreDown = iptables -t nat -D POSTROUTING -s <WG_443_NET>/24 -o eth0 -j MASQUERADE 2>/dev/null; iptables -D FORWARD -i wg-ru-443 -j ACCEPT 2>/dev/null; iptables -D FORWARD -o wg-ru-443 -m state --state RELATED,ESTABLISHED -j ACCEPT 2>/dev/null

[Peer]
PublicKey = $RU_PUB
AllowedIPs = <RU_WG_443_IP>/32
EOF
chmod 600 /etc/wireguard/wg-ru-443.conf

cat >/etc/systemd/system/wg-ru-443.service <<'UNIT'
[Unit]
Description=WG server UDP/443 for RU whitelist path
After=network-online.target
[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/usr/bin/wg-quick up wg-ru-443
ExecStop=/usr/bin/wg-quick down wg-ru-443
[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl enable wg-ru-443.service
systemctl restart wg-ru-443.service 2>/dev/null || true

ufw allow 443/udp comment 'WG whitelist' 2>/dev/null || true
ufw reload 2>/dev/null || true

log "bridge client"
python3 /root/harden-fr-bridge.py 2>/dev/null || true

log "backup cron"
mkdir -p /root/backups/x-ui
cat >/etc/cron.d/x-ui-backup <<'EOF'
23 3 * * * root cp -a /etc/x-ui/x-ui.db /root/backups/x-ui/x-ui.db.$(date +\%Y\%m\%d) 2>/dev/null; find /root/backups/x-ui -mtime +14 -delete 2>/dev/null
EOF

log "restart x-ui"
x-ui restart 2>/dev/null || systemctl restart x-ui
echo "FR_WG443_PUB=$FR_PUB443"
log "done"
