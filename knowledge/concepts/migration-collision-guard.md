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
- **Несколько агентов в worktree'ах, никто ещё не push'нул** (lesson 2026-05-16): когда N агентов стартуют параллельно, локальные проверки (`ls migrations/` + `gh pr list --state open`) у всех проходят — ни один ещё не запушил. Первый pusher выигрывает, остальных блокирует hook/CI. Это by design, но цена — rename после уже сделанного apply + sentinel-прогона. Если знаешь / подозреваешь, что параллельные агенты активны, **спроси owner'а** какой NNN брать **до** apply, даже когда локальные проверки чисты. В этой сессии произошёл коллапс 231→232→234 (231 ушёл в PR #82 пока я работал; 232/233 захвачены другими активными агентами по словам owner'а).

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

## Edge case: parallel subagents в shared worktree (2026-05-29 lesson)

**Сценарий:** Orchestrator (main agent) запускает 2-3 subagents через Agent tool с инструкцией «возьми mig N для тебя, N+1 для меня, N+2 для другого subagent'a». Каждый subagent работает в **своём отдельном worktree** (Agent tool default), полностью изолированно.

**Что произошло 29.05** (Nutritionist 10):
1. Orchestrator проверил `ls migrations/` + open PRs → 374 last, никаких open PRs с миграциями → решил mig 375 = себе, 376 = subagent A, 377 = subagent B.
2. Subagent A был запущен. **Но он сам проверил** `ls migrations/` + `gh pr list` (правильное поведение per CLAUDE.md) — увидел 374 last, никаких open PRs → решил что свободно с 375. Орchestrator-инструкция «возьми 376» воспринята как один из вариантов, не як strict rule.
3. Subagent A apply LIVE mig 375 (его version) + push branch + open PR #229 with mig 375.
4. Несколько минут позже orchestrator apply LIVE свой mig 375 (cycle version) + push + open PR #231.
5. **На прод БД applied 2 разные migrations с одним номером 375**. На GitHub 2 PR с конфликтующими migrations/375_*.sql.

**Почему pre-push hook не сработал у subagent A:**
- Subagent A push'нул **первым** — на момент его push origin/main был на 374. Hook прошёл.
- Orchestrator push'нул вторым с уже-existing-on-origin mig 375 → hook должен был блокировать **orchestrator**, но **migration_collision_check.py** видимо не был активирован в orchestrator's worktree (different hooks setup).

**Resolution (29.05):**
- Один из PR переименован 375 → 378 (filename only, БД уже applied; миграции идемпотентны).
- Используется `git mv` + amend commit + `git push --force-with-lease`.
- На каждый PR comment объясняющий хронологию + rename rationale.

**Lessons for orchestrators:**

1. **Subagent инструкция «возьми mig N» — не enforceable** на уровне subagent'а. Subagent работает в isolation, может **переопределить** твой номер своей независимой проверкой `ls migrations/`.
2. **Orchestrator должен first push свой commit** перед запуском subagents — тогда origin/main уже advanced, subagent'ы увидят занятый номер через pre-push hook.
3. **Альтернатива:** orchestrator делает `git push` **пустого** placeholder файла `migrations/<N>_placeholder.sql` (или DO NOTHING migration) — резервирует номер. После своей работы — amend на real content.
4. **Если коллизия уже произошла:** rename **через git mv** (sed заменить внутри тела «mig N» → «mig M»). БД не трогать — миграции идемпотентны.
5. **`--force-with-lease` на subagent's завершённой ветке** — safe, потому что subagent уже не пишет в неё (его process exited).

## 2026-06-01 — CI guard поймал то, что pre-push hook не видит (PR #277 case 6)

**Что произошло:** агент PR #277 (CLDR plural runtime) запушил mig 418. Pre-push
hook прошёл — `ls-tree origin/main` показал 415 как last (416/417 уже взяты PR #273
mig'и тоже на main к этому моменту). НО параллельно открытый PR #276 (P2.1
trial-card-CTA) тоже держал mig 418 в branch. Pre-push hook **не проверяет
открытые PR'ы** (либо `gh` не авторизован в worktree-сессии, либо проверка
silent-fail'нула).

**Что спасло:** **CI workflow `PR Migration Collision Guard`** — он `gh pr list`'ит
из CI environment (где `GITHUB_TOKEN` всегда есть). Запостил комментарий-инструкцию:
suggested rename → 419 + ready-to-run `git mv` + `git commit --amend` + `git push
--force-with-lease`. 1 минуту от detect до actionable fix.

**Resolution (PR #277):** rename 418 → 419 + 4 internal refs (header, cron comment,
test docstring, error messages). Rebase на свежий main (PR #276 уже merged к этому
моменту) — конфликт в `crons/subscription_lifecycle.py` (оба PR трогали
`_send_renewal_reminders`). Manual resolve: keep PR #276 `_resolve_text()` JSONB
helper + trial-card branch, keep PR #277 `services.i18n_plural` import + universal
`{streak_days_word}` block. 214 tests pass post-rebase. force-with-lease push.

**Lessons:**

- **Layered defense работает.** Layer 1 (pre-push hook) пропустил cross-PR
  collision, Layer 2 (CI workflow) поймал. 1+1 надёжнее чем любой single point.
- **Pre-push hook gap.** Hook вызывает `gh pr list` для cross-PR check'а, НО:
  (a) `gh` может быть unauthenticated в worktree session — fallback на silent skip;
  (b) hook может быть disabled в worktree — `core.hooksPath` per-clone setting,
  не наследуется. Проверять: `git config --get core.hooksPath` в каждом worktree
  при старте сессии.
- **Manual coordination через MEMORY reserve** (owner) — частичное решение.
  «Opus 4.7 берёт mig 421» не охватывает unrelated сессии (PR #277 ничего о
  reserve не знал).
- **6 случаев collision'а за 30 дней (200/217/229-231 cluster/415-417/418/418)**
  → Layer 1 hook надо доводить до 100% (auto-authenticate `gh` через token из
  env, fail-loud если `gh` недоступен, не silent skip).

## Связано

- [[concepts/release-protocol]] — общий протокол релиза, защиты 1-3 (force-push, stale-worktree, semantic-rollback).
- [[concepts/pre-migration-discovery-recipe]] — что делать **внутри** миграции (отдельно от номера).
- [[concepts/session-close-discipline]] — фиксация collision resolution в handover (иначе следующий агент не знает что 2 mig'а на проде с разными file numbers).
- [[concepts/i18n-cldr-plural-runtime]] — конкретный case 6 (PR #277, mig 418→419 после CI catch).
