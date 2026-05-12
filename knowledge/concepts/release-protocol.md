---
title: "Release Protocol — Auto-deploy через GitHub Actions, manual fallback"
aliases: [deploy, ci-cd, release, deploy.sh, github-actions]
tags: [deploy, ops, multi-agent, ci-cd]
sources:
  - "CLAUDE.md cleanup 2026-05-05"
  - "CI/CD setup 2026-05-08 (Parts 1-3)"
created: 2026-05-05
updated: 2026-05-08
---

# Release Protocol — Auto-deploy через GitHub Actions

**Канонический путь (с 2026-05-08):** feature-ветка → Pull Request → merge в `main` → **GitHub Actions автоматически вызывает `./deploy.sh`** + smoke test + Telegram-алерт при failure. Никаких ручных шагов.

**`origin/main` — единственный источник истины** для VPS. Любой обход этого правила = потеря работы.

## Auto-deploy pipeline (default)

`.github/workflows/deploy.yml`:

1. **Trigger:** `on: push: branches: [main]` (плюс `workflow_dispatch` для ручного retry).
2. **Защиты:**
   - `concurrency: deploy-prod, cancel-in-progress: false` — параллельный deploy невозможен.
   - `if: github.ref == 'refs/heads/main'` — двойная защита, deploy не из main физически блокирован даже через workflow_dispatch.
   - All actions pinned by SHA (supply-chain hardening).
3. **Шаги:** checkout main → ssh-agent (`VPS_SSH_PRIVATE_KEY`) → ssh-keyscan → `./deploy.sh` → smoke test (`/health` + `journalctl --since='2 minutes ago' | grep -iE 'error|critical'`) → on failure: Telegram-алерт в admin-chat (`417002669`) через `TG_ADMIN_BOT_TOKEN`.

5 GitHub Secrets обязательны: `VPS_SSH_PRIVATE_KEY`, `VPS_HOST`, `VPS_USER`, `TG_ADMIN_BOT_TOKEN`, `TG_ADMIN_CHAT_ID`. Полная документация по setup, rotation, rollback — `.github/workflows/SETUP.md` в репо.

## Что делать как разработчику

```bash
# 1. Работай в feature-ветке как обычно:
git checkout -b claude/<scope>-<id>
# ...правки, тесты...
git push origin claude/<scope>-<id>

# 2. Открой PR:
gh pr create

# 3. После approval/merge — НИЧЕГО не делай. Watch deploy:
gh run watch --repo sharkovvlad/noms-bot

# 4. На failure — Telegram-алерт прилетит в admin-chat. Открой Actions tab,
#    смотри логи, фикси, push новый PR.
```

## Manual fallback — `./deploy.sh` вручную (emergency only)

Когда нужен ручной deploy:
- GitHub Actions broken (rare).
- Нужен deploy конкретного non-main коммита для проверки гипотезы.
- Hotfix когда срочно и нет времени на PR review.

В этих случаях — старый протокол ниже. **Все остальные сценарии — через Actions.**

## Почему это критично

`deploy.sh` запускает `rsync` локального дерева на VPS. Он:
- **не знает** про git-ветку,
- **не проверяет**, что файлы зафиксированы,
- **затирает** на VPS то, что отличается от локальной копии (включая файлы, которые ваша ветка вообще не трогала).

Параллельно работают несколько агентов в разных worktrees. Если один агент запустит `./deploy.sh` из своей feature-ветки:

1. **Незамёрженный WIP уезжает в прод**, обходя review.
2. **Затирается код другого агента**, чей PR уже вмёржен в `main` и задеплоен. Файлы, которые ваша ветка не трогала, всё равно откатываются до состояния вашего worktree (race condition по rsync).
3. **Расхождение local ↔ GitHub ↔ VPS** — нарушение чек-листа консистентности.

## Разрешённый порядок (только так)

1. PR смержен в `main` (через `gh pr merge` или GitHub UI).
2. В **основном клоне** репо (НЕ worktree): `git checkout main && git pull --ff-only origin main`.
3. Проверить:
   ```bash
   git status                                                      # должен быть clean
   git rev-parse HEAD                                              # совпадает с GitHub main
   gh api repos/<owner>/<repo>/commits/main --jq .sha              # сверка
   ```
4. `./deploy.sh`.

## Запрещено

- `./deploy.sh` из веток `claude/*`.
- `./deploy.sh` из любых worktrees (`.claude/worktrees/...`).
- `./deploy.sh` при `git status` с незакоммиченными правками.
- «Срочный hotfix напрямую на VPS через `ssh + sed`» в обход git — следующий `deploy.sh` затрёт фикс. Если правда срочно: PR с `--admin merge` + deploy из `main`.

## Исключение — редактирование `.env` на VPS

