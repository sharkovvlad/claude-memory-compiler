# Knowledge Base Index

> **Re-organized 2026-05-25** — 130 concepts, 11 domains. +1 (food-recognition-prompt-lab, 2026-06-02). +1 (content-type-classification, 2026-06-03). Foundational hubs marked 🔥, legacy/superseded/duplicate 🏛, stale 💤.
> Каждый non-ACTIVE файл имеет `> ⚠️ status: ...` баннер сверху. История компиляции — `log.md`.

## ⛔ ОБЯЗАТЕЛЬНО перед EOS — Session Close Discipline

> **Перед каждым сообщением «готово»** агент **обязан** выполнить 5-step checklist в [[concepts/session-close-discipline]] 🔥 HUB. Без этого следующая сессия начнётся с разбора завалов (10-40 мин потерянного времени каждый раз). Owner явно flagнул эту проблему 2026-05-29.

## How to use this index

1. **Старт сессии:** скан Quick navigation ниже — найди свой домен. Активные файлы вверху каждой секции, archived/legacy внизу.
2. **Foundational hubs (🔥)** — обязательно читать перед погружением в домен.
3. **При конфликте между файлами** — recent правит. Если видишь `→ [[X]]` — читай X, не оригинал.
4. **Stale (💤)** — не trust на слово, тема могла измениться. Перепроверь через NLM.
5. **Перед EOS** — открой [[concepts/session-close-discipline]] и пройди 5 пунктов self-check.

## Snapshot

| Status | Count | Что значит |
|---|---|---|
| ✅ active | 101 | Живой код / упомянуты в недавних daily |
| 🔥 HUB | 12 | Foundational, ≥5 refs/30d, читать первыми (+5 from 2026-05-29: memory-claim-vs-live, npc-bots-users-table, stage7-global-cutover, cycle-tracking-ux-and-accuracy, **session-close-discipline**) |
| 🏛 legacy-n8n | 9 | n8n-механика, фича мигрирована в Python |
| 🏛 superseded | 5 | Заменён более новым файлом, см. → pointer |
| 🏛 duplicate | 2 | Содержание полностью покрыто canonical файлом |
| 🏛 outdated | 1 | Автор сам пометил OUTDATED |
| 💤 stale | 8 | 0 refs за 30 дней, тема возможно заморожена |
| **Total** | **130** | |

## Start here for common tasks

