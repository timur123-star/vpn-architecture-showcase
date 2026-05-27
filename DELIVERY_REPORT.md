# Отчёт о выполненных работах: VPN RU → Paris (2-tier)

**Дата:** май 2026  
**Заказчик:** внутренняя эксплуатация (5 пользователей)  
**Статус:** RU — production-ready, автоматический аудит **22/22 OK**, `verify-pro.sh` **19/19 OK**

---

## 1. Цель и архитектура

**Задача:** двухзвенный VPN для пользователей в РФ: низкая задержка до входа в РФ, выход в интернет через Paris (FR) с обходом DPI и устойчивостью при ограничениях операторов.

```
[Клиент Hiddify, РФ]
        │  TCP/UDP: 443, 8442, 8443
        ▼
[RU <RU_SERVER_IP>]  x-ui + Xray 26.5.9
        │  RU-сайты (.ru, VK, Яндекс…) → direct
        │  Остальное → балансировщик BRUTAL (5 каналов)
        ▼
[FR <FR_SERVER_IP> / WG <FR_WG_IP>]  x-ui + wireproxy (WARP)
        ▼
[Интернет, exit через Cloudflare WARP]
```

**Принцип:** клиенты подключаются **только к RU**; Paris — транзит и exit, не публикуется как отдельная точка входа для семьи.

---

## 2. Инфраструктура

| Узел | IP | Роль | Панель |
|------|-----|------|--------|
| RU (<HOSTNAME>) | <RU_SERVER_IP> | Вход, маршрутизация, подписки | x-ui 2.9.4, порт **50959** |
| FR (Paris) | <FR_SERVER_IP> / WG **<FR_WG_IP>** | Транзит, WARP-exit | x-ui, bridge-клиент `ru-bridge` |

**Доступ к администрированию:** SSH на RU по ключу Ed25519 (пароли/секреты панели и x-ui **не изменялись** в рамках отчёта — ротация на стороне заказчика).

---

## 3. RU-сервер: реализованный функционал

### 3.1. Входные протоколы (клиентские inbounds)

| Порт | Протокол | Назначение | Статус |
|------|----------|------------|--------|
| **443** | VLESS + Reality + Vision | Маскировка под **VK** (`www.vk.ru`, `spiderX=/`) | Включён |
| **8442** | Trojan TLS | Резерв TCP/TLS | Включён |
| **8443** | Hysteria2 UDP | Обход TCP-DPI | Включён |
| **8444** | VLESS Reality XHTTP (Yandex) | Проблемный inbound | **Отключён** (`enable=0`) |

На каждого пользователя: 3 активных учётки (443 + `_tj` + `_hy`) с общим `subId`.

### 3.2. Транзит RU → Paris (исходящие outbounds)

Пять параллельных путей в шаблоне Xray, балансировщик **BRUTAL** (`leastPing`, observatory 20s):

1. **PARIS — WireGuard Backbone** (`sendThrough` <RU_WG_IP>, UDP **51820**)
2. **PARIS — VLESS Reality Vision** → FR **<FR_WG_IP>:443** (внутри WG, не публичный IP)
3. **PARIS — VLESS Reality XHTTP** → FR:8444 (если ключи синхронизированы)
4. **PARIS — Hysteria2** → FR:8443
5. **PARIS — Trojan TLS** → FR:8442

**Fallback:** WireGuard Backbone.

### 3.3. WireGuard (магистраль)

| Туннель | Порт | Назначение |
|---------|------|------------|
| `wg-fr` | UDP **51820** | Основной RU↔FR (высокий трафик, handshake стабилен) |
| `wg-fr-443` | UDP **443** | Резерв «whitelist path» — трафик под видом HTTPS/443 между серверами |

Проверка: оба туннеля с актуальным `latest handshake`, тест выхода через WG — **HTTP 204** (Google).

### 3.4. Маршрутизация и DNS (исправления утечек)

**Было (проблема):** правило `geoip:ru → direct` отправляло трафик к Google/Gemini на российские CDN-IP в обход Paris — пользователи видели «как из России».

