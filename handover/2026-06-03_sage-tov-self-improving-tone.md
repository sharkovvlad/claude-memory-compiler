# Handover 2026-06-03 — Sage самоулучшающаяся система тона (ToV)

**Для преемника.** Сессия построила фундамент самоулучшающегося тона Номса. Всё LIVE.
Завтра owner хочет первый предметный разбор тона. Старт — ниже.

## TL;DR что сделано (всё merged + LIVE)

| PR | mig | Что | Статус |
|---|---|---|---|
| #283 | — | Sage ToV: 7 правок промптов (убрана «формула из 3 рефлексов», баг правды «зашкаливает», алармизм «фермент на грани», «переборщил», биохим-рефлекс) | LIVE |
| #287 | — | Форс «ты» вместо «Вы» в обоих промптах | LIVE |
| #302 | 440 | «Мой день» stale-insight: `delete_meal_by_id` атомарно NULL-ит `my_day_insight_at` | LIVE |
| #312 | 447 | **Телеметрия тона** — reuse `ai_coach_logs` (НЕ новая таблица) | LIVE+deployed |
| #318 | — | `tools/sage_transcript_export.py` — транскрипт «переписки с Номсом» в MD | LIVE |

## Архитектура «самоулучшения» (4 звена)

1. **👁 Глаза — телеметрия (mig 447).** Каждая реакция Номса пишется в `ai_coach_logs`
   (`context_type` = `sage_food_log` / `sage_my_day`) с `emotion`, `day_context`
   (снимок промпта, что видела модель: `{"prompt": user_prompt}`), `tokens_used`,
   `latency_ms`, `meal_id`. Источник — `services/sage.py:_fire_sage_telemetry` →
   `services/ai_logging.py:log_request` → RPC `log_ai_request`. **Пишет только
   генерации ПОСЛЕ деплоя (17:53 UTC 2026-06-03); прошлые реакции невосстановимы.**
2. **📖 Чтение — транскрипт-тул.** `python3 tools/sage_transcript_export.py [--date]`
   → `~/Documents/NOMS/sage_transcripts/sage_transcript_<date>.md`. Per-user
   хронология food↔reaction (пара по `meal_id`) + «Мой день», `видел HH:MM/phase`
   (контроль фазы). Один календарный день (локальная дата юзера).
3. **⚖️ Судья — скилл `/sage-tov`.** `.claude/commands/sage-tov/SKILL.md` (Фаза 1
   экспорт + Фаза 2 оценка по рубрике 12 правил → отчёт `sage_tov_review_<date>.md`
   + предложенные правки промпта). **Гейт: судья ПРЕДЛАГАЕТ, человек/агент УТВЕРЖДАЕТ.**
4. **🔧 Улучшение** (НЕ построено) — правки промпта/few-shot эталоны под ревью.

## Старт завтра (что делать)

1. **Дать телеметрии накопиться** — за ночь юзеры логируют, копятся `sage_%` строки.
2. **Запустить `/sage-tov`** → транскрипт за день + разбор тона по рубрике.
3. **Owner ждёт предметный разбор** — какие реакции/инсайты подкрутить, какие правки
   промпта (`services/sage.py:_DEFAULT_SYSTEM_PROMPT_EN` / `_MY_DAY_EN`) предложить.
   Правки промпта = отдельный PR (NLM → live-база → деплой; промпт-текст, без миграций).

## Open watch-items (НЕ фиксить вслепую)

- **🟡 Wellbeing-рефлекс** — хвост «стресс/недосып → потянет на сладкое» появлялся в
  3/4 реакций. Сегодня корректно (сон/стресс реально плохие). **Ключевой тест — день
  с НОРМАЛЬНЫМ самочувствием:** если хвост всё равно вылезет → wellbeing-рефлекс
  переродился из биохим-рефлекса, demote-нуть как биохимию (специя, не налог).
- **🟡 «Вы» vs «ты»** — PR #287 форсит «ты». Проверить на новых реакциях, что регистр
  держится (был 1 случай «Ваша каша»).
- **🟡 Owner TZ подозрителен** — `users.timezone='Europe/Madrid'` для 417002669, но
  сообщения приходят на час+ позже («видел 20:00» при сообщении 21:18). Для фазы дня
  (завтрак/обед/ужин) критично. Свериться с реальным TZ owner'а.

## Next builds (на выбор owner'а)

- **Судья-крон** — авто `/sage-tov` по расписанию + дайджест в админ-чат (как
  `StarsDigestCron`). Автоматизирует ручной разбор.
- **«Память юзера»** — ролловый дайджест на юзера (паттерны питания/сна, эмоц.дуга,
  какой тон заходит) → персональные инсайты Номса с контекстом за 1-2 недели → путь
  к удержанию/вовлечению. Owner назвал это вершиной. **Анти-shame на уровне памяти**
  (не слежка/диет-полиция).

## Durable гочи этой сессии

- **`.claude/` целиком в `.gitignore`** → скиллы (kb-close, sage-tov) machine-local,
  НЕ в git/PR. Новый скилл = `.claude/commands/<name>/SKILL.md` **в основном клоне**
  `~/Documents/NOMS/` (worktree-копия зачистится). Gitignored-файл → `cp` без git
  (§12-safe). Сессия, запущенная ДО создания скилла, не видит его в пикере →
  `/reload-skills` или рестарт.
- **Extend RPC новыми параметрами = OVERLOAD-ловушка.** `CREATE OR REPLACE` с другим
  числом параметров создаёт второй overload → `AmbiguousFunction` на старых вызовах.
  ВСЕГДА `DROP FUNCTION IF EXISTS public.foo(<старая сигнатура>)` перед `CREATE` +
  verify `count(*) from pg_proc where proname='foo'` = 1 + `NOTIFY pgrst,'reload schema'`.
  См. [[concepts/safe-create-or-replace-recipe]] §238.
- **Reuse > новая таблица.** NLM советовал создать `sage_responses_log`; live показал
  `ai_coach_logs` (generic `context_type`-лог) + RPC `log_ai_request` + обёртка +
  GDPR уже существуют. Owner-правило «проверь у тебя инфо с полей, сделай лучше».
- **Кэш-инвалидация на мутируемом состоянии** — в самой mutation-RPC (атомарно), не
  в Python-хендлере/фоне (fire-and-forget гонится + silent no-op). [[my-day-llm-insight]].
- **§12 stale-base (4-й case)** — ветка от старого main «удаляет» чужие файлы в дифе
  (PR Sanity Check «N файлов удалено» = stale-base, НЕ коллизия номеров). Fix:
  `git rebase origin/main` + force-with-lease. Sanity-diff перед push.

## Ключевые файлы
- `services/sage.py` — промпты (`_DEFAULT_SYSTEM_PROMPT_EN`/`_MY_DAY_EN`) + `_fire_sage_telemetry`.
- `services/ai_logging.py` — `log_request` (+4 sage-kwarg'а).
- `tools/sage_transcript_export.py` — транскрипт-генератор.
- `.claude/commands/sage-tov/SKILL.md` — скилл (Фаза 1 + Судья + рубрика).
- KB: [[concepts/sage-food-log-llm-integration]] §ToV anti-formula §телеметрия, [[my-day-llm-insight]].
