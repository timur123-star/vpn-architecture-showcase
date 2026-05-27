#!/bin/bash
# VPN-only hardening on RU. Does NOT touch SSH keys or passwords.
set -euo pipefail
FR_IP="<FR_SERVER_IP>"
log() { echo "[$(date -Iseconds)] $*"; }

export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq wireguard-tools sqlite3 curl jq mtr-tiny >/dev/null

log "sysctl"
cat >/etc/sysctl.d/99-vpn-pro.conf <<'EOF'
net.ipv4.ip_forward = 1
net.ipv6.conf.all.forwarding = 1
net.ipv4.tcp_congestion_control = bbr
net.core.default_qdisc = fq
net.ipv4.tcp_fastopen = 3
net.ipv4.tcp_mtu_probing = 1
net.ipv4.tcp_notsent_lowat = 16384
net.core.rmem_max = 67108864
net.core.wmem_max = 67108864
net.ipv4.conf.all.rp_filter = 0
net.ipv4.conf.default.rp_filter = 0
EOF
sysctl --system >/dev/null 2>&1 || true

log "UFW"
ufw --force enable 2>/dev/null || true
for r in 22/tcp 80/tcp 443/tcp 443/udp 8441/tcp 8441/udp 8442/tcp 8443/tcp 8443/udp 8444/tcp 2096/tcp 51820/udp 50959/tcp; do
  ufw allow "$r" comment 'vpn' 2>/dev/null || true
done
ufw reload 2>/dev/null || true

log "x-ui backup cron"
mkdir -p /root/backups/x-ui
cat >/etc/cron.d/x-ui-backup <<'EOF'
17 3 * * * root cp -a /etc/x-ui/x-ui.db /root/backups/x-ui/x-ui.db.$(date +\%Y\%m\%d) 2>/dev/null; find /root/backups/x-ui -mtime +14 -delete 2>/dev/null
EOF

log "WG backup tunnel on UDP/443 (whitelist)"
RU_PRIV=$(cat /etc/wireguard/wg-fr.key 2>/dev/null || wg genkey | tee /etc/wireguard/wg-fr.key)
RU_PUB=$(cat /etc/wireguard/wg-fr.pub 2>/dev/null || echo "$RU_PRIV" | wg pubkey | tee /etc/wireguard/wg-fr.pub)
FR_PUB443=$(cat /etc/wireguard/fr-peer-443.pub 2>/dev/null || cat /etc/wireguard/fr-peer.pub)

if [ -n "$FR_PUB443" ] && [ "$FR_PUB443" != "PLACEHOLDER" ]; then
  cat >/etc/wireguard/wg-fr-443.conf <<EOF
[Interface]
Address = <RU_WG_443_IP>/32
PrivateKey = $RU_PRIV
MTU = 1280
Table = off
PostUp = ip link set %i up; ip route add <FR_WG_IP>/32 dev %i; ip rule add from <RU_WG_443_IP>/32 lookup 51831 priority 101; ip route add default dev %i table 51831
PreDown = ip rule del from <RU_WG_443_IP>/32 lookup 51831 priority 101 2>/dev/null; ip route flush table 51831 2>/dev/null

[Peer]
PublicKey = $FR_PUB443
AllowedIPs = 0.0.0.0/0, ::/0
Endpoint = ${FR_IP}:443
PersistentKeepalive = 25
EOF
  chmod 600 /etc/wireguard/wg-fr-443.conf
  cat >/etc/systemd/system/wg-fr-443.service <<'UNIT'
[Unit]
Description=WG to FR via UDP/443 (whitelist)
After=network-online.target
[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/usr/bin/wg-quick up wg-fr-443
ExecStop=/usr/bin/wg-quick down wg-fr-443
[Install]
WantedBy=multi-user.target
UNIT
  systemctl daemon-reload
  systemctl enable wg-fr-443.service
  systemctl restart wg-fr-443.service 2>/dev/null || true
fi

log "xray template + SS-2022 inbound"
python3 /root/harden-ru-xray.py

log "watchdog"
install -m 755 /root/vpn-watchdog.sh /usr/local/sbin/vpn-watchdog.sh
install -m 644 /root/vpn-watchdog.service /etc/systemd/system/vpn-watchdog.service
install -m 644 /root/vpn-watchdog.timer /etc/systemd/system/vpn-watchdog.timer
systemctl daemon-reload
systemctl enable --now vpn-watchdog.timer

log "restart x-ui"
x-ui restart 2>/dev/null || systemctl restart x-ui
sleep 4
log "done"
