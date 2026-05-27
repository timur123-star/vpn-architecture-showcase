#!/usr/bin/env python3
"""Sync PARIS outbound keys from FR x-ui DB (run on RU with sshpass)."""
import json
import sqlite3
import subprocess
import re
import os

DB = "/etc/x-ui/x-ui.db"
FR = "<FR_WG_IP>"  # SSH over wg-ru-443; public <FR_SERVER_IP>:22 blocked from RU
XRAY = "/usr/local/x-ui/bin/xray-linux-amd64"
RU_WG = "<RU_WG_IP>"
BRIDGE = "<BRIDGE_UUID>"

def fr_fetch():
    # password from run-fr-from-ru.sh on server (already deployed)
    pw = None
    try:
        with open("/root/run-fr-from-ru.sh") as f:
            pw = os.environ.get('SSHPASS')
            if m:
                pw = m.group(1)
    except FileNotFoundError:
        pass
    if not pw:
        pw = os.environ.get("SSHPASS")
    if not pw:
        raise RuntimeError("no FR sshpass")
    env = {**os.environ, "SSHPASS": pw}
    cmd = [
        "sshpass", "-e", "ssh",
        "-o", "StrictHostKeyChecking=no",
        "-o", "ConnectTimeout=15",
        f"root@{FR}",
        "python3 /root/fr-fetch-inbounds.py",
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, env=env)
    if r.returncode != 0:
        print("FR ssh fail", r.stderr[:300])
        return []
    infos = []
    for line in r.stdout.splitlines():
        line = line.strip()
        if line.startswith("{"):
            infos.append(json.loads(line))
    return infos


def load_local_paris_keys():
    """If FR SSH fails, reuse keys from current template."""
    conn = sqlite3.connect(DB)
    row = conn.execute("SELECT value FROM settings WHERE key='xrayTemplateConfig'").fetchone()
    conn.close()
    if not row:
        return {}, "", "", ""
    tpl = json.loads(row[0])
    fr = {}
    hy_auth = tj_pass = ""
    fr443_pub = fr8444_pub = ""
    for o in tpl.get("outbounds", []):
        tag = o.get("tag", "")
        if "VLESS Reality Vision" in tag:
            rs = o.get("streamSettings", {}).get("realitySettings", {})
            fr443_pub = rs.get("publicKey", "")
            fr[443] = {"reality_pub": fr443_pub, "sni": rs.get("serverName", ""), "shortId": rs.get("shortId", "c2")}
        if "XHTTP" in tag:
            rs = o.get("streamSettings", {}).get("realitySettings", {})
            fr8444_pub = rs.get("publicKey", "")
            fr[8444] = {"reality_pub": fr8444_pub, "sni": rs.get("serverName", ""), "shortId": rs.get("shortId", "")}
        if "Hysteria2" in tag:
            hy_auth = o.get("streamSettings", {}).get("hysteriaSettings", {}).get("auth", "")
        if "Trojan" in tag and o.get("protocol") == "trojan":
            tj_pass = o.get("settings", {}).get("servers", [{}])[0].get("password", "")
    return fr, fr443_pub, fr8444_pub, hy_auth, tj_pass


infos = fr_fetch()
print("FR inbounds", len(infos))
fr = {x["port"]: x for x in infos}
fr443_pub = fr.get(443, {}).get("reality_pub", "")
fr8444_pub = fr.get(8444, {}).get("reality_pub", "")
hy_auth = fr.get(8443, {}).get("hy_auth", "<HY2_AUTH>")
tj_pass = fr.get(8442, {}).get("tj_pass", "<TROJAN_PASSWORD>")

if not fr443_pub:
    print("WARN: FR SSH failed, using local template keys")
    fr, fr443_pub, fr8444_pub, hy_auth, tj_pass = load_local_paris_keys()
if not fr443_pub:
    print("ERROR: cannot read FR 443 pubkey")
    raise SystemExit(1)

PARIS = [
    {
        "tag": "PARIS — WireGuard Backbone",
        "protocol": "freedom",
        "settings": {"domainStrategy": "UseIPv4"},
        "sendThrough": RU_WG,
    },
    {
        "tag": "PARIS — VLESS Reality Vision (TCP/443)",
        "protocol": "vless",
        "settings": {
            "address": FR,
            "port": 443,
            "id": BRIDGE,
            "flow": "xtls-rprx-vision",
            "encryption": "none",
        },
        "streamSettings": {
            "network": "tcp",
            "security": "reality",
            "realitySettings": {
                "publicKey": fr443_pub,
                "fingerprint": "chrome",
                "serverName": fr.get(443, {}).get("sni", "www.nvidia.com"),
                "shortId": fr.get(443, {}).get("shortId", "c2"),
                "spiderX": "/",
            },
        },
    },
    {
        "tag": "PARIS — Hysteria2 (UDP/8443)",
        "protocol": "hysteria",
        "settings": {"address": FR, "port": 8443, "version": 2},
        "streamSettings": {
            "network": "hysteria",
            "security": "tls",
            "tlsSettings": {
                "serverName": FR,
                "alpn": ["h3"],
                "fingerprint": "chrome",
                "allowInsecure": True,
            },
            "hysteriaSettings": {
                "version": 2,
                "auth": hy_auth,
                "initStreamReceiveWindow": 8388608,
                "maxStreamReceiveWindow": 8388608,
                "initConnectionReceiveWindow": 20971520,
                "maxConnectionReceiveWindow": 20971520,
            },
        },
    },
    {
        "tag": "PARIS — Trojan TLS (TCP/8442)",
        "protocol": "trojan",
        "settings": {"servers": [{"address": FR, "port": 8442, "password": tj_pass}]},
        "streamSettings": {
            "network": "tcp",
            "security": "tls",
            "tlsSettings": {
                "serverName": FR,
                "allowInsecure": True,
                "fingerprint": "chrome",
                "alpn": ["h2", "http/1.1"],
            },
        },
    },
]

