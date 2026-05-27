# VPN RU → Paris — 2-tier architecture showcase

A production-oriented reference for a **two-hop VPN**: clients connect only to a **RU entry** node;
foreign traffic is balanced to a **Paris (FR) transit** host and exits through **Cloudflare WARP**
via wireproxy. Sanitized for public Git — no real IPs, domains, keys, or personal data.

`Xray` · `3x-ui / x-ui 2.9` · `WireGuard` · `VLESS Reality` · `Hysteria2` · `Trojan` · `Python 3`

[![License](https://img.shields.io/badge/license-All%20rights%20reserved-c4302b.svg)](./LICENSE)
[![Xray](https://img.shields.io/badge/Xray-26.x-1e88e5)](https://github.com/XTLS/Xray-core)
[![WireGuard](https://img.shields.io/badge/WireGuard-tunnel-88171a?logo=wireguard&logoColor=white)](https://www.wireguard.com)
[![Python](https://img.shields.io/badge/automation-Python%203-3776ab?logo=python&logoColor=white)](https://www.python.org)

**Languages:** [English](./README.md) · [Русский](./README.ru.md) · [Español](./README.es.md) · [Français](./README.fr.md) 

---

## About this project

This repository documents a **real-world 2-tier VPN** built for users in Russia: low latency to
the entry point, resilient paths under DPI, and a **Paris exit** through WARP. It is published as a
**portfolio / architecture showcase**: every sensitive value is replaced with placeholders such as
`<RU_SERVER_IP>`, `<FR_WG_IP>`, and `<YOUR_REALITY_PUBLIC_KEY>`.

The repo includes automation that was used in production: subscription proxy for Hiddify, Paris
outbound sync, anti-leak routing fixes, x-ui client provisioning, hardening scripts, and a
22-point audit suite.

> **Disclaimer.** This is **not** a hosted VPN service. Placeholders are not valid credentials.
> Deploy only on infrastructure you own. Review security and local law before use.
> Designed and documented by **Timur Valerievich**.

> **Companion context.** Routing targets **VK-shaped Reality** on port 443, optional **UDP 443**
> WireGuard between servers, and a **BRUTAL** least-ping balancer across five Paris channels.
> See [`DELIVERY_REPORT.md`](./DELIVERY_REPORT.md) for the full delivery narrative (Russian).

---

## What is inside

### Architecture

```
[Client — Hiddify / v2rayN / etc.]
        │  TCP/UDP: 443, 8442, 8443
        ▼
[RU  <RU_SERVER_IP>]   x-ui + Xray
        │  RU sites (.ru, VK, Yandex…) → direct
        │  Global / Google / AI → balancer BRUTAL
        ▼
[FR  <FR_SERVER_IP> / WG <FR_WG_IP>]   x-ui + wireproxy → WARP
        ▼
[Internet — Cloudflare WARP egress]
```

Clients never receive a separate “Paris subscription” — Paris is transit and exit only.

### Client entry (RU)

| Port | Protocol | Role |
| --- | --- | --- |
| **443** | VLESS + Reality + Vision | Masquerade as **VK** (`www.vk.ru`, `spiderX=/`) |
| **8442** | Trojan TLS | TCP/TLS fallback |
| **8443** | Hysteria2 (UDP) | DPI bypass on UDP |
| **8444** | VLESS Reality XHTTP | Disabled in production template |

### Transit RU → Paris

Five parallel outbounds under balancer **BRUTAL** (`leastPing`, observatory ~20s):

1. WireGuard backbone (`wg-fr`, UDP 51820)
2. WireGuard on UDP **443** (`wg-fr-443`) — “whitelist path” between servers
3. VLESS Reality Vision → `<FR_WG_IP>:443`
4. Hysteria2 → FR:8443
5. Trojan TLS → FR:8442

**Fallback:** WireGuard backbone.

### Subscription layer

- Custom **`x-ui-sub-proxy`** on port **80** injects Reality `pbk` and `flow=xtls-rprx-vision`
  for Hiddify-compatible links (`http://<RU_SERVER_IP>/sub/<SUB_ID>#<SUB_ID>`).
- Scripts: `sub-proxy-standalone.py`, `setup-sub-port80.py`, `x-ui-sub-proxy.service`.

### Routing & leak fixes

- Removed `geoip:ru → direct` (was leaking Google/Gemini to RU CDN).
- Paris targets use **WG inner IP** `<FR_WG_IP>`, not the public FR address.
- Example rules: [`ru-routing.example.json`](./ru-routing.example.json).
- FR exit example: [`fr-config.example.json`](./fr-config.example.json) → SOCKS `127.0.0.1:40000` (wireproxy).

### Operations & quality

| Script | Purpose |
| --- | --- |
| `pro-final-master.sh` | One-shot apply: sysctl, UFW, WG, sub proxy, routing, audit |
| `pro-final-audit.py` | 22-check production checklist |
| `verify-pro.sh` | 19-check shell verification |
| `test-reality.sh` | Local VLESS Reality smoke test (expect HTTP 204) |
| `check-whitelist-paths.sh` | UDP 443 / path diagnostics |
| `vpn-watchdog.sh` | Cron-friendly health probe |

---

## Repository layout

```
vpn-architecture-showcase/
├── README.md                 # English (this file)
├── README.ru.md              # Русский
├── README.es.md              # Español
├── README.fr.md              # Français
├── LICENSE
├── DELIVERY_REPORT.md        # Full delivery report (RU)
├── SANITIZE_CHECKLIST.md
├── sub-proxy-standalone.py
├── setup-sub-port80.py
├── x-ui-sub-proxy.service
├── fix-routing-paris.py
├── sync-fr-paris.py
├── fix-hiddify-connect.py
├── add-xui-client.py
├── fr-fetch-inbounds.py
├── harden-fr-bridge.py
├── setup-ru-inbounds.py
├── vpn-harden-ru.sh
├── vpn-harden-fr.sh
├── vpn-watchdog.sh
├── vpn-watchdog.service
├── pro-final-master.sh
├── pro-final-audit.py
├── verify-pro.sh
├── check-whitelist-paths.sh
├── test-reality.sh
├── list-sub-links.py
├── ru-routing.example.json
├── fr-config.example.json
└── run-fr-from-ru.sh.example
```

Parent monorepo (not for public push): `scripts/build-github-showcase.py`, `scripts/sanitize-showcase-final.py`.

---

## Getting started

### 1. Verify anonymization (maintainers)

From the **parent** project root:

```bash
py -3 scripts/sanitize-showcase-final.py
```

Must print: `OK: showcase fully anonymized`.

### 2. Deploy on your servers (operators)

1. Replace every placeholder with **your** IPs, keys, UUIDs, and passwords.
2. Install **x-ui 2.9+**, Xray **26.x**, WireGuard, wireproxy on FR.
3. Copy scripts to `/root/` on RU (and FR where applicable).
4. Run `bash pro-final-master.sh` after setting `SSHPASS` for optional FR checks (see `run-fr-from-ru.sh.example`).
5. Never commit `run-fr-from-ru.sh` with a real password.

```bash
# Example — on RU server
scp -r vpn-architecture-showcase/* root@<RU_SERVER_IP>:/root/
ssh root@<RU_SERVER_IP> 'bash /root/pro-final-master.sh'
python3 /root/pro-final-audit.py
```

### 3. Environment placeholders

| Placeholder | Meaning |
| --- | --- |
| `<RU_SERVER_IP>` | Public IPv4 of the Russia entry node |
| `<FR_SERVER_IP>` | Public IPv4 of the France host |
| `<FR_WG_IP>` | WireGuard inner IP of FR (e.g. `10.x.x.2`) |
| `<RU_WG_IP>` | WireGuard inner IP of RU on backbone tunnel |
| `<YOUR_REALITY_PUBLIC_KEY>` | Reality public key for subscriptions |
| `<SUB_ID>` | Per-user x-ui subscription id |
| `SSHPASS` | FR SSH password — **env only**, never in git |

---

## Quality bar

- **22/22** checks in `pro-final-audit.py` (documented in `DELIVERY_REPORT.md`).
- **19/19** in `verify-pro.sh` for shell-level validation.
- Subscription links must include `pbk` + `flow=xtls-rprx-vision` for stable Hiddify Reality.
- WARP **0 ms** in the FR panel is normal (local SOCKS on the same host).

---

## Pre-push checklist

Publish **only** this folder — not the parent repo (live recon, `.ssh/`, secrets).

1. `py -3 scripts/sanitize-showcase-final.py` → **OK**
2. Confirm no `run-fr-from-ru.sh` (only `.example`)
3. Grep for private IPs / real subIds — must be empty

---

## Credits

Designed and documented by **Timur Valerievich** as a portfolio piece. Infrastructure
placeholders are fictional in this repository; production values live only on private servers.

## License

**All rights reserved.** Copyright © 2026 Timur Valerievich.

You may view the source for reference and personal study. You may not copy, fork, mirror,
redeploy, or reuse the code or documentation for commercial work without written permission.
See [`LICENSE`](./LICENSE) for the full terms.
