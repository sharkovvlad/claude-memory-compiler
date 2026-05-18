---
title: "Safety Banner UX Redesign — Multi-Guard Stacking Problem (research)"
aliases: [safety-banner-redesign, multi-guard-ux, banner-consolidation]
tags: [ux, safety, headless, my-plan, profile, design-research]
sources:
  - "concepts/safety-guard-ux-pattern.md"
  - "concepts/ux-crosscutting-principles.md"
  - "concepts/ui-screens-map.md"
  - "daily/2026-05-18.md"
  - "migrations/252_my_plan_safety_guard_banners.sql"
  - "migrations/263_banner_skip_informational_severity.sql"
created: 2026-05-18
updated: 2026-05-18
status: research / awaiting owner decision
---

# Safety Banner UX Redesign — Multi-Guard Stacking

> **Тип документа:** product design research. Содержит две альтернативы (A — конservative consolidation; B — radical Safety Center), decision tree, миграционная стоимость, открытые вопросы. **НЕ содержит SQL/Python**. Owner выбирает направление, потом отдельная сессия пишет код.

## 1. Problem Statement

Live-тест 2026-05-18 (user 786301802, F/16, maintain → user менял goal на lose+fast) выявил 4 проблемы рендеринга safety-guard banner-block в `my_plan` screen:

1. **Banner stacking (главная).** Когда активны 2+ guards (например age `underage_forced_maintain` **hard block** + maternal `pregnancy_force_maintain` **hard regulated**), `banner_block` стал 7-9 строк. Главное содержимое («Цель/Темп/Калории») уехало за viewport на mobile. Пользователь не видит actionable план без скролла, ради которого открыл экран.
2. **«Темп: Быстро» при forced maintain.** Если `original_goal_type=lose+fast` форсирован в `effective_goal_type=maintain`, label «Темп: Быстро» теряет смысл — у maintain нет ни «slow», ни «fast». На UI выглядит как противоречие («maintain + быстро»), хотя SQL корректен.
3. **Множественные banner на одном screen.** Юзер видит **2 баннера подряд**. Industry-best (Apple Health, Flo): один banner-strip с топ-приоритетным warning + counter («+ 2 more» → tap → list). NOMS сейчас stack'ает все activated, что близко к worst-case для mobile.
4. **Hierarchy кнопок профиля.** Profile main screen: 6 кнопок в 5 рядах (Изменить цель / Активность / Тренировки / Телосложение / Мои Данные / Назад). Apple Health Settings, Telegram Wallet — обычно ≤4 «top» + остальное в подменю. Не блокер #1, но усиливает visual noise.

**Текущая инфра, которую trogают эти проблемы:**

- `get_my_plan_business_data` v2 (mig 252) — family-agnostic loop по `['age','bmi','min_kcal','maternal']`, concat'ит banner_title/body для **каждого** active warning.
- Helper `build_safety_guard_banner_block` (mig 256, расширение mig 252) — общая функция, вызывается из `my_plan` + `personal_metrics` + `profile_main`.
- `build_safety_guard_banner_block` (mig 263) — skip informational severity для persistent banner. Hard / hard regulated / soft override **всегда** persistent, никакой consolidation.

**Сегодняшний worst case (live):**

```
🛡️ До 18 — без жёсткого дефицита              ← banner 1 title (hard block)
До 18 жёсткий дефицит небезопасен — ставлю
поддержание. Формулы для подростков работают
иначе.

🛡️ Беременность — только поддержание           ← banner 2 title (hard regulated)
При беременности жёсткий дефицит небезопасен —
кетоны проходят через плаценту. Добавляю
+340 ккал для второго триместра.

🎯 Мой План                                    ← main content, often below fold
Цель: Поддержание (исходно: Похудение)
Темп: Быстро                                  ← contradictory!
Цель по калориям: 2934 ккал
```

Telegram message height budget — практически ~12 строк до требования «show more» / scroll. Здесь уже 11.

