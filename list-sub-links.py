#!/usr/bin/env python3
import json
import sqlite3

HOST = "<RU_SERVER_IP>"
seen = {}
c = sqlite3.connect("/etc/x-ui/x-ui.db")
r = c.execute("select settings from inbounds where port=443").fetchone()
for cl in json.loads(r[0])["clients"]:
    if not cl.get("enable") or not cl.get("subId"):
        continue
    sid = cl["subId"]
    if sid in seen:
        continue
    seen[sid] = cl.get("comment") or cl.get("email", "")
for sid, label in sorted(seen.items(), key=lambda x: x[1]):
    print(f"{label}")
    print(f"http://{HOST}/sub/{sid}#{sid}")
    print()
