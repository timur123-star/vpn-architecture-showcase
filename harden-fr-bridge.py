#!/usr/bin/env python3
"""FR: dedicated bridge user, limitIp=1, fix client fields."""
import json
import sqlite3

RU_IP = "<RU_SERVER_IP>"
BRIDGE_UUID = "<BRIDGE_UUID>"
BRIDGE_EMAIL = "ru-bridge"

def main():
    conn = sqlite3.connect("/etc/x-ui/x-ui.db")
    cur = conn.cursor()
    cur.execute("SELECT id, settings FROM inbounds")
    for iid, settings in cur.fetchall():
        s = json.loads(settings)
        changed = False
        for c in s.get("clients", []):
            if c.get("id") == BRIDGE_UUID or c.get("email", "").startswith("o3cd0wfs"):
                c["email"] = BRIDGE_EMAIL
                c["comment"] = "RU backbone only"
                c["limitIp"] = 1
                if "limitIpValue" in c:
                    del c["limitIpValue"]
                changed = True
        if changed:
            cur.execute("UPDATE inbounds SET settings=? WHERE id=?", (json.dumps(s), iid))
    conn.commit()
    conn.close()
    print("FR bridge hardened")

if __name__ == "__main__":
    main()