## 2. Industry Analysis — Multi-Warning Patterns

Сравнение surfacing-паттернов для multi-warning user state в health/fitness apps:

| Product | Multi-warning behavior | Where it lives | Lesson для NOMS |
|---|---|---|---|
| **Apple Health** (iOS) | **One top-of-screen banner** = highest-severity (red). Lower-severity (yellow/blue) свёрнуты в дискретный «Notifications» badge в Summary. User tap on badge → list of all alerts. | Top of Summary, persistent. | One banner > stacking. Counter badge для secondary. |
| **Flo** | Pregnancy/cycle warnings показываются как **modal на open** (one-time), затем «pill» в header (small chip). Multiple — pill стэкается горизонтально, max 3, потом «+N». | Persistent header pill row. | Initial education = modal. Persistence = compact chip, не full banner. |
| **Glow** (fertility) | Active medical warnings в **dedicated «Health Insights» tab**. Main dashboard показывает только plan/numbers + single badge «You have 2 health alerts →». | Separate hub. | Dashboard остаётся clean; warnings concentrated в их собственном месте. |
| **Noom** | Caloric floor / restriction warnings — **modal только при action** (когда user снижает калории ниже floor). Persistent — micro-pill «Plan adjusted» внизу. Tap → explanation. | Action-triggered + tiny footer pill. | Argued override не обязан жить на главном экране — может быть на action moment. |
| **MyFitnessPal** | Single «You're below your goal» strip + один контекстный line. Multi-warning не encountered — MFP редко форсит override, в основном informational. | Top strip on diary. | MFP свидетельствует, что **больше 1 strip = редкость в этой категории**. |
| **Cronometer** | Informational warnings о nutrient deficiencies — отдельный «Targets» tab. Main diary — ни одного banner. | Dedicated tab. | Power-user pattern: deep info живёт в отдельной view, не на главной. |
| **Clue** | Predicted-risk warnings — soft chip в header. Tap → educational card (full-screen). | Chip + sheet. | Размер UI элемента ≈ severity: chip < strip < banner < modal. |

**Общий cross-pattern (5 из 7):**

1. **One primary banner-strip на screen** (highest severity), всё остальное — counter/pill.
2. **Initial education = modal (one-time)**, дальше — компактный signifier.
3. **Dedicated «Safety/Insights» surface** для drill-down (Apple Health, Glow, Cronometer).
4. **Severity → UI-size matrix** (chip < strip < banner < modal) — не «больше severity = больше banner» наивно, а «больше severity = persistent + actionable» (compact, но не игнорируемый).
5. **Force-changes явно объясняются на action moment** (Noom modal), а не размазаны навсегда по profile.

## 3. Recommendation A — Conservative (low SQL impact)

**Идея:** оставить banner-block в `my_plan`, но переделать **rules of stacking + label suppression**. Никаких новых screens.

### A.1 Banner consolidation rule

Текущий helper `build_safety_guard_banner_block` (mig 263) стэкает все non-informational. Изменение:

- **Один banner на screen.** Берём highest-severity warning (hard block > hard regulated > soft override).
- Если есть ещё guards того же или ниже tier'а — добавляем **inline counter**: `+ еще N предупреждений →` (clickable, если screen supports inline buttons; иначе просто text hint).
- Click on counter → open `safety_warnings_modal` (новый headless screen, лёгкий — list всех текущих guards с full body каждого).

Visual:

```
🛡️ До 18 — без жёсткого дефицита
До 18 жёсткий дефицит небезопасен — ставлю
поддержание. Формулы для подростков работают
иначе.

🔍 Ещё 1 предупреждение — открыть      ← inline link (new ui_screen_button)

🎯 Мой План
Цель: Поддержание (исходно: Похудение)
Темп: —
Цель по калориям: 2934 ккал
```

Высота сократилась с 11 до 8 строк → main content above fold.

### A.2 «Темп» suppression при forced override

В `get_my_plan_business_data`:

