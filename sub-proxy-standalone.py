#!/usr/bin/env python3
"""
Subscription server :80 /sub/{id} — builds links from x-ui DB (no :<XUI_SUB_PORT>).
Fixes Hiddify 502 on profile update.
"""
import json
import sqlite3
import subprocess
import urllib.parse
import re
from http.server import HTTPServer, BaseHTTPRequestHandler

HOST = "<RU_SERVER_IP>"
PORT = 80
XRAY = "/usr/local/x-ui/bin/xray-linux-amd64"
DB = "/etc/x-ui/x-ui.db"


def pub_from_priv(priv):
    r = subprocess.run([XRAY, "x25519", "-i", priv], capture_output=True, text=True)
    for line in (r.stdout + r.stderr).splitlines():
        if ("Public" in line or "Password" in line) and ":" in line:
            return line.split(":", 1)[1].strip()
    return None


def build_sub_for_sid(sub_id: str) -> str:
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    lines = []

    # 443 VLESS Reality
    cur.execute(
        "SELECT remark, settings, stream_settings FROM inbounds WHERE port=443 AND enable=1"
    )
    row = cur.fetchone()
    if row:
        remark, settings, stream = row
        s = json.loads(settings)
        st = json.loads(stream)
        rs = st["realitySettings"]
        pub = rs.get("publicKey") or pub_from_priv(rs["privateKey"])
        sid = next((x for x in rs.get("shortIds", []) if x), "<REALITY_SHORT_ID>")
        for cl in s.get("clients", []):
            if cl.get("subId") != sub_id or not cl.get("enable"):
                continue
            email = cl.get("email", "")
            if email.endswith("_tj") or email.endswith("_hy") or email.endswith("_yd"):
                continue
            uid = cl["id"]
            flow = (cl.get("flow") or "").strip()
            if not flow:
                # x-ui 2.9 still applies vision in runtime when DB flow is empty
                flow = "xtls-rprx-vision"
            params = {
                "encryption": "none",
                "security": "reality",
                "flow": flow,
                "pbk": pub,
                "fp": "chrome",
                "sni": "www.vk.ru",
                "sid": sid,
                "spx": "/",
                "type": "tcp",
            }
            params = urllib.parse.urlencode(params)
            tag = urllib.parse.quote(
                cl.get("comment") or remark or "RU VLESS Reality VK 443"
            )
            lines.append(f"vless://{uid}@{HOST}:443?{params}#{tag}")

    for port, proto in ((8442, "trojan"), (8443, "hysteria2")):
        cur.execute(
            "SELECT remark, settings, stream_settings FROM inbounds WHERE port=? AND enable=1",
            (port,),
        )
        row = cur.fetchone()
        if not row:
            continue
        remark, settings, stream = row
        s = json.loads(settings)
        st = json.loads(stream) if stream else {}
        for cl in s.get("clients", []):
            if cl.get("subId") != sub_id or not cl.get("enable"):
                continue
            if proto == "trojan":
                pwd = cl.get("password", "")
                params = urllib.parse.urlencode({
                    "security": "tls",
                    "sni": HOST,
                    "type": "tcp",
                    "allowInsecure": "1",
                    "insecure": "1",
                    "alpn": "h2,http/1.1",
                })
                tag = urllib.parse.quote(cl.get("comment") or remark or f"RU Trojan {port}")
                lines.append(f"trojan://{pwd}@{HOST}:{port}?{params}#{tag}")
            elif proto == "hysteria2":
                auth = cl.get("auth") or cl.get("password", "")
                params = urllib.parse.urlencode({
                    "security": "tls",
                    "sni": HOST,
                    "insecure": "1",
                    "alpn": "h3",
                })
                tag = urllib.parse.quote(cl.get("comment") or remark or f"RU Hysteria2 {port}")
                lines.append(f"hysteria2://{auth}@{HOST}:{port}?{params}#{tag}")

    conn.close()
    if not lines:
        return ""
    return "\n".join(lines) + "\n"


class Handler(BaseHTTPRequestHandler):
    def _serve_sub(self, send_body=True):
        path = self.path.split("?", 1)[0]
        parts = [p for p in path.strip("/").split("/") if p]
        if len(parts) >= 2 and parts[0] == "json":
            sub_id = parts[1]
            body = build_sub_for_sid(sub_id)
            if not body:
                self.send_error(404, "no clients for subId")
                return
            # minimal sing-box from first vless line only
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            if send_body:
                self.wfile.write(b'{"outbounds":[]}')
            return
        if len(parts) < 2 or parts[0] != "sub":
            self.send_error(404)
            return
        sub_id = parts[1]
        body = build_sub_for_sid(sub_id)
        if not body:
            self.send_error(404, "no clients for this subId")
            return
        data = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        if send_body:
            self.wfile.write(data)

    def do_GET(self):
        self._serve_sub(True)

    def do_HEAD(self):
        self._serve_sub(False)

    def log_message(self, fmt, *args):
        pass


if __name__ == "__main__":
    HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