`/home/taskbot/noms/.env` **не в git**, rsync его не трогает. Допустимо править прямо на VPS через `ssh + sed`. **Обязательно** после правки:

```bash
systemctl restart noms-webhooks noms-cron     # ОБА сервиса, не один
```

systemd читает env только при старте. Если перезапустить только webhooks — cron остаётся со старыми переменными в памяти. Инцидент 27.04 22:15 MSK — именно по этой причине.

## Если агент работает в worktree

Типичный случай: основной клон с `main` checkout'нут где-то ещё, поэтому `gh pr merge` локально падает с `'main' is already used by worktree at ...` (lesson 04.05).

**Workaround:** агент **мержит PR через GitHub API**, не локально:

```bash
gh api -X PUT repos/<owner>/<repo>/pulls/<n>/merge -f merge_method=merge
```

Возвращает `{merged:true, sha:...}` без локального checkout. Но **деплой агент не делает** — это задача тимлида (или следующего агента) из основного клона `main`.

## SQL-миграции — отдельный lifecycle от code deploy

**Принцип:** SQL и Python имеют разные точки применения. `deploy.sh` (rsync файлов на VPS) не трогает БД. Миграции применяются отдельно.

| Артефакт | Как применяется | Когда |
|---|---|---|
| Python / config файлы | **Автоматически** через GitHub Actions при merge в `main` | Сразу после merge |
| `migrations/NNN_*.sql` | psycopg2 → Supabase pooler ([[access-credentials]] Recipe 1) | До flip флага feature функциональности |
| `app_constants` feature flag flip | psycopg2 UPDATE, **с явным approval тимлида в разговоре** | После migration apply + после ручного UAT |
| `.env` на VPS | `ssh + sed` + `systemctl restart noms-webhooks noms-cron` | Только когда вне-git секреты меняются |

### Phase-style migration workflow (canonical с Phase 4)

1. Агент строит миграцию через builder script (stale-base snapshot live прода через `pg_get_functiondef`, см. [[safe-create-or-replace-recipe]]).
2. Файл миграции коммитится в PR-ветку — для аудита (PR review видит логику).
3. Миграция применяется через psycopg2 → verify через `pg_get_functiondef` + spot-check rows. Допустимо как до, так и после merge PR, но обязательно до flip флага feature-функциональности.
4. PR merge → код деплоится через GitHub Actions.
5. Flag flip — отдельный шаг, требует явного approval тимлида в разговоре. Migration apply = безопасное backward-compatible изменение схемы/RPC; flag flip = переключение прод-трафика на новый код-путь.

### Запрещено

- **Полагаться на `./deploy.sh` для применения миграций** — он только rsync файлов, БД не меняет. Файл миграции в `main` без psycopg2-apply = «висящая» миграция, бот ломается («код ожидает новой колонки/RPC, в БД её нет»).
- **`UPDATE app_constants ... SET value='true'` без явного approval тимлида** в текущем разговоре.
- **`CREATE OR REPLACE FUNCTION` с базой из git-файла** — всегда `pg_get_functiondef` ЖИВОГО прода в момент применения (см. [[safe-create-or-replace-recipe]] — 3 stale-base regression incidents).

## Pre-merge sanity check (PR review)

