#!/bin/bash
# Health watchdog for RU VPN stack (no credential changes)
set -uo pipefail
LOG=/var/log/vpn-watchdog.log
STATE=/run/vpn-watchdog.state
FR=<FR_SERVER_IP>

log() { echo "$(date -Iseconds) $*" >> "$LOG"; }

restart_if_down() {
  local svc=$1
  if ! systemctl is-active --quiet "$svc"; then
    log "Restarting $svc"
    systemctl restart "$svc" || true
  fi
}

restart_if_down x-ui

for wg in wg-fr wg-fr-443; do
  if [ -f "/etc/wireguard/${wg}.conf" ]; then
    restart_if_down "${wg}.service" 2>/dev/null || true
    if ! ip link show "$wg" &>/dev/null; then
      wg-quick up "$wg" 2>>"$LOG" || true
    fi
  fi
done

for port in 443 8441 8442 8444; do
  ss -tulpnH | grep -q ":${port} " || log "WARN: xray not listening on $port"
done
ss -tulpnH | grep -q ':8443 ' || log "WARN: hysteria 8443 down"

for port in 443 8442 8444; do
  timeout 3 bash -c "echo >/dev/tcp/${FR}/${port}" 2>/dev/null || log "WARN: FR tcp/$port down"
done

if /usr/local/x-ui/bin/xray-linux-amd64 run -test -config /usr/local/x-ui/bin/config.json >/dev/null 2>&1; then
  echo "ok $(date -Iseconds)" > "$STATE"
else
  log "CRITICAL: xray config invalid — restarting x-ui"
  systemctl restart x-ui || true
fi

exit 0
