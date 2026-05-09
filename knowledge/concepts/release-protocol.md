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

### Что система автоматизирует (в работе)

- **CI sanity-check workflow** (`.github/workflows/pr-sanity.yml`) — для каждого PR проверять «удаление >500 строк в файлах не из commit message» → status check `⚠️ Suspicious diff`. Не enforces в Free, но визуально шумит и виден в UI PR.
- **Stale-worktree pre-push hook** — отказ push'ить, если worktree отстал от main на >50 коммитов без явного override. Расширение существующего `.github/hooks/pre-push.sh`.
- **Nightly mergeability check** — workflow раз в сутки проходит по всем открытым PR, считает diff vs main; >5000 строк удалено → алерт в админ-чат `417002669`.

## Related Concepts

- [[concepts/n8n-self-hosting]] — VPS infra
- [[concepts/specs-vs-reality-ground-truth]] — local vs live truth priority
- `.github/workflows/deploy.yml` + `.github/workflows/SETUP.md` (в noms-bot репо) — реализация auto-deploy и operations guide.