if fr8444_pub:
    PARIS.insert(
        2,
        {
            "tag": "PARIS — VLESS Reality XHTTP (TCP/8444)",
            "protocol": "vless",
            "settings": {"address": FR, "port": 8444, "id": BRIDGE, "encryption": "none"},
            "streamSettings": {
                "network": "tcp",
                "security": "reality",
                "realitySettings": {
                    "publicKey": fr8444_pub,
                    "fingerprint": "chrome",
                    "serverName": fr.get(8444, {}).get("sni", "www.nvidia.com"),
                    "shortId": fr.get(8444, {}).get("shortId", "<SHORT_ID>"),
                    "spiderX": "/",
                },
            },
        },
    )

# Only Russian *domains* go direct. Do NOT use geoip:ru — Google/Gemini CDN IPs in RU
# would bypass Paris and look "like Russia".
RU_DIRECT = {
    "type": "field",
    "domain": [
        "geosite:category-ru",
        "regexp:.*\\.ru$",
        "domain:vk.com", "domain:vk.ru", "domain:yandex.ru", "domain:ya.ru",
        "domain:mail.ru", "domain:ok.ru", "domain:avito.ru", "domain:wildberries.ru",
        "domain:ozon.ru", "domain:sberbank.ru", "domain:gosuslugi.ru",
    ],
    "outboundTag": "direct",
}

# Force global / AI / streaming through Paris (domain match before IP fallback)
GLOBAL_VIA_PARIS = {
    "type": "field",
    "domain": [
        "geosite:google",
        "geosite:openai",
        "geosite:microsoft",
        "geosite:apple",
        "geosite:netflix",
        "geosite:spotify",
        "geosite:twitter",
        "geosite:facebook",
        "geosite:instagram",
        "geosite:discord",
        "geosite:github",
        "geosite:cloudflare",
        "domain:gemini.google.com",
        "domain:ai.google.dev",
        "domain:generativelanguage.googleapis.com",
        "domain:anthropic.com",
        "domain:claude.ai",
    ],
    "balancerTag": "BRUTAL",
}

conn = sqlite3.connect(DB)
cur = conn.cursor()
cur.execute("SELECT value FROM settings WHERE key='xrayTemplateConfig'")
row = cur.fetchone()
tpl = json.loads(row[0]) if row else {}
tpl["log"] = {"loglevel": "warning"}
tpl["dns"] = {
    "servers": [
        {
            "address": "https://1.1.1.1/dns-query",
            "domains": ["geosite:geolocation-!cn"],
            "skipFallback": True,
        },
        {
            "address": "https://dns.google/dns-query",
                "domains": ["geosite:google"],
            "skipFallback": True,
        },
        "localhost",
    ],
    "queryStrategy": "UseIPv4",
    "disableCache": False,
}
tpl["outbounds"] = [
    {"tag": "direct", "protocol": "freedom", "settings": {"domainStrategy": "UseIPv4"}},
    {"tag": "blocked", "protocol": "blackhole", "settings": {}},
    {"tag": "dns-out", "protocol": "dns"},
] + PARIS

sel = [p["tag"] for p in PARIS]
tpl["routing"] = {
    "domainStrategy": "IPIfNonMatch",
    "rules": [
        {"type": "field", "inboundTag": ["api"], "outboundTag": "api"},
        {"type": "field", "port": "53", "outboundTag": "dns-out"},
        {"type": "field", "ip": ["geoip:private"], "outboundTag": "blocked"},
        {"type": "field", "protocol": ["bittorrent"], "outboundTag": "blocked"},
        {"type": "field", "domain": [FR, "<FR_WG_IP>", "<FR_SERVER_IP>", "vpn.example.com"], "outboundTag": "direct"},
        GLOBAL_VIA_PARIS,
        RU_DIRECT,
        {"type": "field", "network": "tcp,udp", "balancerTag": "BRUTAL"},
    ],
    "balancers": [{
        "tag": "BRUTAL",
        "selector": sel,
        "fallbackTag": "PARIS — WireGuard Backbone",
        "strategy": {"type": "leastPing"},
    }],
}
tpl["observatory"] = {
    "subjectSelector": sel,
    "probeUrl": "https://www.google.com/generate_204",
    "probeInterval": "20s",
    "enableConcurrency": True,
}
cur.execute(
    "UPDATE settings SET value=? WHERE key='xrayTemplateConfig'",
    (json.dumps(tpl, ensure_ascii=False),),
)
conn.commit()
conn.close()
print("Synced PARIS pub", fr443_pub[:24], "... paths", len(PARIS))
