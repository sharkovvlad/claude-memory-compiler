---
status: 🔥 HUB
domain: Onboarding / FSM
last_verified: 2026-05-30
---

# FSM state whitelist discipline

> **HARD RULE.** Adding a new `registration_step_*` (or any onboarding FSM state) to `workflow_states` is **not enough**. You MUST also register it in the appropriate `dispatcher/router.py` frozensets in the same migration, or callbacks/text in that state will silently fall to `target=menu` (legacy n8n drop) → user sees no response.

## Why this keeps happening

Live recurrences (audit 2026-05-30):

| Date | Mig | State added | Whitelist forgotten | Symptom | Lesson agent |
|---|---|---|---|---|---|
| 2026-05-13 | 259 | `registration_step_maternal*` | BUTTON_ONLY_STATUSES + ONBOARDING_STATUSES | `cmd_onb_maternal_*` dropped → menu_v3 has no handler | First time codified |
| 2026-05-13 | 187 | `registration_step_phenotype_quiz` | BUTTON_ONLY_STATUSES | `cmd_quiz_q1_*` text in quiz mode routed to AI food log | mig 187 inline comment |
| 2026-05-29 | 359 | `registration_step_cycle` | BUTTON_ONLY_STATUSES + ONBOARDING_STATUSES | `cmd_save_cycle_*` dropped during onboarding | inline mig 359 comment |
| 2026-05-30 | 382 | `registration_step_diet` | BUTTON_ONLY_STATUSES + ONBOARDING_STATUSES | All 4 `cmd_diet_*` callbacks silently dropped → owner UAT blocked → required PR #240 hotfix | This concept |
| 2026-05-30 | 386 | `registration_step_cycle_length_input` + `_start_date_input` | NUMERIC_INPUT_STATUSES (text input flow) — wrongly added to BUTTON_ONLY | `"30"` for cycle length routed to AI food | mig 386 fix in #239, again refined in #240 |

3+ recurrences over 2 weeks. **This is the single most expensive recurring lesson in NOMS onboarding.**

## The four router frozensets and when each matters

`dispatcher/router.py` keeps three small frozensets that gate FSM dispatch. Picking the right one(s) for a new state is the whole job.

### `BUTTON_ONLY_STATUSES` — line 73

> «User on this screen is **expected to tap an inline button**. Free-form text is treated as food log fallback (`text_food_from_button_step`).»

Add state here when the screen is `input_type='inline_kb'` AND has no callable text path. Examples: gender pick, maternal status, cycle question (Yes/Skip/Explain), diet (omnivore/vegetarian/vegan/skip), phenotype quiz, goal pick.

If you forget: `cb_data=cmd_X` falls into section 4l `is_menu_callback` → `target=menu_v3` → 4xx (no handler) → user sees nothing.

### `NUMERIC_INPUT_STATUSES` — line 63

> «User on this screen is **expected to type a number**. Non-numeric text is treated as food log.»

Add state here when the screen is `input_type='text_input'` with a numeric `save_rpc` (set_user_age / weight / height / cycle_length / etc.).

If you forget: section 8 (NUMERIC_RE match → onboarding) doesn't fire → text falls to section 11 catch-all → AI food engine → user sees «не еда?».

### `ONBOARDING_STATUSES` — line 361

> «User is mid-onboarding. Don't route them through registered-user paths (PROFILE_V5_CALLBACKS, menu_v3 commands, etc.).»

Add state here for ALL `registration_step_*` and `onboarding:*` states. This is the «am I in the funnel» guard used by sections 4h.5, 4f, 10.5 to prevent leaks.

If you forget: random callbacks (cmd_safety_center, cmd_my_plan) start working mid-onboarding → broken FSM transitions.

### `NO_INDICATOR_STATUSES` — `telegram_proxy.py:63`

> «Suppress the thinking-sticker on this screen because the response is fast OR the state expects specific text we don't want to look like food.»

Add when render is instant (button picker, inline preview) AND user might type something like `📋 Выбрать из списка`. Rare. Don't reflex-add.

After 2026-05-30 round 4: with global `delete_thinking` in `webhook_server._send_and_persist`, this set is now LESS necessary — even a false-positive indicator gets cleaned up post-render.

## Checklist when adding a new `registration_step_*` state

Copy-paste into your migration PR description:

```
- [ ] state added to workflow_states (FK to ui_screens)
- [ ] state in process_onboarding_input FSM (text + callback branches)
- [ ] state in ONBOARDING_STATUSES — ALWAYS for registration_step_*
- [ ] state in BUTTON_ONLY_STATUSES — if screen is inline_kb only
- [ ] state in NUMERIC_INPUT_STATUSES — if screen is text_input expecting a number
- [ ] state in NO_INDICATOR_STATUSES — only if response is <50ms (rare)
- [ ] new cmd_* callbacks in HEADLESS_CALLBACKS — if dispatched via dispatch_with_render save_via_callback
- [ ] python router test covering target resolution for this state
```

The first 4 lines catch 95% of recurrences. If you skip them, expect owner UAT to find the bug within hours.

## Recurrence 2026-05-31 — un-hidden button без routing-check (mig 390 → fix #248)

mig 390 **показал** кнопку «Назад» (снял visible_condition) на `edit_speed` в онбординге, но `registration_step_speed` **отсутствовал в BUTTON_ONLY_STATUSES** → `cmd_back` маршрутизировался в `target='ai'` (food engine) вместо onboarding → юзер видел мусор. goal/activity/training там были (повезло), speed — нет. Fix #248: + `registration_step_speed` в BUTTON_ONLY.

**Два новых правила из этого рецидива:**
1. **Показываешь inline-кнопку на статусе → проверь, что статус в правильном whitelist.** Un-hide кнопки = новый callback-путь, которого раньше не было. «Кнопка есть в БД, но скрыта» = routing никогда не тестировался.
2. **🔴 Тестируй back-навигацию через `dispatcher.router.route()` (ПОЛНЫЙ путь), а НЕ прямой вызов `process_onboarding_input`.** mig 390 тестировался прямым вызовом RPC → переходы верны, но пропущено, что роутер вообще не доводит `cmd_back` до RPC (уходит в 'ai'). Прямой-RPC тест = **ложная зелёнка**. Минимум: `route(callback, ctx) → target` + `route(text, ctx) → target`.

Открытый риск (handover 2026-05-31): text-шаги `registration_step_2/3/4` (age/weight/height) тоже route cmd_back → 'ai'. Не баг пока (text_input → remove_keyboard, кнопки нет). Но variant-1 (инлайн-back на text-шагах) обязан сперва добавить их в routing.

## Related

- [[concepts/headless-fsm-vs-dynamic-handler-separation]] — broader FSM vs handler architecture
- [[concepts/action-router-pattern]] — router design
- [[concepts/router-prefix-collision]] — sibling gotcha (callback prefix matching)
- [[concepts/onboarding-v3-map]] — FSM state map
- mig 259 (canonical first codification of this lesson)
- mig 382 + 386 (latest recurrences fixed)
