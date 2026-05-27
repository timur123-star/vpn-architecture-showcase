#!/bin/bash
echo "========== WHITELIST / DPI PATHS (RU) =========="
echo "Server IP: $(curl -s --max-time 5 ifconfig.me 2>/dev/null || hostname -I | awk '{print $1}')"
echo ""
echo "--- Client entry (DPI bypass) ---"
python3 <<'PY'
import json, sqlite3
c = sqlite3.connect("/etc/x-ui/x-ui.db")
for port, name in [(443, "VLESS Reality VK"), (8442, "Trojan TLS"), (8443, "Hysteria2"), (8444, "8444 Yandex")]:
    r = c.execute("select enable, remark, stream_settings from inbounds where port=?", (port,)).fetchone()
    if not r: continue
    en, rem, st = r
    s = json.loads(st) if st else {}
    rs = s.get("realitySettings", {})
    print(f"  [{('ON' if en else 'OFF')}] :{port} {rem or name}")
    if port == 443:
        print(f"       SNI/serverNames: {rs.get('serverNames')}")
        print(f"       target: {rs.get('target')}")
        print(f"       spiderX: {rs.get('spiderX')}")
PY
echo ""
echo "--- Backbone whitelist tunnel (RU->FR UDP/443) ---"
systemctl is-active wg-fr-443 >/dev/null && echo "  wg-fr-443: active" || echo "  wg-fr-443: INACTIVE"
wg show wg-fr-443 2>/dev/null | grep -E 'endpoint|handshake|transfer' | sed 's/^/  /'
echo ""
echo "--- Main backbone (RU->FR UDP/51820) ---"
wg show wg-fr 2>/dev/null | grep -E 'endpoint|handshake|transfer' | sed 's/^/  /'
echo ""
echo "--- Paris failover (balancer) ---"
python3 -c "
import json,sqlite3
t=json.loads(sqlite3.connect('/etc/x-ui/x-ui.db').execute(\"select value from settings where key='xrayTemplateConfig'\").fetchone()[0])
print('  PARIS paths:', len([o for o in t['outbounds'] if 'PARIS' in o.get('tag','')]))
print('  BRUTAL selector:', t['routing']['balancers'][0]['selector'][:2], '...')
"
echo ""
echo "--- Listening ---"
ss -tlnp | grep -E ':443 |:8442 |:80 ' | sed 's/^/  /'
ss -ulnp | grep -E ':443 |:8443 ' | sed 's/^/  /'
