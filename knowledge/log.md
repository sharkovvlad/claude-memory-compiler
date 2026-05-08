# Build Log

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