- Если `effective_goal_type='maintain'` AND `original_goal_type != 'maintain'`:
  - `goal_speed_label := '—'` (или null → label hidden целиком)
  - Или: `goal_speed_label := emdash` + tooltip «Темп не применяется при поддержании».
- Для **non-forced** maintain (юзер сам выбрал) — текущая логика hidden, OK.

Это меньше противоречий («maintain + быстро»), без редизайна screen.

### A.3 Кнопки профиля — частичный clean

Минимум: показать в profile_main только **3-4 «top» кнопки** (Изменить цель / Мои Данные / Назад), остальное (Активность / Тренировки / Телосложение) — за подменю «Параметры тела». Не блокер если A.1+A.2 done, может быть отложен.

### A.4 Concrete SQL changes (без кода)

- **mig N (~80 строк):** обновить `build_safety_guard_banner_block` — pick highest-severity warning, return banner_block + warnings_count. Build counter line из перевод-ключа `safety.more_warnings` (13 langs).
- **mig N+1 (~20 строк):** `get_my_plan_business_data` — `goal_speed_label` suppression rule.
- **mig N+2 (~30 строк):** новый `ui_screen` `safety_warnings_modal` + headless render (loop over all active warnings → full text per each). Callback `cmd_show_safety_warnings`.
- **Translations:** 1 key × 13 langs (`safety.more_warnings`, e.g. `+ Ещё {n} →`). Если делать suppression label — ещё 1 key.

**Effort estimate:** ~3-4 миграции, 1 copywriter mini-session (2 keys × 13 langs ≈ 26 entries). Python — нет изменений (всё в SQL через render_screen pipeline).

## 4. Recommendation B — Radical (Safety Center subscreen)

**Идея:** изолировать safety warnings в отдельном «Safety Center» screen. Main profile screens (my_plan, personal_metrics) показывают только **alert badge** ([⚠ 2 alerts]), а сам drill-down — в dedicated screen.

### B.1 Architecture

```
Profile (main)
  ├─ 🎯 Мой План          → my_plan screen
  │     [⚠ 2 alerts →]   ← compact pill, не full banner
  │     Цель: Поддержание
  │     Темп: —
  │     Калории: 2934
  ├─ 📊 Мои данные        → personal_metrics
  │     [⚠ 2 alerts →]   ← same pill
  ├─ 🛡️ Безопасность      ← NEW root entry в Profile
  │     2 active warnings
  └─ ...

Safety Center (new screen, `safety_center`)
  ┌─────────────────────────────────────────┐
  │ 🛡️ Безопасность                         │
  │                                         │
  │ Активно: 2 предупреждения               │
  │                                         │
  │ 🛡️ HARD BLOCK                           │
  │   До 18 — без жёсткого дефицита         │
  │   До 18 жёсткий дефицит небезопасен...  │
  │   [Подробнее →]                         │
  │                                         │
  │ 🛡️ HARD REGULATED                       │
  │   Беременность — только поддержание     │
  │   При беременности жёсткий дефицит...   │
  │   [Подробнее →]                         │
  │                                         │
  │ [🔙 Назад]                              │
  └─────────────────────────────────────────┘
```

### B.2 Visual on `my_plan`

```
🎯 Мой План

[⚠ 2 предупреждения →]              ← single compact line, tap → Safety Center

Цель: Поддержание (исходно: Похудение)
Темп: —
Цель по калориям: 2934 ккал
```

Высота banner-area: **1 строка** (вместо 7-9). Main content всегда above fold.

### B.3 Onboarding & Auto-reset notifications

