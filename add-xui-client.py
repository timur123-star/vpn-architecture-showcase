#!/usr/bin/env python3
"""Add VPN user: inbounds JSON + clients table (visible in x-ui panel) + subscription."""
import json
import secrets
import sqlite3
import string
import subprocess
import sys
import time
import uuid

DB = "/etc/x-ui/x-ui.db"
HOST = "<RU_SERVER_IP>"
FLOW = "xtls-rprx-vision"


def rand_id(n=16):
    a = string.ascii_lowercase + string.digits
    return "".join(secrets.choice(a) for _ in range(n))


def now_ms():
    return int(time.time() * 1000)


def base_json_client(comment, email, sub_id, vless_uuid=None):
    t = now_ms()
    c = {
        "comment": comment,
        "created_at": t,
        "email": email,
        "enable": True,
        "expiryTime": 0,
        "limitIp": 0,
        "reset": 0,
        "subId": sub_id,
        "tgId": 0,
        "totalGB": 0,
        "updated_at": t,
    }
    if vless_uuid:
        c["id"] = vless_uuid
        c["flow"] = FLOW
    return c


def insert_db_client(cur, email, sub_id, comment, uid, password, auth, flow):
    t = now_ms()
    cur.execute(
        """INSERT INTO clients
        (email, sub_id, uuid, password, auth, flow, security, reverse,
         limit_ip, total_gb, expiry_time, enable, tg_id, comment, reset, created_at, updated_at)
        VALUES (?,?,?,?,?,?,?,?,0,0,0,1,0,?,0,?,?)""",
        (email, sub_id, uid or "", password or "", auth or "", flow or "", "", "", comment, t, t),
    )
    return cur.lastrowid


def main():
    comment = sys.argv[1] if len(sys.argv) > 1 else "User_Android_1"
    email = rand_id(8)
    sub_id = rand_id(16)
    vless_uuid = str(uuid.uuid4())
    tj_pass = secrets.token_urlsafe(16)[:22]
    hy_auth = f"hy_{email[:8]}"
    email_hy = f"{email}_hy"
    email_tj = f"{email}_tj"

    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    existing = [
        r
        for r in cur.execute("select email, sub_id from clients where comment=?", (comment,))
        if "_" not in r[0]
    ]
    if existing:
        row = existing[0]
        print("already exists", row)
        conn.close()
        print(f"http://{HOST}/sub/{row[1]}#{row[1]}")
        return 0

    inbound_ids = {}
    for port, key in ((443, "vless"), (8443, "hy"), (8442, "tj")):
        inbound_ids[key] = cur.execute("select id from inbounds where port=?", (port,)).fetchone()[0]

    # inbound JSON
    cur.execute("SELECT id, settings FROM inbounds WHERE port=443")
    iid, settings = cur.fetchone()
    s = json.loads(settings)
    s["clients"].append(base_json_client(comment, email, sub_id, vless_uuid))
    cur.execute("UPDATE inbounds SET settings=? WHERE id=?", (json.dumps(s), iid))

    cur.execute("SELECT id, settings FROM inbounds WHERE port=8442")
    iid, settings = cur.fetchone()
    s = json.loads(settings)
    c = base_json_client(comment, email_tj, sub_id)
    c["password"] = tj_pass
    s["clients"].append(c)
    cur.execute("UPDATE inbounds SET settings=? WHERE id=?", (json.dumps(s), iid))

    cur.execute("SELECT id, settings FROM inbounds WHERE port=8443")
    iid, settings = cur.fetchone()
    s = json.loads(settings)
    c = base_json_client(comment, email_hy, sub_id)
    c["auth"] = hy_auth
    s["clients"].append(c)
    cur.execute("UPDATE inbounds SET settings=? WHERE id=?", (json.dumps(s), iid))

    # panel: clients + links + traffic
    cid_main = insert_db_client(cur, email, sub_id, comment, vless_uuid, "", "", FLOW)
    cid_hy = insert_db_client(cur, email_hy, sub_id, comment, "", "", hy_auth, "")
    cid_tj = insert_db_client(cur, email_tj, sub_id, comment, "", tj_pass, "", "")
    t = now_ms()
    for cid, iid, flow_ov in (
        (cid_main, inbound_ids["vless"], FLOW),
        (cid_hy, inbound_ids["hy"], ""),
        (cid_tj, inbound_ids["tj"], ""),
    ):
        cur.execute(
            "INSERT INTO client_inbounds (client_id, inbound_id, flow_override, created_at) "
            "VALUES (?,?,?,?)",
            (cid, iid, flow_ov, t),
        )
    for em, iid in ((email, inbound_ids["vless"]), (email_hy, inbound_ids["hy"]), (email_tj, inbound_ids["tj"])):
        cur.execute(
            "INSERT INTO client_traffics (inbound_id, enable, email, up, down, expiry_time, total, reset, last_online)"
            " VALUES (?,1,?,0,0,0,0,0,0)",
            (iid, em),
        )

    conn.commit()
    conn.close()

    subprocess.run(["systemctl", "restart", "x-ui"], check=False)
    subprocess.run(["systemctl", "restart", "x-ui-sub-proxy"], check=False)

    sub_url = f"http://{HOST}/sub/{sub_id}#{sub_id}"
    print("OK")
    print(f"comment={comment}")
    print(f"email={email}")
    print(f"subId={sub_id}")
    print(sub_url)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