| Если задача про... | Сначала прочитай (🔥 = foundational hub) |
|---|---|
| **Новый screen / inline UX** | 🔥 `headless-architecture`, `one-menu-ux`, `ui-screens-map`, `headless-button-creation-gotchas` |
| **Новый/правимый edit-picker (diet/training/goal/…)** | `headless-picker-pattern` — ⭐ **Pattern B = owner-mandated дефолт** (остаться на экране + ✅ переезжает + live-число пересчёта); сеттер ОБЯЗАН парсить `cmd_*`; тест через `dispatch_with_render`, не прямой вызов |
| **SQL миграция / RPC** | 🔥 `pre-migration-discovery-recipe`, `migration-collision-guard`, `migration-deploy-ordering`, `safe-create-or-replace-recipe`, `jsonb-shallow-merge-antipattern` |
| **n8n workflow правка** | 🔥 `n8n-data-flow-patterns`, `n8n-subworkflow-contract`, `n8n-selfhost-migration` |
| **Payment / Stripe / Stars** | `payment-idempotency-pattern`, `payment-integration`, `subscription-management-headless`, `claim-vs-check-idempotency-anti-pattern`, 🔥 `stars-subscriptions-botfather-prereq` (P0 2026-05-28) |
| **Перевод / 13 langs / Sage** | `copywriter-playbook`, `ui-translations-bulk-update-recipe`, `sassy-sage-multilingual-glossary`, `double-emoji-button-anti-pattern`, `i18n-rpc-audit-pattern` |
| **Adaptive modifiers (sleep/stress/luteal)** | `adaptive-modifiers-architecture`, `safety-guard-ux-pattern` |
| **Cron / scheduled jobs** | `cron-silent-failure-alerting`, `cron-reminder-suppression-tunables`, `cron-pushed-callback-fallback-pattern` |
| **Deploy / TLS / Caddy issue** | `release-protocol`, `tls-caddy-nomsbot` |
| **Python handler (cutover)** | `phase2-python-menu-v3`, `phase4-onboarding-migration`, `webhook-server-async-patterns` |
| **Классификация типов контента (photo/doc/audio/junk/location)** | 🔥 `content-type-classification` — 3 независимых классификатора, обязаны быть синхронны; `content-type-routing-gotchas` — предыстория PR #294 |
| **Day-summary / Stats / Mood** | 🔥 `profile-v5-screens-specs`, `stats-main-headless`, `personalized-macro-split`, `my-day-llm-insight`, `meals-picker-two-stage` |
| **Bug идемпотентности / дубль event** | `claim-vs-check-idempotency-anti-pattern`, `payment-idempotency-pattern` |
| **Subagent → LIVE apply (orchestrator hat)** | `subagent-live-apply-review-rule`, `agent-collaboration-protocol`, `pre-migration-discovery-recipe` |
| **`content \|\| payload` JSONB safety** | `jsonb-shallow-merge-antipattern` (P0 2026-05-26), `ui-translations-bulk-update-recipe` |
| **JSONB-array Sassy variants** | `jsonb-array-python-consumer-blind-spot` (P0 2026-05-31) — Python `.replace()` падает AttributeError; grep всех consumer'ов после mig string→array |
| **Multi-stage PRs / stacked merges** | 🔥 `stacked-pr-base-change-gotcha` (P0 2026-05-28), `migration-collision-guard`, `release-protocol` |
| **Stars subscriptions (recurring) — setup гoтча** | 🔥 `stars-subscriptions-botfather-prereq` — `provider_token` omit, BotFather prereq, re-enable checklist |
| **Test-user reset / fresh start** | `test-user-reset-recipe` (НЕ `start-fresh-flow` — outdated) |
| **Aggregate по `users` / counts / engagement** | 🔥 `npc-bots-users-table` — ВСЕГДА `WHERE is_bot=false`, иначе 119 NPC ботов искажают цифры на ≈30% |
| **MEMORY/handover claim → verify перед действием** | 🔥 `memory-claim-vs-live-verification` (2026-05-29 Stage 7 case), `pre-migration-discovery-recipe` |
| **AI Engine cutover / Stage 7 history** | `stage7-global-cutover` (mig 299→373, canary→global blueprint + monitoring metrics) |
| **Качество vision-распознавания / prompt improvement** | `food-recognition-prompt-lab` — текущие промпты v3, дефекты (схлопывание, пропуск тарелок), варианты патча, дизайн eval golden-set, gotcha _prompt_cache |
| **Лог по штрихкоду / упакованная еда / OpenFoodFacts / FatSecret** | `barcode-logging-openfoodfacts` — MVP-дизайн (zxing-cpp, OFF, barcode=ветка фото не новый класс); 🔴 находки: orphan `barcode_cache`, фантомный контракт-тест (CI сломан на main), граница с FatSecret-агентом |
| **🚨 ПЕРЕД EOS («готово») — обязательный self-check** | 🔥 `session-close-discipline` — 5-step checklist (daily / handover / KB / MEMORY / size), real failure cases, anti-patterns. **Owner-flagged 29.05: каждая новая сессия = 20-40мин на разбор завалов.** |
| **Cycle tracking UX / luteal accuracy** | 🔥 `cycle-tracking-ux-and-accuracy` (Phase 3d, 4 design risks closed mig 375 — Decisions implemented section + historical context) |

## Quick navigation

- **🛡 Safety & Clinical Guards** — 8 files · 121 refs/30d
- **🎨 UX Patterns & Screens** — 31 files · 108 refs/30d (1 hub, 8 archived)
- **🔧 Migration & Headless Patterns** — 17 files · 79 refs/30d (2 hub)
- **🐍 Python Handlers (cutover targets)** — 11 files · 61 refs/30d
- **✍️ Copywriter & i18n (13 langs)** — 5 files · 54 refs/30d
- **🏛 Architecture & Infrastructure** — 8 files · 53 refs/30d (1 archived)
- **⚙️ n8n Legacy (active during cutover)** — 13 files · 40 refs/30d (1 hub, 10 archived)
- **📘 Engineering Lessons & Tooling** — 14 files · 31 refs/30d (1 archived, 1 new HUB)
- **🗄 Data Layer & RPCs** — 4 files · 28 refs/30d (1 hub, 1 archived)
- **💳 Payment & Subscriptions** — 7 files · 14 refs/30d (1 new HUB)
- **🎮 Gamification (XP / mana / leagues)** — 9 files · 7 refs/30d (4 archived)

