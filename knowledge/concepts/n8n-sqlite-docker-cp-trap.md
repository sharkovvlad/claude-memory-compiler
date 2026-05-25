---
title: "n8n SQLite + `docker cp` ownership trap"
aliases: [docker-cp-trap, sqlite-readonly, n8n-database-readonly]
tags: [n8n, docker, vps, ops, infra]
sources:
  - "daily/2026-05-19.md Stage 6 incident"
created: 2026-05-19
updated: 2026-05-19
---

# n8n SQLite + `docker cp` ownership trap

> ⚠️ **status: legacy-n8n** — описывает n8n-механику. Соответствующая фича/target мигрирована в Python (Variant B cutover, 2026-04...05). Документ полезен для понимания n8n-эры; новые правки идут в Python handlers.

**TL;DR:** `docker cp <host>:file <container>:/path/database.sqlite` копирует файл с ownership хост-юзера (`root:root` если делаешь как root). Внутри контейнера n8n работает как `node:node`. Файл становится unwritable → SQLite возвращает `SQLITE_READONLY` → n8n уходит в crash loop каждые ~30 сек. Все workflows встают. Молчаливо.

## Симптомы

- Бот перестаёт распознавать еду (`03_AI_Engine`), Location / Onboarding (если ещё в n8n) тоже падают.
- `curl http://127.0.0.1:8443/telegram/health` отдаёт `503` с `"n8n":false`.
- `docker logs noms-n8n` крутится с `SqliteError: SQLITE_READONLY: attempt to write a readonly database` каждые 30 сек.
- `systemctl status noms-n8n` (или docker compose ps) показывает контейнер постоянно «Restarting».

## Root cause

`docker cp` копирует UID/GID **хост-системы** в namespace контейнера. Если на хосте ты `root` (uid=0), файл внутри контейнера становится owned by uid=0. n8n внутри контейнера работает как `node` (обычно uid=1000), не имеет write-доступа к файлу, который owned by root.

SQLite пытается приобрести exclusive lock для писем → fails → `SQLITE_READONLY` → не может стартовать → restart loop.

## Fix (live, минута)

```bash
ssh root@89.167.86.20
docker exec --user root noms-n8n chown node:node /home/node/.n8n/database.sqlite
docker restart noms-n8n
docker logs noms-n8n --tail 50  # должен подняться без SQLITE_READONLY
```

## Правильные patterns (как НЕ ловить trap)

### Pattern A — `docker exec` с sqlite3 внутри контейнера (preferred)

Не выноси файл наружу. Если в контейнере нет sqlite3 CLI — установи:
```bash
docker exec --user root noms-n8n apt-get update
docker exec --user root noms-n8n apt-get install -y sqlite3
docker exec --user node noms-n8n sqlite3 /home/node/.n8n/database.sqlite "UPDATE workflow_entity SET active=0 WHERE id='T9753zO3ZyiYsgkp';"
```

Ownership наследуется от `--user node` → файл остаётся `node:node`.

### Pattern B — `docker cp` + immediate `chown`

Если уже сделал `docker cp` (например для бэкапа на хост и обратно):
```bash
docker cp ./n8n.db noms-n8n:/home/node/.n8n/database.sqlite
docker exec --user root noms-n8n chown node:node /home/node/.n8n/database.sqlite
docker restart noms-n8n
```

`chown` сразу после `cp`, до restart. Иначе сам restart не поможет — файл всё равно `root:root`.

### Pattern C — `docker cp` через sidecar volume

Для bulk-операций (несколько SQL UPDATE'ов, импорт/экспорт):
```bash
# Запустить временный sidecar с тем же volume:
docker run --rm -v noms-n8n_data:/data --user node:node \
  -v $(pwd)/n8n.db:/tmp/n8n.db \
  alpine:latest cp /tmp/n8n.db /data/database.sqlite
```

Используется `--user node:node` → файл наследует ownership правильно.

## Когда это случается на практике

- Деактивация workflow через прямой SQL `UPDATE workflow_entity SET active=0` (когда n8n API отказывается, например для legacy workflow без ownership).
- Восстановление БД из бэкапа.
- Bulk renumber / cleanup workflows перед миграцией.

Если делаешь это редко — не помнишь о trap. Поэтому **зафиксировано как durable KB**.

## Lesson 2026-05-19 (этот файл)

Я (агент Stage 6) деактивировал `10_Payment` через копию БД на хост + правка + `docker cp` обратно. Не chown'ил. N8N упал на 1+ час во время финальной фазы Stage 6. Eat AI Engine / Location / Onboarding. Восстановил через chown + restart.

Stage 6 PR'ы при этом не виноваты — incident произошёл строго на инфраструктурной операции, не на коде Python handler'а.

## Related

- [[concepts/n8n-self-hosting]] — VPS infra, Docker compose setup
- [[concepts/n8n-data-flow-patterns]] — Safe PUT recipe (когда n8n API работает, его и используем; SQLite — emergency-only)
