#!/bin/bash
set -e
XRAY=/usr/local/x-ui/bin/xray-linux-amd64
PRIV=$(python3 -c "import sqlite3,json; r=sqlite3.connect('/etc/x-ui/x-ui.db').execute('select stream_settings from inbounds where port=443').fetchone()[0]; print(json.loads(r)['realitySettings']['privateKey'])")
PUB=$($XRAY x25519 -i "$PRIV" 2>/dev/null | awk -F': ' '/Public|Password/{print $2; exit}')
UUID=<YOUR_UUID_HERE>
cat > /tmp/xc.json <<EOF
{
  "log": {"loglevel": "warning"},
  "inbounds": [{"listen": "127.0.0.1", "port": 10818, "protocol": "socks", "settings": {}}],
  "outbounds": [{
    "protocol": "vless",
    "settings": {"vnext": [{"address": "127.0.0.1", "port": 443, "users": [{"id": "$UUID", "encryption": "none", "flow": "xtls-rprx-vision"}]}]},
    "streamSettings": {
      "network": "tcp",
      "security": "reality",
      "realitySettings": {
        "serverName": "www.vk.ru",
        "fingerprint": "chrome",
        "publicKey": "$PUB",
        "shortId": "<REALITY_SHORT_ID>",
        "spiderX": "/"
      }
    }
  }]
}
EOF
pkill -f 'xray.*xc.json' 2>/dev/null || true
timeout 12 $XRAY run -c /tmp/xc.json &
sleep 2
CODE=$(curl -s -o /dev/null -w '%{http_code}' --max-time 8 -x socks5h://127.0.0.1:10818 https://www.google.com/generate_204 || echo fail)
echo "REALITY_TEST code=$CODE pub=${PUB:0:20}..."
pkill -f 'xray.*xc.json' 2>/dev/null || true
[ "$CODE" = "204" ] || [ "$CODE" = "200" ]