- **First-trigger modal** (touch-point #3 из safety-guard-ux-pattern) — full-screen, как и было. После acknowledgement — banner свёртывается в pill, drill-down в Safety Center.
- **Auto-reset** (variant A/B/C из safety-guard-ux-pattern §6) — one-shot Telegram message + clearing pill из profile.
- Education не страдает: важная info всё ещё показывается first-trigger; persistent surface — minimal (pill).

### B.4 Concrete SQL/UI changes

- **mig N (~150 строк):** новый screen `safety_center` в `ui_screens` + `ui_screen_buttons` (loop через все families, build sections + «Подробнее» per warning).
- **mig N+1 (~80 строк):** `get_my_plan_business_data` + `get_personal_metrics_business_data` (+ profile_main RPC) — добавить `alert_pill_text` = `"⚠ {n} предупреждения"` или `''`, заменить `banner_block` → `alert_pill`.
- **mig N+2 (~40 строк):** update `profile.my_plan_text` (13 langs) — заменить `{banner_block}` на `{alert_pill}\n\n`. Аналогично для других screens.
- **mig N+3 (~30 строк):** `safety.alert_pill` translation keys (`⚠ {n} предупреждения`, plural-aware: «1 предупреждение» / «2 предупреждения» / «5 предупреждений»). 13 langs × pluralization = ~40-50 entries.
- **mig N+4 (~50 строк):** add «Безопасность» button to `profile_main` + nav_stack frame для back to profile from safety_center.
- **Python:** none (всё headless через `render_screen`).

**Effort estimate:** ~5-6 миграций, 1 copywriter session medium-size (pluralization-aware ≈ 40-50 entries × care for grammar в FA/AR/UK). New ui_screen design (textual mockup OK in headless model).

## 5. Decision Tree

| Question | If yes → choose | If no → choose |
|---|---|---|
| Multi-guard cases уже > 5% активных users? | B | A |
| Roadmap имеет ещё 5+ guards в течение 3 месяцев? (RED-S, diet break, EA, BMI extreme, athlete phenotype, etc.) | B | A |
| Mobile (Telegram) — primary surface (>80% юзеров)? | B (above-fold critical) | A |
| Owner хочет **минимум 2-4 недели до live**? | A | B |
| Education / argued-override должен ВСЕГДА быть в первом экране? | A | B (но first-trigger modal остаётся!) |
| Юзеры жалуются на «информационный шум» в Profile? | B | A |

**Чек-лист NOMS state:**

1. Multi-guard cases (age + maternal, BMI + min_kcal): **в одной cohort F/15-50** = **frequent** (любая беременная подросток / любая lose с BMI<18.5). Это не редкость.
2. Roadmap calc-user-targets-roadmap имеет **6 ещё не-implemented guards** (P0.6 maternal done sql-only; P1.5 formula switch; P2.3 Katch-McArdle; P2.5 RED-S; P2.6 diet break; P3 athlete) → tendency «больше guards → больше stacking».
3. Telegram = 100% mobile-first. Above-fold critical.
4. Owner says "UX не нравится" — implicit запрос на noise reduction.

→ **Lean: B** для long-term. Но если бюджет 2 недели — start с A.1 (consolidation rule) как quick mitigation, B запустить параллельно.

## 6. Migration Effort Delta (rough)

| Item | A (conservative) | B (Safety Center) |
|---|---|---|
| SQL миграции | 3 шт., ~130 строк | 5-6 шт., ~350 строк |
| Translations entries | ~26 (2 keys × 13) | ~50 (pluralization-aware) |
| Copywriter sessions | 1 mini | 1 medium |
| New ui_screens | 1 (modal) | 1 (safety_center) + button add |
| Python changes | 0 | 0 |
| Test coverage (live-test sentinels) | 2 cases (consolidation + speed-suppress) | 4 cases (pill + drill-down nav + plural correctness × langs + first-trigger modal flow) |
| Risk to existing screens | low (in-place edit of helper) | medium (3 screens lose banner_block, need fallback rules) |
| Reversibility | high (revert mig 263 + 1 new mig) | medium (multi-mig revert, screen removal) |
| **Calendar estimate** | **2-3 days** | **5-7 days** |

A — minimal-impact, B — proper-but-bigger.

## 7. Quick Wins для owner — independent of A vs B decision

Эти 3 wins можно сделать **сразу, до выбора A или B**. Они улучшат UX и совместимы с любым final подходом.

1. **«Темп» suppression при forced maintain.** Простое условие в `get_my_plan_business_data`: `IF original != effective AND effective='maintain' THEN goal_speed_label := '—'`. ~10 строк SQL, 0 translations. Устраняет contradictory «Темп: Быстро». **Может быть сделан сегодня.**
2. **Banner severity ordering.** Текущий loop порядок `['age','bmi','min_kcal','maternal']` — fixed by family, не by severity. Если 2 active, hard block (age `underage_forced_maintain`) **может оказаться ниже** hard regulated (maternal `pregnancy_force_maintain`) в banner-block. Фикс: пересортировать через severity-table. ~30 строк SQL, 0 translations.
3. **Banner body length cap.** Text bodies сейчас не имеют ограничения, некоторые тексты 2-3 предложения. Telegram SRE recommended ≤140 chars / banner_body (см. safety-guard-ux-pattern §5). Audit ui_translations `warning.*.banner_body` — найти overflow'ы, скоротить (copywriter mini-session). Это снижает высоту даже без consolidation.

Эти три **не блокируют** A vs B решение, и каждый из них работает в обоих подходах.

## 8. Open Questions для owner

1. **Tolerance к scroll на mobile.** Готов ли owner принять, что safety education занимает приоритет над main content (текущий стек ≥ A.1)? Или main plan numbers критичнее (→ B)?
2. **Frequency of multi-guard.** Можем ли мы быстро посчитать, % cohort с 2+ active warnings? (SQL по `users` с `birth_date<2008-01-01 + (is_pregnant OR BMI<18.5)`). Это calibrates A vs B.
3. **First-trigger modal status.** Touch-point #3 в safety-guard-ux-pattern §2b — ❌ NOT implemented. Owner хочет это сделать **до** redesign, **параллельно** или **после**? B становится естественнее если first-trigger modal уже работает (он берёт education burden, освобождая profile от full-text repetition).
4. **Persistence philosophy.** Если user уже видел modal_full однажды (mig 239 `users.shown_guards`), нужен ли persistent banner вообще для hard guards? (Apple Health для life-threatening alerts — yes; для diet — debatable.)
5. **Кнопки профиля consolidation.** Готов ли owner на отдельную mini-task для рефакторинга 6 кнопок → 3 top + submenu «Параметры тела» (Активность / Тренировки / Телосложение)? Не зависит от A/B.
6. **Safety Center naming.** Если B выбран — слово «Безопасность» / «Health Alerts» / «Замечания» / «Warnings» — какой tone Sassy Sage предпочитает? (Avoid medical-officialese, prefer caring-but-direct.)
7. **Auto-resolve notifications.** Когда пользователю исполнится 18 / beremennost закончится — где показывать «защита снята»: Telegram push, in-app toast on next open, или дополнительная section в Safety Center? Это часть auto-reset cron, который пока ❌ NOT implemented.

## Связано

- [[concepts/safety-guard-ux-pattern]] — основной pattern, к которому это redesign-extension.
- [[concepts/ux-crosscutting-principles]] — One Menu, Shared Screens, indicator latency.
- [[concepts/ui-screens-map]] — навигация между my_plan / personal_metrics / profile_main.
- [[concepts/headless-architecture]] — `render_screen` pipeline для banner_block / alert_pill.
- [[concepts/calc-user-targets-roadmap]] — roadmap уточняет, сколько ещё guards впереди (P0.6 done sql, P1.5/P2.x in queue).
- [[concepts/sassy-sage-multilingual-glossary]] — tone reference для copywriter sessions A или B.

## Source live screenshots / data

- `claude-memory-compiler/daily/2026-05-18.md` секции «End-to-end render verification» и «Mig 252+253+254» — текущие render outputs RU/EN/FA, 4 sentinel cases.
- live user 786301802 (F/16, lose+fast switch) — primary subject UX feedback.
- migrations 252, 256 (helper extended scope), 263 (informational skip) — implementation baseline.
