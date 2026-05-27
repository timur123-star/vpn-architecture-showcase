# VPN RU → Paris — витрина двухзвенной архитектуры

Продакшен-ориентированный референс **двухзвенного VPN**: клиенты подключаются только к **входу в РФ**;
зарубежный трафик балансируется на **транзит Paris (FR)** и выходит через **Cloudflare WARP**
(wireproxy). Репозиторий обезличен — без реальных IP, доменов, ключей и персональных данных.

`Xray` · `3x-ui / x-ui 2.9` · `WireGuard` · `VLESS Reality` · `Hysteria2` · `Trojan` · `Python 3`

[![License](https://img.shields.io/badge/license-All%20rights%20reserved-c4302b.svg)](./LICENSE)
[![Xray](https://img.shields.io/badge/Xray-26.x-1e88e5)](https://github.com/XTLS/Xray-core)
[![WireGuard](https://img.shields.io/badge/WireGuard-tunnel-88171a?logo=wireguard&logoColor=white)](https://www.wireguard.com)
[![Python](https://img.shields.io/badge/automation-Python%203-3776ab?logo=python&logoColor=white)](https://www.python.org)

**Языки:** [English](./README.md) · [Русский](./README.ru.md) · [Español](./README.es.md) · [Français](./README.fr.md) · [Отчёт о работах](./DELIVERY_REPORT.md)

---

## О проекте

Репозиторий описывает **реальную двухзвенную схему VPN** для пользователей в России: низкая
задержка до входа, устойчивость под DPI и **выход в Paris** через WARP. Публикация — **портфолио /
архитектурная витрина**: все чувствительные значения заменены плейсхолдерами (`<RU_SERVER_IP>`,
`<FR_WG_IP>`, `<YOUR_REALITY_PUBLIC_KEY>` и т.д.).

Включена автоматизация, использованная в продакшене: прокси подписок для Hiddify, синхронизация
Paris-outbound, исправления утечек маршрутизации, добавление клиентов x-ui, hardening и аудит на
22 проверки.

> **Дисклеймер.** Это **не** коммерческий VPN-сервис. Плейсхолдеры не являются рабочими
> учётными данными. Разворачивайте только на своей инфраструктуре. Учитывайте безопасность и
> законодательство. Автор документации — **Тимур Валерьевич**.

> **Контекст.** Reality под маской **VK** на 443, резервный **WireGuard UDP 443** между серверами,
> балансировщик **BRUTAL** по пяти каналам в Paris. Подробный отчёт — [`DELIVERY_REPORT.md`](./DELIVERY_REPORT.md).

---

## Содержимое

### Архитектура

```
[Клиент — Hiddify / v2rayN и др.]
        │  TCP/UDP: 443, 8442, 8443
        ▼
[RU  <RU_SERVER_IP>]   x-ui + Xray
        │  RU-сайты (.ru, VK, Яндекс…) → direct
        │  Global / Google / AI → балансировщик BRUTAL
        ▼
[FR  <FR_SERVER_IP> / WG <FR_WG_IP>]   x-ui + wireproxy → WARP
        ▼
[Интернет — выход Cloudflare WARP]
```

Отдельная «парижская подписка» клиентам не выдаётся — Paris только транзит и exit.

### Вход (RU)

| Порт | Протокол | Назначение |
| --- | --- | --- |
| **443** | VLESS + Reality + Vision | Маскировка под **VK** (`www.vk.ru`) |
| **8442** | Trojan TLS | Резерв TCP/TLS |
| **8443** | Hysteria2 (UDP) | Обход TCP-DPI |
| **8444** | VLESS Reality XHTTP | Отключён в шаблоне |

### Транзит RU → Paris

Пять исходящих каналов, балансировщик **BRUTAL** (`leastPing`, observatory ~20 с):

1. WireGuard backbone (`wg-fr`, UDP 51820)
2. WireGuard UDP **443** (`wg-fr-443`) — путь «под whitelist»
3. VLESS Reality Vision → `<FR_WG_IP>:443`
4. Hysteria2 → FR:8443
5. Trojan TLS → FR:8442

**Fallback:** WireGuard backbone.

### Подписки

- **`x-ui-sub-proxy`** на порту **80** добавляет Reality `pbk` и `flow=xtls-rprx-vision` для Hiddify.
- Формат: `http://<RU_SERVER_IP>/sub/<SUB_ID>#<SUB_ID>`.

### Маршрутизация

- Убрано `geoip:ru → direct` (утечка Google/Gemini в РФ).
- Цели Paris — **внутренний WG IP** `<FR_WG_IP>`.
- Примеры: [`ru-routing.example.json`](./ru-routing.example.json), [`fr-config.example.json`](./fr-config.example.json).

### Эксплуатация

| Скрипт | Назначение |
| --- | --- |
| `pro-final-master.sh` | Применение: sysctl, UFW, WG, подписки, маршруты, аудит |
| `pro-final-audit.py` | 22 проверки |
| `verify-pro.sh` | 19 shell-проверок |
| `test-reality.sh` | Локальный тест Reality (ожидается 204) |
| `vpn-watchdog.sh` | Периодический health-check |

---

## Структура репозитория

См. дерево файлов в [английском README](./README.md#repository-layout) — имена файлов
идентичны; отчёт о работах только на русском: `DELIVERY_REPORT.md`.

---

## Быстрый старт

### Проверка обезличивания (перед push)

Из **корня** монорепозитория:

```bash
py -3 scripts/sanitize-showcase-final.py
```

Должно быть: `OK: showcase fully anonymized`.

### Развёртывание

1. Замените все плейсхолдеры на **свои** IP, ключи, UUID, пароли.
2. Установите x-ui 2.9+, Xray 26.x, WireGuard, wireproxy на FR.
3. Скопируйте файлы в `/root/` на RU.
4. `bash pro-final-master.sh` (для FR — `SSHPASS` по примеру `run-fr-from-ru.sh.example`).
5. Не коммитьте `run-fr-from-ru.sh` с реальным паролем.

### Плейсхолдеры

| Плейсхолдер | Смысл |
| --- | --- |
| `<RU_SERVER_IP>` | Публичный IPv4 входа в РФ |
| `<FR_SERVER_IP>` | Публичный IPv4 FR |
| `<FR_WG_IP>` | Внутренний WG-адрес FR |
| `<SUB_ID>` | id подписки x-ui на пользователя |
| `SSHPASS` | Пароль SSH на FR — **только env** |

---

## Планка качества

- **22/22** в `pro-final-audit.py`
- **19/19** в `verify-pro.sh`
- WARP **0 ms** на FR в панели — норма (локальный SOCKS)

---

## Перед публикацией на GitHub

Публикуйте **только** эту папку, не родительский репозиторий.

1. `sanitize-showcase-final.py` → **OK**
2. Нет `run-fr-from-ru.sh` (только `.example`)
3. Grep по реальным IP/subId — пусто

---

## Автор и лицензия

Документация и автоматизация — **Тимур Валерьевич**, портфолио. Плейсхолдеры в git не
являются продакшен-секретами.

**Все права защищены.** © 2026 Тимур Валерьевич. Полный текст — [`LICENSE`](./LICENSE).
