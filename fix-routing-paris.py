#!/usr/bin/env python3
"""Fix RU→Paris routing without FR SSH: no geoip:ru direct, global sites via BRUTAL, DoH DNS."""
import json
import sqlite3
import subprocess

DB = "/etc/x-ui/x-ui.db"
FR_WG = "<FR_WG_IP>"
FR_PUB = "<FR_SERVER_IP>"

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


def main():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute("SELECT value FROM settings WHERE key='xrayTemplateConfig'")
    tpl = json.loads(cur.fetchone()[0])

    paris = [o for o in tpl.get("outbounds", []) if o.get("tag", "").startswith("PARIS")]
    if not paris:
        print("ERROR: no PARIS outbounds in template")
        return 1

    # Prefer WG internal address for Paris protocol outbounds
    for o in paris:
        tag = o.get("tag", "")
        if tag == "PARIS — WireGuard Backbone":
            continue
        if o.get("protocol") == "vless":
            o.setdefault("settings", {})["address"] = FR_WG
        elif o.get("protocol") == "hysteria":
            o.setdefault("settings", {})["address"] = FR_WG
        elif o.get("protocol") == "trojan":
            o.setdefault("settings", {}).setdefault("servers", [{}])
            o["settings"]["servers"][0]["address"] = FR_WG
            if o.get("streamSettings", {}).get("tlsSettings"):
                o["streamSettings"]["tlsSettings"]["serverName"] = FR_WG

    base = [o for o in tpl.get("outbounds", []) if not o.get("tag", "").startswith("PARIS")]
    tpl["outbounds"] = base + paris

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
    }

    sel = [p["tag"] for p in paris]
    tpl["routing"] = {
        "domainStrategy": "IPIfNonMatch",
        "rules": [
            {"type": "field", "inboundTag": ["api"], "outboundTag": "api"},
            {"type": "field", "port": "53", "outboundTag": "dns-out"},
            {"type": "field", "ip": ["geoip:private"], "outboundTag": "blocked"},
            {"type": "field", "protocol": ["bittorrent"], "outboundTag": "blocked"},
            {
                "type": "field",
                "domain": [FR_WG, FR_PUB, "vpn.example.com"],
                "outboundTag": "direct",
            },
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

    subprocess.run(["x-ui", "restart"], check=False)
    print("routing fixed: removed geoip:ru direct, global→BRUTAL, Paris addr", FR_WG)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
