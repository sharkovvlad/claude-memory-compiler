---
title: "Release Protocol — Deploy на VPS только из main"
aliases: [deploy, ci-cd, release, deploy.sh]
tags: [deploy, ops, multi-agent]
sources:
  - "CLAUDE.md cleanup 2026-05-05"
created: 2026-05-05
updated: 2026-05-05
---

# Release Protocol — Deploy на VPS только из `main`

**Единственный путь кода в production:** feature-ветка → Pull Request → merge в `main` → `./deploy.sh` из чистого чекаута `main`.

**`origin/main` — единственный источник истины** для VPS. Любой обход этого правила = потеря работы.

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

- Каждый агент — своя ветка `claude/<scope>-<id>`. Перед merge: `git rebase origin/main`. Force-push только `--force-with-lease`.
- Перед стартом проверь свежие [handover'ы](../handover/) и [daily logs](../daily/) — другой агент мог сегодня тронуть тот же файл.
- **rsync `deploy.sh` на VPS может откатить файлы**, если две ветки трогали одно — координация через тимлида обязательна.
- SQL-миграции обычно не пересекаются с Python другого агента. Но Python-handlers, `webhook_server.py`, `dispatcher/forward.py` — высокая вероятность конфликта, требует ребейза перед merge.

## Related Concepts

- [[concepts/n8n-self-hosting]] — VPS infra
- [[concepts/specs-vs-reality-ground-truth]] — local vs live truth priority
