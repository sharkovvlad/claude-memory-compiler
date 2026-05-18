---
title: "Safety Center Implementation Plan (B0 → B1 → B2 → B3)"
aliases: [safety-center-plan, safety-hub-roadmap, plan-b-implementation]
tags: [ux, safety, headless, my-plan, profile, implementation-plan]
sources:
  - "concepts/safety-banner-ux-redesign-2026-05-18.md"
  - "concepts/safety-guard-ux-pattern.md"
  - "concepts/headless-architecture.md"
  - "migrations/256_extend_banner_injection.sql"
  - "migrations/264_safety_guard_first_trigger_modals.sql"
created: 2026-05-18
updated: 2026-05-18
status: approved by owner — execution pending
estimated: 8-12 dev days, phased
---

# Safety Center — Implementation Plan (Plan B, phased)

> **Status:** owner approved 2026-05-18. Phasing B0→B1→B2→B3 утверждено. Naming `🛡️ Твоя безопасность` утверждено. Сам код пишется в **отдельных миграциях с отдельными PR'ами per phase** — не one big PR.
>
> **Context:** Plan B chosen из [safety-banner-ux-redesign-2026-05-18](safety-banner-ux-redesign-2026-05-18.md). Rationale: roadmap имеет ≥6 не-implemented guards (RED-S, diet breaks, extreme BMI, vegan protein, ABW obese, athlete phenotype), inline-banners не масштабируются. Mobile-first + headless arch good fit.

## Phasing overview

| Phase | Scope | Days | Owner sign-off needed |
|---|---|---|---|
| **B0** | Profile cleanup — group 6 buttons → 3-4 top + submenu | 1-2 | Layout review |
| **B1** | New Safety Center screen + pill replacement в `my_plan` only | 3-4 | UX + texts |
| **B2** | Pill rollout на `profile_main` + `personal_metrics` + cleanup inline banner_block | 2-3 | Regression check |
| **B3** | Translations 13 langs (pill labels + Safety Center screens) + post-deploy monitoring | 3-5 | L1 (and Fiverr L2 if budget) |

**Sequential dependency:** B0 безопасен независимо. B1 → B2 → B3 sequential. Total 8-12 dev days (с buffer на L1/L2 review циклы).

---

## B0 — Profile cleanup (independent, ship anytime)

**Why:** Profile main сейчас 6 кнопок: «Изменить цель / Активность / Тренировки / Телосложение / Мои Данные / Назад». Apple/Telegram pattern = ≤4 top + submenu. Это не блокер для B1-B3 — но если сделать сейчас, B1 будет на чистом канвасе.

### Scope

- **Top row (3-4 buttons):** «Мой план» (рекомендация) + «Мои Данные» (уже там) + «Назад».
- **Submenu «⚙️ Настройки плана»:** «Изменить цель», «Активность», «Тренировки», «Телосложение».
- Опционально: переименование existing buttons для прямолинейности.

### Migration

`mig 271 — profile_main button regrouping + settings_submenu screen`

```sql
-- 1) Create new ui_screen `profile_settings_submenu`
INSERT INTO ui_screens (screen_code, ...)
VALUES ('profile_settings_submenu', ...);

-- 2) Move existing 4 buttons из profile_main → profile_settings_submenu
UPDATE ui_screen_buttons SET screen_code='profile_settings_submenu'
WHERE screen_code='profile_main' AND button_code IN (
  'cmd_edit_goal','cmd_activity','cmd_workouts','cmd_body_composition'
);

-- 3) Add new button «⚙️ Настройки плана» в profile_main → routes к submenu
INSERT INTO ui_screen_buttons ...;
```

### Translations needed

- `buttons.settings_submenu` (13 langs) — «⚙️ Настройки плана»
- `profile.settings_submenu_text` (13 langs) — header экрана подменю

**Estimated entries:** ~26 (2 keys × 13 langs)

### Router

`dispatcher/router.py:PROFILE_V5_CALLBACKS` — добавить `cmd_settings_submenu` если новый callback.

### Live-test scenarios

- Click «Профиль» → 3-4 buttons + новая «⚙️ Настройки плана»
- Click «⚙️ Настройки плана» → подменю с 4 perenesennyh кнопок
- Click «Изменить цель» в подменю → goal editor (existing flow)
- Click «Назад» из подменю → profile_main

