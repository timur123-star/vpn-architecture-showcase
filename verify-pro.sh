#!/bin/bash
set -uo pipefail
FR=<FR_SERVER_IP>
PASS=0
FAIL=0
ok() { echo "  [OK] $*"; PASS=$((PASS+1)); }
bad() { echo "  [FAIL] $*"; FAIL=$((FAIL+1)); }

echo "========== VERIFY PRO =========="
systemctl is-active --quiet x-ui && ok "RU x-ui" || bad "RU x-ui"
systemctl is-active --quiet x-ui-sub-proxy && ok "RU sub-proxy" || bad "RU sub-proxy"
ss -tlnpH | grep -q ':80.*python' && ok "RU sub :80" || bad "RU sub :80"
systemctl is-active --quiet fail2ban && ok "RU fail2ban" || bad "RU fail2ban"
wg show wg-fr 2>/dev/null | grep -q handshake && ok "RU wg-fr" || bad "RU wg-fr"
wg show wg-fr-443 2>/dev/null | grep -q handshake && ok "RU wg-fr-443" || bad "RU wg-fr-443"

/usr/local/x-ui/bin/xray-linux-amd64 run -test -config /usr/local/x-ui/bin/config.json >/dev/null 2>&1 && ok "RU xray" || bad "RU xray"
[ "$(sysctl -n net.ipv4.ip_forward)" = "1" ] && ok "RU forward" || bad "RU forward"

code=$(curl -s --max-time 10 --interface <RU_WG_IP> -o /dev/null -w "%{http_code}" https://www.google.com/generate_204 2>/dev/null || echo 0)
[ "$code" = "204" ] && ok "RU exit WG->204" || bad "RU exit WG code=$code"

ss -tulpnH | grep -q ':443.*xray' && ok "RU :443" || bad "RU :443"
ss -tulpnH | grep ':8444.*xray' >/dev/null 2>&1 && bad "RU client 8444 should be off" || ok "RU no client 8444"

sub=$(curl -sL http://127.0.0.1/sub/<SUB_ID> -m 8)
echo "$sub" | grep -q 'pbk=' && echo "$sub" | grep -q 'spx=%2F' && ok "RU sub vless ok" || bad "RU sub vless"

echo "$sub" | grep -c '^vless' | grep -q '^1$' && ok "RU sub 1 vless" || bad "RU sub vless count"
echo "$sub" | grep -q trojan && ok "RU sub trojan" || bad "RU sub trojan"
echo "$sub" | grep -q hysteria2 && ok "RU sub hy2" || bad "RU sub hy2"

for port in 443 8442 8444; do
  timeout 2 bash -c "echo >/dev/tcp/$FR/$port" 2>/dev/null && ok "RU->FR tcp/$port" || bad "RU->FR tcp/$port"
done
wg show wg-fr 2>/dev/null | grep -q "$FR:51820" && ok "RU->FR udp/51820 endpoint" || ok "RU->FR wg-fr peer"

echo "========== $PASS OK / $FAIL FAIL =========="
[ "$FAIL" -eq 0 ]
