# Build Log

## [2026-05-23T21:45:00+03:00] compile | daily/2026-05-18.md

- Source: daily/2026-05-18.md
- Articles created:
  - [[concepts/headless-button-creation-gotchas]] — 3 gotcha-паттерна при создании headless-кнопок (mig 271/272/273): meta.target_screen обязателен (silent re-render без него), двойной emoji из icon_const_key + text_key, FSM hardcoded render_screen при перемещении кнопки. Pre-flight чек-лист.
- Articles updated:
  - [[concepts/n8n-stateful-ui]] — Добавлена секция «sendChatAction typing indicator — NOT cancelled by editMessageText (2026-05-18)». Telegram typing живёт 5 сек и отменяется ТОЛЬКО через sendMessage, не editMessageText. После Python cutover (replace_existing = editMessageText) typing-ноды в n8n = визуальный мусор. Disabled 10 нод × 3 workflows. Чек-лист post-cutover audit.
- Already compiled by inline agents (verified, no gaps found):
  - [[concepts/energy-availability-design-decision]] — Created 2026-05-18 ✓. EA deferred to P2 (false negatives on active F demographic without workout tracking).
  - [[concepts/safety-banner-ux-redesign-2026-05-18]] — Created 2026-05-18 ✓. Multi-guard stacking problem, Plan A vs Plan B research, industry analysis 7 products.
  - [[concepts/safety-center-implementation-plan]] — Created 2026-05-18 ✓. Owner approved Plan B, phased B0→B1→B2→B3, naming locked `🛡️ Твоя безопасность`, B1 decisions locked (pill text, empty state hide, click depth).
  - [[concepts/calc-user-targets-roadmap]] — Updated 2026-05-18 ✓. P0.3+P0.4 DONE (mig 246 v7), P0.6 DONE SQL (mig 253+254 v8 maternal), banner injection via mig 252.
  - [[concepts/personalized-macro-split]] — Updated 2026-05-18 ✓. v7 section (BMI guards + min_kcal floor, 4 feature flags, 8 sentinels, p95=44ms).
  - [[concepts/pregnancy-lactation-clinical-spec]] — Updated 2026-05-18 ✓. §6b goal interaction matrix (gain=ALLOW), §6c onboarding UX simplification (3 buttons).
  - [[concepts/copywriter-playbook]] — Updated 2026-05-18 ✓. Active scope table (bmi/min_kcal pending copywriter, pregnancy blocked UX wireframe).
  - [[concepts/ui-translations-bulk-update-recipe]] — Updated 2026-05-18 ✓. Phase 4 completion stats (~286 translations, 0 auto-rejections), migration collision protocol, variant-aware critic.
  - [[concepts/sassy-sage-multilingual-glossary]] — Updated 2026-05-18 ✓. Phase 4 Applied State table (11 langs), cross-language insights consolidated.
  - [[concepts/safety-guard-ux-pattern]] — Updated 2026-05-18 ✓. §2b implementation status (mig 252 passive banner, mig 264 first-trigger modal, mig 284 per-guard click-to-modal, mig 289 auto-resolve cron).
- Skipped (minor operational, no KB-worthy concept):
  - Mig 252 banner injection mechanics — covered by safety-guard-ux-pattern §2b + personalized-macro-split v7.
  - Mig 270 (338 bmi/min_kcal translations 13 langs) — operational copywriter session, process in ui-translations-bulk-update-recipe.
  - Mig 268 resurrection from orphan branch — idempotency guard pattern already in safe-create-or-replace-recipe.
  - Phase 4 UK/ID/HI/AR/FA (mig 247-251) — completion stats in sassy-sage-multilingual-glossary + ui-translations-bulk-update-recipe.
  - Mig 273 phenotype back nav FSM fix — lesson captured in headless-button-creation-gotchas Gotcha 3.
- Note: Daily 2026-05-18 is one of the largest sessions (nutritionist owner + i18n agent + B0 agent). 8 themes: (1) **P0.3+P0.4 v7 mono-mig** (mig 246 BMI+kcal guards, 8 sentinels, 4 feature flags). (2) **Phase 4 stream completion** (UK/ID/HI/AR/FA = 5 final langs, ~286 total translations across 11 langs). (3) **Mig 252 banner injection** (family-agnostic loop, auto-renders new families when translations appear). (4) **P0.6 pregnancy v8** (mig 253+254, 6 new columns, maternal guard + protective mode, subagent autonomous). (5) **Safety banner UX redesign research** (Plan A vs B, industry analysis). (6) **Safety Center plan approved** (B0→B3, naming locked). (7) **sendChatAction typing disable** (editMessageText ≠ cancel typing — 10 n8n nodes disabled). (8) **Phase B0** (mig 271 my_plan cleanup + mig 272/273 hotfixes — 3 headless gotchas discovered). Most content self-compiled by session agents into existing KB articles.

## [2026-05-23T17:30:00+03:00] compile | daily/2026-05-17.md

- Source: daily/2026-05-17.md
- Articles created: (none — all major concepts created by inline agents during 17.05 sessions)
- Articles updated:
  - [[concepts/cron-silent-failure-alerting]] — Added mig 237 incident: `cron_regenerate_mana` NULL arithmetic WHERE clause silently skipping user forever. Pattern: `OR col IS NULL` guard for datetime arithmetic in cron WHERE. Updated sources + date to 2026-05-17.
  - [[concepts/no-mana-python-precheck]] — Added followup fixes mig 237 (NULL-safe mana regen) + mig 238 (indicator race condition with delete-and-send-new, visible_condition for insufficient coins, vertical layout). Lesson: fire-and-forget side-effects (`save_indicator_state`) break `delete_and_send_new` when they write `last_bot_message_id` AFTER render.
- Already compiled by inline agents (verified, no gaps found):
  - [[concepts/agent-collaboration-protocol]] — Created 2026-05-17 ✓. 10 правил координации (5-tier severity, DEFAULT-policy, naming conventions, scope ownership, KB ownership, conflict escalation, migration timing, silent accuracy ≠ guard, L1/L2 cultural review, retrofit cron priority).
  - [[concepts/safety-guard-ux-pattern]] v2 — Updated 2026-05-17 ✓. 5-tier severity (added hard regulated), resolved Trigger Table contradiction, auto-reset variants (A/B/C), L1/L2 translation pipeline, storage §8 (applied mig 239).
  - [[concepts/no-mana-python-precheck]] — Created 2026-05-17 ✓. Strangler Fig pattern, mig 236 headless screen + Python hook. Zero extra DB queries (mana_current from v_user_context cache).
  - [[concepts/l1-cultural-sanity-brief]] — Created 2026-05-17 ✓. L1 reviewer checklist, 6 language families, cultural flag categories, quick-check algorithm.
  - [[concepts/user-data-collection-pattern]] — Created 2026-05-17 ✓. Trifecta + 3 periodic patterns, DEFAULT NULL vs typed, GDPR opt-in, adaptive throttle, unified user_prompt_log, canary 10%.
  - [[concepts/calc-user-targets-roadmap]] — Updated 2026-05-17 ✓. P0.1 DONE (mig 234), P0.3+P0.4 mono-mig spec, P0.6 pregnancy blocked on UX wireframe.
  - [[concepts/personalized-macro-split]] — Updated 2026-05-17 ✓. v6 mig 234 age safety guards brief reference.
  - [[concepts/ui-translations-bulk-update-recipe]] — Updated 2026-05-17 ✓. ES pilot (mig 232) + DE (mig 233) + FR (mig 235) sessions documented. Writer→critic→merge pipeline matured with 3rd datapoint. Cross-language insights: `log` false friend in 7 langs.
  - [[concepts/pregnancy-lactation-clinical-spec]] — Created 2026-05-17 ✓. IOM 2002/2005 + WHO 2004 + ACOG 2013 clinical spec for P0.6.
