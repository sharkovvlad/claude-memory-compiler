# Migration Collision Guard

> Pre-push hook + CI workflow, защищающие от ситуации, когда два агента в параллельных worktree'ах берут один и тот же номер миграции `migrations/NNN_<slug>.sql`.

## Проблема

SQL-миграции в NOMS — последовательные: `migrations/NNN_<slug>.sql`, NNN растёт монотонно. Агенты обычно берут «следующий номер» через `ls migrations/ | tail -1` в момент старта сессии. Между этим моментом и `git push` другой агент в параллельном worktree может смерджить свою миграцию с **тем же** NNN.

Зафиксированные инциденты:
- **2026-04** (×2) — упомянуты в MEMORY.md, точные номера не сохранены.
- **2026-05-11** — два агента взяли mig 200 параллельно. Применили оба на проде (разные RPC/таблицы — физического конфликта в БД нет), но косметически коллизия. Sticker-mig перенумерована в 201.
- **2026-05-15** — mig 217 коллизия. Триггер для автоматизации.

После каждого инцидента — 30-60 минут ручного renumber'а (правка filename + ссылок в daily/handover'ах + force-push). Риск: пропустить = два файла с одинаковым именем после merge → один молча перезатирает другой.

Существовавшее правило в `CLAUDE.md` («перед `git push` проверить `ls migrations/ + gh pr list`») было **ручным** и не работало: ≥4 инцидентов после внедрения.

## Решение — двухуровневая автоматика

### Уровень 1: pre-push hook (локально)

`.github/hooks/pre-push.sh` секция «Защита 4». Активация на машину — `git config core.hooksPath .github/hooks` (one-time, см. `.github/HOOKS.md`).

Hook собирает в loop'е `while read` по push'имым ref'ам пути `migrations/NNN_*.sql`, добавленные в push-range (`git diff --diff-filter=A merge-base..local_sha`). После loop'а — вызывает `.github/scripts/migration_collision_check.py --mode=local` с списком путей на stdin.

Скрипт:
1. `git fetch origin main --quiet`.
2. `git ls-tree origin/main migrations/` → словарь `{NNN: filename}` на свежем main.
3. Если `gh` авторизован — `gh pr list --state open --json files,headRefName,number,title` (исключая текущую ветку).
4. Для каждой пушимой миграции — сверка NNN с обоими набора. Коллизия = разные filename'ы с одинаковым NNN.
5. На коллизию — печатает next free NNN, exit 1.

Override: `ALLOW_MIG_COLLISION=1 git push ...` (только для legitimate rename'а после координации).

### Уровень 2: CI workflow (backstop)

`.github/workflows/pr-migration-collision.yml`. Триггер: `pull_request: [opened, synchronize, reopened]`.

Запускает тот же `migration_collision_check.py --mode=ci --pr=N --base=main`. Скрипт:
1. `gh pr view N --json files` → список файлов в PR.
2. Cross-check с `git diff --diff-filter=A origin/main...HEAD -- migrations/` чтобы оставить только added (не renamed-внутри-PR).
3. Те же проверки против `origin/main` + других открытых PR.
4. На коллизию — пишет `migration_collision_comment.md` (идемпотентный, с маркером `<!-- pr-migration-collision -->`), выставляет `flagged=true` в `GITHUB_OUTPUT`.
5. Workflow на `flagged=true` — постит / обновляет комментарий через `actions/github-script` + fail status.

CI-комментарий содержит:
- Список коллизий с гиперссылками на конфликтующие PR.
- Suggested next free NNN.
- Команду `git mv migrations/NNN_<slug>.sql migrations/<free>_<slug>.sql` + `git commit --amend` + `git push --force-with-lease`.

## Почему оба уровня

Hook ловит локально (быстро, бесплатно, понятное сообщение **до** push'а), но требует one-time setup `core.hooksPath`. Свежий clone репо без этой настройки → hook не сработает. CI workflow — backstop, который не даёт merge'нуть PR с коллизией.

Дублирование check'а между bash hook и Python скриптом отвергнуто (lesson 2026-05-08, `pr-sanity.yml` сделан так же): bash + Python — одна реализация в Python, hook вызывает её subprocess'ом. Hook остаётся 30 строками bash, основной алгоритм — в Python.

## Edge cases

- **Legitimate rename миграции** (например, тимлид решил перенумеровать) — override `ALLOW_MIG_COLLISION=1 git push`. В CI — закрыть/обновить PR (нет аналогичного override через env). Это intentionally — coordination в CI должна идти через комментарий PR.
- **Push оффлайн / без `gh` auth** — `git fetch` упадёт тихо, проверка main пропустится с WARN, PR-check пропустится. На совсем оффлайн push hook не блокирует — лучше пропустить чек, чем заблокировать legitimate work.
- **Renamed внутри одного PR** (`git mv`) — `--diff-filter=A` оставляет только added. Old path появляется как deleted, не проверяется.
- **`gh pr list` rate limit** — на NOMS репо <100 открытых PR, лимит 5000/hour не достижим.
- **Параллельный `gh pr list` в момент merge** — есть окно (~1 сек) когда PR уже мерджится, но `gh pr list --state open` ещё его показывает. Ложный positive возможен, но retry push'а через 5 сек его уберёт. Допустимо.

## Файлы

- `.github/hooks/pre-push.sh` — секция «Migration collision guard» (защита 4).
- `.github/scripts/migration_collision_check.py` — общая реализация для hook'а и CI.
- `.github/workflows/pr-migration-collision.yml` — CI backstop.
- `.github/HOOKS.md` — инструкция активации hook'а + override env.
- `CLAUDE.md` секция «Миграции БД» п.8 — ссылка на этот KB.

## Тестирование

После изменений автор должен проверить:

1. `echo "migrations/<existing_NNN>_test.sql" | python3 .github/scripts/migration_collision_check.py --mode=local` → exit 1.
2. `echo "migrations/999_test.sql" | python3 .github/scripts/migration_collision_check.py --mode=local` → exit 0.
3. CI-часть — закрытый draft-PR с реальной коллизией → workflow fail + комментарий.

## Связано

- [[concepts/release-protocol]] — общий протокол релиза, защиты 1-3 (force-push, stale-worktree, semantic-rollback).
- [[concepts/pre-migration-discovery-recipe]] — что делать **внутри** миграции (отдельно от номера).