---

## 🛡 Safety & Clinical Guards

_8 files · 121 incoming refs (30d)_

- [[adaptive-modifiers-architecture]] — Adaptive Modifiers Architecture (Phase 3, mig 301+)
- [[cycle-tracking-ux-and-accuracy]] **`🔥 HUB`** — Cycle tracking UX matrix (mig 334-360, Phase 3d) + nutritional accuracy. **4 design risks closed by mig 375** (2026-05-29): dynamic dates, «Не помню точно» silent skip, menopause gate age≥55, inline cycle length range 21-35. Original historical context сохранён в статье.
- [[energy-availability-design-decision]] — Energy Availability (EA / RED-S) — Design Decision: defer to P2
- [[personalized-macro-split]] — Each user receives unique daily protein/fat/carbs targets computed from their body type, training style, and weight goal — replacing the previous one-size-fits-all macro percent...
- [[phenotype-quiz]] — Phenotype Quiz (Body Composition Classification)
- [[pregnancy-lactation-clinical-spec]] — Pregnancy / Lactation — Clinical Spec для P0.6
- [[safety-banner-ux-redesign-2026-05-18]] — Safety Banner UX Redesign — Multi-Guard Stacking Problem (research)
- [[safety-center-implementation-plan]] — Safety Center Implementation Plan (B0 → B1 → B2 → B3)
- [[safety-guard-ux-pattern]] — Safety Guard UX Pattern — Argued Override (Reusable)

## 🎨 UX Patterns & Screens

_31 files · 108 incoming refs (30d)_

- [[profile-v5-screens-specs]] **`🔥 HUB`** — Profile v5 — Источник Истины (UX каталог всего бота)
- [[checkmark-prefix-pattern]] — Checkmark Prefix Pattern — ✅ на текущем выборе
- [[hybrid-modal-routing-pattern]] — Hybrid Modal Routing Pattern (async overlay modal)
- [[nav-stack-architecture]] — Nav Stack — Иерархическая навигация Назад (Bug 6)
- [[noop-render-strategy-pattern]] — Noop Pattern — подавить main item, использовать carrier как единственное текстовое сообщение
- [[onboarding-v3-map-supplement]] — Supplement: Pre-implementation audit (Block 1-4)
- [[onboarding-v3-map]] — 02_Onboarding_v3 — карта для миграции на Headless + Python
- [[one-menu-ux]] — The bot keeps exactly one active navigation screen in chat at any time. When a reply-keyboard button is tapped, the previous menu message is deleted before (or in parallel with)...
- [[one-time-attach-pattern]] — One-Time Attach Pattern (Reply-Keyboard Lifecycle)
- [[picker-unification-strategy]] — Picker Unification Strategy (Onboarding ≡ Edit Profile)
- [[reaction-on-param-save-ux]] — UX-паттерн: реакция бота на изменение параметров пользователя
- [[reply-keyboard-lifecycle]] — Все события attach/detach/revive reply-kb одним списком + WONTFIX re-attach на food-log (полагаться на чек-ины mig374 + /start mig182; крон-пуши НЕ привязывают)
- [[reply-keyboard-routing-pattern]] — Reply-Keyboard vs Inline Callback Routing — Two-Path Architecture
- [[save-bot-message-contract]] — save_bot_message Contract — обязательство для всех воркфлоу
- [[soft-delete-account]] — Soft Delete Account (GDPR-safe)
- [[start-fresh-gaps-2026-05-11]] — Start Fresh Flow — Identified Gaps (2026-05-11)
- [[telegram-proxy-indicator]] — Telegram Proxy для мгновенного Typing Indicator
- [[telegram-sticker-pipeline]] — Telegram Sticker Pipeline (NOMS)
- [[ui-screens-map]] — UI Screens Map — Navigation Tree (canonical)
- [[user-data-collection-pattern]] — User Data Collection Pattern — Retrofit для existing users
- [[user-profile-personalization]] — System for keeping user names current and injecting them into notifications and UI. Built across migrations 043–044.
- [[ux-crosscutting-principles]] — UX Cross-Cutting Principles (NOMS Bot)
- [[visible-condition-business-data-gotcha]] — visible_condition gotcha — пишет только из public.users
- [[ux-mobile-compact-redesign-sweep]] — UX Mobile Compact Redesign (mig 347-355): stats/progress/profile mobile layout, ±10% macro corridor, premium-hide line, checkmark daily_metrics extension

