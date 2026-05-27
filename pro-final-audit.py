#!/usr/bin/env python3
"""Production audit RU VPN — report OK/FAIL with details."""
import json
import re
import sqlite3
import subprocess
import sys

DB = "/etc/x-ui/x-ui.db"
HOST = "<RU_SERVER_IP>"
FR_WG = "<FR_WG_IP>"
XRAY = "/usr/local/x-ui/bin/xray-linux-amd64"

PASS = FAIL = 0


def ok(msg):
    global PASS
    PASS += 1
    print(f"  [OK] {msg}")


def bad(msg):
    global FAIL
    FAIL += 1
    print(f"  [FAIL] {msg}")


def run(cmd, timeout=15):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)


def main():
    print("========== PRO FINAL AUDIT (RU) ==========")

    for svc in ("x-ui", "x-ui-sub-proxy", "wg-fr", "wg-fr-443", "fail2ban"):
        r = run(f"systemctl is-active {svc}")
        (ok if r.stdout.strip() == "active" else bad)(f"service {svc}")

    r = run(f"{XRAY} -test -config /usr/local/x-ui/bin/config.json")
    (ok if r.returncode == 0 else bad)(f"xray config: {(r.stderr or r.stdout)[-120:]}")

    tpl = json.loads(sqlite3.connect(DB).execute(
        "select value from settings where key='xrayTemplateConfig'"
    ).fetchone()[0])

    rules = tpl.get("routing", {}).get("rules", [])
    ru_rule = next((x for x in rules if x.get("outboundTag") == "direct" and "geosite" in str(x.get("domain", []))), None)
    if ru_rule and "geoip:ru" in str(ru_rule.get("ip", [])):
        bad("routing: geoip:ru still in direct rule (Gemini leak)")
    else:
        ok("routing: no geoip:ru direct leak")

    if any(x.get("balancerTag") == "BRUTAL" and "google" in str(x.get("domain", [])) for x in rules):
        ok("routing: Google/Gemini forced via BRUTAL")
    else:
        bad("routing: missing global→Paris rule")

    paris = [o for o in tpl.get("outbounds", []) if o.get("tag", "").startswith("PARIS")]
    if len(paris) >= 4:
        ok(f"PARIS outbounds: {len(paris)}")
    else:
        bad(f"PARIS outbounds: {len(paris)}")

    vless = next((o for o in paris if "Vision" in o.get("tag", "")), None)
    if vless and vless.get("settings", {}).get("address") == FR_WG:
        ok("PARIS vless via WG IP <FR_WG_IP>")
    else:
        addr = vless.get("settings", {}).get("address") if vless else "?"
        bad(f"PARIS vless address={addr} (want {FR_WG})")

    r = run("wg show wg-fr 2>/dev/null | grep -c handshake")
    (ok if r.stdout.strip() != "0" else bad)("wg-fr handshake")

    r = run("wg show wg-fr-443 2>/dev/null | grep -c handshake")
    (ok if r.stdout.strip() != "0" else bad)("wg-fr-443 handshake")

    r = run(
        "curl -s --max-time 10 --interface <RU_WG_IP> -o /dev/null -w '%{http_code}' "
        "https://www.google.com/generate_204"
    )
    (ok if r.stdout.strip() in ("204", "200") else bad)(f"exit via WG code={r.stdout.strip()}")

  # subscriptions port 80
    for sid in (
        "<SUB_ID>",
        "<SUB_ID>",
        "<SUB_ID>",
        "<SUB_ID>",
        "<SUB_ID>",
    ):
        r = run(f"curl -sL --max-time 8 http://127.0.0.1/sub/{sid}/")
        body = r.stdout or ""
        if "pbk=" in body and "flow=xtls-rprx-vision" in body and body.count("vless://") == 1:
            ok(f"sub {sid[:8]}…")
        else:
            bad(f"sub {sid[:8]}… (vless/pbk/flow)")

    clients = sqlite3.connect(DB).execute(
        "select count(distinct sub_id) from clients where instr(email,'_')=0"
    ).fetchone()[0]
    (ok if clients >= 5 else bad)(f"panel clients (main): {clients}")

    cur = sqlite3.connect(DB).execute("select enable from inbounds where port=8444").fetchone()
    (ok if cur and cur[0] == 0 else bad)("8444 Yandex inbound disabled")

    r = run("ss -tlnp | grep ':80 '")
    (ok if "python3" in (r.stdout or "") or ":80" in (r.stdout or "") else bad)("sub-proxy on :80")

    sub_uri = sqlite3.connect(DB).execute(
        "select value from settings where key='subURI'"
    ).fetchone()
    if sub_uri and f"http://{HOST}/sub/" in sub_uri[0]:
        ok("subURI template")
    else:
        bad(f"subURI={sub_uri[0] if sub_uri else '?'}")

    print(f"========== {PASS} OK / {FAIL} FAIL ==========")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
