# VPN RU → Paris — vitrine d'architecture à deux sauts

Référence **production** pour un **VPN à deux niveaux** : les clients ne se connectent qu'au
**nœud d'entrée RU** ; le trafic étranger est équilibré vers le **transit Paris (FR)** et sort via
**Cloudflare WARP** (wireproxy). Dépôt anonymisé — pas d'IP, domaines, clés ni données personnelles réelles.

`Xray` · `3x-ui / x-ui 2.9` · `WireGuard` · `VLESS Reality` · `Hysteria2` · `Trojan` · `Python 3`

[![License](https://img.shields.io/badge/license-All%20rights%20reserved-c4302b.svg)](./LICENSE)
[![Xray](https://img.shields.io/badge/Xray-26.x-1e88e5)](https://github.com/XTLS/Xray-core)
[![WireGuard](https://img.shields.io/badge/WireGuard-tunnel-88171a?logo=wireguard&logoColor=white)](https://www.wireguard.com)
[![Python](https://img.shields.io/badge/automation-Python%203-3776ab?logo=python&logoColor=white)](https://www.python.org)

**Langues :** [English](./README.md) · [Русский](./README.ru.md) · [Español](./README.es.md) · [Français](./README.fr.md) · [Rapport de livraison](./DELIVERY_REPORT.md)

---

## À propos

Ce dépôt documente un **VPN à deux sauts** déployé pour des utilisateurs en Russie : faible latence
vers l'entrée, chemins résilients sous DPI et **sortie à Paris** via WARP. Publication en **portfolio /
vitrine d'architecture** : chaque valeur sensible est remplacée par des placeholders (`<RU_SERVER_IP>`,
`<FR_WG_IP>`, `<YOUR_REALITY_PUBLIC_KEY>`, etc.).

Automatisation incluse : proxy d'abonnement Hiddify, sync des outbounds Paris, corrections de fuites
de routage, provisionnement clients x-ui, durcissement et audit en 22 points.

> **Avertissement.** Ce n'est **pas** un service VPN hébergé. Les placeholders ne sont pas des
> identifiants valides. Déployez uniquement sur votre infrastructure. Respectez la sécurité et la loi locale.
> Conçu et documenté par **Timur Valerievich**.

> **Contexte.** Reality masqué **VK** sur le port 443, **WireGuard UDP 443** optionnel entre serveurs,
> balanceur **BRUTAL** sur cinq canaux vers Paris. Rapport complet (russe) :
> [`DELIVERY_REPORT.md`](./DELIVERY_REPORT.md).

---

## Contenu

### Architecture

```
[Client — Hiddify / v2rayN / etc.]
        │  TCP/UDP : 443, 8442, 8443
        ▼
[RU  <RU_SERVER_IP>]   x-ui + Xray
        │  Sites RU (.ru, VK, Yandex…) → direct
        │  Global / Google / IA → balanceur BRUTAL
        ▼
[FR  <FR_SERVER_IP> / WG <FR_WG_IP>]   x-ui + wireproxy → WARP
        ▼
[Internet — sortie Cloudflare WARP]
```

Pas d'abonnement « Paris » séparé pour les clients — Paris = transit et sortie uniquement.

### Entrée (RU)

| Port | Protocole | Rôle |
| --- | --- | --- |
| **443** | VLESS + Reality + Vision | Déguisement **VK** (`www.vk.ru`) |
| **8442** | Trojan TLS | Secours TCP/TLS |
| **8443** | Hysteria2 (UDP) | Contournement DPI TCP |
| **8444** | VLESS Reality XHTTP | Désactivé dans le modèle |

### Transit RU → Paris

Cinq outbounds parallèles, balanceur **BRUTAL** (`leastPing`, observatory ~20 s) :

1. WireGuard backbone (`wg-fr`, UDP 51820)
2. WireGuard UDP **443** (`wg-fr-443`)
3. VLESS Reality Vision → `<FR_WG_IP>:443`
4. Hysteria2 → FR:8443
5. Trojan TLS → FR:8442

**Secours :** WireGuard backbone.

### Abonnements

- **`x-ui-sub-proxy`** sur le port **80** injecte `pbk` Reality et `flow=xtls-rprx-vision`.
- Format : `http://<RU_SERVER_IP>/sub/<SUB_ID>#<SUB_ID>`.

### Routage

- Suppression de `geoip:ru → direct` (fuites Google/Gemini vers CDN russes).
- Cibles Paris via IP WG interne `<FR_WG_IP>`.
- Exemples : [`ru-routing.example.json`](./ru-routing.example.json), [`fr-config.example.json`](./fr-config.example.json).

### Exploitation

| Script | Rôle |
| --- | --- |
| `pro-final-master.sh` | Application : sysctl, UFW, WG, proxy, routes, audit |
| `pro-final-audit.py` | 22 contrôles |
| `verify-pro.sh` | 19 contrôles shell |
| `test-reality.sh` | Test Reality local (HTTP 204) |
| `vpn-watchdog.sh` | Sonde périodique |

---

## Arborescence

Voir l'[README anglais](./README.md#repository-layout). Rapport de livraison en russe :
`DELIVERY_REPORT.md`.

---

## Démarrage

### Vérifier l'anonymisation (avant push)

Depuis la racine du monorepo :

```bash
py -3 scripts/sanitize-showcase-final.py
```

Doit afficher : `OK: showcase fully anonymized`.

### Déploiement

1. Remplacez tous les placeholders par **vos** IP, clés, UUID et mots de passe.
2. Installez x-ui 2.9+, Xray 26.x, WireGuard et wireproxy sur FR.
3. Copiez les scripts vers `/root/` sur RU.
4. Lancez `bash pro-final-master.sh` (`SSHPASS` selon `run-fr-from-ru.sh.example`).
5. Ne commitez pas `run-fr-from-ru.sh` avec un mot de passe réel.

### Placeholders

| Placeholder | Signification |
| --- | --- |
| `<RU_SERVER_IP>` | IPv4 publique du nœud d'entrée RU |
| `<FR_SERVER_IP>` | IPv4 publique de l'hôte France |
| `<FR_WG_IP>` | IP WireGuard interne de FR |
| `<SUB_ID>` | id d'abonnement x-ui par utilisateur |
| `SSHPASS` | Mot de passe SSH FR — **variable d'environnement uniquement** |

---

## Niveau de qualité

- **22/22** dans `pro-final-audit.py`
- **19/19** dans `verify-pro.sh`
- WARP **0 ms** sur le panneau FR : normal (SOCKS local)

---

## Avant publication sur GitHub

Publiez **uniquement** ce dossier, pas le dépôt parent.

1. `sanitize-showcase-final.py` → **OK**
2. Pas de `run-fr-from-ru.sh` (seulement `.example`)
3. Recherche d'IP/subIds réels — vide

---

## Crédits et licence

Documentation et automatisation : **Timur Valerievich**, portfolio.

**Tous droits réservés.** © 2026 Timur Valerievich. Termes complets : [`LICENSE`](./LICENSE).