### 🏛 Archived / legacy / stale

- [[day-summary-ux]] **`🏛 superseded`** → [[stats-main-headless]] — The main stats screen showing daily nutrition progress, XP, streak, and meal history. Accessed via the "☀️ Мой день" reply keyboard button.
- [[edit-picker-dual-render]] **`🏛 superseded`** → [[headless-picker-pattern]] — Edit Picker Dual Render Pattern
- [[profile-redesign-v5]] **`🏛 superseded`** → [[profile-v5-screens-specs]] — Profile Redesign v5.0 — Agent Dossier
- [[start-fresh-flow]] **`🏛 outdated`** — cmd_start_fresh — как работает в текущей системе
- [[sticker-architecture-adr]] **`🏛 merged-stub`** → [[ui-stickers-headless]] — ADR rationale (Context / Alternatives / Consequences) перенесён в winner как раздел «ADR rationale»; этот файл = 5-line stub
- [[ui-inventory]] **`🏛 superseded`** → [[ui-screens-map]] — UI Inventory — All Screens, Callbacks, Menus
- [[progress-screen-redesign]] **`💤 stale`** — Редизайн экрана Progress (inline) в рамках обновления геймификации: новые иконки, Premium-маркер, формат отображения стрика и маны, личность Sassy Sage в инсайтах. Standalone wo...
- [[user-preferences]] — Working style + **communication style** (простой язык, без жаргона, объяснять последствиями — owner-flagged 2026-05-30) для owner-а NOMS.

## 🔧 Migration & Headless Patterns

_16 files · 79 incoming refs (30d)_

- [[headless-architecture]] **`🔥 HUB`** — Headless Architecture (Variant C) — Profile v5 Pilot
- [[pre-migration-discovery-recipe]] **`🔥 HUB`** — Pre-Migration Discovery Recipe — Phase 0 protocol
- [[headless-button-creation-gotchas]] — Headless Button Creation Gotchas — meta.target_screen + double emoji + meta-copy trap
- [[headless-fsm-vs-dynamic-handler-separation]] — Разделение ответственности — Headless FSM (SQL) vs Dynamic Handler (Python)
- [[headless-picker-pattern]] — Headless Picker Pattern — полный recipe для inline-kb pickers
- [[headless-template-substitution]] — Pure Headless: разделение слоёв + template substitution
- [[language-switch-headless-ux]] — Language Switch UX in Headless Architecture
- [[premium-hide-line-pattern]] — Pre-resolved SQL line с leading/trailing `\n` для conditional-hide строк в template без orphan blank line (mig 343/348/353/354/355)
- [[jsonb-shallow-merge-antipattern]] — `content \|\| payload` wipes nested namespaces (P0 incident 2026-05-26, mig 359 → mig 360 recovery). 3 safe alternatives documented.
- [[jsonb-array-python-consumer-blind-spot]] — Sassy variants (mig 306) переводят translation key в JSONB-array, но Python-consumers через `.replace()` остаются не array-aware → AttributeError. Recipe: grep всех consumer'ов (SQL + Python), фикс через `isinstance(list)`. P0 2026-05-31 PR #263.
- [[migration-collision-guard]] — SQL-миграции в NOMS — последовательные: `migrations/NNN_<slug>.sql`, NNN растёт монотонно. Агенты обычно берут «следующий номер» через `ls migrations/ | tail -1` в момент старта...
- [[migration-deploy-ordering]] — Migration Deploy Ordering — split additive vs breaking schema changes
- [[progress-hub-headless]] — Progress Hub Headless Migration (Phase 3A Iterations 2-4)
- [[python-vs-n8n-template-grammar]] — Python `services/template_engine.py` vs n8n Dumb Renderer — две грамматики, одно `ui_translations`
- [[safe-create-or-replace-recipe]] — Safe `CREATE OR REPLACE FUNCTION` Recipe — защита от stale-base regression
- [[stats-main-headless]] — Stats Main Screen — Headless Phase 3A (Migrations 122–124)
- [[subscription-management-headless]] — Subscription Management Headless
- [[ui-stickers-headless]] — Sticker Architecture (4 Channels, Single Source of Truth)
- [[variant-b-cutover]] — Variant B Cutover — паттерн постепенного переноса n8n → Python