**Сделано:**
- Удалён `geoip:ru` из direct-правила.
- Direct только по **доменам** (`geosite:category-ru`, `.ru`, VK, Яндекс, Ozon, банки и т.д.).
- Явное правило: **Google, OpenAI, Microsoft, Netflix, соцсети, Gemini-домены** → `balancerTag: BRUTAL`.
- DNS: DoH (1.1.1.1, dns.google) для международных зон + `localhost` для RU.
- `domainStrategy: IPIfNonMatch`.

### 3.5. Сервис подписок (Hiddify)

**Проблема:** x-ui 2.9.4 на :<XUI_SUB_PORT> отдавал подписку без `pbk=` → Hiddify **502** / сломанный Reality.

**Решение:** отдельный `x-ui-sub-proxy` (Python), сборка ссылок из SQLite `/etc/x-ui/x-ui.db`:

- Порт **80**, URL: `http://<RU_SERVER_IP>/sub/{subId}#{subId}`
- В ссылках: `pbk`, `flow=xtls-rprx-vision`, `spx=/`, `sni=www.vk.ru`, пароли Trojan/Hysteria2 (`auth` для hy2)
- Имя профиля в `#fragment` из поля `comment` клиента

`subURI` в настройках x-ui: `http://<RU_SERVER_IP>/sub/`

### 3.6. Пользователи (5 клиентов)

| Отображаемое имя | subId (фрагмент URL) |
|------------------|----------------------|
| User_Desktop | `<SUB_ID>` |
| User_iOS_1 | `<SUB_ID>` |
| User_iOS_3 | `<SUB_ID>` |
| User_iOS_2 | `<SUB_ID>` |
| User_Android_1 | `<SUB_ID>` |

Клиенты заведены в **таблицу `clients` + `client_inbounds` + `client_traffics`** (видимость в панели x-ui 2.9), не только в JSON inbounds.

### 3.7. Reality / Hiddify (стабильность 443)

- Ключи Reality **не перегенерировались** (фиксированный `publicKey` в подписке).
- `spiderX=/`, SNI `www.vk.ru`.
- В подписке обязателен `flow=xtls-rprx-vision` (соответствие runtime x-ui).
- Самотест: `test-reality.sh` → **204** через локальный VLESS Reality.

### 3.8. Hardening RU

- `sysctl`: ip_forward, **BBR**, fq, rp_filter=0.
- **UFW:** 22, 80, 443/tcp, 443/udp, 8442–8443, 51820/udp, 50959.
- **fail2ban:** active.
- Cron: бэкап `x-ui.db` (14 дней).
- `vpn-watchdog` (cron */5): перезапуск критичных сервисов.
- Скрипты сопровождения в `/root/` (см. раздел 6).

---

## 4. FR-сервер (Paris): состояние по проекту

| Компонент | Назначение |
|-----------|------------|
| x-ui + inbounds 443/8442/8443/8444 | Приём трафика с RU (bridge UUID) |
| `wireproxy` → SOCKS **127.0.0.1:40000** | Exit через **Cloudflare WARP** |
| `wg-ru` / `wg-ru-443` | Приём WG с RU (51820 / 443 UDP) |
| Маршрутизация FR | Почти весь трафик → outbound `warp` |

**Примечание:** удалённый SSH с RU на FR периодически недоступен (таймаут/пароль); на работу клиентского VPN не влияет. Синхронизация ключей Paris: `sync-fr-paris.py` (при доступном SSH) или `fix-routing-paris.py` (локальные ключи из шаблона).

**WARP 0 ms в панели FR:** норма (локальный SOCKS на том же хосте).

---

## 5. Устранённые инциденты

