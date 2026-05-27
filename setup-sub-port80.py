#!/usr/bin/env python3
import sqlite3

HOST = "<RU_SERVER_IP>"
BASE = f"http://{HOST}/sub/"

conn = sqlite3.connect("/etc/x-ui/x-ui.db")
cur = conn.cursor()
for key, val in [
    ("subURI", BASE),
    ("subJsonURI", f"http://{HOST}/json/"),
    ("subDomain", HOST),
    ("subPort", "80"),
    ("subPath", "/sub/"),
]:
    cur.execute("UPDATE settings SET value=? WHERE key=?", (val, key))
conn.commit()
conn.close()
print("subURI=", BASE)
