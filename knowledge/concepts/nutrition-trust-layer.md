---
title: "Nutrition Trust Layer — explainable wisdom + Telegram rich formatting"
aliases: [trust-layer, wisdom-layer, sage-explainable, expandable-wisdom, nutrition-wisdom]
tags: [sage, ux, telegram-api, trust, retention, llm-prompt, copywriter, future-scope]
sources:
  - "daily/2026-06-13.md#EOD Telegram rich message formatting"
  - "concepts/sage-payload-meta-override-pattern.md"
  - "concepts/copywriter-playbook.md"
  - "concepts/sassy-sage-multilingual-glossary.md"
  - "concepts/sage-silent-presence-mode.md"
  - "concepts/sage-tone-dry-run-protocol.md"
  - "Master Blueprint 3.0.md §Sassy Sage + §RLHF Closed-Loop"
  - "migrations/462_calc_v15_macro_ranges.sql"
  - "migrations/055_personalized_macros.sql"
created: 2026-06-13
updated: 2026-06-13
status: PROPOSED — owner approved 2026-06-13 (research + design spike, NOT implementation)
---

# Nutrition Trust Layer — explainable wisdom + Telegram rich formatting

Концепт **future feature**: Sage умеет объяснять **почему** даётся совет — в раскрывающемся блоке (`expandable_blockquote`, новый Telegram Bot API 2026-06-13). Идея: trust + transparency как retention-lever. Sage из приятного character'а становится consultant. Шаг к premium-сегменту, отличающему NOMS от MyFitnessPal.

> ⚠️ **Status:** approved as proposal (2026-06-13). Implementation — отдельный sprint, отдельный план. Этот концепт = design source of truth.

## Key Points