GitHub `mergeable=true` ≠ семантически безопасный merge (lesson 04.05, PR #6). Если PR-ветка ушла от main до свежей работы в main, diff PR vs новый main может **удалить** эти изменения.

**Перед `gh pr merge`:**

```bash
git diff origin/main..origin/<pr-branch> --stat
```

Большие отрицательные числа в файлах **не из scope PR** = семантический откат. Закрыть + cherry-pick на свежий main или rebase.

## Coordination правила (multi-agent)

- Каждый агент — своя ветка `claude/<scope>-<id>`. **Rebase перед commit** (не перед merge): `git fetch origin main && git rebase origin/main`. Force-push только `--force-with-lease`.
- Перед стартом проверь свежие [handover'ы](../handover/) и [daily logs](../daily/) — другой агент мог сегодня тронуть тот же файл.
- **rsync `deploy.sh` на VPS может откатить файлы**, если две ветки трогали одно — координация через тимлида обязательна.
- SQL-миграции обычно не пересекаются с Python другого агента. Но Python-handlers, `webhook_server.py`, `dispatcher/forward.py` — высокая вероятность конфликта, требует ребейза перед merge.

## Lesson 2026-05-08: stale worktree + git commit -a → catastrophic откат

### Что произошло

Агент работал в worktree, созданном неделей раньше (между созданием и моментом commit'а в main вмёржилось ~30 PR от других агентов: миграции 174-190, handler-фиксы, тесты). Агент правил **только** один файл (`CLAUDE.md`). Сделал `git commit + git push -u origin <branch>`. Diff vs main: **−10 005 строк** в **33 файлах**, которые он не трогал — миграции/handlers/тесты других агентов.

Если бы PR смерджили → откатилась бы вся работа за 8 дней. Catastrophic risk: discrete (либо случилось, либо нет), big (откат недели работы), stealthy (diff `+180/−366` визуально как нормальный refactor; чтобы заметить — надо смотреть **в каких файлах** удаления).

### Корневая причина

`git commit` сохраняет **snapshot всего worktree**, не «только что я недавно правил». Если worktree устарел — в snapshot'е попадают **старые** версии всех файлов, включая те которые ты не трогал. Когда GitHub применяет такой PR через merge, он **молча заменяет** живые файлы старыми. Семантический откат без конфликтов и без предупреждений.

### Спасло

Правило sanity-check, которое сам же агент только что вписал в этот документ:

```bash
git diff origin/main..HEAD --stat
```

При первом push увидел `33 files changed, 10005 deletions` → стоп → `git fetch + rebase origin/main` → diff схлопнулся до правильного scope (1 файл, +180/−366 = нормальный CLAUDE.md restructure) → `git push --force-with-lease`. Никто не пострадал.

### 3 правила защиты (закреплены в global CLAUDE.md §12)

1. **Rebase перед commit, не перед merge.** `git fetch origin main && git rebase origin/main` — снапшот worktree должен браться от свежего main, не от устаревшего.
2. **Sanity-check diff перед push.** `git diff origin/main..HEAD --stat` — если в diff файлы, не упомянутые в commit message, или удаления >500 строк в чужих файлах → стоп.
3. **Force-push только `--force-with-lease`.** Никогда не `--force` без `--with-lease`. Lease защищает от перезаписи параллельной работы другого агента.

### Что система автоматизирует (PR #32, ждёт merge)

3 защиты реализованы в PR #32 (стэкован поверх PR #31 с `deploy.yml` + базовым `pre-push.sh`):

- **Защита 1 — CI sanity-check workflow** (`.github/workflows/pr-sanity.yml` + `.github/scripts/pr_sanity_audit.py`). Триггер `pull_request: [opened, synchronize, reopened]`. Чеки:
  1. Total deletions > 5000 (configurable через repo variable `PR_SANITY_TOTAL_DELETIONS_LIMIT`).
  2. Удаление любого `migrations/*.sql` (миграции forward-only, всегда suspicious).
  3. Удаление файлов без mention в PR title/body и без ключевых слов «delete/remove/drop/cleanup».
  4. Удаления > 500 строк (configurable `PR_SANITY_PER_FILE_DELETIONS_LIMIT`) в файле не из scope title/body.

  При флаге → fail status check + идемпотентный PR comment (обновляется при каждом push, не плодится). На GitHub Free required-status-check для приватного репо не enforce'ится → не блокирует merge физически, но видим в UI PR.

- **Защита 2 — stale-worktree pre-push hook** (расширение `.github/hooks/pre-push.sh` +82 строки). Перед каждым push в feature-ветку считает `git rev-list --count $(git merge-base HEAD origin/main)..origin/main`:
  - > 10 коммитов — warning, push продолжается.
  - > 50 коммитов — block (override `ALLOW_STALE_PUSH=1 git push ...`).

  Тихо skip при недоступном remote (offline). Пороги настраиваются через env `STALE_WARN_THRESHOLD` / `STALE_BLOCK_THRESHOLD`. Hook требует one-time локальной установки (`git config core.hooksPath .github/hooks`) — см. `.github/HOOKS.md`.

- **Защита 3 — nightly mergeability check** (`.github/workflows/nightly-pr-audit.yml` + `.github/scripts/nightly_pr_audit.py`). Cron `0 3 * * *` UTC + `workflow_dispatch`. Через `gh pr list` обходит все open PR, для каждого `git diff --numstat` vs base. Suspicious (deletions > 5000 ИЛИ удалённые migrations) → один аггрегированный Telegram-alert в admin chat `417002669`. Тишина при чистом state — не шумит. Использует те же secrets что `deploy.yml` (`TG_ADMIN_BOT_TOKEN`, `TG_ADMIN_CHAT_ID`).

**Defense-in-depth логика:**
- Защита 2 ловит до создания PR (push в feature-ветку).
- Защита 1 ловит при создании / push в PR (серверный аудит).
- Защита 3 ловит уже-существующие PR, созданные до того, как защита 1 появилась в main (backup).

## Related Concepts

- [[concepts/n8n-self-hosting]] — VPS infra
- [[concepts/specs-vs-reality-ground-truth]] — local vs live truth priority
- `.github/workflows/deploy.yml` + `.github/workflows/SETUP.md` (в noms-bot репо) — реализация auto-deploy и operations guide.
