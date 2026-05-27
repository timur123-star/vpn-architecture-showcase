#!/usr/bin/env python3
import sqlite3
import json
import subprocess

XRAY = "/usr/local/x-ui/bin/xray-linux-amd64"

def pub(priv):
    r = subprocess.run([XRAY, "x25519", "-i", priv], capture_output=True, text=True)
    for line in (r.stdout + r.stderr).splitlines():
        if ("Public" in line or "Password" in line) and ":" in line:
            return line.split(":", 1)[1].strip()
    return ""

for port in (443, 8444, 8442, 8443):
    row = sqlite3.connect("/etc/x-ui/x-ui.db").execute(
        "select settings, stream_settings from inbounds where port=?", (port,)
    ).fetchone()
    if not row:
        continue
    s, st = json.loads(row[0]), json.loads(row[1])
    info = {"port": port}
    if st.get("security") == "reality":
        rs = st["realitySettings"]
        info["reality_pub"] = rs.get("publicKey") or pub(rs.get("privateKey", ""))
        ids = [x for x in rs.get("shortIds", []) if x]
        info["shortId"] = ids[0] if ids else ""
        sn = rs.get("serverNames") or []
        info["sni"] = sn[0] if sn else ""
        info["network"] = st.get("network", "tcp")
    if port == 8443 and s.get("clients"):
        info["hy_auth"] = s["clients"][0].get("password", "")
    if port == 8442 and s.get("clients"):
        info["tj_pass"] = s["clients"][0].get("password", "")
    print(json.dumps(info))