| # | Симптом | Причина | Решение |
|---|---------|---------|---------|
| 1 | Hiddify 502 при обновлении подписки | Прокси :2097 → мёртвый :<XUI_SUB_PORT> | Sub-proxy из БД, порт 80 |
| 2 | Reality «красный», не коннектится | Подписка без `flow`, рассинхрон с сервером | `flow=xtls-rprx-vision` в sub + DB |
| 3 | Gemini/Google «как из России» | `geoip:ru → direct` | Убран geoip:ru, явный маршрут Google→BRUTAL |
| 4 | xray не стартовал | Несуществующие geosite (`category-ai`, `geosite:ru`) | Корректные списки geosite |
| 5 | 4-й клиент не в панели | Только JSON inbounds, без `clients` | `add-xui-client.py` + `fix-masha-panel.py` |
| 6 | Неверный формат URL подписки | `:80` и без `#subId` | `:80`, формат как у заказчика |
| 7 | 8444 Yandex | `invalid public_key`, нестабилен | Inbound отключён |
| 8 | DNS geosite в template | EOF / падение xray | Простой DNS + DoH в fix-routing |

---

## 6. Автоматизация и артефакты

**На сервере RU (`/root/`):**

| Скрипт | Назначение |
|--------|------------|
| `pro-final-audit.py` | 22 проверок production |
| `verify-pro.sh` | Быстрый smoke-test |
| `fix-routing-paris.py` | Маршрутизация RU→Paris без SSH на FR |
| `sync-fr-paris.py` | Синхронизация ключей FR → outbounds |
| `sub-proxy-standalone.py` | Подписки :80 |
| `add-xui-client.py` | Новый пользователь (панель + 3 протокола) |
| `fix-hiddify-connect.py` | Стабильный Reality 443 |
| `check-whitelist-paths.sh` | DPI/whitelist пути |
| `test-reality.sh` | Self-test Reality |
| `list-sub-links.py` | Список URL подписок |

**Репозиторий:** `vpn-ru-paris` (локально), документация: `PRO_FINAL_REPORT.md`, `DELIVERY_REPORT.md`, `ANALYSIS.md`.

**Systemd:** `x-ui-sub-proxy.service` (порт 80), `wg-fr`, `wg-fr-443`.

---

## 7. Результаты верификации (фактические)

```
pro-final-audit.py  → 22 OK / 0 FAIL
verify-pro.sh       → 19 OK / 0 FAIL
xray -test          → Configuration OK
wg-fr / wg-fr-443   → handshake active
WG exit test        → HTTP 204
5 subscriptions   → vless+trojan+hysteria2, pbk+flow present
```

---

## 8. Ограничения и рекомендации

1. **«Белый список оператора»** (беспилотная опасность) — не равен «белому IP» из Habr/IANA. Гарантий нет; при ограничениях первый узел для проверки: **RU VLESS Reality VK 443**.
2. **IP RU** `<RU_SERVER_IP>` — публичный маршрутизируемый (`is_global: true`), в списки МТС/Мегафон не входит; работает маскировка трафика, не «регистрация IP».
3. **FR SSH** — восстановить доступ для `sync-fr-paris.py` и проверки WARP-exit country.
4. **Ротация секретов** — пароли x-ui, Trojan, FR SSH — по политике заказчика (в отчёт не включены).
5. **8444** — не включать без отдельной настройки Reality XHTTP.

---

## 9. Инструкция для пользователя (кратко)

1. Hiddify → добавить подписку по персональному URL (`http://<RU_SERVER_IP>/sub/...#...`).
2. Режим работы: узел **balance** (автовыбор пути в Paris).
3. При жёстких ограничениях LTE: вручную **RU VLESS Reality VK 443**, затем Hysteria2 / Trojan.
4. Проверка выхода: https://ifconfig.me — не должен показывать домашний RU IP и не `<RU_SERVER_IP>`.

---

## 10. Итог

Развёрнута и отлажена **production-конфигурация 2-tier VPN**: вход в РФ на Xray с тремя клиентскими протоколами, магистраль RU→Paris по WG и протоколам с балансировкой, exit через WARP на FR. Устранены ошибки подписок, маршрутизации и отображения клиентов. Система покрыта автоматическими проверками и скриптами сопровождения.

**Готовность к эксплуатации:** RU — **да** (по результатам аудита). FR — **да** (по архитектуре и историческим проверкам; периодический контроль WARP рекомендуется после восстановления SSH).