### Acceptance

- [ ] Profile_main: 3-4 buttons + Back, не 6
- [ ] Submenu reachable + functional all 4 actions
- [ ] No regressions в `cmd_edit_goal`/`cmd_activity`/`cmd_workouts`/`cmd_body_composition` callbacks

---

## B1 — Safety Center screen + pill в my_plan

**Why:** Главный visual fix — убрать 7-9 строк banner_block из `my_plan`, заменить на компактную плашку. Калории/БЖУ становятся first-screen без скролла.

### New artefacts

#### 1. Headless screen `safety_center`

`ui_screens` row: title = `🛡️ Твоя безопасность`, kind = `dynamic` (содержимое генерируется RPC).

```sql
INSERT INTO ui_screens (screen_code, kind, meta) VALUES (
  'safety_center', 'dynamic',
  '{"render_via":"get_safety_center_data","target_screen":"safety_center"}'::jsonb
);
```

#### 2. New RPC `get_safety_center_data(user_id)`

Returns:
- List of active guards (age/bmi/min_kcal/maternal × 4 surfaces из существующего `_safety_guard_severity` matrix)
- Per guard: severity, banner_title, banner_body, modal_full (вытягивает из `ui_translations -> warning -> <family> -> <enum>`)
- Metadata: when guard activated (из `users.shown_guards`), какие effective changes (если override fired)
- Pagination: чтобы при 5+ guards рендерилось ≤Telegram message budget

#### 3. New helper `build_safety_pill_block(user_id, lang_code)` (replaces banner_block)

Returns compact text suitable для inline injection в любой screen body:

```
⚠ 2 предупреждения активны →
```

- Counter из active guards (non-informational).
- 0 guards → empty string (no pill rendered).
- 1 guard → `⚠ 1 предупреждение активно →` или короткий title если budget позволяет.
- 2+ → `⚠ N предупреждений активны →`.
- Hard block присутствует → `🛡️` prefix вместо `⚠`.

#### 4. Mutation `my_plan_text` template: `{banner_block}` → `{safety_pill_block}`

Только в `my_plan` на этой фазе. Profile_main + personal_metrics остаются с inline `{banner_block}` до B2.

### Migrations

- `mig 272 — safety_center screen + ui_screen_buttons`
- `mig 273 — get_safety_center_data RPC + build_safety_pill_block helper`
- `mig 274 — my_plan_text template: banner_block → safety_pill_block`

### Translations needed (B3 territory, но minimum для B1 deploy)

- `safety_center.title` (13 langs) — `🛡️ Твоя безопасность`
- `safety_center.empty_state` (13 langs) — «Активных предупреждений нет 🎉»
- `safety_center.list_header` (13 langs) — header перед list
- `pill.warnings_active_singular` (13 langs) — `⚠ 1 предупреждение активно →`
- `pill.warnings_active_plural` (13 langs) — `⚠ N предупреждений активны →`
- `pill.warnings_active_hard` (13 langs) — `🛡️ ВНИМАНИЕ →` (если hard block present)

Per lang ~6 entries × 13 = **78 entries**. Можно объединить с B3, но bare-minimum нужно для deploy.

### Router

- New callback `cmd_safety_center` → `PROFILE_V5_CALLBACKS` в `dispatcher/router.py`
- Pill clickable → callback opens `safety_center` screen
- Из `safety_center` → Back → возврат к `my_plan` (origin tracking)

### Live-test scenarios

- User 786301802 с age `underage_forced_maintain` + maternal `pregnancy_force_maintain`:
  - `my_plan` → top section: «🎯 Мой План», «Цель: ...», «Калории: ...» (no scroll!)
  - Bottom: `🛡️ 2 предупреждения активны →` pill
  - Click pill → `safety_center` screen with full list (age + maternal cards)
