# Handover — Session close 2026-05-24

## State you're inheriting

**DB head: mig 329.** Today merged: 312, 313, 314, 315, 316, 317, 318, 319, 320, 321, 322, 323, 324, 325, 326, 327, 328, 329 (18 migrations этой сессии и накануне). All deployed via GitHub Actions auto-deploy. Live state synced with main.

**Active feature flags** (`app_constants`):
- `sage_food_log_enabled='true'` (Noms one-liner on food log card)
- `sage_my_day_enabled='true'` (LLM insight on My Day, cache-on-write)
- `sage_food_log_timeout_ms='5000'`
- `sage_food_log_max_tokens='300'`
- `sage_food_log_temperature='0.7'`
- `handler_menu_v3_use_python='true'`, food_log + others — see `dispatcher/forward.py:TARGET_TO_PATH`

## Что закрыто этой сессией (PRs #160-171)

| # | Что | Mig |
|---|---|---|
| 160 | Noms character v2 — JSON mode, tg-emoji, UX polish | 314 |
| 161 | Sage food_log_fallback × 13 langs | 315 |
| 162 | Phase 3c stress UX (параллельный агент) | 317 |
| 163 | 3 P0 фикса — Edit btn, Sage timeout fallback, unicode emoji rollback | 318 |
| 164 | My Day LLM insight (cache-on-write architecture) | 319+320 |
| 165 | 4 P1 фикса — food card persist, timeout 5s, fallback rewording | 321 |
| 166 | Hotfix — payload normaliser «zero calories» + Edit visibility + template polish | 322 |
| 167 | My Day prompt LOGIC GUARDRAILS (kill schizophrenia) | 323 |
| 168 | Full 2-stage meals_picker | 324 |
| 169 | stats_main target_screen meta fix | 326 |
| 170 | 3 bugs — literal `\n`, edit-meal time travel, anti-spam regen | 327+328 |
| 171 | get_day_summary timezone fix | 329 |

Subagent merged **mig 325** (My Day translations × 11 langs) до connection drop. Все 13 langs покрыты для: `sage.system_prompt_my_day`, `meals_picker.title`, `meal_action.title`.

## Что ТОЧНО в проде сейчас

1. **«Мой день» (stats_main)** — LLM insight from cache; кнопка `[Исправить]` ведёт в **meals_picker** (2-stage flow); meal times в user TZ.
2. **meals_picker** — динамические per-meal кнопки `cmd_select_meal_<uuid>`; tap meal → `meal_action`.
3. **meal_action** — `[✏️ Исправить][🗑️ Удалить][← Назад]`. Исправить ведёт через editing_meal flow с **сохранением** оригинального `consumed_at` (mig 328).
4. **Food log card** — Sage one-liner `NOMS {emoji}: "..."` (unicode emoji, не tg-custom). Карточка persistent (не удаляется next nav click).
5. **Sage timeout fallback** — карточка food_log НИКОГДА не отрендерится без Noms-comment (pre-baked per-language fallback на timeout).
6. **My Day insight cache** — fresh = 0 LLM call на view (anti-spam). Regen kick'ается только на miss + после каждого food_log.
7. **TZ correctness** — все display-time RPCs читают `users.timezone`. День boundary — user midnight, не UTC.

## Открытые vектора (TODO)

### Перевод
- **`sage.system_prompt_food_log` × 11 langs** (есть только ru/en от mig 312). Subagent в фоне завершил `my_day` перевод (mig 325), но **food_log** prompts всё ещё ru/en only — другие langs падают на `_DEFAULT_SYSTEM_PROMPT_EN` constant. Через copywriter playbook.
- **Owner pending**: side-eye + sage Telegram custom emoji IDs (если решит вернуть 3D emoji). Сейчас все 4 эмоции — unicode (😏🤩🤨🧘‍♂️).

### Уязвимости
- **`delete_meal_by_id(p_meal_id)` RPC не имеет ownership check** на telegram_id. Сейчас мы вызываем только через `ctx.editing_meal_id` (который уже ownership-checked в set_editing_meal_by_id), но **прямой вызов RPC** позволяет удалить чужой meal. Defense-in-depth — добавить telegram_id parameter + check.

### Feature backlog
- **Closed-loop telemetry** — `sage_responses_log` table (Sage outputs + emotion + кэш-hit, для будущего RLHF). Spec не написан.
- **Per-meal voice/photo edit** в meals_picker flow — сейчас editing_meal flow поддерживает text/voice/photo (existing handler), но **только для последнего залогированного meal-id** в смысле context'а. Edit через picker → проверь что AI cascade корректно берёт `editing_meal_id` из ctx, не assume last meal.
- **Clear my_day_insight cache on profile change** — `clear_my_day_insight_cache(tid)` RPC создан в mig 319, но НЕ wire'ится в profile handlers (goal/weight/diet change). Нужно добавить call в `handlers/profile.py` куда уместно.

### Tech debt
- **n8n self-host cleanup**: 03_AI_Engine ещё содержит legacy nodes которые не используются (after food_log full Python cutover). Аудит + DELETE.
- **deploy.sh ничего не апплаит из `migrations/`** — это намеренно (см. [[concepts/migration-deploy-ordering]]), но было бы хорошо добавить `tools/apply_unapplied_migs.py` который check'ает `pg_proc` / `information_schema` + apply'ит только новое. Сейчас mig apply вручную через psycopg2. Возможный future улучшение для CI/CD.

## Pitfalls которые ты избежишь читая KB

1. **[[concepts/migration-deploy-ordering]]** — split additive vs breaking. Не apply'ить mig который требует deployed code до deploy.
2. **[[concepts/headless-button-creation-gotchas]]** — 5 gotcha'ев для кнопок. Особенно gotcha 4 (копируешь cb_data → копируй meta) и gotcha 5 (visible_condition после delete соседа).
3. **[[concepts/pre-migration-discovery-recipe]]** — расширил 6 новыми gotcha'ями: PG single-quote escape trap, LIKE escape semantics, LLM payload validation vs live RPC shape, timezone в RPC, deploy ordering.

## Ритуал при старте

1. Прочитай `daily/2026-05-24.md` целиком — там детали по каждому PR.
2. `gh pr list --state open` — должно быть пусто (sub-agent #a150808d закрылся, моя сессия закрывается, ничего не висит).
3. Если live bug от owner — **сначала** проверь live state via psycopg2 (не доверяй ассумпциям) **потом** правь.
4. Любой mig с UPDATE к существующим `ui_screen_buttons.callback_data` или `ui_translations.{screen}.*` — apply ПОСЛЕ deploy кода. Если делаешь оба одновременно — деплой code first, mig second.

## Что owner попросил «обязательно сделать»

(Не было урезано требование — всё закрыто или в backlog с обоснованием.)

## Спасибо

Сегодня большой день — закрыт полный stack Sage character v2 + My Day LLM + 2-stage meals_picker. Owner-driven test cycle с быстрым feedback loop был ключом — баги вылавливались за минуты, не дни.

Удачи!