- **Wisdom = opt-in expandable** (`expandable_blockquote` Telegram API, лимит сообщения 32k+ vs старых 4096). Юзер не обязан разворачивать — таппает если интересно.
- **Quality > economy** — owner mandate. Архитектура **Hybrid C** (pre-gen base text + LLM personal lead-in 40-60 tok), не cheapest A.
- **Formulas read from DB live** — wisdom **никогда не хардкодит** «Mifflin» / «1450 ккал». Источник = `calculate_user_targets` return values (`bmr`, `tdee`, `bmr_formula`, `pal_*`, `protein_g_per_kg`, etc, см. [migrations/462_calc_v15_macro_ranges.sql:620-688](migrations/462_calc_v15_macro_ranges.sql:620)). Это закладывает совместимость с **adaptive TDEE** roadmap-фичей.
- **Free для всех** — wisdom как retention/trust lever, не paywall feature. Premium-conversion = косвенный эффект.
- **Multi-lang term «логи» = prereq** — нужен native-Номс term per language (как mig 507 закрыл «streak»). Lock до wisdom MVP.
- **Anti-shame / РПП gates** — каждый wisdom text проходит существующие FORBIDDEN-проверки (никаких «лишний», medical claims, push'ей при `severe_deficit`).
- **Sage tone dry-run обязателен** — любой новый prompt = [[sage-tone-dry-run-protocol]] gate перед merge.
- **Source rotation** — пре-ген texts в `ui_translations` как массивы вариантов ([[sassy-sage-dialog-variants]] pattern), deterministic select по `(telegram_id, day, topic)`.

## Audience

Master Blueprint v3.0 + MEMORY: **mixed audience**, не только качки. ~70% — не профессионалы; «BMR» / «TDEE» = шум. Wisdom **обязан** говорить языком последствий, не механики.

**Test phrase:** «сколько ты ешь vs сколько тратишь», НЕ «энергетический баланс системы обмена веществ».

Учитывая Master Blueprint § Safety:
- РПП Detection
- Paradoxical Intervention
- BMI Filter
- Anti-Shaming
- Medical Disclaimer

Wisdom layer **не должен** активироваться при extreme deficit / underweight / РПП-flag без specific safety wording.

## Architecture — Hybrid C (RECOMMENDED)

### Three options summary

| Option | Idea | Best for | Why not always |
|---|---|---|---|
| **A** Pre-gen `ui_translations` + template engine | Pure static text + `{bmr}`/`{tdee}` placeholders | Encyclopedic topics (formula explainer, фенотип-раскладка) | Generic — не реагирует на momentum |
| **B** Full LLM on tap | New `_build_wisdom_prompt(ctx, topic)` | Highly contextual (streak ack adapts to length+history) | Cost + 2-5s latency на каждый tap; dry-run gate на каждое prompt change |
| **🎯 C Hybrid** | Pre-gen base + LLM personal lead-in (40-60 tok) | Default | Сложнее код (два источника в одном render path) |

### Hybrid C render pattern

```
[Outer Sage reaction — existing Card B/C/P/S/etc, character-driven]

[🧠 <Question> — tappable expandable_blockquote]
  ↓ (user taps)
  «LLM-generated personal lead-in (40-60 tok, references current state)» ← Sage payload-meta extension
  
  Pre-gen base text from ui_translations.content[lang].wisdom.<topic> [variants[idx]]
  with {target_kcal}, {deficit_pct}, {formula_name} resolved live
```

**Lead-in** использует existing payload pattern [[sage-payload-meta-override-pattern]] — extension `_build_user_prompt` с param `wisdom_lead_in_topic`. **НЕ** отдельный prompt builder — переиспользует existing Sage system prompt + voice cards + 10 META cascade. Dry-run gate ([[sage-tone-dry-run-protocol]]) на 8 baseline + 3 wisdom-specific scenarios.

**Cost estimate:** ~$0.075/100k MAU при 5% tap rate. Negligible.

### Where formulas live (critical)

> Wisdom **обязан** читать `calculations.bmr_formula` из live RPC return, **никогда не хардкодит** literal «Mifflin». `calculate_user_targets` v15 (mig 462) уже возвращает:
> - `bmr`, `tdee`, `bmr_formula` (mifflin / schofield_hw / molnar / luhrmann / katch_mcardle)
> - `pal_base`, `pal_adjusted`
> - `deficit_or_surplus_pct`, `effective_deficit_pct`
> - `protein_g_per_kg`, `lbm_kg`, `rfm_body_fat_pct`
> - `bmi_value`, `bmi_warning`, `min_kcal_warning`
> - + adaptive TDEE compatibility — когда roadmap-mig добавит correction layer, wisdom покажет адаптированную цифру без правки текста.

**Mapping** `formula_name → human-readable` хранится в `ui_translations.content[lang].wisdom.bmr_formulas.{mifflin, schofield_hw, molnar, luhrmann, katch_mcardle}` — короткое 1-2 строки, template engine resolve'ит `{formula_name}` по live `calculations.bmr_formula`.

**Anti-drift gate:** все числовые значения в wisdom — через `{template}` (`{target_kcal}`, `{deficit_pct}`, `{protein_g}`), **никогда** literals.

## 7 wisdom examples (RU drafts — single-source per mig 412)

Все examples прошли **interestingness test** («хотел бы я САМ это развернуть?») + **anti-shame / РПП check** + **FORBIDDEN-words scan**.

> «логи» → «отметки» (RU draft). Final term per-lang locked в Phase 1.5 copywriter session.

### #1 — Protein push при `goal=lose` (Phase 2 MVP target)

| Surface | Sage food_log reaction |
|---|---|
| Trigger | `payload.protein >= 20` AND `effective_goal_type='lose'` (reuse `_rule7_hard_guard` gate) |
| Frequency | High — fires на каждый meal с protein ≥20 г |
| Title | «🧠 Почему белок важен именно сейчас?» |
| Data source | `deficit_or_surplus_pct`, `macros.protein_g`, `macros.protein_g_per_kg`, `user_data.weight` |

**Outer (existing Card B/C):**
> Творог зашёл. Серия идёт ровно. Завтрак собран.

**Expandable body (draft):**
> Дефицит — это команда телу «жги запасы». Но тело само решает, что жечь — жир или мышцы. И первое, что оно выбирает, — мышцы (их «дороже» содержать, выгоднее сжечь). Если только не сказать ему обратное.
>
> Белок — это «обратное». Это химический сигнал «руки прочь от мышц». Норма для тебя: **{protein_g} г в день** ({protein_g_per_kg} г/кг при {weight} кг).
>
> Что будет без этого: за месяц минус 2 кг — но эти 2 кг будут наполовину мышцами. На весах красиво, в зеркале — нет. И всё это вернётся за две недели после возвращения к нормальной еде. С белком — медленнее, но это будет жир.

### #2 — Mealtime push к овощам / клетчатке

| Surface | Sage food_log reaction (mealtime push) |
|---|---|
| Trigger | `current_fibre_g < 0.5 * target_fibre_g` AND `local_hour >= 16` |
| Frequency | Medium |
| Title | «🧠 Зачем овощи вечером?» |
| Data source | `day_summary.fibre_total` (verify), `app_constants.fibre_target_g` |

**Expandable body** — physiology of hunger («скорость сахара в крови»), concrete numbers (current_fibre vs 25-30 g), evening anchor («спокойствие в 10 вечера»).

### #3 — Streak ack (42 days = habit) — RETENTION-strengthening

> ⚠️ Owner correction 2026-06-13: wisdom **усиливает** мотивацию серии, **не предлагает** ослабить.

| Surface | Sage my_day reaction at milestone |
|---|---|
| Trigger | `streak_n` ∈ {21, 30, 42, 60, 90, 100, 150, 200, 365} |
| Frequency | Low (rare milestones) but emotional high |
| Title | «🧠 Что значит {streak_n} дня?» |
| Data source | `users.streak_count`, `users.created_at` |

**Expandable body** — behavioral research range «21-66 days → automatic», positioning серии как **mechanism precision** («Номс начинает видеть **твою** норму, не шаблонную»), tease «на 90 днях Номс перестаёт догадываться и начинает предсказывать».

**Anti-shame check:** ✅ нет «надо», нет «должен», есть «продолжай» без императива.

### #4 — Late-night close с обоснованием

| Surface | Sage food_log при `local_hour >= 22` |
|---|---|
| Trigger | `_late_night_close_meta` already fires (PR #392) |
| Frequency | Daily для evening loggers |
| Title | «🧠 Почему после 10 не пушим?» |
| Data source | `local_hour`, `day_status` |
| РПП-sensitive | YES — careful tone gate |

**Expandable body** — physiology of sleep prep, **explicit allowance для real hunger** (`late_night_soft` branch: «пара ложек творога…»), framing «план на неделе» снимает stress от «недобрал день».

**Anti-РПП critical:** «не запрет — выбор», conditional anchor.

### #5 — Откуда цифры (BMR/TDEE + activity + training) — highest formal trust

| Surface | `/my_plan` screen — expandable под основным my_plan body |
|---|---|
| Trigger | screen load |
| Frequency | Daily-weekly (whenever user opens my_plan) |
| Title | «🧠 Откуда эти цифры?» |
| Data source | full `calculate_user_targets` return — `calculations.{bmr, tdee, bmr_formula, pal_*}`, `user_data.{goal_speed, training_type, phenotype}`, `users.activity_level`, `macros.protein_g_per_kg` |
| Phase 4 fix-button hook | YES (изменить темп) |

**Three-layer structure:**
1. **Слой 1 — тело в покое** (BMR, формула `{formula_name}`)
2. **Слой 2 — движение** (activity_level + training_type → PAL multipliers)
3. **Слой 3 — цель** (deficit_pct from `app_constants.goal_speed_*_deficit` — реально **slow=10% / normal=15% / fast=20%**, [mig 055](migrations/055_personalized_macros.sql))

**Phase 4 integration:** в expandable встроены inline-кнопки «Изменить темп: slow / normal / fast» — закрывает [[task_c783554d]]. Tap → reply keyboard → `set_user_goal_speed` RPC → my_plan re-render. Технически expandable_blockquote позволяет inline-entities — verify в Phase 1 spike.

### #6 — Фенотип + Activity + Training (раскладка макро)

| Surface | onboarding completion + при смене phenotype |
|---|---|
| Title | «🧠 Почему такая раскладка?» |
| Data source | `user_data.{phenotype, training_type}`, `users.activity_level`, `macros.protein_g_per_kg` |

**Three knobs** mental model: phenotype → ratio (jiry/уголеводы), activity_level → upper-bound of range, training_type → protein multiplier.

### #7 — Quiet steady day (silent presence + wisdom)

| Surface | Sage food_log при `silent_presence` META (mig 507) |
|---|---|
| Frequency | Common — balanced days |
| Title | «🧠 Что вообще сейчас происходит?» |

**Tone calibration:** Card S = silent. Expandable wisdom **не нарушает** silent presence — opt-in.

**Anti-confusion с [Изменить] button:** explicit wording «план целей не трогаешь, темп не меняешь, профиль на месте» — про **settings/plan**, не про meal correction.

## KPI / Metrics

| Metric | Goal | Source |
|---|---|---|
| `tap_rate` = taps / shows | ≥30% high-curiosity (streak, formula), ≥10% secondary (late-night) | `ai_coach_logs.day_context.wisdom_shown` + callback `wisdom:tap:<topic>` |
| `return_to_tap` | Low good (single «aha»); high = unclear text | dedupe (telegram_id, topic) 7d window |
| `retention_delta` D7/D30 | +X% wisdom-engaged vs control | join `users.created_at` + cohort |
| `premium_conversion_delta` | +X% trial→paid for cohort | `subscription_status` + cohort |
| `tap_to_action` (Phase 4) | % tapping inline-button after wisdom | `ui_clicks` correlate |

**Source-of-truth:** event-log architecture (не агрегат) — позволяет ретроспективные cohort'ы. Реализация — extension `ai_coach_logs` или новая `wisdom_events` table (выбор на impl phase).

## Telegram API constraints

| Параметр | Что знаем | Verify когда |
|---|---|---|
| `expandable_blockquote` | MessageEntity type. HTML `<blockquote expandable>`. MarkdownV2 точный синтаксис. | Phase 1 spike |
| Length limit | 32k+ (vs 4096). | Phase 1 |
| Custom emoji 🎨 | MessageEntity `custom_emoji` + `custom_emoji_id`. Premium-only? | Phase 1 + design |
| parse_mode default | NOMS = HTML. | Phase 1 confirm |
| Old client degradation | <iOS17 / <Android11 / <Desktop5.5 — expandable rendered as regular blockquote. | Acceptable graceful |

**Custom emoji opportunity:** premium Telegram emoji (✨🧠📊🎯) or **custom NOMS emoji pack** (Sage character + nutrition emoji). Premium-channel hook.

## Multi-lang term «логи» → native (Phase 1.5 prerequisite)

«Логи» — айтишно. Тот же класс англицизмов-пустышек, как «streak» (resolved mig 507). Needs native term per language.

| Lang | Current «logs» transliterate | Direction (verify L1) |
|---|---|---|
| en | logs / tracking | ✅ keep |
| ru | логи / записи | → «отметки» (draft) |
| uk | логи | → «записи» / «позначки» |
| de | logs | → `Eintrag`, `Notizen` |
| es | logs | → `registros`, `anotaciones` |
| fr | logs | → `notes`, `entrées` |
| it | logs | → `registrazioni` / `note` |
| pt | logs | → `anotações`, `registros` |
| pl | logi | → `zapisy`, `wpisy` |
| id | catatan | ✅ keep |
| hi | लॉग | → `entry` / `नोट` / Hinglish-Latin |
| ar | logs | → `سجلات` (sijillāt) |
| fa | لاگ | → `یادداشت‌ها` (yāddāsht-hā) |

**Process** — copywriter session ([[copywriter-playbook]] standard 10-step) → lock in [[sassy-sage-multilingual-glossary]] §Addendum → audit-grep `tools/audit_logs_literal.py` → apply migration in Phase 2 first wisdom PR.

## Phases — big-tech-style, foundation-first, effect-priority

| Phase | Title | Effort | Effect | Gate |
|---|---|---|---|---|
| **0** | KB landing (this file) | 1 session | foundation | — |
| **1** | Telegram API spike (helper + verify) | 2-3 days | foundation, no user-visible | sandbox bot ready |
| **1.5** | Multi-lang term lock «логи»→native | 1-2 days | Phase 2 prereq | L1 review per lang |
| **2** | Wisdom #1 (protein push) — Hybrid C | 1 PR | highest-frequency surface, first trust signal | Sage dry-run + L1 |
| **3** | Wisdom #5 + #3 + #4 | 2 PR | broader trust coverage, multi-surface | dry-run each |
| **4** | Fix-button closure (PR-3d task_c783554d) | 1 PR | closed loop понимание ↔ действие | — |
| **5** | Wisdom #2 + #6 + #7 | 1 PR | completeness | — |
| **6** | RLHF feedback signal (👍/👎 + LLM-judge weekly) | 2-3 PR | continuous quality improvement | — |

## Owner decisions locked (2026-06-13)

1. **Phase 2 topic = wisdom #1** (protein push) — highest-frequency, fastest KPI signal.
2. **Premium gate = free для всех** — wisdom как retention lever, not paywall feature.
3. **Multi-lang term lock до Phase 2** — Phase 1.5 separate copywriter sprint.
4. **No A/B** — 5 active users, statistical power weak. Roll out 100%.
5. **Hybrid C сразу с MVP** — quality > economy.

## Open для owner discussion (residual)

1. Custom emoji NOMS pack — Phase 1 / Phase 3?
2. Phase 1 timeline — кто запускает API spike (нужен sandbox bot)?
3. Phase 1.5 copywriter — какой агент / L1 reviewers per lang?

## Anti-patterns (do NOT)

- ❌ Хардкодить literal «Mifflin» / «1450 ккал» / «15% дефицит» в wisdom text. Всё через `{template}` или mapping.
- ❌ Активировать wisdom на surfaces с РПП/maternal/teen guard без specific tone-of-voice review.
- ❌ Использовать «лишний» / medical claims / pseudonum systems («метаболическая система») — FORBIDDEN.
- ❌ «Доказано» — даже behavioral research = «сходятся в диапазоне», не «доказано».
- ❌ Делать wisdom premium-only сейчас — owner-mandated free для trust building.
- ❌ Внедрять wisdom БЕЗ Sage dry-run gate ([[sage-tone-dry-run-protocol]]).
- ❌ Внедрять wisdom БЕЗ multi-lang term lock «логи»→native (Phase 1.5 gate).
- ❌ Использовать «корректировка» в wisdom #7 (путается с food_log [Изменить] button).

## Related Concepts

- [[sage-payload-meta-override-pattern]] (🔥 HUB) — Sage payload pattern + 10 META cascade; wisdom lead-in extends `_build_user_prompt`
- [[copywriter-playbook]] (🔥 HUB) — 10-step apply pipeline для wisdom texts (Phase 1.5 + Phase 2 base)
- [[sassy-sage-multilingual-glossary]] (🔥 HUB) — tone per 13 langs + Addendum для term lock
- [[sage-tone-dry-run-protocol]] (HARD GATE) — mandatory pre-merge dry-run для new prompts
- [[sage-silent-presence-mode]] — wisdom #7 (quiet_steady) interacts with silent_presence META
- [[sassy-sage-dialog-variants]] — variant-array structure для pre-gen wisdom (`ui_translations.content[lang].wisdom.<topic>[3]`)
- [[adaptive-modifiers-architecture]] — phenotype/luteal/maternal/EA модификаторы — wisdom reads via `effective_goal_type` + bonuses
- [[headless-architecture]] — где будут жить wisdom blocks в screens (Phase 2 render integration)
- [[release-protocol]] — git discipline для wisdom PRs

## Sources

- `migrations/462_calc_v15_macro_ranges.sql` (lines 620-688) — `calculate_user_targets` return shape with all derivation breadcrumbs
- `migrations/055_personalized_macros.sql` — canonical deficit values slow=10% / normal=15% / fast=20%
- `migrations/292_bmr_formula_switch_pediatric_geriatric.sql` — `bmr_formula` field (Mifflin / Schofield / Molnar / Lührmann / Katch-McArdle)
- `migrations/507_streak_native_words_audit.sql` — precedent для multi-lang term lock pattern
- `services/sage.py` — `_build_user_prompt`, `_build_my_day_prompt`, voice cards, 10 META cascade
- `Master Blueprint 3.0.md` §«Архитектура Самообучающейся ИИ-Экосистемы (RLHF & Closed-Loop Feedback)» — long-term wisdom = Sage persona evolution input
- `daily/2026-06-13.md` §«EOD: Telegram rich message formatting» — owner direction
- `/Users/vladislav/.claude/plans/rustling-nibbling-lark.md` — approved plan v2 (this file's source)