## 🐍 Python Handlers (cutover targets)

_12 files · 61 incoming refs (30d)_

- [[canonical-hybrid-location-picker]] — Canonical Hybrid Location Picker — reply-kb prompt + inline list
- [[dumb-renderer-interpolation-gotchas]] — Dumb Renderer Interpolation — Gotchas
- [[phase2-python-menu-v3]] — Phase 2 — Python `menu_v3` handler + Template Engine
- [[phase4-onboarding-migration]] — Phase 4: Миграция онбординга n8n → Python (29.04 — 04.05.2026)
- [[phase6-location-migration-plan]] — Phase 6 — миграция 02.1_Location в Python (план)
- [[python-telegram-adapter]] — Python Telegram Adapter — Replacing Telegram Trigger in n8n
- [[webhook-server-async-patterns]] — Webhook Server Async Patterns — concurrency + performance
- [[food-log-python-cutover]] — Stage 7a — food log confirmation rendering migration from n8n to Python (4 PRs, 5 n8n iterations, first callback endpoint)
- [[content-type-routing-gotchas]] — Content-type routing gotchas: image/* document (desktop «как файл») → vision AI, message.audio → transcription, junk→messages.spam_protect reuse (уже ×13 в БД), полный список junk-типов. PR #294.
- [[content-type-classification]] **`🔥 HUB-кандидат`** — Канонический паттерн классификации контента (photo/image-doc/voice/audio/junk/location-flow). **3 независимых классификатора** (router.py/telegram_proxy.py/location.py), обязаны быть синхронны — рассинхрон = 3 регрессии за 1 день (2026-06-03). Таблица классов + правило «меняешь один — обнови все три» + хроника инцидентов.
- [[sage-food-log-llm-integration]] — Sassy Sage LLM one-liner (gpt-4o-mini) после каждого food log. Первый OpenAI call в NOMS. 5 safety paths, pre-baked fallback, asyncio parallel + timeout. PR #156, mig 312. **v2 (23.05):** JSON mode, emotion→tg-emoji, macros focus, fallback × 13 langs (mig 314-315). **v3 (24.05):** timeout 5s, always-fallback, emoji rollback unicode, persist_as_menu fix.
- [[my-day-llm-insight]] — My Day LLM Insight — cache-on-write gpt-4o-mini insight для stats_main. 10-enum `day_status` tone anchor, prompt guardrails (4 rules), normaliser shape fix. PR #164 mig 319-320, PR #166 mig 322, PR #167 mig 323.
- [[meals-picker-two-stage]] — 2-stage meal edit/delete flow (meals_picker → meal_action). Dynamic per-meal buttons, parametric `cmd_select_meal_<uuid>`, 4 RPCs. PR #168 mig 324.
- [[food-recognition-prompt-lab]] — Текущие промпты GPT-4o vision/text/recalculate (v3, mig 336), каталог дефектов качества (схлопывание позиций, пропуск тарелок, нестабильные макросы), варианты промпта для теста, дизайн оффлайн eval golden-set, `_prompt_cache` gotcha (нет hot-reload → нужен restart noms-webhooks).

## ✍️ Copywriter & i18n (13 langs)

_6 files · 54 incoming refs (30d)_

- [[copywriter-playbook]] — Copywriter Playbook — single entry point для translation sessions
- [[double-emoji-button-anti-pattern]] — `icon_const_key` + emoji prefix в i18n value → двойной рендер (CLAUDE.md rule 2 + KB concept; 19 keys fixed 2026-05-26)
- [[i18n-cldr-plural-runtime]] — `{N word}` форматирование через babel CLDR + `services/i18n_plural.py:format_count()`; ru/uk/pl/ar 3+ форм, ar 6 категорий, «teens trap» в Slavic (mig 421, PR #277, 2026-06-01)
- [[l1-cultural-sanity-brief]] — L1 Cultural Sanity Brief — Чек-лист для нутрициолога
- [[sassy-sage-dialog-variants]] — Sassy Sage Dialog Variants System
- [[sassy-sage-multilingual-glossary]] — Sassy Sage Multilingual Glossary
- [[ui-translations-bulk-update-recipe]] — UI Translations Bulk Update Recipe
- [[handover/2026-06-01_fiverr_dunning_l1_review_brief]] **`📬 open handover`** — Fiverr brief для native-review dunning + plan_name × 7 langs (AR/FA/HI/PL priority, ID/PT/UK sign-off); 70 strings, ~$120-180, owner action.

## 🏛 Architecture & Infrastructure

_8 files · 53 incoming refs (30d)_

- [[access-credentials]] — NOMS Access Credentials + Agent Tools Recipe
- [[architecture-registry]] — Architecture Registry — Python authoritative vs n8n fallback
- [[cron-silent-failure-alerting]] — Cron Silent Failure Pattern + Centralized BaseCron Alerting
- [[cron-reminder-suppression-tunables]] — Tunables для cron reminder suppression (mute-windows, hour cutoffs) живут в `app_constants`, не в RPC body
- [[cron-pushed-callback-fallback-pattern]] — Любая cron-pushed inline button MUST иметь row в `_global_floating_actions` virtual screen (mig 372 P0 lesson — без fallback callback fails molча, F3 mutex не срабатывает)
- [[noms-architecture]] — Telegram nutrition tracking bot with AI food recognition, gamification (XP, leagues, quests, NomsCoins), 13-language support, and subscriptions. Character: "Sassy Sage" — helpfu...
- [[project-structure]] — Project Structure & Tech Stack
- [[release-protocol]] — Release Protocol — Auto-deploy через GitHub Actions, manual fallback
- [[tls-caddy-nomsbot]] — TLS edge: Caddy + Let's Encrypt на `nomsbot.com`

### 🏛 Archived / legacy / stale

- [[dispatcher-callback-pipeline]] **`💤 stale`** — Система передачи данных callback_query через Dispatcher (01_Dispatcher) в 04_Menu. После цепочки нод с IF и HTTP Request референсы на `$('Telegram Trigger')` ломаются из-за n8n ...

## ⚙️ n8n Legacy (active during cutover)

_13 files · 40 incoming refs (30d)_

- [[n8n-data-flow-patterns]] **`🔥 HUB`** — Rules for working with data flows in n8n workflows. These patterns prevent silent bugs caused by how n8n handles `$json` after HTTP Request nodes.
- [[n8n-selfhost-migration]] — n8n Self-Host: Миграция с Cloud на собственный VPS
- [[n8n-subworkflow-contract]] — n8n Sub-Workflow Data Contract

### 🏛 Archived / legacy / stale

- [[action-router-pattern]] **`🏛 legacy-n8n`** — Action Router Pattern (Code classifier → Switch router)
- [[n8n-legacy-node-strip-recipe]] **`🏛 legacy-n8n`** — n8n Legacy Node Strip Recipe — хирургическое удаление фиче-нод из live workflow
- [[n8n-multi-agent-workflow-editing]] **`🏛 legacy-n8n`** — Multi-Agent n8n Workflow Editing Protocol
- [[n8n-performance-optimization]] **`🏛 legacy-n8n`** — Techniques applied to reduce reply-button latency from ~400-800ms to under 300ms, and eliminate the perception of lag via immediate user feedback.
- [[n8n-route-classifier-edit-loc-patch]] **`🏛 legacy-n8n`** — 01_Dispatcher Route Classifier — edit-location reply-back early branch (patch v9, 08.05.2026)
- [[n8n-self-hosting]] **`🏛 merged-stub`** → [[n8n-selfhost-migration]] — Operational env-tuning + multi-agent SSH safety + n8n Cloud cancellation history перенесены в winner как раздел «Ongoing operations»; этот файл = 5-line stub
- [[n8n-sqlite-docker-cp-trap]] **`🏛 legacy-n8n`** — n8n SQLite + `docker cp` ownership trap
- [[n8n-stateful-ui]] **`🏛 legacy-n8n`** — The bot behaves like a Mini App inside Telegram chat. Messages are edited in-place rather than creating new ones, keeping the chat clean and stateful. Every tap gets immediate v...
- [[n8n-switch-duplicate-outputkey-bug]] **`🏛 legacy-n8n`** — n8n Switch v3.4 Duplicate outputKey Bug
- [[n8n-template-engine]] **`🏛 legacy-n8n`** — The Dispatcher-level substitution system that replaces `{{icon_xxx}}` and `{name}` placeholders in `ui_translations` strings before they reach sub-workflows.

## 📘 Engineering Lessons & Tooling

_14 files · 31 incoming refs (30d)_

- [[session-close-discipline]] **`🔥 HUB`** — **MUST READ перед каждым EOS.** 5-step checklist (daily / handover / KB / MEMORY / housekeeping). Real failure cases (Stage 7 phantom 25→29.05, BMI warnings phantom debt 18→29.05, migration collision parallel subagents). Owner explicitly flagged 2026-05-29 — каждая новая сессия начинается с разбора завалов предыдущей.
- [[stacked-pr-base-change-gotcha]] **`🔥 HUB`** — Stacked-PR base-change gotcha — `gh api PATCH base=feature-branch` redirects «Merge pull request» button into the intermediate branch, NOT main (P0 2026-05-28).
- [[memory-claim-vs-live-verification]] **`🔥 HUB`** — MEMORY/handover claim ↔ live разрыв. 5 классов claim'ов которые ОБЯЗАТЕЛЬНО verify через 2+ независимых источника. Case study: Stage 7 «GLOBAL CUTOVER 25.05» был ложным 4 дня (2026-05-29).
- [[stage7-global-cutover]] — Stage 7 Python AI Engine — full cutover history (mig 299 canary 21.05 → mig 373 global 29.05). Architecture diff, rollback recipe, monitoring metrics, n8n SQLite execution_entity quirk.
- [[adversarial-review-protocol]] — Adversarial Review Protocol — pre-apply critical pass
- [[agent-collaboration-protocol]] — Agent Collaboration Protocol — Shared rules для всех NOMS-агентов
- [[anti-spam-debounce]] — Anti-Spam / Debounce — защита от повторных нажатий
- [[claim-vs-check-idempotency-anti-pattern]] — Idempotency claim vs check — anti-pattern double-call
- [[dispatcher-webhook-reregistration]] — Dispatcher Webhook Re-registration Bug (01_Dispatcher PUT)
- [[docker-bridge-networking-pattern]] — Docker bridge networking: container→host loopback gotcha
- [[e2e-telethon-crawler]] — E2E Telethon DFS Crawler — headless UI smoke testing
- [[nlm-sync-infrastructure]] — NLM Sync Infrastructure — NOMS
- [[router-prefix-collision]] — Router prefix collision — exclusion guard pattern
- 🔥 [[fsm-state-whitelist-discipline]] — HUB. Adding registration_step_* requires BUTTON_ONLY + ONBOARDING + NUMERIC_INPUT registration. mig 259 lesson 3+ recurrences in 2 weeks (mig 382/386 latest). Checklist included.
- [[specs-vs-reality-ground-truth]] — Specs vs Reality — Ground Truth Protocol
- [[subagent-live-apply-review-rule]] — Subagent LIVE-apply: orchestrator МUST review SQL before authorize. TaskStop ≠ rollback (P0 lesson 2026-05-26)
- [[systemd-dropin-override-pattern]] — systemd drop-in override pattern для persistent service config changes
- [[i18n-rpc-audit-pattern]] — i18n RPC Audit: scan pg_proc for hardcoded localized strings separately from ui_translations JSONB (mig 285/286 lesson)
- [[test-user-reset-recipe]] — Test User Reset Recipe — обнуление для повторного онбординга

### 🏛 Archived / legacy / stale

- [[notebooklm-code-sync]] **`🏛 superseded`** → [[nlm-sync-infrastructure]] — NotebookLM Code Sync (code_to_nlm.py)

## 🗄 Data Layer & RPCs

_4 files · 28 incoming refs (30d)_

- [[supabase-db-patterns]] **`🔥 HUB`** — Patterns and conventions for Supabase schema management, migrations, and data integrity in the NOMS project.
- [[calc-user-targets-roadmap]] — calculate_user_targets — Roadmap (P0 active sprint + P1+ backlog)
- [[calc-user-targets-test-spreadsheet]] — calculate_user_targets v8 — Golden Test Cases (Digital Twin Spreadsheet)

### 🏛 Archived / legacy / stale

- [[supabase-security]] **`💤 stale`** — Supabase Security — RLS and Access Control

## 💳 Payment & Subscriptions

_7 files · 14 incoming refs (30d)_

- [[stars-subscriptions-botfather-prereq]] **`🔥 HUB`** — Telegram Stars Subscriptions require BotFather setup before `subscription_period` works. Without setup → client error `PROVIDER_ACCOUNT_INVALID` (P0 2026-05-28). Currently disabled in NOMS; re-enable checklist inside.
- [[ambassador-payout-system]] — Squad/Банда UX v2 — расширение реферальной программы до полноценной ambassador-программы с RevShare (25%+5%), системой вывода средств и ручным одобрением CEO. Разбито на 7 незав...
- [[payment-idempotency-pattern]] — Status:** captured 2026-05-20 после PR #134 (post-first-live-payment audit). Покрывает три ортогональные idempotency-проблемы которые открылись после первого live Stripe платежа.
- [[payment-integration]] — Three payment methods (Telegram Stars, Stripe card, TON/USDT) integrated without a dedicated "Payments" menu. Entry points are the Profile screen and Shop screen.
- [[phone-collection-strategy]] — Phone Collection Strategy — Progressive Profiling в 3 точках
- [[telegram-invoice-constraints]] — Telegram invoice — UI editing constraints (editMessageText silently rejected)
- [[ton-api-v3-forward-payload-boc]] — TON API v3 forward_payload — base64 BoC parsing

## 🎮 Gamification (XP / mana / leagues)

_9 files · 7 incoming refs (30d)_

- [[npc-bots-users-table]] **`🔥 HUB`** — 119 NPC-ботов сидят в `users` с `is_bot=true` + отрицательный telegram_id `-1XXX`. **ЛЮБОЙ** aggregate query по `users` обязан фильтровать `is_bot=false` — иначе counts искажены ≈30%. Safe-патtern templates + 4 типичные ошибки агентов.
- [[league-npc-system]] — NPC bots fill league groups to ensure competition exists even with few real users — inspired by Duolingo's approach. 25 bots with `telegram_id` from −1001 to −1025, later extend...
- [[no-mana-python-precheck]] — No-Mana Python Pre-check — Strangler Fig pattern
- [[smart-freeze-notification-delivery]] — Smart Freeze Notification Delivery (mig 191)
- [[streak-freeze-cron-logic]] — Streak / Freeze Cron Logic — last_log_date vs last_active_at + Milestone Unified
- [[xp-model]] — Three-tier economy: XP (social, weekly reset) + NomsCoins (persistent currency) + Mana (energy limiter).

### 🏛 Archived / legacy / stale

- [[fasting-feature]] **`💤 stale`** — The "Skip Meal / Fasting" feature allows users to explicitly mark a period as intentional fasting rather than forgetting to log food. Implemented via a dedicated RPC, inline but...
- [[league-fomo-push]] **`💤 stale`** — League FOMO Push and Rich League Notifications
- [[league-ux-v2]] **`💤 stale`** — League UX v2 — Duolingo-style Smart Leaderboard
- [[squad-referral-screen]] **`💤 stale`** — Экран "Твоя Банда" (Squad) — первый UI для реферальной системы NOMS. Реферальная механика была полностью реализована в БД ещё в Phase 1; этот экран впервые делает её видимой пол...

---

_Compiled 2026-05-25 by `Phase 2 KB cleanup`. Source data: `/tmp/noms_kb_audit_v2.json` + `/tmp/noms_kb_dupe_scan.json`._
_For per-file change history → `log.md`. To regenerate this index — see Phase 1/2 procedure in `RULES.md`._
