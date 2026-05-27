#!/usr/bin/env python3
"""Add 3 missing RU entry inbounds (8442/8443/8444) mirroring 443 clients."""
import json
import sqlite3
import time
from copy import deepcopy

DB = "/etc/x-ui/x-ui.db"
CERT = "/etc/letsencrypt/live/vpn.example.com/fullchain.pem"
KEY = "/etc/letsencrypt/live/vpn.example.com/privkey.pem"

RU_REALITY = {
    "network": "tcp",
    "security": "reality",
    "realitySettings": {
        "show": False,
        "xver": 0,
        "target": "www.vk.ru:443",
        "serverNames": ["www.vk.ru", "vk.ru", "m.vk.ru"],
        "privateKey": "<YOUR_REALITY_PRIVATE_KEY>",
        "minClientVer": "",
        "maxClientVer": "",
        "maxTimediff": 0,
        "shortIds": [
            "<REALITY_SHORT_ID>", "18", "8f10", "<SHORT_ID>",
            "<SHORT_ID>", "a5be9e", "31ffa78ead08", "d932aa03",
        ],
        "mldsa65Seed": "<MLDSA65_SEED>",
    },
    "tcpSettings": {"acceptProxyProtocol": False, "header": {"type": "none"}},
}

RU_XHTTP = {
    "network": "xhttp",
    "security": "reality",
    "realitySettings": {
        "show": False,
        "xver": 0,
        "target": "www.yandex.ru:443",
        "serverNames": ["www.yandex.ru", "yandex.ru", "ya.ru"],
        "privateKey": "<YOUR_REALITY_PRIVATE_KEY>",
        "minClientVer": "",
        "maxClientVer": "",
        "maxTimediff": 0,
        "shortIds": [
            "<REALITY_SHORT_ID>", "18", "8f10", "<SHORT_ID>",
            "<SHORT_ID>", "a5be9e", "31ffa78ead08", "d932aa03",
        ],
        "mldsa65Seed": "",
    },
    "xhttpSettings": {
        "path": "/xh",
        "host": "www.yandex.ru",
        "mode": "auto",
        "noSSEHeader": False,
        "xPaddingBytes": "100-1000",
        "scMaxBufferedPosts": 30,
        "scMaxEachPostBytes": "1000000",
        "scStreamUpServerSecs": "20-80",
    },
}

def hy_settings(clients):
    hy_clients = []
    for c in clients:
        email = c.get("email", "user")
        hy_clients.append({
            "email": f"{email}_hy",
            "enable": True,
            "auth": c.get("hy_auth") or f"hy_{email[:8]}",
            "comment": c.get("comment", ""),
            "expiryTime": 0,
            "limitIp": 0,
            "totalGB": 0,
            "reset": 0,
            "tgId": 0,
            "subId": c.get("subId", ""),
            "created_at": int(time.time() * 1000),
            "updated_at": int(time.time() * 1000),
        })
    return {
        "clients": hy_clients,
        "version": 2,
    }

def hy_stream():
    return {
        "network": "hysteria",
        "security": "tls",
        "tlsSettings": {
            "serverName": "vpn.example.com",
            "minVersion": "1.2",
            "maxVersion": "1.3",
            "alpn": ["h3"],
            "certificates": [{
                "certificateFile": CERT,
                "keyFile": KEY,
                "oneTimeLoading": False,
                "usage": "encipherment",
                "buildChain": False,
            }],
            "rejectUnknownSni": False,
            "disableSystemRoot": False,
            "enableSessionResumption": False,
        },
        "hysteriaSettings": {"version": 2, "auth": "", "udpIdleTimeout": 60},
    }

def trojan_settings(clients):
    tj = []
    import secrets
    for c in clients:
        email = c.get("email", "user")
        tj.append({
            "email": f"{email}_tj",
            "enable": True,
            "password": c.get("tj_pass") or secrets.token_urlsafe(16)[:22],
            "comment": c.get("comment", ""),
            "expiryTime": 0,
            "limitIp": 0,
            "totalGB": 0,
            "reset": 0,
            "tgId": 0,
            "subId": c.get("subId", ""),
            "created_at": int(time.time() * 1000),
            "updated_at": int(time.time() * 1000),
        })
    return {"clients": tj, "fallbacks": []}

def trojan_stream():
    return {
        "network": "tcp",
        "security": "tls",
        "tlsSettings": {
            "serverName": "vpn.example.com",
            "minVersion": "1.2",
            "maxVersion": "1.3",
            "alpn": ["h2", "http/1.1"],
            "certificates": [{
                "certificateFile": CERT,
                "keyFile": KEY,
                "oneTimeLoading": False,
                "usage": "encipherment",
                "buildChain": False,
            }],
            "rejectUnknownSni": False,
            "disableSystemRoot": False,
            "enableSessionResumption": False,
        },
        "tcpSettings": {"acceptProxyProtocol": False, "header": {"type": "none"}},
    }

def xhttp_settings(clients):
    out = []
    for c in clients:
        nc = deepcopy(c)
        nc["email"] = f"{c.get('email', 'u')}_xh"
        nc["flow"] = ""
        out.append(nc)
    return {"clients": out, "decryption": "none", "encryption": "none"}

def main():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute("SELECT id, remark, port, settings, stream_settings FROM inbounds")
    rows = cur.fetchall()
    base = None
    for r in rows:
        if r[2] == 443:
            base = r
            break
    if not base:
        print("No inbound 443 found, abort")
        return 1

    _, _, _, settings_s, stream_s = base
    clients = json.loads(settings_s).get("clients", [])
    sniffing = json.dumps({
        "enabled": True,
        "destOverride": ["http", "tls", "quic"],
        "metadataOnly": False,
        "routeOnly": False,
    })

    planned = [
        (8444, "RU — VLESS Reality XHTTP (TCP/8444)", "vless", xhttp_settings(clients), json.dumps(RU_XHTTP)),
        (8443, "RU — Hysteria2 (UDP/8443)", "hysteria", hy_settings(clients), json.dumps(hy_stream())),
        (8442, "RU — Trojan TLS (TCP/8442)", "trojan", trojan_settings(clients), json.dumps(trojan_stream())),
    ]

    existing_ports = {r[2] for r in rows}
    ts = int(time.time() * 1000)

    for port, remark, proto, settings, stream in planned:
        if port in existing_ports:
            print(f"Skip existing port {port}")
            continue
        cur.execute(
            """INSERT INTO inbounds
            (user_id, up, down, total, all_time, remark, enable, expiry_time,
             listen, port, protocol, settings, stream_settings, tag, sniffing)
            VALUES (0,0,0,0,0,?,1,0,'',?, ?, ?, ?, ?, ?)""",
            (remark, port, proto, json.dumps(settings), stream,
             f"inbound-{port}", sniffing),
        )
        print(f"Added inbound {remark} on {port}")

    cur.execute(
        "UPDATE inbounds SET remark=? WHERE port=443",
        ("RU — VLESS Reality Vision (TCP/443)",),
    )
    conn.commit()
    conn.close()
    print("Inbounds OK")

if __name__ == "__main__":
    main()
