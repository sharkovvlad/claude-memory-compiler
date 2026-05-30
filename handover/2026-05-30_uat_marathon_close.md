# Handover — UAT marathon close (2026-05-30)

**From:** Opus 4.7 (1M context) session, 10:30-17:30 МСК
**To:** Next NOMS agent
**Status:** ✅ 9 migrations applied LIVE + ~10 PRs (8 merged, 2 pending owner merge), all 5 UAT rounds closed. Owner confirmed «Всё остальное работает» before /kb-close.

---

## TL;DR

5-round UAT marathon на test user 786301802. Каждый round = owner feedback → diagnose → fix → apply LIVE → next test. **19 багов закрыто.** 1 design task deferred.

**Migration HEAD на LIVE: 388.** Все 9 миграций сессии (380-388) применены LIVE. На origin/main — 387 merged, 388 (PR #243) ждёт owner merge.

---

## Migration timeline this session

| Mig | What | PR | Merged? |
|---|---|---|---|
| 380 | delete_account confirm template `{tr:...}` syntax × 13 langs + delete_account_success screen + Python refactor _render_via_render_screen via template_engine | [#234](https://github.com/sharkovvlad/noms-bot/pull/234) | ✅ |
| 381 | cycle iter 2 — cycle_length_input + cycle_start_date_input screens + set_user_cycle_start_date RPC + 6 i18n keys × 13 langs + router whitelist | [#235](https://github.com/sharkovvlad/noms-bot/pull/235) | ✅ |
| 382 | onboarding diet_question step (between activity and goal) + workflow_states row + process_onboarding_input FSM 4 surgical patches | [#237](https://github.com/sharkovvlad/noms-bot/pull/237) | ✅ |
| 383 | welcome V4 rewrite × 13 langs (Sage tone, anti-shame, 3-CTA, differentiation from «boring diet coach») | [#238](https://github.com/sharkovvlad/noms-bot/pull/238) | ✅ |
| 384 | delete_user_account clears stickers_shown + last_indicator_index + last_text_indicator_date (mirror reset_to_onboarding) | [#236](https://github.com/sharkovvlad/noms-bot/pull/236) | ✅ |
| 385 | diet «➖ Пропустить» button (defaults к omnivore) + FSM mapping via DO regex replace | [#236](https://github.com/sharkovvlad/noms-bot/pull/236) | ✅ |
| 386 | process_onboarding_input cycle FSM — cmd_save_cycle_unknown / cmd_edit_cycle_length / cmd_edit_cycle_start_date + 2 new workflow_states for text-input sub-states + Patches A/B/C | [#240](https://github.com/sharkovvlad/noms-bot/pull/240) | ✅ |
| 387 | precise cycle date input → advance to ask_weight (was stay on setup — UX dead-end) | [#242](https://github.com/sharkovvlad/noms-bot/pull/242) | ✅ |
| 388 | buttons.continue × 13 langs + phenotype «Готово»→«➡️ Продолжить» + skip button on cycle_start_date_input + FSM handler in date_input state | [#243](https://github.com/sharkovvlad/noms-bot/pull/243) | ⏳ pending merge |

---

## Python changes (PR #239-#241)

- **dispatcher/router.py:**
  - Added `registration_step_diet` to BUTTON_ONLY_STATUSES + ONBOARDING_STATUSES (mig 382 subagent had skipped this — mig 259 lesson recurring)
  - Cycle text-input sub-states: moved from BUTTON_ONLY → NUMERIC_INPUT_STATUSES (PR #239 had wrongly put them in BUTTON_ONLY, where text routes to AI)
  - New section 9.5 — text in cycle text-input states → target='onboarding' (catches DD.MM.YYYY which doesn't match NUMERIC_RE)
  - Section 10.4c (PR #236) — explicit route for `cmd_onb_city_yes:*` and `cmd_onb_city_no` BEFORE section 10.5 funnel
- **handlers/onboarding_v3.py:**
  - Proactive `ghost_remove_reply_keyboard` on `/start` at `status='new'` (closes bare-/start path after psql reset)
  - `_handle_start_fresh`: clear `decision.callback_message_id` before render so welcome is fresh send_new (not edit-in-place) → sticker arrives FIRST + prepend `delete_only` for original cmd_start_fresh message
- **handlers/profile.py:**
  - `_render_via_render_screen` refactored to call `template_engine.render_envelope` (was reading non-existent `rendered.get("text")` field)
  - `_handle_confirm_delete` adds `ghost_remove_reply_kb` OutboundItem before terminal send_new (two-layer reply-kb removal)
- **handlers/location.py:**
  - `_finalize_with_timezone` already_completed path → render `stats_main` (canonical) instead of `main_menu` (doesn't exist)
- **services/template_engine.py:** unchanged this session — but its `_resolve_text` Pass 1 `{tr:section.key}` semantics are now the canonical pattern for delete_account template (mig 380)
- **telegram_proxy.py:**
  - Geo location returns True from `_content_needs_indicator` (was blanket False)
  - Removed `onboarding:country` + `onboarding:timezone` from `NO_INDICATOR_STATUSES` (was blocking indicator for slow AI city resolver) — trade-off resolved by global delete_thinking in webhook_server
- **webhook_server.py:**
  - Global `delete_thinking` in `_send_and_persist` after `telegram_send` completes — all handlers now get indicator cleanup, not just food_log

---

## All 19 bugs closed (numbered by owner UAT round)

| # | Bug | Cause | Fix |
|---|---|---|---|
| 1 | delete confirm пустой «Noms: «»» | template uses raw `{bullet_*}` (i18n sub-keys not in template_vars) | mig 380 — `{tr:delete_account.xxx}` syntax × 13 langs |
| 2 | reply-kb persists after delete | template never rendered (cascade from #1) | mig 380 + Python refactor |
| 3 | welcome generic «¡Hola! Soy NOMS — tu nutricionista IA» | original copy | mig 383 V4 × 13 langs |
| 4 | welcome sticker AFTER text | (a) stickers_shown not cleared on delete; (b) cmd_start_fresh edit-in-place keeps text above sticker | mig 384 + onboarding_v3 cmd_start_fresh patch |
| 5a | «❓ Не помню» cycle button dead | not in HEADLESS_CALLBACKS | mig 381 router patch |
| 5b-5f | cycle UX — length/date inputs, layout, disable removal | needed iter 2 | mig 381 + mig 386 + mig 387 + mig 388 |
| 6 | city confirm tap → silent | router section 10.5 caught onboarding:country callback before location dispatch | router section 10.4c (PR #236) |
| 7 | no indicator on geo share | telegram_proxy excluded location messages | telegram_proxy fix |
| 8 | diet not asked in onboarding | gap | mig 382 + 385 |
| 9 | diet buttons silent drop | registration_step_diet NOT in BUTTON_ONLY_STATUSES — mig 259 lesson recurring | PR #240 router fix |
| 10 | cycle buttons loop to explain | process_onboarding_input ELSE catch-all | mig 386 |
| 11 | reply-kb leak after psql reset | no proactive ghost_remove on bare /start | onboarding_v3 patch |
| 12 | cycle length "30" → AI food | added cycle states to BUTTON_ONLY instead of NUMERIC | PR #240 router fix |
| 13 | welcome sticker after text on cmd_start_fresh | edit-in-place keeps text above sticker | onboarding_v3 patch |
| 14 | «Something went wrong» on city confirm | handler renders «main_menu» (doesn't exist) | location.py → stats_main |
| 15 | thinking sticker not deleted after non-food handlers | only food_log had delete_thinking | webhook_server global cleanup |
| 16 | no indicator on city free-text «днепр» | onboarding:country in NO_INDICATOR_STATUSES | telegram_proxy fix |
| 17 | date input stays on setup, no advance | mig 386 mirrored length flow | mig 387 |
| 18 | phenotype «✅ Готово» reads as «registration done» | wrong semantics | mig 388 — `buttons.continue` |
| 19 | «>35 days» error mentions button on different screen | non-actionable error | mig 388 — add skip on input + FSM handler |

---

## Deferred design tasks (owner-acknowledged)

### Bug #3 — food during onboarding → mana-aware redirect

Owner: «мы не блокируем распознавание еды, даём попробовать с первой секунды. Дойдём некоторое количество попыток (маны) даже для пользователей которые не завершили регистрацию.»

Currently: ANY text in onboarding states routes through router to AI food engine (or to FSM if status=BUTTON_ONLY). Mana check happens at food_log handler — if mana=0, returns mana_exhausted screen.

Desired flow:
- Mana > 0 → process food as usual (current behavior)
- Mana = 0 → render «Доделай регистрацию, мана закончилась» + redirect to current onboarding screen

Open questions for next agent:
1. Where to add the gate — router section 10 catch-all, or food_log handler entry?
2. Copy for the redirect message × 13 langs (probably needs `errors.onboarding_food_blocked` key)
3. Whether photos vs text behave differently (photo processing more expensive — should we gate harder?)
4. Referral bonus mana — should it extend the trial window? (Currently NPC and referral give the same baseline mana_current=2)

### «Авилес» (Cyrillic transliteration of small Spanish town) edge case

From Sonnet handover 2026-05-30. AI gpt-4o-mini confidence < 0.7 for small foreign cities in Cyrillic transliteration.

Options (from prior handover):
- A. Lower confidence threshold 0.7 → 0.5 (services/city_resolver.py:36) — quick win, may increase false positives
- B. Better AI system prompt — explicit transliteration examples (Авилес→Avilés, Гранада→Granada)
- C. Geoapify forward-geocode fallback when AI confidence < 0.7
- D. Combo B + C

Owner UAT round 2-5 didn't hit this — they used recognized cities. Open for next session.

---

## KB additions / updates this session

| File | Action | Why |
|---|---|---|
| `concepts/fsm-state-whitelist-discipline.md` | **NEW HUB** | mig 259 lesson 3rd recurrence (mig 382 + 386). Hard checklist for adding new registration_step_*. |
| `concepts/test-user-reset-recipe.md` | UPDATE | Note proactive `ghost_remove_reply_keyboard` in handle_onboarding closes the bare-/start gap. Manual HTTP ghost still cleaner UX-wise. |
| `knowledge/index.md` | UPDATE | Index entry for new HUB concept. |
| `daily/2026-05-30.md` | APPEND | Session log + bugs table + meta. |
| `MEMORY.md` (`-Users-vladislav-Documents-NOMS/memory/`) | UPDATE | Current state — mig HEAD 387 LIVE, 388 in flight, Python changes summary, new HUB pointer. |

---

## Git incident — lesson 2026-05-08 recurred again

After owner merged PRs #234-#238 mid-session, I continued committing to my worktree's branch `claude/fervent-aryabhata-2189a1` **without rebasing onto fresh main**. GitHub's banner offered "Compare & pull request" but the diff would have shown massive deletion of migs 381/382/383 (work I never had on my branch).

Caught via `git diff origin/main..HEAD --stat` pre-push sanity check. Force-pushed with `--force-with-lease` after rebase. PR #239 ended up clean.

**Reinforces CLAUDE.md §12.1 «Rebase ПЕРЕД commit, не после»** whenever main has moved. Add this to your default workflow when working in shared worktrees during owner merge bursts.

---

## What's open for next agent

1. **Bug #3 design pass** (food during onboarding → mana redirect) — owner deferred, see above for open questions
2. **«Авилес» edge case** — Issue 2 follow-up, see above for options A-D
3. **mig 388 PR #243 merge** — pending owner merge. LIVE state already correct (idempotent applied). Merge needed for code consistency.
4. **Auto-mode classifier widening** — owner per-mig authorized LIVE applies multiple times this session; consider a settings.json permission rule for idempotent `CREATE OR REPLACE` migs to speed UAT iteration without losing safety on destructive ops.
5. **MEMORY-housekeeping** — file is at ~170 lines (just under 200 limit per CLAUDE.md §Закрытие сессии). Will need `/anthropic-skills:consolidate-memory` pass soon — flag to owner.

---

## How to start next session

1. Read this handover + `daily/2026-05-30.md` + main `CLAUDE.md`
2. Glance MEMORY.md — verify mig HEAD against live (`ls migrations/ | sort | tail -3` + `pg_get_functiondef` for any RPC you'll touch)
3. Open the KB HUB [[concepts/fsm-state-whitelist-discipline]] if touching onboarding FSM
4. Verify auto-mode classifier behavior — if it's still blocking idempotent migs, ask owner for permission rule before starting

---

**EOS:** 2026-05-30 ~17:30 МСК
**Author:** Opus 4.7 (1M context)
**Owner satisfaction signal:** «Всё остальное работает. /kb-close» — explicit close signal received

Удачи! 🌸