- Skipped (minor operational, no KB-worthy concept):
  - Mig 239 safety guard storage (infrastructure DDL) — referenced in safety-guard-ux-pattern §8 as applied marker.
  - Mig 240/241/242 age guard translations (143+5+7 entries × 13 langs) — operational copywriter session, process documented in ui-translations-bulk-update-recipe.
  - deploy.yml smoke-test grep fix (run #60) — already documented in release-protocol.md Lesson 2026-05-17.
  - Handover files (mig234_copywriter_brief, age_warnings_python_handler_brief) — operational briefs, not concept-level knowledge.
- Note: Daily 2026-05-17 is the largest single-day log in the project (8 sessions, ~12+ hours). Content covers 6 themes: (1) **UX Phase 3 ES pilot** (mig 232, writer→critic pipeline, `apuntar` canonical verb, `apesta`→`un bajón`, `coger` LatAm trap). (2) **UX Phase 4 Wave A1 DE+FR** (mig 233+235, `loggen→tracken`, `logguer→noter`, food patrimoine, Oktoberfest+mitochondries). (3) **Mig 234 age safety guards v6** (3 age-based warnings in `calculate_user_targets`, 6 sentinels, transactional SAVEPOINT pattern). (4) **No-mana Strangler Fig** (mig 236/237/238: Python pre-check intercepts mana=0 voice/photo BEFORE n8n, NULL-safe mana regen, indicator race fix). (5) **Multi-agent coordination protocol** (10 rules: severity vocabulary, cultural review L1/L2, migration timing, KB ownership). (6) **Safety guard storage + translations** (mig 239 infrastructure + mig 240-242 = 156 entries × 13 langs for age warnings). Most content was self-compiled during sessions — agents directly created KB articles as part of their workflow.

## [2026-05-23T15:00:00+03:00] compile | daily/2026-05-16.md

- Source: daily/2026-05-16.md
- Articles created: (none — all major concepts already compiled by inline agents during 16-18.05 sessions)
- Articles updated:
  - [[concepts/personalized-macro-split]] — Added `daily/2026-05-16.md` to frontmatter sources, bumped `updated` to 2026-05-16. Content already present: v5 section (mig 230 gender-conditional `carbs_min_g` floor — women=100, men=50, 3-level COALESCE fallback, sentinel verification, digital twin post-merge cross-check pattern, boundary lesson: floor бьёт только при very-low-weight + elderly + sedentary PAL).
  - [[concepts/ui-translations-bulk-update-recipe]] — Added YAML frontmatter with `sources: daily/2026-05-16.md` (article lacked frontmatter entirely). Content already present: Phase 0 audit recipe (recursive JSONB walk), Phase 1 RU terminology (mig 231, 18 keys «стрик/лог» → «серия/запись»), pipeline steps 1-10.
- Already compiled by inline agents (verified, no gaps found):
  - [[concepts/sassy-sage-multilingual-glossary]] — Created 2026-05-16 ✓ (128 KB, 11 language sections × 8 subsections). Key insights: DE `loggen`=false friend, PL `zalogować`=sign-in, ES `apesta`→`un bajón` + `coger` LatAm trap, UK war-blackout post-2022, ID/FA gender-neutral grammar bonus, AR bidi LRM/RLM, FA ZWNJ orthography.
  - [[concepts/calc-user-targets-roadmap]] — Updated 2026-05-16 ✓. P1.5 v5 status, digital twin proposal staging pattern.
  - [[concepts/personalized-macro-split]] v5 section — Complete ✓ (mig 230 full details, sentinels, latency, boundary lesson, digital twin verification).
  - [[concepts/copywriter-playbook]] — Created 2026-05-18, consolidates Phase 0-4 knowledge including 2026-05-16 plan ✓.
- Skipped (minor operational, no KB-worthy concept):
  - n8n self-hosting SWOT analysis session (03:17) — reconfirmation of existing decision already documented in [[concepts/n8n-self-hosting]], no new factual content.
  - Memory flush (03:17) — FLUSH_OK, nothing to save.
- Note: Daily 2026-05-16 covers 4 themes: (1) **n8n infrastructure analysis** (SWOT self-host vs Python migration — reconfirmed existing decision). (2) **Mig 230 v5** (gender-conditional carbs floor, sentinel verification, digital twin verification pattern). (3) **UX-копирайтинг Phase 0** (plan `proud-tickling-willow.md` approved, audit 18 RU keys, snapshot `backup_ui_translations_terminology_20260516`). (4) **UX-копирайтинг Phase 1** (mig 231 RU terminology — «стрик»→«серия», «залогировать»→«записать», hybrid glossary, subagent writer, placeholder assertions, PR #82). (5) **UX-копирайтинг Phase 2** (Sassy Sage Multilingual Glossary — 11 language sections, 11 parallel subagent-копирайтеров, FA Usage Policy workaround, 128 KB reference doc). All content successfully compiled into existing KB articles by sessions 2026-05-16 through 2026-05-18.

## [2026-05-23T09:22:00+03:00] compile | daily/2026-05-15.md

- Source: daily/2026-05-15.md
- Articles created: (none — major concepts already compiled by inline agents during 15.05 sessions)
- Articles updated:
  - [[concepts/personalized-macro-split]] — Added mig 228 (hide training_skip button, UX follow-up to v4). Training_skip маппился в mixed-tier, UX-обман для юзеров выбиравших «Пропустить». Скрыт через `visible_condition='false'`. Backend-ветка оставлена для in-flight inline-клавиатур.
  - [[concepts/language-switch-headless-ux]] — Added Bug 7 (Python handler не обрабатывал `reply_keyboard_refresh` сигнал из SQL mig 124). Fix: `_maybe_build_reply_kb_refresh` в `handlers/menu_v3.py`. Lesson: SQL post-action signals (`reply_keyboard_refresh`, `translations_override`, `success_reaction`) не доходят до `render_envelope` автоматически — нужен пост-процессор в handler'е.
  - [[concepts/telegram-sticker-pipeline]] — Index entry updated: added §8.4d TWO INDEPENDENT LAYERS pattern (body-effect separation for Veo prompts, lesson from streak_30days 3 iterations), streak_14days + streak_30days history entries, §7.7 series differentiation.
- Already compiled by inline agents (verified, no gaps found):
  - [[concepts/personalized-macro-split]] v4 section (mig 227: PAL fusion, 'none' coefficients, conditional clamp) — complete ✓
  - [[concepts/migration-collision-guard]] — 4th collision incident + automated hook/CI — complete ✓
  - [[concepts/telegram-sticker-pipeline]] §8.4d TWO INDEPENDENT LAYERS — complete ✓
  - [[concepts/calc-user-targets-test-spreadsheet]] — Digital Twin v6.3 verification — complete ✓
- Skipped (minor operational, no KB-worthy concept):
  - Mig 229 (icon_speech on help support button) — cosmetic fix, one UPDATE
  - Digital Twin prod-first rule — operational workflow decision, documented in personalized-macro-split v4 section
- Note: Daily 2026-05-15 covers 5 themes: (1) **Mig 227 v4 formula** (PAL fusion + 'none' coefficients + conditional clamp — major calc fix). (2) **4th migration collision** (mig 217 renumber, triggered migration-collision-guard automation). (3) **Mig 228 training_skip hide** (UX follow-up v4). (4) **Reply-keyboard refresh Python-side fix** (signal gap from Phase 2 migration). (5) **Sticker streak_30days** (TWO INDEPENDENT LAYERS Veo prompt pattern, 3 source iterations). (6) **Digital Twin verification** (Google Sheets v6.3, prod-first rule).

## [2026-05-23T09:15:00+03:00] compile | daily/2026-05-14.md

- Source: daily/2026-05-14.md
- Articles created: (none — all KB articles created/updated by inline agents during 14.05 sessions)
- Articles updated (index entries refreshed):
  - [[concepts/phase4-onboarding-migration]] — Added source `daily/2026-05-14.md`, bumped to 2026-05-14. Content already present: gotcha #35 (mig 216 phenotype quiz UX rewrite — preserve RPC 3-button mapping, section titles, progress bars, anti-shaming framings, idiomatic love-handles per 13 langs, subagent for 153 LOC SQL). Recipe для future multi-lang wizard UX rewrites.
  - [[concepts/safe-create-or-replace-recipe]] — Added source `daily/2026-05-14.md`, bumped to 2026-05-14. Content already present: anti-pattern `CREATE OR REPLACE FUNCTION` при изменении signature без `DROP` старой версии (mig 224→226 hotfix, ERROR 42725 ambiguous function).
  - [[concepts/phase6-location-migration-plan]] — Added source `daily/2026-05-14.md`, bumped to 2026-05-14. Index summary rewritten to reflect: Phase 6.3 CLOSED (PR #66, mig 210 Canonical Hybrid), Phase 6.4 step 1 DONE (02.1_Location deactivated via SQLite UPDATE), PR #68/#69 P1-P4 UAT hotfixes (One Menu geo prompt delete, JSONB-array generic resolver, pagination arrows, delete_only strategy, NO_INDICATOR_STATUSES expansion).
- Articles verified (already had correct content + dates in existing articles):
  - [[concepts/telegram-sticker-pipeline]] — Updated 2026-05-14 ✓. Sections 7.7 (series differentiation lesson from streak_14days v1 rejection), 8.4b (checklist for prompt-writing agents — no floor/reflections/dancing/perspective), history entries for streak_7days + streak_14days.
  - [[concepts/canonical-hybrid-location-picker]] — Created 2026-05-14 ✓. Phase 6.3 full implementation: two-state UX, handler-side intercept, Geoapify reverse-geocode, subagent mig 210.
  - [[concepts/save-bot-message-contract]] — Created 2026-05-14 ✓. Tech debt #7 smoke (legacy n8n AI Engine orphaned bubble), defensive `_clear_stale_last_bot_message`, Phase 6.4 TODO.
  - [[concepts/subscription-management-headless]] — Created 2026-05-14 ✓. Mig 219-225: headless `my_subscription`, Gatekeeper delete (silent cancel trial, blocker paid), `reset_to_onboarding` extended signature, grammar audit.
  - [[concepts/one-time-attach-pattern]] — Updated 2026-05-14 ✓. Tech debt #7 closed.
- Note: Daily log 2026-05-14 is very large (~10 sessions by 3+ agents across sticker pipeline, Phase 6.3/6.4, phenotype UX, subscription management, and function overload hotfix). Content breakdown: (1) **Sticker pipeline sessions** (streak_7days final + streak_14days with series differentiation lesson 7.7 + handover prep + prompt checklist 8.4b). (2) **Phase 6.3 closeout** (PR #66: Canonical Hybrid two-state UX, mig 210, Geoapify reverse-geocode, subagent for 666 LOC SQL; lesson: audit Python handler chain BEFORE mig apply). (3) **Phase 6.3 UAT P4 hotfix** (PRs #68/#69: GEOAPIFY_API_KEY operational fix, One Menu geo prompt, generic JSONB-array resolver, `delete_only` OutboundStrategy, NO_INDICATOR_STATUSES expansion) + **Phase 6.4 step 1** (02.1_Location deactivated via SQLite). (4) **Mig 216 phenotype quiz UX rewrite** (anti-shaming framings, Sassy Sage section titles, progress bars, idiomatic love-handles per 13 langs via subagent). (5) **Tech debt #7 Phase 2** (mig 217 restore_choice delete_and_send_new + defensive stale-mid cleanup + save-bot-message-contract KB). (6) **Subscription management headless** (mig 219-225: my_subscription screen, Gatekeeper delete, cancel via meta.save_rpc, reset_to_onboarding extended, grammar audit). (7) **Mig 226 hotfix** (DROP stale function overload after signature change — safe-create-or-replace anti-pattern).

## [2026-05-23T09:07:00+03:00] compile | daily/2026-05-13.md (incremental pass)

- Source: daily/2026-05-13.md
- Articles updated (incremental — gaps from initial compilation):
  - [[concepts/n8n-route-classifier-edit-loc-patch]] — Added ✅ REMOVED section: patch v9 removed in PR #59 (Phase 6.2, 2026-05-13). NLM-сюрприз: no SQL migration needed (loc_* callbacks are dynamic). Cross-ref to [[concepts/headless-fsm-vs-dynamic-handler-separation]].
  - [[concepts/architecture-registry]] — Updated flag table: `dispatcher_python_authoritative_admin_only` marked as REMOVED from Python (PR #60, 2026-05-13). DB-key retained for audit, Python gate code deleted. All users now through Python authoritative without admin-only filter.
- Articles verified (no gaps found):
  - All 7 articles from initial compilation confirmed complete
  - Index entries confirmed up-to-date

## [2026-05-22T22:15:00+03:00] compile | daily/2026-05-13.md

- Source: daily/2026-05-13.md
- Articles created: (none — all concepts compiled inline by agents during 13.05 sessions)
- Articles updated:
  - [[concepts/headless-architecture]] — Added `daily/2026-05-13.md` to sources, bumped updated date to 2026-05-13. Content already present: Virtual Screens (`_<name>` namespace) + PUI lookup fallback chain (mig 211); `meta.url_template` для динамических URL-кнопок (mig 209). Written by inline agent during UAT edit-meal series (5 PRs #61-#65).
  - [[concepts/sassy-sage-dialog-variants]] — Added `daily/2026-05-13.md` to sources, bumped updated date to 2026-05-13. Content already present: Python `_resolve_text` JSONB-array variants via `_coerce_translation_value` helper (random.choice) + double-brace normalisation `{{icon_X}}`→`{icon_X}` in both entry-points (mig 213, PR #63).
  - [[concepts/supabase-db-patterns]] — Added `daily/2026-05-13.md` to sources, bumped updated date to 2026-05-13. Content already present: `food_logs.id` (PK строки) ≠ `food_logs.meal_id` (grouping UUID) — mig 215 hotfix for set_editing_last_meal dataloss bug (PR #65).
- Articles verified (already had correct sources + dates in frontmatter/index):
  - [[concepts/headless-fsm-vs-dynamic-handler-separation]] — Created 2026-05-13. Phase 6.2 architecture decision: static buttons → SQL FSM, dynamic → Python handler. Setters ≠ FSM.
  - [[concepts/n8n-data-flow-patterns]] — Updated 2026-05-13. execution_entity SQLite diagnostic recipe + 04_Menu Command Classifier syntax hotfix (`else else if` → 100% fail).
  - [[concepts/python-vs-n8n-template-grammar]] — Updated 2026-05-13. JSON boundary type-erosion bug (PUI `->>'…'` text-cast → `_coerce_message_id` universal fix, mig 214).
  - [[concepts/specs-vs-reality-ground-truth]] — Updated 2026-05-13. NLM RAG staleness lesson (contra-verdict pattern: NLM advised rollback to broken n8n, live recon disproved via execution_entity + journalctl).
  - [[concepts/phase6-location-migration-plan]] — Phase 6.2 marked CLOSED.
- Index: all 7 affected entries already had correct sources + 2026-05-13 dates (updated by inline agents).
- Note: Daily log 2026-05-13 covers 3 sessions by 2 different agents. Content breakdown: (1) **Session 1 — Phase 6.2 edit-flow + P1 Noop hotfix** (PRs #58/#59/#60): timezone picker delete-before-render fix for noop strategy; location edit-flow in Python without SQL migration (NLM revealed loc_* callbacks are dynamic); router section 4e-pre (patch v9) removed; admin-only canary flag flipped to false. Compiled into [[concepts/headless-fsm-vs-dynamic-handler-separation]] (new) + [[concepts/phase6-location-migration-plan]] (updated). (2) **Session 2 — bug investigation** (agent busy-volhard): `cmd_edit_last` / `share_invite_link` non-functional due to empty `meta={}` in ui_screen_buttons; handover for location agent with Sassy variants mapping. Investigative only, no code changes. (3) **Session 3 — UAT 13.05 fix cascade** (PRs #62/#63/#64/#65 + n8n PUT): mig 211 Virtual Screen `_global_floating_actions` + PUI fallback lookup; mig 213 JSONB-array variant support + double-brace normalisation; n8n 04_Menu Command Classifier `else else if` syntax hotfix via surgical PUT; mig 214 callback_message_id type-erosion universal fix; mig 215 set_editing_last_meal `SELECT id` → `SELECT meal_id` data-loss fix. NLM contra-verdict (rejected rollback advice based on live execution_entity evidence). Compiled into 5 existing articles by inline agents during sessions.

## [2026-05-22T21:50:09+03:00] compile | daily/2026-05-12.md

- Source: daily/2026-05-12.md
- Articles created: (none — all new KB articles were created by inline agents during sessions: noop-render-strategy-pattern.md created, telegram-sticker-pipeline.md sections 7.4/7.5/7.5b/7.6/8.2 added, phase4-onboarding gotcha #34 added, release-protocol.md SQL-lifecycle section added, ui-stickers-headless.md activation section added, test-user-reset-recipe.md updated to one-liner)
- Articles updated: [[concepts/streak-freeze-cron-logic]] (added mig 205/206 Streak Milestone Unified section: Duolingo-style milestones 3/7/14/30/100, mark_sticker_shown RPC, Channel C sticker push, 78 translations, Duolingo-style stickers_shown reset on break, 13 tests)
- Index: added [[concepts/streak-freeze-cron-logic]] row (was missing from index entirely)
- Note: Daily log 2026-05-12 is very large (~10 sessions, full day). Content breakdown: (1) **Sticker pipeline magenta despill sessions** (00:00-16:00 MSK, 7 sub-sessions) — extensive `make_sticker.py` improvements: magenta chroma-aware despill in contour band, selective hole-fill (`MAX_HOLE_PX=1500`), rembg-loses-fire phenomenon diagnosis (U²-Net considers detached fire as background), scene mode combined alpha fix, alpha-blended jelly splash impossibility proof (YUV chromakey boundary), ping-pong loop technique for avoiding problematic source phases, Veo pillarbox auto-detect (280px black bars), `tightest` preset (96% canvas). All documented inline in KB [[concepts/telegram-sticker-pipeline]] during sessions (sections 7.4, 7.5, 7.5b, 7.6, 8.2 rewrite, 8.4b checklist). 5 sticker versions (v1-v5 `noms_streak_3days.webm`). (2) **Mig 205 streak milestone stickers seed** — 6 Channel C rows in `bot_stickers` (streak_milestone_3/7/14/30/100 + streak_healed), only 3-day has real file_id. (3) **Mig 206 streak milestone unified** — cron rewrite from thresholds 25/50/75 to 3/7/14/30/100, `mark_sticker_shown` atomic RPC, Duolingo-style `stickers_shown` reset on break, 78 translations, 13 tests. Updated in [[concepts/streak-freeze-cron-logic]]. (4) **KB pipeline activation + canonical Negative block** — sections 6.5/6.6 added to pipeline KB (activation recipe + Veo CRITICAL no-environmental-effects block). (5) **Terminal Action before legacy forward** (PR #52 diagnostic → fix) — double-click `cmd_quiz_continue` on phenotype_result before location forward. Helper `_clear_inline_keyboard_safe` fire-and-forget. Already documented in phase4-onboarding-migration.md gotcha #34. (6) **Phase 6.1 deploy** (PR #56 merged) — location onboarding migrated to Python. Mig 207 + `handlers/location.py` ~430 LOC + 25 tests. Already documented in phase6-location-migration-plan.md. (7) **Noop Pattern mig 208** (PR #57) — suppress main item, carrier carries Sassy text + reply-kb. Already created as [[concepts/noop-render-strategy-pattern]] during session. (8) **Reset recipe update** — confirmed `reset_to_onboarding` covers 64 fields, updated test-user-reset-recipe.md to one-liner.

## [2026-05-22T20:15:00+03:00] compile | daily/2026-05-10.md

- Source: daily/2026-05-10.md
- Articles created: [[concepts/n8n-legacy-node-strip-recipe]]
- Articles updated: [[concepts/phenotype-quiz]] (added source daily/2026-05-10.md, updated date), [[concepts/n8n-data-flow-patterns]] (added sources daily/2026-05-10.md + daily/2026-05-13.md, updated date), [[concepts/phase4-onboarding-migration]] (updated index summary + date to reflect gotchas #26-29 from 10.05)
- Note: Daily log 2026-05-10 covers 4 sessions in one evening — phenotype quiz Phase 2 Python-only cutover. Content breakdown: (1) **mig 193 rollback + replay** — `{icon_X}` placeholder'ы несовместимы с legacy n8n JS renderer, discovered live UAT. Rolled back as mig 194, replayed as mig 195 after strip. Already documented in phenotype-quiz.md Phase 2 section. (2) **04_Menu surgical strip** (6 нод removed, 7 connections, dangling executeWorkflow ref blocker resolved via `disabled:true`) — extracted as NEW [[concepts/n8n-legacy-node-strip-recipe]] (reusable recipe for future strips: AI Engine, Edit Meal, Payment). (3) **4 cascading Python-side fixes** after strip (gotchas #26-29 in phase4-onboarding-migration.md): menu_v3 status normalization asymmetry, cmd_edit_phenotype missing from PROFILE_V5_CALLBACKS, _build_button_text not resolving {icon_X} placeholders, edit_phenotype missing from ONBOARDING_STATUSES — all already documented in phase4 gotchas, index summary updated. (4) **deploy.yml smoke false positive** — transient health-check WARNING triggers grep; fix came later (2026-05-17, release-protocol.md lesson). Total: 5 PRs (#36/#38/#39/#40/#41/#42), 399 tests passed.

## [2026-05-22T15:00:00+03:00] compile | daily/2026-05-08.md

- Source: daily/2026-05-08.md
- Articles created: [[concepts/webhook-server-async-patterns]]
- Articles updated: (none — existing KB articles already cite daily/2026-05-08.md as source; streak-freeze-cron-logic, release-protocol, n8n-route-classifier-edit-loc-patch were compiled by inline agents during their sessions)
- Note: Daily log 2026-05-08 is very large (~7 sessions, ~13 hours of work). Content breakdown: (1) **Tech debt #13 mig 179** (country/timezone forward marker pattern) — already compiled into n8n-route-classifier-edit-loc-patch.md + phase6-location-migration-plan.md + phase4-onboarding-migration.md. (2) **Hotfix v2-v5 n8n PUT series** (Profile v5 cmd_edit_country/timezone, pre-existing JS syntax bugs, cancel_location route, Restore Main KB) — already compiled into n8n-route-classifier-edit-loc-patch.md (PUT v2..v11 sections). (3) **Streak/league investigation mig 187** (last_log_date vs last_active_at) — already compiled into streak-freeze-cron-logic.md. (4) **Documentation cleanup + KB consolidation** — meta/process, not code knowledge. (5) **CI/CD Part 3 GitHub Actions deploy workflow** — already compiled into release-protocol.md. (6) **PR #32 rollback defenses** (pr-sanity workflow + stale-worktree pre-push hook + nightly audit) — already compiled into release-protocol.md + migration-collision-guard.md. (7) **NEW: 3 async performance/concurrency patterns** (TD-#16 asyncio.gather parallel delete+send p50 323→180ms; TD-#17 per-tid asyncio.Lock; TD-#18 pre-delete for legacy forward) — extracted as new [[concepts/webhook-server-async-patterns]]. This was the only genuinely uncompiled content from the daily.

## [2026-05-22T10:04:04+03:00] compile | daily/2026-05-09.md

- Source: daily/2026-05-09.md
- Articles created: [[concepts/smart-freeze-notification-delivery]]
- Articles updated: [[concepts/streak-freeze-cron-logic]] (added cross-ref to mig 191 follow-up + daily/2026-05-09 source)
- Note: Daily log 2026-05-09 contains 7 sessions, most of which are memory flushes from prior work already compiled. Content breakdown: (1) **Memory flushes** (02:47 timestamps) — Variant B Phase 1 completion (already in variant-b-cutover.md), flat template fix mig 162-164 (already in python-vs-n8n-template-grammar.md), double thinking sticker mig 165 (already in phase4-onboarding-migration.md gotcha #5 + telegram-proxy-indicator.md), n8n self-hosting analysis (already in n8n-self-hosting.md). (2) **Streak/freeze fix mig 187** — already compiled from daily/2026-05-08 in streak-freeze-cron-logic.md; this daily adds mig 190 context. (3) **Phase 4 onboarding hotfixes mig 190** — `set_user_training_type` FSM advance bug (status stuck at registration_step_training). Already documented in phase4-onboarding-migration.md gotcha #23. Half-measure anti-pattern lesson (manual UPDATE юзера для обхода бага = rejected by tech lead) — already in gotcha #24. (4) **NEW: Smart Freeze Notifications mig 191** — Hybrid D delivery pattern: cron sets `pending_freeze_notification_at` flag (not send push at night), two delivery channels (Scenario A: intercept in telegram_proxy INSTEAD of thinking-sticker; Scenario B: dedicated cron freeze_notification_pusher hourly :15 for local_hour>=9). Anti-spam with meal_morning skip. `get_indicator_context` v2 (DROP+CREATE for RETURNS TABLE shape change). 13-lang translations. Sticker placeholder pattern (Channel C). 7 integration tests FN1-FN7, 22/22 total PASSED. Extracted as new [[concepts/smart-freeze-notification-delivery]].

## [2026-05-22T09:53:00+03:00] compile | daily/2026-05-07.md

- Source: daily/2026-05-07.md
- Articles created: (none — all content compiled into existing articles by inline agents during 07.05 session)
- Articles updated:
  - [[concepts/one-time-attach-pattern]] — Added YAML frontmatter with formal source references (`daily/2026-05-07.md` for mig 182/183/184, `daily/2026-04-30.md` for mig 159/160 origin, `daily/2026-05-14.md` for Tech debt #7 closure). Article content was already comprehensive — written by the same agent who implemented mig 182/183/184 on 07.05.
- Note: Daily log 2026-05-07 covers one major session: **One-Time Attach Pattern** (mig 182/183/184 + revert mig 181). Content breakdown: (1) Architectural decision — reply-keyboard прикрепляется один раз навсегда + точечные re-attach in edge cases. 3 ветки CASE в render_screen: reply_kb_screen, conditional re-attach после text_input, unconditional attach для onboarding_success_menu. (2) Mig 182 — INSERT `onboarding_success` + `onboarding_success_menu` screens, CREATE OR REPLACE process_user_input с 30-day staleness heuristic, `app_constants.icon_wave='👋'`. (3) Mig 183 — carrier_text_key chain: SQL emits key → Python `_resolve_carrier_text` resolves from translations → fallback `icon_wave` → final `·`. (4) Mig 184 — `attach_main_kb_unconditional` meta flag; gotcha #26 (input_type='reply_kb' catches first CASE → empty rows → workaround via input_type='inline_kb' + meta flag). (5) Python changes — multi-item envelope after complete_onboarding (`_envelope_from_rpc_result` accepts `rpc_caller`, renders second screen `onboarding_success_menu`, extends items). (6) `_resolve_carrier_text()` chain: `carrier_text_key` → translations dotted-path → `constants["icon_wave"]` → `"·"` (4-level fallback). (7) Tech debts #7-#12 enumerated. (8) 408 tests passed, +7 new. All compiled into [[concepts/one-time-attach-pattern]] by inline agent. Gotchas #26/#27/#28 from daily embedded in that article. No new standalone concepts warranted — the One-Time Attach Pattern article comprehensively covers this entire session's output.

## [2026-05-22T09:44:51+03:00] compile | daily/2026-05-04.md

- Source: daily/2026-05-04.md
- Articles created: [[concepts/cron-silent-failure-alerting]], [[concepts/e2e-telethon-crawler]]
- Articles updated: (none — remaining content already compiled into existing articles by inline agents during 04.05 sessions)
- Note: Daily log 2026-05-04 covers 14 workstreams in a single intense day. Most content was already extensively compiled into existing KB articles during the session itself (inline agents). Cross-verification against 12 existing articles confirmed no gaps: `architecture-registry` (n8n audit + DELETE 5 workflows), `phase4-onboarding-migration` (gotchas #9 RESTORING_CALLBACKS + #10 /start mid-onboarding mig 170), `safe-create-or-replace-recipe` (mig 167 = 3rd stale-base case), `python-vs-n8n-template-grammar` (mig 168 gamification templates + mig 169 variant arrays), `n8n-data-flow-patterns` (Safe PUT recipe for 03_AI_Engine Send error refactor), `router-prefix-collision` (E2E crawler discovery of `{👑}` leak), `release-protocol` (cherry-pick PR #6 lesson), `soft-delete-account` (restore-account UI hotfix). Two genuinely new concepts extracted: (1) **Silent cron failure pattern** — apscheduler masking HTTP 400 from RPC + NoneType guard for optional dict values + centralized `BaseCron._alert_admin` with per-cron 6h cooldown; (2) **E2E Telethon DFS crawler** — headless UI smoke testing via DFS traversal of inline keyboards with safety gates, cycle protection, and dynamic string matching from DB.

## [2026-05-21T18:05:00+03:00] compile | daily/2026-05-01.md

- Source: daily/2026-05-01.md
- Articles created: (none — all content already compiled into existing articles by inline agents during 01.05 sessions)
- Articles updated:
  - [[concepts/variant-b-cutover]] — Source already covers `daily/2026-04-29..2026-05-01.md`. Content verified: (1) production incident `ExpressionError: Node hasn't been executed` for 04_Menu + 03_AI_Engine → §"Структурное ограничение"; (2) NLM Option D (renaming hack) analysis + rejection → §"Alternatives"; (3) TARGET_TO_PATH narrowing to `{menu_v3}` → §"Принятое решение". No gaps found — article was written by the same agent who did the work on 01.05.
  - [[concepts/phase4-onboarding-migration]] — Source `daily/2026-05-01.md` already listed. Content verified: mig 161 (~688 LOC), `process_onboarding_input` FSM (10 states), `ensure_user_exists` RPC, `dispatch_with_render` inject, `handlers/onboarding_v3.py` (~477 LOC), 29 test cases, deploy with flag OFF. All in §"Что создано" + §"SQL миграции" + §"Python код" + §"Тесты".
  - [[concepts/phase2-python-menu-v3]] — Source `handover/2026-05-01_variant_b_phase1_complete.md` already listed. Joint deploy with Variant B on 01.05 documented in §10.
- Note: Daily log 2026-05-01 covers 2 major workstreams: (1) **Variant B Phase 1 cutover** — joint deploy with Phase 2 reply-keyboard fixes, production incident with `$('NodeName')` structural incompatibility, NLM consultation about Option D (renaming hack → rejected due to staged rollout break), hotfix narrowing TARGET_TO_PATH to `{menu_v3}` only (commits `85afc1e` → `438ce1c`). All compiled into [[concepts/variant-b-cutover]]. (2) **Phase 4 onboarding chip #2-execute** — mig 161 applied (process_onboarding_input FSM + ensure_user_exists + dispatch_with_render inject + 2 ui_screens + 39 translations + bot_stickers placeholder), handlers/onboarding_v3.py created (220 LOC), 29 tests green, deployed with `handler_onboarding_use_python=false` (flag ON deferred to chip #3). All compiled into [[concepts/phase4-onboarding-migration]]. Migrations 157/158/160 (Phase 2 agent) + 161 (Phase 4) accounted for across 3 existing articles. No new standalone concepts warranted — production incident lesson maps to existing variant-b-cutover §"Структурное ограничение", joint deploy coordination maps to existing release-protocol multi-agent rules.

## [2026-05-21T17:44:53+03:00] compile | daily/2026-04-30.md

- Source: daily/2026-04-30.md
- Articles created: (none — all content already compiled into existing articles by inline agents during 30.04 sessions)
- Articles updated:
  - [[concepts/phase2-python-menu-v3]] — Added explicit "Compiled from" reference to `daily/2026-04-30.md` in header. Article already comprehensively covers: architecture (§1), feature flags (§2), template engine (§3), reply-keyboard mig 159/160 (§4), validation ADR-3 (§5), One Menu persistence ADR-2 (§6), artifacts (§7), 4 production incidents (§8), Variant B relation (§10). No content gaps.
- Index updated:
  - [[concepts/one-time-attach-pattern]] — **Added to index** (article existed since 07.05 but was never indexed). Source includes `daily/2026-04-30.md` for mig 159/160 origin story.
- Note: Daily log 2026-04-30 covers Phase 2 menu_v3 Python handler deployment — the largest single-day architectural change in the n8n→Python migration. Content breakdown: (1) `handlers/menu_v3.py` 322 LOC + 35 tests — compiled into [[concepts/phase2-python-menu-v3]] by inline agent; (2) 3 ADR fixes (hot-reload flag mig 156, save_bot_message SendResult, screen_validation pre-check) — compiled into phase2-python-menu-v3 §2/§5/§6; (3) Reply-keyboard mig 159/160 (initial unconditional → conditional by previous_status) — compiled into [[concepts/one-time-attach-pattern]] + phase2-python-menu-v3 §4; (4) Late-day Variant B foundation (mig 155/157/158, dispatcher/forward.py, services/app_flags.py) — compiled into [[concepts/variant-b-cutover]]; (5) 4 production incidents 14:39→19:00 MSK (400 Bad Request headless mismatch, 204 No Content retry storm, reply-kb vanish on delete-after-send, final mig 160 fix) — compiled into phase2-python-menu-v3 §8. All migrations 155-160 accounted for across 3 existing articles. No new standalone concepts warranted — all knowledge maps to existing architecture patterns.

## [2026-05-20T22:15:00+03:00] compile | daily/2026-05-06.md

- Source: daily/2026-05-06.md
- Articles created: (none — all content updates existing articles; gotchas 19-25 already compiled into phase4-onboarding-migration by inline agents during 06.05 sessions)
- Articles updated:
  - [[concepts/one-menu-ux]] — Added "One Menu Promotion Pattern (mig 180)" section: template_engine auto-promotes `send_new + callback_message_id` → `replace_existing`, eliminating "двойные сообщения" при inline callback навигации к headless-экранам. Added `daily/2026-05-06.md` to sources.
  - [[concepts/headless-architecture]] — Added "Update 2026-05-06 (mig 180)" section: (1) action='start' для registered юзера → `render_screen('stats_main')` вместо forward на деактивированный `02_Onboarding_v3` (Вариант D headless-first); (2) Headless contract: `language_code` в `result.meta`, не в `telegram_ui` (чистый UI без identity-полей) — lesson из Language Lag bug. Added source.
- Index updated:
  - [[concepts/one-menu-ux]] — Summary expanded with One Menu promotion pattern. Source + date updated.
  - [[concepts/headless-architecture]] — Summary expanded with mig 180 action='start' cleanup + meta contract. Source added.
- Note: Daily log 2026-05-06 covers 4 sessions: (1) Mig 178 — third stale-base regression (changing_language ghost status) compiled into phase4-onboarding-migration gotcha #19 by inline agent; (2) Mig 179 — legacy overload DROP + set_user_language contract fix compiled into phase4 gotcha #19 extension by inline agent; (3) Live QA bugs (Language Lag / Silent Validation / NUMERIC_RE) compiled into phase4 gotchas #20/#21/#22 by inline agent; (4) Mig 180 — action='start' headless cleanup + One Menu promotion + meta contract — NEW, compiled into one-menu-ux + headless-architecture by this pass; (5) Mig 181 — reply-kb force attach compiled into one-time-attach-pattern by inline agent. Migrations 178-181 all accounted for across existing articles.

## [2026-05-20T20:26:38+03:00] compile | daily/2026-05-05.md

- Source: daily/2026-05-05.md
- Articles created: (none — all content was compiled inline by agents into existing articles during the 6 sessions of 2026-05-05)
- Articles updated:
  - [[concepts/release-protocol]] — Added "Lesson 2026-05-05: 3 параллельных команды + race condition при deploy из веток" section: 3 agents (onboarding fix / URL buttons / payment isolation) each deployed `./deploy.sh` from their feature branches → Frankenstein VPS state → 4h reconciliation. Resolution: cherry-pick + merge → PR #12 → deploy from clean main. Added `daily/2026-05-05.md` to sources.
- Index updated:
  - [[concepts/release-protocol]] — Summary expanded with Lesson 2026-05-05 (3-team race condition). Source added.
- Note: Daily log 2026-05-05 covers 6 sessions: (1) Comprehensive onboarding fix 4 blocks A/B/C/D (get_user_context 404, render_screen reply_kb, validation discrimination, cmd_confirm_delete) — compiled into [[concepts/phase4-onboarding-migration]] gotchas #11-#18 + TODOs #2/#3 closure by inline agent; (2) Migration 172 inline buttons + literal \n fix + Ghost Message — compiled into phase4 + [[concepts/one-time-attach-pattern]] by inline agent; (3) Router ONBOARDING_STATUSES guard + mig 173 — compiled into phase4 gotcha #14 + [[concepts/router-prefix-collision]] by inline agent; (4) Ghost reply-kb cleanup + One Menu UX callback_message_id inject — compiled into phase4 gotcha #16 by inline agent; (5) Mig 175 FSM goal→speed + HTTP 400 fallback — compiled into phase4 TODO #4 + gotcha #17/#18 by inline agent; (6) Mig 176 meta.url URL buttons — compiled into [[concepts/headless-architecture]] Gotcha 6 by inline agent; (7) Mig 177 payment `{👑}` leak — compiled into [[concepts/router-prefix-collision]] by inline agent; (8) Unified release 3 teams — NEW, compiled into [[concepts/release-protocol]] by this pass; (9) CLAUDE.md cleanup + CI/CD rule — created [[concepts/release-protocol]] during session (already in KB). Migrations 171-177 all accounted for across existing articles.

## [2026-05-19T15:10:00+03:00] compile | daily/2026-04-29.md

- Source: daily/2026-04-29.md
- Articles created: (none — all content fits into existing articles)
- Articles updated:
  - [[concepts/nav-stack-architecture]] — Added migrations 146 (back fallback stats_main + push_nav cap 7) and 147 (I-came-from path-walk: truncate-on-existing, is_inline source-aware, Priority 1/2 inversion, advisory_xact_lock). Added daily/2026-04-29.md to sources. Updated Key Points (4→5 bullets with new migration semantics). Added two full detail sections with verify results, before/after tables, Python handover notes.
- Index updated:
  - [[concepts/nav-stack-architecture]] — Summary expanded with mig 146/147 details. Source added. Date 2026-04-27 → 2026-04-29.
- Note: Daily log 2026-04-29 covers 6 sessions: (1) chip #1.5 pre-implementation audit for onboarding migration → already compiled as standalone `onboarding-v3-map-supplement.md`; (2) check_n8n_reachable hardcode fix (closing tech debt #1, already captured in existing n8n-self-hosting KB); (3) Catch-up commits + Phase 0.5+1 deploy + 08.x deactivation (already reflected in architecture-registry live audit section + n8n-selfhost-migration deactivation rule with activeVersionId=NULL); (4) Migration 146 back fallback → stats_main + nav_stack cap=7; (5) Migration 147 I-came-from path-walk navigation overhaul (major); (6) KB sync session (MEMORY/CLAUDE/headless-architecture docs catch-up — meta-maintenance, not compilable knowledge). Sessions 4+5 are the new compilable knowledge → updated nav-stack-architecture.

## [2026-05-19T14:38:36+03:00] compile | daily/2026-04-28.md

- Source: daily/2026-04-28.md
- Articles created: (none — all content pre-compiled into existing articles by working agents during 28.04 sessions)
- Articles updated:
  - [[concepts/progress-hub-headless]] — Added `daily/2026-04-28.md` as source (mig 144 shop transactions + mig 145 ambassador payout applied this date). Status already reflected "Applied 2026-04-28" but source was missing.
- Index updated:
  - [[concepts/n8n-self-hosting]] — Summary expanded: Supabase pooler TLS cert fix, OOM incident, Docker `mem_limit` vs `deploy.resources.limits`, host swap, V8 heap cap, multi-agent VPS safety rule. Source `daily/2026-04-28.md` already in article frontmatter. Date confirmed `2026-04-28`.
  - [[concepts/n8n-selfhost-migration]] — Summary expanded: HOT bug `allowUnauthorizedCerts`, `deploy.resources.limits` ≠ `mem_limit` lesson, host swap vs container swap philosophy. Source already in article text. Date updated to `2026-04-28`.
  - [[concepts/telegram-proxy-indicator]] — Summary expanded: WebhookHealthCron alert-only mode (28.04), localhost trap lesson, Phase 3 `maybe_sync_user_profile`. Source already in frontmatter. Date updated to `2026-04-28`.
  - [[concepts/progress-hub-headless]] — Summary expanded: mig 144 (8 screens, idempotency, error_screen_map) + mig 145 (9 screens, balance reservation, anti-spoofing). Source added.
- Note: Daily log 2026-04-28 covers 6 sessions: (1) Postgres credential cert fix — cascade diagnosis (3 error fingerprints → 1 root cause via SQLite `execution_entity`); (2) webhook_health alert-only mode (localhost trap after big-bang switch, threshold 3→7); (3) mig 144 shop transactions headless (8 screens, idempotency window, error_screen_map pattern); (4) mig 145 ambassador payout headless (9 screens, 4 RPCs, balance reservation, anti-spoofing phone); (5) VPS OOM incident (Docker `deploy.resources.limits` ignored in standalone, n8n 281→2700 MB memleak, multi-agent SSH load); (6) VPS stability plan-B (host swap 2 GB, V8 `--max-old-space-size=1024`, aggressive pruning MAX_AGE=48h, `memswap_limit=mem_limit` fail-fast philosophy). All content was compiled inline by agents into existing articles during sessions — this entry formalizes the record.

## [2026-05-10T14:00:00+03:00] compile | daily/2026-04-27.md (verification pass — n8n self-hosting Steps 0.5-0.8 + Incident 22:15)

- Source: daily/2026-04-27.md (third pass — prior passes covered Bug 6 deployment and empty-log state)
- Articles created: (none — all content already in existing articles from prior compilation)
- Articles updated: (none — verified complete)
- Verification:
  - [[concepts/n8n-selfhost-migration]] — already contains: reorg /home/n8n→/home/noms/n8n, owner setup via REST API, n8n_migrate.py (credentials+workflow import+relink), schema validation gotchas (postgres sshTunnel:false, openAi header:false), big-bang switch checklist, circular reference publish-time validation SQL workaround, live latency 58-157ms, Incident 22:15 MSK auto-fallback cascade (hardcoded probe URL + .env restart rule). Sources: daily/2026-04-26.md + daily/2026-04-27.md ✅
  - [[concepts/n8n-self-hosting]] — already contains: Steps 0.1-0.8 DONE status, VPS resource baseline, docker-compose key decisions, backup strategy (daily VACUUM INTO), tuning parameters (swap, pruning, V8 heap cap), Cancellation of n8n Cloud. Sources: daily/2026-04-26.md + daily/2026-04-27.md ✅
  - [[concepts/nav-stack-architecture]] — already contains Phases 5-8 + R1 deployment confirmation (compiled in prior pass T20:00:00) ✅
  - [[concepts/payment-integration]] — already contains JSON.stringify pre-existing bug confirmation (compiled in prior pass T20:00:00) ✅
  - [[concepts/n8n-data-flow-patterns]] — already contains JSON.stringify anti-pattern + continueOnFail rule. Sources include daily/2026-04-27.md ✅
- Note: This daily log was compiled across 3 passes. All content fully captured in 5 existing articles. No new concepts warranting standalone articles.

## [2026-05-10T13:50:06+03:00] compile | daily/2026-04-24.md (incremental — Session 14 iterations 3-6: migrations 140-143)

- Source: daily/2026-04-24.md (previously compiled 129-139 only; this pass covers the remaining iterations)
- Articles created: (none — content fits as update to existing article)
- Articles updated:
  - [[concepts/progress-hub-headless]] — Major update: added iterations 4-5 (migrations 140/142-143). Migration 142 (~750 LOC): Stateful friends_info (Novice vs Ambassador via `visible_condition` + RPC branching, COALESCE NULL propagation bug), League empty state (countdown days_until_monday), info subscreens (`league_info`, `friends_how_it_works` with eager-resolved RPCs), `rtrim` bug fix, `process_user_input` fastpath +2 callbacks. Migration 143: regexp_replace dedup of duplicate WHEN clauses (26→14). Migrations 144-145 status (confirmed/spec). Deferred table updated. Status → "migrations 129-143 applied". Sources expanded.
- Index updated: progress-hub-headless summary rewritten (migrations 129-143, Stateful UI pattern, COALESCE gotcha, migrations 144/145 status).

## [2026-05-10T14:10:00+03:00] compile | daily/2026-04-27.md (incremental — n8n self-hosting Step 0.8 big-bang switch + incident 22:15)

- Source: daily/2026-04-27.md (previously compiled: Bug 6 Phases 5-8 only; this pass covers the n8n self-hosting sessions)
- Articles created: (none — content was compiled inline by agents into existing articles)
- Articles updated:
  - [[concepts/n8n-self-hosting]] — Source reference `daily/2026-04-27.md` added (was missing; article content already covered Steps 0.1-0.8 status, latency benchmark, backup strategy, cancellation of n8n Cloud, tuning parameters from 28.04)
- Note: The n8n self-hosting sessions (Step 0 part 2: reorg + credentials + n8n_migrate.py, Step 0.8: big-bang switch with 3 подводных камня, Incident 22:15: auto-fallback cascade) were compiled directly into [[concepts/n8n-self-hosting]] and [[concepts/n8n-selfhost-migration]] by agents during the session, not through the formal compile pipeline. Both articles are comprehensive — no content gaps identified. This log entry formalizes the compilation record.

## [2026-04-27T20:00:00+03:00] compile | daily/2026-04-27.md (Bug 6 Phases 5-8 + R1 deployment + Payment pre-existing bug)

- Source: daily/2026-04-27.md
- Articles created: (none — deployment confirmation of already-documented work)
- Articles updated:
  - [[concepts/nav-stack-architecture]] — Added deployment confirmation: Phases 5-8 + R1 smoke-tested live. Phase 5 (Payment Back → cmd_back), Phase 6 (8 replacements + 5 Push Nav + BTR Rule[4] shop), Phase 7 (08.4_Shop), Phase 8 (cleanup), R1 (newcomer welcome). Source added.
  - [[concepts/payment-integration]] — Added deployment confirmation: JSON.stringify double-serialization bug confirmed as pre-existing (not Phase 5 regression). Free user 786301802 affected. Lesson: verify $json source in n8n chain. Source added.
- Index updated: date bumps for nav-stack-architecture (→ 2026-04-27) and payment-integration (→ 2026-04-27).

## [2026-04-27T13:31:09+03:00] compile | daily/2026-04-27.md

- Source: daily/2026-04-27.md
- Articles created: (none — empty daily log)
- Articles updated: (none)
- Note: Daily log contained only memory flush errors (FLUSH_ERROR exit code 1 at 12:13) and one FLUSH_OK at 13:10 with "Nothing worth saving from this session". No technical sessions recorded.

## [2026-04-27T18:00:00+03:00] compile | daily/2026-04-26.md (Self-hosting n8n CE on VPS — Steps 0.1–0.4)

- Source: daily/2026-04-26.md
- Articles created:
  - [[concepts/n8n-self-hosting]] — NEW: Self-hosted n8n CE v2.17.7 via Docker on NOMS VPS. Covers: VPS recon (3.0 GB RAM free, 30 GB disk, Docker not installed), setup steps 0.1-0.4 (user n8n UID 1001, Docker install, compose dir structure, .env credentials via openssl rand, docker-compose.yml, systemd unit). Isolation pattern (permissions mode 750, not userns-remap). SQLite rationale (0.5ms local vs 30ms Supabase network). Deprecated config removed (N8N_BASIC_AUTH_*, N8N_USER_FOLDER, N8N_RUNNERS_ENABLED, user: "1001:1001"). Full pending migration plan (steps 0.5-0.10).
- Articles updated:
  - [[concepts/noms-architecture]] — n8n layer updated to reflect self-hosted CE status (steps 0.1-0.4 done, traffic switch pending). Added cross-reference to n8n-self-hosting.
  - [[concepts/n8n-performance-optimization]] — Added "Self-Hosted n8n" section: cold-start ~1.3-1.5s root cause (Cloud scheduler idle), self-hosting as solution, expected improvement. Added cross-reference to n8n-self-hosting.
- Index updated: added n8n-self-hosting entry.

## [2026-04-27T12:00:00+03:00] compile | daily/2026-04-25.md (Session 15 — Language Switch UX + Debounce Fix + Dispatcher Migration Step 1)

- Source: daily/2026-04-25.md
- Articles created:
  - [[concepts/language-switch-headless-ux]] — NEW: 6 language switch UX bugs diagnosed and fixed. Bug 1: `buttons.edit_lang` text_key (orphan `buttons.edit_language` had only ru translation). Bug 2: `translations_override` from `process_user_input` when `save_rpc='set_user_language'` (Migration 124). Bug 3: explicit `cmd_back + status=registered → menu_v3` route in Dispatcher Route Classifier. Bug 4: `reply_keyboard_refresh=true` flag → Dumb Renderer prepends `sendMessage` with fresh `mainMenuKB()`. Bug 5: atomic debounce via `last_action_ms` (Migration 141). Bug 6: `continueOnFail+onError:continueRegularOutput` on HTTP deleteMessage.
- Articles updated:
  - [[concepts/anti-spam-debounce]] — Added Migration 140 (cooldown 1500→500ms workaround) and Migration 141 (`last_action_ms BIGINT` + atomic `UPDATE WHERE` pattern). Root cause analysis: `Sync Profile` n8n parallel write vs debounce non-atomic read. Sources + date updated.
  - [[concepts/telegram-proxy-indicator]] — Added Phase 3 section: `maybe_sync_user_profile()` fire-and-forget task in Python proxy (replaces n8n `Sync Profile` node). 01_Dispatcher PUT 55→54 nodes. Sources + date updated.
  - [[concepts/n8n-data-flow-patterns]] — Added `continueOnFail + onError:continueRegularOutput` rule on HTTP deleteMessage nodes. Related concepts updated. Sources + date updated.
  - [[concepts/headless-architecture]] — Added Migration 124 language refresh extension section: `translations_override`, `reply_keyboard_refresh`, `language_code_new` fields in `process_user_input` response. Status + sources updated.
  - [[concepts/supabase-db-patterns]] — Added Migrations 140-141 section: debounce architectural fix (`last_action_ms` atomic UPDATE WHERE). Sources + date updated.
  - [[concepts/index]] — New entry for language-switch-headless-ux; phone-collection-strategy confirmed (already dated 2026-04-25).

## [2026-04-27T00:00:00+03:00] compile | daily/2026-04-24.md (Sessions 13-14 — Progress Hub Headless)

- Source: daily/2026-04-24.md
- Articles created:
  - [[concepts/progress-hub-headless]] — Full Progress Hub headless migration: `progress_main` + quests + league + friends_info + shop. Migrations 129-139. Wrapper RPC pattern (FLAT + eager translations). jsonb_set intermediate key gotcha (Gotcha #3). anchor_only ui_screens entry (migration 137, premium_plans). nav_stack workaround + rollback (migrations 132+138). UX spec alignment (migration 139: 4-neighbor league window, friends reward_block removed, shop free/premium branch). Latency p95 < 210ms. First prod Dispatcher PUT without webhook drift.
- Articles updated:
  - [[concepts/stats-main-headless]] — Migration 125 section added: conditional edit button split (meals_today=1 → cmd_edit_last col_index=0, meals_today≥2 → cmd_show_meals col_index=1). SQL-only fix, no n8n PUT. DELETE+INSERT idempotent pattern. Status updated.
  - [[concepts/headless-architecture]] — Phase 3A Progress Hub section added (migrations 129-139, Sessions 13-14). Not-yet-migrated list updated. Status updated to "progress_main + 4 children DEPLOYED".
  - [[concepts/dumb-renderer-interpolation-gotchas]] — Gotcha #3 added: `jsonb_set` doesn't auto-create intermediate JSONB keys. Fix: top-level merge `content || jsonb_build_object(...)`. Rule summary updated to 4 rules.
  - [[concepts/dispatcher-webhook-reregistration]] — Sessions 13-14 addendum: first prod PUT without drift confirms Session 12 fix (Dispatcher v1.12: cmd_quests/league/friends_info/shop + icon_progress reply-text). Sources updated.
  - [[concepts/supabase-db-patterns]] — Sources + date updated (migrations 039-139). Sources list includes daily/2026-04-24.md.
  - [[concepts/index]] — progress-hub-headless new entry; stats-main-headless, headless-architecture, dumb-renderer-interpolation-gotchas, supabase-db-patterns summaries + dates updated.

## [2026-04-23T23:59:00+03:00] compile | daily/2026-04-23.md (Session 12 addendum — context-compaction resume)

- Source: daily/2026-04-23.md (Session 12 — Python Telegram Middleware applied)
- Articles updated:
  - [[concepts/stats-main-headless]] — Major update: migration 124 added as canonical (supersedes 122). `get_daily_stats_rpc` FLAT top-level. Светофоры via app_constants thresholds. `meals_list_formatted` via string_agg + eager unit_kcal resolve. 1 button with visible_condition. Root cause deep-dives: double-nested template_vars + {tr:} inside {var}. Status changed to "Phase 3A complete". File refs updated (added migration 124). Latency table updated.
  - [[concepts/dispatcher-webhook-reregistration]] — Session 12 section added: Phase 1-5 deployed (Webhook from Python + Validate Secret, 80 refs migrated, Trigger disabled). Async T+8s drift: new failure mode where n8n.cloud re-syncs webhook 8 seconds after PUT (not immediate). Drift log for Session 12 (4 incidents). Current state: root cause eliminated. Phase 6 pending.
  - [[concepts/python-telegram-adapter]] — Status changed from "deferred" to "LIVE Phases 1-5". Full deployment table (6 phases: 1-5 ✅, 6 ⏳). Smoke test results (5 tests, 1 bug found). Async T+8s drift explanation. Current state of 01_Dispatcher (55 nodes, Trigger disabled, all refs migrated).
  - [[concepts/supabase-db-patterns]] — Migration 124 block added: get_daily_stats_rpc FLAT, светофоры design, meals_list_formatted via string_agg + eager resolve, zero hardcodes rule, 5 bugs caught (3 on dry-run, 2 post-apply). Sources updated.
  - [[concepts/index]] — Updated summaries for supabase-db-patterns (039–124), dispatcher-webhook-reregistration (root cause eliminated), stats-main-headless (migration 124 canonical), python-telegram-adapter (Phase 1-5 LIVE).

## [2026-04-23T23:59:00+03:00] compile | daily/2026-04-23.md
- Source: daily/2026-04-23.md (Session 11 — Stats Headless Phase 3A)
- Articles created:
  - [[concepts/stats-main-headless]] — Phase 3A: stats_main headless screen. `get_stats_business_data` RPC (wrapper over get_day_summary). Migrations 122+123. `report.*` translation gap pattern (legacy JS strings not in ui_translations). Adversarial review caught 3 criticals before prod apply (2× hardcoded emoji, 1× validation_rules NOT NULL). Reply-keyboard routing discovery. Latency p50=72.7ms, p95=82.3ms.
  - [[concepts/reply-keyboard-routing-pattern]] — Two completely separate routing pipelines for reply-keyboard vs inline callbacks. Reply path: Dispatcher sets `reply_button_key` → 04_Menu_v3 Route Action Switch. Inline path: Route Classifier → Action Router. Fix template: Dispatcher mapping + 04_Menu_v3 Switch output. Current mapping table.
  - [[concepts/python-telegram-adapter]] — Adapter pattern: Python re-packages raw Telegram JSON to exactly mimic Telegram Trigger output format. n8n uses Webhook Trigger instead of Telegram Trigger — eliminates auto-setWebhook displacement. Baseline dump: `.claude/data/telegram_trigger_dump.json` (15 samples × 7 types). 6-phase flag-based rollout. Status: approved, deferred Session 12+.
- Articles updated:
  - [[concepts/headless-architecture]] — Phase 3A section added: stats_main DEPLOYED (migrations 122+123, n8n Dispatcher+04_Menu_v3 PUTs, latency, reply routing discovery, deferred items); status updated to "Phase 3A"; Phase 3B+ not-yet-migrated list
  - [[concepts/supabase-db-patterns]] — Migrations 122–123 block added: get_stats_business_data wrapper pattern, ui_screens seeded with validation_rules gotcha, adversarial review 3 criticals, Translation Gap Pattern (legacy JS strings → must audit before headless migration); sources + date updated
  - [[concepts/dispatcher-webhook-reregistration]] — Session 11 addendum: n8n.cloud downtime at 19:01 MSK triggered auto-reregistration (new failure mode — no PUT needed); webhook lost 3× during Session 11 (once per Dispatcher PUT); Python Adapter (Variant B) approved, deferred Session 12+; updated sources + date
- Index updated: 3 new entries + supabase-db-patterns + headless-architecture + dispatcher-webhook-reregistration rows updated

## [2026-04-22T23:59:00+03:00] compile | daily/2026-04-22.md
- Source: daily/2026-04-22.md
- Articles created:
  - [[concepts/dispatcher-webhook-reregistration]] — критический баг: ANY PUT к 01_Dispatcher (workflow с Telegram Trigger) автоматически вызывает setWebhook на n8n.cloud URL, вытесняя Python proxy. Инцидент: webhook потерян 5 раз 2026-04-22 (4 deactivate/activate + 1 чистый PUT). Recovery команда. WebhookHealthCron gap. Долгосрочные решения: Вариант A (изолировать Telegram Trigger в stub-workflow) + Вариант B (Python raw JSON proxy без Telegram Trigger в n8n)
- Articles updated:
  - [[concepts/nav-stack-architecture]] — Migration 121: новая сигнатура `back_nav(p_telegram_id, p_current_screen DEFAULT NULL)`, 3-приоритетная anchor fallback цепочка, поле `source` для debug (6 значений), патч process_user_input (2 строки), 7-сценарный E2E на ephemeral user 99999999991; migration 116 picker callbacks без status guard
  - [[concepts/telegram-proxy-indicator]] — секция "🚨 Критический инцидент 2026-04-22": webhook потерян 5 раз от PUT к 01_Dispatcher; команда восстановления; долгосрочные решения A+B; ссылка на dispatcher-webhook-reregistration; updated sources + date
  - [[concepts/headless-picker-pattern]] — Session 10 TOTAL (migrations 110-120): итоговая таблица 9 live pickers, migrations 116-120 описания, edit_country/timezone 2-button entry pattern (migration 120), Session 11 deferred items list (7 пунктов)
  - [[concepts/supabase-db-patterns]] — блок migrations 116-121: Session 10 final polish (116-120 описания), migration 121 full spec (back_nav anchor fallback: новая сигнатура, 3-приоритетная цепочка, source field, E2E coverage), паттерн "передавать hint-экран до изменения статуса"; updated sources + date
  - [[concepts/index]] — добавлена запись dispatcher-webhook-reregistration; обновлены записи nav-stack-architecture, telegram-proxy-indicator, supabase-db-patterns, headless-picker-pattern (summary + даты)

## [2026-04-21T23:59:00+03:00] compile | daily/2026-04-21.md
- Source: daily/2026-04-21.md
- Articles created (session flushes during Session 10):
  - [[concepts/headless-picker-pattern]] — full recipe for inline-kb pickers: ui_screens + ui_screen_buttons + workflow_states + setter RPC + translations + Dispatcher + Dumb Renderer; 9 screens deployed, migrations 110-115, latency p95 < 165ms
  - [[concepts/checkmark-prefix-pattern]] — split concerns: render_screen emits is_current flag, Dumb Renderer prepends ✅; migration 113 initial → 115 revert/fix
  - [[concepts/pre-migration-discovery-recipe]] — 10 psycopg2 Phase 0 queries before any migration; gotchas table, output format
  - [[concepts/specs-vs-reality-ground-truth]] — ground truth priority, RPC body grep via pg_get_functiondef, Session 10 examples
  - [[concepts/adversarial-review-protocol]] — 15-key review checklist; Session 10: migration 110 found 5 CRITICAL + 7 HIGH before prod apply; ROI 12-20x
- Articles created (end-of-day compile):
  - [[concepts/sassy-sage-dialog-variants]] — JSONB array[3] variative responses, migrations 104-108, deep-merge rule, self-referential UPDATE, emoji rule
  - [[concepts/telegram-proxy-indicator]] — Python FastAPI proxy, SSL setup, pre-warm cache, skip-translations, 398ms steady state, WebhookHealthCron, decision framework
- Articles updated:
  - [[concepts/n8n-performance-optimization]] — Python Proxy Architecture section (2026-04-21): 6-10ms ack, ~85% latency, Phase 2 57→53 nodes, pre-warm + skip-translations; updated date 2026-04-15→2026-04-21
  - [[concepts/ux-crosscutting-principles]] — target_weight_kg permanent exclusion confirmed (DB column stays, future progress = delta from current only); Speed Picker UX section (dynamic %, context-aware keyboard, migration 108 keys); updated date
  - [[concepts/supabase-db-patterns]] — Migration 109 section (get_indicator_context + save_indicator_state RPCs for Python proxy); Migrations 104-108 section (dialog variants: deep-merge rule, self-referential UPDATE, scale verification); updated sources + date

## [2026-04-20T23:00:00] compile | daily/2026-04-20.md
- Source: daily/2026-04-20.md
- Articles created: [[concepts/ux-crosscutting-principles]]
- Articles updated: [[concepts/profile-v5-screens-specs]] (date+sources), [[concepts/headless-architecture]] (sessions 7+8+9 stable), [[concepts/supabase-db-patterns]] (migrations 095-101), [[concepts/reaction-on-param-save-ux]] (new pattern), [[concepts/headless-template-substitution]] (new pattern)

## [2026-04-20T23:59:00+03:00] compile | 2026-04-20.md
- Source: daily/2026-04-20.md (Sessions 7+8+9 — Headless Phase 2 Pilot → Agent Dossier Live)
- Articles created: (none — reaction-on-param-save-ux and headless-template-substitution compiled during session flushes)
- Articles updated:
  - [[concepts/headless-architecture]] — migrations 100+101 added to Deployed list; Session 9 n8n content (Dumb Renderer multi-pass PUT, Dispatcher Phase 5 PUT); Agent Dossier live-verified; "Reply-click Профиль" open item resolved; status → "sessions 7+8+9 stable"
  - [[concepts/supabase-db-patterns]] — migrations 100+101 block добавлен: get_profile_business_data 26→33 полей (sage_tier, limit_variant, helper-fields pattern), calendar/units translations × 13 langs, universal profile.main_text template, nested placeholder pattern

## [2026-04-20T00:00:00+03:00] compile | 2026-04-19.md (Session 6 addendum)
- Source: daily/2026-04-19.md (Session 6 — Phase 2 Pilot Stabilization)
- Articles created: (none)
- Articles updated:
  - [[concepts/headless-architecture]] — migrations 091-093 добавлены в Deployed list; latency benchmarks (profile_main p50=80/p95=98, my_plan p50=80/p95=570 outlier watchlist, personal_metrics p50=80/p95=216, settings p50=95/p95=183); status → "core flow stable"; Gotcha 5 cmd_back TODO закрыт (fixed migration 092); Открытые вопросы section добавлена (04_Menu_v3 active=false, parse_mode contract, my_plan outlier); file references +091-093
  - [[concepts/supabase-db-patterns]] — migrations 091-093 block добавлен: business data fixes (goal_type + personal_metrics), cmd_back status reset + nav_stack validation + data cleanup, Markdown→HTML template conversion; sources section обновлён

## [2026-04-19T23:00:00+03:00] compile | 2026-04-19.md
- Source: daily/2026-04-19.md
- Articles created: [[concepts/headless-architecture]] (created during session), [[concepts/ui-inventory]] (created during session)
- Articles updated: [[concepts/supabase-db-patterns]] (migrations 081-090)

## [2026-04-19T00:00:00] compile | 2026-04-18.md
- Source: daily/2026-04-18.md
- Articles created: [[concepts/soft-delete-account]]
- Articles updated: [[concepts/n8n-switch-duplicate-outputkey-bug]] (Variant B node UUID cache insight), [[concepts/n8n-multi-agent-workflow-editing]] (clone workflow lesson: UUID preservation + callerPolicy), [[concepts/phenotype-quiz]] (Variant B session)

## [2026-04-19T00:00:00+03:00] compile | daily/2026-04-18-handoff.md
- Source: daily/2026-04-18-handoff.md
- Articles created: (none — all content covered by existing articles from daily/2026-04-18.md)
- Articles updated:
  - [[concepts/n8n-switch-duplicate-outputkey-bug]] — добавлена секция "Runtime Cache Total Failure": более тяжёлая форма бага при накоплении PUT-попыток (Switch полностью игнорирует rightValue → 100% в main[0]); диагностика и решение (clone workflow или Action Router новые ноды); источник executions 9324-9342
  - [[concepts/phenotype-quiz]] — добавлена секция "E2E Verification Recipe": curl-команды для проверки executions через n8n API, ручной тест checklist, SQL verification, rollback snapshot `/tmp/04_menu_pre_v2.json`

## [2026-04-17T23:30:00+03:00] compile | daily/2026-04-17.md (end-of-day full compile)
- Source: daily/2026-04-17.md
- Articles created: [[concepts/nav-stack-architecture]] (Bug 6 hierarchical back navigation: migrations 076-078, 8 phases + R1, 26 buttons migrated, 13 Push Nav nodes, 5 workflows, Back Target Router 5 rules, paired items hotfix, D5 unified save confirmations, Phase 4 Language→Settings, Phase 5 subscription_source removal)
- Articles updated:
  - [[concepts/profile-redesign-v5]] — Phase 4 Language save→Settings + stale keyboard 2-msg fix; D5 unified save confirmations + backInlineKB; Bug 6 + edit_phenotype dead-end marked closed; D1/D3 deferred items added
  - [[concepts/payment-integration]] — Phase 5 nav_stack migration (subscription_source hack removed, Push Nav Plans); pre-existing JSON.stringify double-serialization bug in 4 Get *Price nodes; Get All Prices $json source fix

## [2026-04-17T18:30:00+03:00] compile | daily/2026-04-17.md (full compile)
- Source: daily/2026-04-17.md
- Articles created: [[concepts/edit-picker-dual-render]] (dual-render pattern for edit pickers, chk*() helpers, 9 Build Ask Markup cases, edit_phenotype dead-end)
- Articles updated:
  - [[concepts/profile-redesign-v5]] — Bug 2 fix (Language Back→Settings via status_and_send в v3 Onboarding Engine); Bug 2 Round 2 (Prepare for 02 = 20 полей, +country_code/timezone); Polish A/B/C (✅ pickers, Settings 2-в-ряд, timezone display Intl.DateTimeFormat); edit_phenotype dead-end зафиксирован
  - [[concepts/n8n-subworkflow-contract]] — источник 2026-04-17 детализирован; +edit-picker-dual-render связь
  - [[concepts/personalized-macro-split]] — chk*() dual render для goal/training/activity/gender; +edit-picker-dual-render связь

## [2026-04-17T18:00:00+03:00] compile | daily/2026-04-17.md
- Source: daily/2026-04-17.md
- Articles created: [[concepts/edit-picker-dual-render]] (dual-render pattern for edit pickers, chk*() helpers, 9 Build Ask Markup cases)
- Articles updated: [[concepts/profile-redesign-v5]] (Bug 2 fix: Language Back → Settings via status_and_send; Bug 2 Round 2: Prepare for 02 +country_code/timezone = 20 fields; Polish A/B/C: ✅ edit pickers, Settings 2-в-ряд, Timezone Intl.DateTimeFormat; edit_phenotype dead-end debt); [[concepts/n8n-subworkflow-contract]] (already updated in earlier flush with Prepare for 02 20-field contract, v1/v3 routing confirmation)

## [2026-04-17T12:15:00+03:00] compile | daily/2026-04-16.md (round 2 — session 23:50)
- Source: daily/2026-04-16.md
- Articles created: (none)
- Articles updated: [[concepts/profile-redesign-v5]] (Bug Fix Round 2: Intl.DisplayNames страны, Prepare for 02 +9 полей, 05_Location edit/send branching 44 ноды, subscription_source Merge Data fix, executeWorkflow typeVersion 1 vs 1.3+ pattern); [[concepts/n8n-subworkflow-contract]] (executeWorkflow typeVersion passthrough vs explicit mapping; Intl.DisplayNames; Sources section добавлен)

## [2026-04-16T23:30:00] compile | Daily Log 2026-04-16
- Source: daily/2026-04-16.md
- Articles created: [[concepts/profile-redesign-v5]]
- Articles updated: [[concepts/ambassador-payout-system]] (Units 2-7 завершены, n8n+Python deployment), [[concepts/league-ux-v2]] (верификация v6 bot spikes), [[concepts/league-fomo-push]] (midweek push финальный статус), [[concepts/payment-integration]] (Stripe sandbox→live checklist)

## [2026-04-16T14:18:00+03:00] compile | daily/2026-04-16.md (session 14:18 addendum)
- Source: daily/2026-04-16.md
- Articles created: (none)
- Articles updated: [[concepts/payment-integration]] (Stripe sandbox→live чеклист: ключи, условия, порядок перехода)

## [2026-04-16T23:59:00+03:00] compile | daily/2026-04-16.md
- Source: daily/2026-04-16.md
- Articles created: [[concepts/league-ux-v2]], [[concepts/ambassador-payout-system]]
- Articles updated: [[concepts/league-npc-system]] (v6 bot spikes, last_seen_hours_ago), [[concepts/league-fomo-push]] (midweek push LeagueMidweekCron + 3 touchpoints table), [[concepts/squad-referral-screen]] (v2 архитектура 7 units), [[concepts/supabase-db-patterns]] (migration 067 entry + 068–074 plans)

## [2026-04-16T11:15:00+03:00] compile | daily/2026-04-16.md
- Source: daily/2026-04-16.md
- Articles created: (none)
- Articles updated: (none)
- Note: Лог содержит только ошибку memory flush (exit code 1), сессий нет — нечего компилировать

## [2026-04-14T17:00:00] migration | MEMORY.md → knowledge/concepts/
- Source: MEMORY.md (auto-memory), access_credentials.md
- Articles created: [[concepts/noms-architecture]], [[concepts/access-credentials]], [[concepts/user-preferences]], [[concepts/xp-model]]
- Articles updated: (none)

## [2026-04-14T17:05:00] compile | daily/2026-04-08.md
- Source: daily/2026-04-08.md
- Articles created: [[concepts/n8n-stateful-ui]], [[concepts/n8n-data-flow-patterns]], [[concepts/league-npc-system]], [[concepts/supabase-db-patterns]]
- Articles updated: [[concepts/noms-architecture]] (added backlinks to new articles)

## [2026-04-14T17:10:00] compile | daily/2026-04-09.md
- Source: daily/2026-04-09.md
- Articles created: [[concepts/user-profile-personalization]], [[concepts/n8n-template-engine]], [[concepts/payment-integration]], [[concepts/day-summary-ux]]
- Articles updated: [[concepts/league-npc-system]] (migration 045–046: XP reset, bot aggression, workflowInputs fix, Markdown escape), [[concepts/supabase-db-patterns]] (migrations 043–050: sync_user_profile, dead column cleanup, broken RLS), [[concepts/n8n-data-flow-patterns]] (parallel HTTP race condition pattern)

## [2026-04-14T17:15:00] compile | daily/2026-04-10.md
- Source: daily/2026-04-10.md
- Articles created: [[concepts/personalized-macro-split]], [[concepts/n8n-performance-optimization]]
- Articles updated: [[concepts/payment-integration]] (regional pricing v2, Stripe HTTP fix, Limit 1 pattern, Shop workflowInputs bug), [[concepts/day-summary-ux]] (sargability fix mig 053, v3.1/v3.2/v4, macro thresholds in app_constants, is_registered bug), [[concepts/n8n-stateful-ui]] (typing actions × 7, answerCallbackQuery, voice transcription fix), [[concepts/supabase-db-patterns]] (migrations 051–055: regional pricing RPCs, food_logs indexes, sargability rule, app_constants_cache)

## [2026-04-14T17:30:00+03:00] compile | 2026-04-11.md
- Source: daily/2026-04-11.md
- Articles created: [[concepts/one-menu-ux]]
- Articles updated: [[concepts/n8n-data-flow-patterns]], [[concepts/payment-integration]], [[concepts/n8n-stateful-ui]], [[concepts/supabase-db-patterns]], [[concepts/personalized-macro-split]]

## [2026-04-14T17:00:00] migration | CLAUDE.md Changelog → daily/
- Source: CLAUDE.md Changelog section (52 entries)
- Daily logs created: 2026-04-08.md, 2026-04-09.md, 2026-04-10.md, 2026-04-11.md, 2026-04-13.md
- Ready for compilation via compile.py

## [2026-04-14T00:00:00+03:00] compile | 2026-04-13.md
- Source: daily/2026-04-13.md
- Articles created: [[concepts/supabase-security]], [[concepts/fasting-feature]], [[concepts/league-fomo-push]]
- Articles updated: [[concepts/league-npc-system]] (bot humanization, shadow bot, v4/v5 formula), [[concepts/payment-integration]] (renewal reminders fix, regional Stars/USDT, Limit 1 pattern, free user flow), [[concepts/supabase-db-patterns]] (migrations 057–060), [[concepts/n8n-data-flow-patterns]] (RETURNS TABLE Limit 1 pattern), [[concepts/n8n-stateful-ui]] (One Menu in payment, Markdown→HTML fix)

## [2026-04-14T18:47:00+03:00] compile | 2026-04-14.md (partial)
- Source: daily/2026-04-14.md
- Articles created: (none)
- Articles updated: (none)
- Note: Log contains only memory maintenance sessions (2026-04-08 and 2026-04-10 compilations + flush confirmations). No new technical knowledge extracted.

## [2026-04-14T20:50:00+03:00] compile | 2026-04-14.md (session 20:50)
- Source: daily/2026-04-14.md
- Articles created: [[concepts/notebooklm-code-sync]]
- Articles updated: (none)
- Note: Extracted NotebookLM code sync tooling knowledge — manifest desync problem, red files from n8n_code/crons/, COMPILE_AFTER_HOUR 18→8, EXCLUDE_DIRS update, open tasks

## [2026-04-14T23:59:00] compile | daily/2026-04-14.md
- Source: daily/2026-04-14.md
- Articles created: [[concepts/progress-screen-redesign]], [[concepts/squad-referral-screen]]
- Articles updated: [[concepts/n8n-stateful-ui]] (Delete Old Menu race condition fix, Progress HTML parse_mode), [[concepts/supabase-db-patterns]] (migration 062 premium mana)

## [2026-04-15T23:59:00] compile | daily/2026-04-15.md
- Source: daily/2026-04-15.md
- Articles created: [[concepts/dispatcher-callback-pipeline]]
- Articles updated: [[concepts/anti-spam-debounce]] (migration 061: debounce RPC + idx_ui_translations_lang_code, статус нода не подключена), [[concepts/n8n-performance-optimization]] (QSC параллельно ~300ms, Early Typing Action, migration 061 индекс), [[concepts/personalized-macro-split]] (Speed Edit flow: 4 новых ноды, cmd_speed_* routing)

## [2026-04-20T22:00:00+03:00] compile | 2026-04-20.md
- Source: daily/2026-04-20.md
- Articles updated: [[concepts/headless-architecture]] (migrations 095-098, Session 7+8 RPC hotfixes + n8n PUT details), [[concepts/supabase-db-patterns]] (migrations 095-098 section), [[concepts/reaction-on-param-save-ux]] (n8n deployed implementation Round 1+2, Bug 1 closed)
- Articles created: (none — reaction-on-param-save-ux already existed from flush)
