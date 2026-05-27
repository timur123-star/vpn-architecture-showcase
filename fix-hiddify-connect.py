#!/usr/bin/env python3
"""
Fix Hiddify connection errors:
1. Stable Reality keys (no regen)
2. spiderX=/ fixed in DB
3. Client flow EMPTY (Hiddify/sing-box often breaks on vision in sub)
4. sub-proxy builds canonical vless link
5. Ensure client user_b enabled on 443 only for main email
"""
import json
import sqlite3
import subprocess

DB = "/etc/x-ui/x-ui.db"
XRAY = "/usr/local/x-ui/bin/xray-linux-amd64"

conn = sqlite3.connect(DB)
cur = conn.cursor()

cur.execute("SELECT id, settings, stream_settings FROM inbounds WHERE port=443")
iid, settings, stream = cur.fetchone()
s = json.loads(settings)
st = json.loads(stream)
rs = st.get("realitySettings", {})

priv = rs.get("privateKey")
if not priv:
    r = subprocess.run([XRAY, "x25519"], capture_output=True, text=True)
    for line in (r.stdout + r.stderr).splitlines():
        if "Private" in line and ":" in line:
            priv = line.split(":", 1)[1].strip()
    rs["privateKey"] = priv

r2 = subprocess.run([XRAY, "x25519", "-i", priv], capture_output=True, text=True)
pub = None
for line in (r2.stdout + r2.stderr).splitlines():
    if ("Public" in line or "Password" in line) and ":" in line:
        pub = line.split(":", 1)[1].strip()

rs.update({
    "show": False,
    "dest": "www.vk.ru:443",
    "target": "www.vk.ru:443",
    "serverNames": ["www.vk.ru", "vk.ru", "m.vk.ru"],
    "privateKey": priv,
    "publicKey": pub,
    "shortIds": ["<REALITY_SHORT_ID>"],
    "spiderX": "/",
    "xver": 0,
})
rs.pop("mldsa65Seed", None)
rs.pop("mldsa65Verify", None)

st = {
    "network": "tcp",
    "security": "reality",
    "realitySettings": rs,
    "tcpSettings": {"acceptProxyProtocol": False, "header": {"type": "none"}},
}

for c in s.get("clients", []):
    c["enable"] = True
    if c.get("email") == "user_b":
        # Hiddify: no vision in client link — server accepts with or without
        c["flow"] = ""
    elif "user_b" in c.get("email", ""):
        c["enable"] = False  # only main on 443

cur.execute(
    "UPDATE inbounds SET remark=?, settings=?, stream_settings=?, enable=1 WHERE id=?",
    ("RU VLESS Reality VK 443", json.dumps(s), json.dumps(st), iid),
)

# 8444 off
cur.execute("UPDATE inbounds SET enable=0 WHERE port=8444")

# Trojan 8442 - fix SNI to match cert if possible
cur.execute("SELECT id, settings, stream_settings FROM inbounds WHERE port=8442")
row = cur.fetchone()
if row:
    iid2, s2, st2 = row
    s2 = json.loads(s2)
    st2 = json.loads(st2) if st2 else {}
    st2.setdefault("tlsSettings", {})
    # use IP as sni (self-signed panel cert)
    for c in s2.get("clients", []):
        if "user_b" in c.get("email", ""):
            c["enable"] = True
    cur.execute(
        "UPDATE inbounds SET settings=?, stream_settings=?, enable=1 WHERE id=?",
        (json.dumps(s2), json.dumps(st2), iid2),
    )

for k, v in [
    ("subURI", "http://<RU_SERVER_IP>:80/sub/"),
    ("subEncrypt", "false"),
    ("subClashEnable", "false"),
    ("subEnableRouting", "false"),
]:
    cur.execute("UPDATE settings SET value=? WHERE key=?", (v, k))

conn.commit()
conn.close()

subprocess.run(["x-ui", "restart"], check=False)
import time

time.sleep(4)
subprocess.run(["systemctl", "restart", "x-ui-sub-proxy"], check=False)
print("PUBLIC_KEY", pub)
print("FLOW on user_b: empty (Hiddify fix)")
print("spiderX: /")
print("DONE")
