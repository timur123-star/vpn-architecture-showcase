# VPN RU → Paris — vitrina de arquitectura de dos saltos

Referencia orientada a producción de un **VPN de dos niveles**: los clientes se conectan solo al
**nodo de entrada en RU**; el tráfico extranjero se equilibra hacia el **tránsito en París (FR)**
y sale por **Cloudflare WARP** vía wireproxy. Repositorio anonimizado — sin IPs, dominios, claves
ni datos personales reales.

`Xray` · `3x-ui / x-ui 2.9` · `WireGuard` · `VLESS Reality` · `Hysteria2` · `Trojan` · `Python 3`

[![License](https://img.shields.io/badge/license-All%20rights%20reserved-c4302b.svg)](./LICENSE)
[![Xray](https://img.shields.io/badge/Xray-26.x-1e88e5)](https://github.com/XTLS/Xray-core)
[![WireGuard](https://img.shields.io/badge/WireGuard-tunnel-88171a?logo=wireguard&logoColor=white)](https://www.wireguard.com)
[![Python](https://img.shields.io/badge/automation-Python%203-3776ab?logo=python&logoColor=white)](https://www.python.org)

**Idiomas:** [English](./README.md) · [Русский](./README.ru.md) · [Español](./README.es.md) · [Français](./README.fr.md)

---

## Sobre el proyecto

Este repositorio documenta un **VPN de dos saltos** desplegado para usuarios en Rusia: baja
latencia al punto de entrada, rutas resilientes bajo DPI y **salida en París** mediante WARP. Se
publica como **portafolio / vitrina de arquitectura**: cada valor sensible se sustituye por
marcadores como `<RU_SERVER_IP>`, `<FR_WG_IP>` y `<YOUR_REALITY_PUBLIC_KEY>`.

Incluye automatización usada en producción: proxy de suscripciones para Hiddify, sincronización de
outbounds París, correcciones anti-fugas de enrutamiento, alta de clientes en x-ui, hardening y
auditoría de 22 puntos.

> **Aviso legal.** **No** es un servicio VPN alojado. Los marcadores no son credenciales válidas.
> Despliega solo en infraestructura propia. Revisa seguridad y legislación local.
> Diseñado y documentado por **Timur Valerievich**.

> **Contexto.** Reality con aspecto **VK** en el puerto 443, **WireGuard UDP 443** opcional entre
> servidores y balanceador **BRUTAL** con cinco canales a París. Informe completo (ruso):
> [`DELIVERY_REPORT.md`](./DELIVERY_REPORT.md).

---

## Contenido

### Arquitectura

```
[Cliente — Hiddify / v2rayN / etc.]
        │  TCP/UDP: 443, 8442, 8443
        ▼
[RU  <RU_SERVER_IP>]   x-ui + Xray
        │  Sitios RU (.ru, VK, Yandex…) → direct
        │  Global / Google / IA → balanceador BRUTAL
        ▼
[FR  <FR_SERVER_IP> / WG <FR_WG_IP>]   x-ui + wireproxy → WARP
        ▼
[Internet — salida Cloudflare WARP]
```

Los clientes no reciben una suscripción «París» aparte — París es solo tránsito y salida.

### Entrada (RU)

| Puerto | Protocolo | Función |
| --- | --- | --- |
| **443** | VLESS + Reality + Vision | Disfraz **VK** (`www.vk.ru`) |
| **8442** | Trojan TLS | Reserva TCP/TLS |
| **8443** | Hysteria2 (UDP) | Evitar DPI TCP |
| **8444** | VLESS Reality XHTTP | Desactivado en la plantilla |

### Tránsito RU → París

Cinco outbounds en paralelo, balanceador **BRUTAL** (`leastPing`, observatory ~20 s):

1. WireGuard backbone (`wg-fr`, UDP 51820)
2. WireGuard UDP **443** (`wg-fr-443`)
3. VLESS Reality Vision → `<FR_WG_IP>:443`
4. Hysteria2 → FR:8443
5. Trojan TLS → FR:8442

**Reserva:** WireGuard backbone.

### Suscripciones

- **`x-ui-sub-proxy`** en el puerto **80** inyecta `pbk` de Reality y `flow=xtls-rprx-vision`.
- Formato: `http://<RU_SERVER_IP>/sub/<SUB_ID>#<SUB_ID>`.

### Enrutamiento

- Eliminado `geoip:ru → direct` (fugas de Google/Gemini a CDN rusos).
- Objetivos París con IP interna WG `<FR_WG_IP>`.
- Ejemplos: [`ru-routing.example.json`](./ru-routing.example.json), [`fr-config.example.json`](./fr-config.example.json).

### Operaciones

| Script | Propósito |
| --- | --- |
| `pro-final-master.sh` | Aplicación integral: sysctl, UFW, WG, proxy, rutas, auditoría |
| `pro-final-audit.py` | 22 comprobaciones |
| `verify-pro.sh` | 19 comprobaciones shell |
| `test-reality.sh` | Prueba local Reality (HTTP 204) |
| `vpn-watchdog.sh` | Health-check periódico |

---

## Estructura del repositorio

Ver el árbol en el [README en inglés](./README.md#repository-layout). El informe de entrega está
en ruso: `DELIVERY_REPORT.md`.

---

## Primeros pasos

### Verificar anonimización (antes del push)

Desde la raíz del monorepo:

```bash
py -3 scripts/sanitize-showcase-final.py
```

Debe mostrar: `OK: showcase fully anonymized`.

### Despliegue

1. Sustituye todos los marcadores por **tus** IPs, claves, UUID y contraseñas.
2. Instala x-ui 2.9+, Xray 26.x, WireGuard y wireproxy en FR.
3. Copia los scripts a `/root/` en RU.
4. Ejecuta `bash pro-final-master.sh` (`SSHPASS` según `run-fr-from-ru.sh.example`).
5. No subas `run-fr-from-ru.sh` con contraseña real.

### Marcadores

| Marcador | Significado |
| --- | --- |
| `<RU_SERVER_IP>` | IPv4 pública del nodo de entrada en RU |
| `<FR_SERVER_IP>` | IPv4 pública del host en Francia |
| `<FR_WG_IP>` | IP interna WireGuard de FR |
| `<SUB_ID>` | id de suscripción x-ui por usuario |
| `SSHPASS` | Contraseña SSH FR — **solo variable de entorno** |

---

## Nivel de calidad

- **22/22** en `pro-final-audit.py`
- **19/19** en `verify-pro.sh`
- WARP **0 ms** en el panel FR es normal (SOCKS local)

---

## Antes de publicar en GitHub

Publica **solo** esta carpeta, no el repositorio padre.

1. `sanitize-showcase-final.py` → **OK**
2. Sin `run-fr-from-ru.sh` (solo `.example`)
3. Búsqueda de IPs/subIds reales — vacía

---

## Créditos y licencia

Documentación y automatización: **Timur Valerievich**, pieza de portafolio.

**Todos los derechos reservados.** © 2026 Timur Valerievich. Términos completos en [`LICENSE`](./LICENSE).