- User без guards → my_plan без pill (empty string injected, no extra blank line)
- User informational only → pill `💡 1 заметка →` (informational не должно prefix'аться `⚠`/`🛡️`)

### Acceptance

- [ ] `my_plan` ≤ 7 lines + pill в нижнем secondary section
- [ ] Калории + БЖУ в первых 5 строк (above fold проверено на iOS Telegram)
- [ ] Pill clickable + opens `safety_center`
- [ ] Safety Center показывает all active guards с full body
- [ ] Empty state работает (no guards → no pill, no empty line)

---

## B2 — Pill rollout на profile_main + personal_metrics + inline banner cleanup

**Why:** B1 решает только `my_plan`. Profile_main + personal_metrics всё ещё показывают inline banner_block (через mig 256 helper). После B2 — везде pill.

### Scope

- Apply pill replacement к `profile_main_text` + `personal_metrics_text` templates.
- **Decommission** `build_safety_guard_banner_block` (mig 256) — или сохранить как deprecated fallback и удалить через quarter post-deploy.
- Severity-sorted banner stacking (mig 268) — больше не нужен; severity сортировка перемещается в `get_safety_center_data` RPC.

### Migrations

- `mig 275 — profile_main + personal_metrics templates: banner_block → safety_pill_block`
- `mig 276 — (optional, defer until B3 post-deploy) decommission build_safety_guard_banner_block helper`

### Live-test scenarios

- All 3 surfaces (my_plan, profile_main, personal_metrics) show **identical pill** for user with 2 guards
- Click pill from any surface → same Safety Center destination
- Back navigation от Safety Center → returns к origin surface (track via callback_data param)

### Acceptance

- [ ] Pill consistent на 3 surfaces
- [ ] No double-rendering (inline banner_block НЕ должен показываться вместе с pill)
- [ ] No regressions в `personal_metrics` или `profile_main` content rendering

---

## B3 — Translations 13 langs + post-deploy monitoring

**Why:** B1 включил minimum pill/safety_center переводы (78 entries). B3 расширяет до полного покрытия per-guard в Safety Center и post-deploy quality pass.

### Scope

#### Translation expansion

Safety Center показывает per-guard cards с:
- Banner title (уже в `warning.<family>.<enum>.banner_title` — done by mig 240/258/270)
- Banner body (уже там — done)
- Modal full (уже там)
- **NEW:** Action recommendations per severity (например для hard_block: «Контактировать врача», для hard_regulated: «Можно опротестовать через /support», для informational: «Просто к сведению»)

Per guard action text: 7 enums (4 bmi + 3 min_kcal — age/maternal уже covered separately) × 1 surface (`action_hint`) × 13 langs = **~91 entries**.

Plus Safety Center UI labels (если не closed в B1) = ~78 entries.

**Total B3 translations:** ~169 entries.

#### Post-deploy monitoring (7 days)

- Watch `users.shown_guards` populate rate (Tier 1 first-trigger modal hook from mig 264)
- Telethon E2E: sentinel user → all 13 langs render correctly через Safety Center
- VPS logs: `journalctl -u noms-webhooks | grep safety_center_opened` — sanity check usage
- ES/PT/HI/AR users: native text qualifications post mig 269/270 (closes 21:34 owner bug end-to-end)

#### Fiverr L2 review (optional, $200)

- AR/FA medical-authority register (mig 270 self-flagged items)
- HI caste-aware healthcare (clean per L1, double-check)
- ID halal-friendly (clean per L1)

### Migrations

- `mig 277 — safety_center action hints translations (13 langs)`
- `mig 278 — pill/safety_center UI labels translations (if not in B1)`

### Acceptance

- [ ] 13 langs: Safety Center renders native end-to-end
- [ ] No EN fallback observed in 7-day monitoring
- [ ] L2 sign-off (or budget decision to defer)
- [ ] Snapshot drops: `backup_ui_translations_mig270_*` (7 days post-deploy from B3 start)

---

## Architectural decisions — locked

### 1. Naming
- Hub screen: `🛡️ Твоя безопасность` (RU canonical, lang-localized)
- Callback: `cmd_safety_center`
- Screen code: `safety_center`
- Helper: `build_safety_pill_block`
- RPC: `get_safety_center_data`

### 2. Severity → UI-size mapping
- Hard block → `🛡️` pill prefix (red urgency tone via emoji)
- Hard regulated → `🛡️` pill prefix (same — both are hard)
- Soft override → `⚠` pill prefix
- Informational → `💡` pill prefix (only if ≥1 informational AND 0 hard/soft — else dominated)

### 3. Banner_block compatibility window
- B1 NOT removes `build_safety_guard_banner_block` — only switches my_plan template usage
- B2 switches profile_main + personal_metrics
- After B2 verified clean (7 days), B3+ phase OR explicit follow-up mig — decommission helper
- Old `banner_block` placeholder remains в БД as deprecated (no template uses it, but kept для rollback)

### 4. Modal Tier 1 hook (mig 264) — preserved
- `safety_guards.py` Python hook continues to fire first-trigger modals (banner_title text)
- NOT replaced by Safety Center — это **complementary** UX (Tier 1 = push notification, Safety Center = persistent surface)
- After B1 deploy: Tier 1 modal text может добавить hint «Подробнее в 🛡️ Твоя безопасность»

### 5. Auto-resolve cron (Tier 5, deferred)
- Not in B0-B3 scope. Separate workstream (existing in roadmap as Tier 5 cron).
- When auto-resolve fires (e.g. user turns 18, BMI clears 18.5) → `shown_guards` entry для этого warning удаляется. Safety Center пересчитывает list автоматически (через `get_safety_center_data` re-query).

---

## B1 decisions locked (owner approved 2026-05-18 evening)

| Question | Decision | Rationale |
|---|---|---|
| **Pill micro-copy** | `🛡️ Активная защита: [N] 〉` (RU canonical) | Shield icon `🛡️` matches hub naming `🛡️ Твоя безопасность` — consistency, не пугающий `⚠`. «Защита» = забота, не ошибка системы. Pattern для 12 других langs следует тот же tone. |
| **Empty state** | **Full hide** (no pill rendered) | "No news is good news" (Apple Health pattern). Pill появляется только когда есть что сказать. Glow positive reinforcement отвергнут — занимает ценное mobile space. |
| **Click depth** | `my_plan` → pill → `safety_center` → per-guard card → modal_full (4-deep) | Scalable: roadmap имеет ≥6 не-implemented guards. Inline list возродил бы "простыню" текста. Separate screen более headless-friendly + matches Cronometer "Targets" tab pattern. |
| **B2 timing** | Wait **3-5 days** after B1 deploy | Собрать первичную analytics: понимают ли pill, кликают ли, нет ли тикетов «куда пропало предупреждение». После confirmation pattern works → rollout на profile_main + personal_metrics. |

### Pill text per-lang (B1 spec, B3 будет писать full Sassy Sage translations)

| Lang | Pill text |
|---|---|
| ru | `🛡️ Активная защита: 2 〉` |
| en | `🛡️ Active safety: 2 〉` |
| uk | `🛡️ Активний захист: 2 〉` |
| es | `🛡️ Protección activa: 2 〉` |
| pt | `🛡️ Proteção ativa: 2 〉` |
| de | `🛡️ Aktiver Schutz: 2 〉` |
| fr | `🛡️ Protection active : 2 〉` |
| it | `🛡️ Protezione attiva: 2 〉` |
| pl | `🛡️ Aktywna ochrona: 2 〉` |
| id | `🛡️ Perlindungan aktif: 2 〉` |
| hi | `🛡️ सक्रिय सुरक्षा: 2 〉` |
| ar | `🛡️ حماية نشطة: 2 〉` |
| fa | `🛡️ محافظت فعال: 2 〉` |

Singular vs plural handling per lang: brief требует ICU plural rules или 2 разных ключа (`pill.active_safety_singular`, `pill.active_safety_plural`). Slavic langs (ru/uk/pl) — 3-form plural (1/2-4/5+). Romance — 2-form (1/many). Arabic — 6-form. **Решение для B1:** хардкодим единое `:N 〉` format — number в конце, без word agreement. Worst case looks slightly awkward в Russian («Активная защита: 1») но универсально и не блокирует deploy.

### Pre-B1 prerequisite — DONE 2026-05-18 evening

**B0 (mig 271) shipped:** `my_plan` cleaned from 6 buttons → 4 buttons. Submenu `my_plan_settings` introduced. Это плацдарм для B1 pill injection — теперь my_plan имеет место для pill (между `personal_metrics` и `configure_plan` рядами, или вверху над контентом).

---

## Cross-references

- [safety-banner-ux-redesign-2026-05-18](safety-banner-ux-redesign-2026-05-18.md) — original Plan A vs Plan B research
- [safety-guard-ux-pattern](safety-guard-ux-pattern.md) — severity matrix + 5 touch points
- [headless-architecture](headless-architecture.md) — ui_screens + ui_screen_buttons + ui_translations patterns
- [copywriter-playbook](copywriter-playbook.md) — для B3 translation session
