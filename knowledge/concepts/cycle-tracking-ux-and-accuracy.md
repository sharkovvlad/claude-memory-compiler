---
title: "Cycle Tracking UX matrix + nutritional accuracy risks (Phase 3d)"
aliases: [cycle-tracking, luteal-accuracy, cycle-tracking-setup, period-tracking-ux]
tags: [nutrition, safety, ux, adaptive-modifiers, phase-3d, decisions-implemented]
sources:
  - "migrations/334-360 (Phase 3d cycle UX + luteal foundation)"
  - "RPC save_user_cycle_data (mig 355) — period_choice ENUM"
  - "RPC compute_cycle_day_for_user — modular arithmetic"
  - "RPC set_user_cycle_disabled — opt-out preserves history"
  - "migrations/375 (Phase 3d polish — 4 risks closed)"
  - "daily/2026-05-29.md (Nutritionist 10 UAT + полный рефактор)"
created: 2026-05-29
updated: 2026-05-29
status: active
severity: clinical-safety
---

# Cycle Tracking — UX Matrix + Nutritional Accuracy

> **TL;DR.** Phase 3d добавила opt-in tracking менструального цикла с прибавкой +175 kcal в лютеальной фазе (Premium-only). **Точность критически важна**: 7-day error в дате старта = до 50% wrong-phase classification. UAT 2026-05-29 обнаружил 4 design risks — **закрыты mig 375** (см. секцию «Decisions implemented»).

## ✅ Decisions implemented (mig 375 — Phase 3d Polish, 2026-05-29)

Все 4 risks закрыты в одной миграции после согласования с owner + 2 external AI reviews:

| Risk | Решение | Реализация |
|---|---|---|
| **Default `'7d_ago'` с pre-selected ✅** | «Не помню точно» → silent skip | Новая кнопка `cmd_save_cycle_unknown` → existing `set_user_cycle_disabled` (enabled=FALSE, start_date NULL). Toast «✓ Понятно. Пропущу подстройку тихо.» × 13 langs. `compute_cycle_day_for_user` уже возвращает NULL когда start_date=NULL → modifier silent skip. |
| **Static checkmark drift** | Убрать ✅ в setup, dynamic dates | `current_value_col` удалён из `ui_screens.cycle_tracking_setup.meta`. `get_cycle_setup_context` расширен — возвращает `date_today`, `date_7d_ago`, `date_14d_ago` (DD.MM). Кнопки получили `{date_*}` template placeholders × 13 langs. |
| **Нет menopause guard** | Hard cut-off age ≥ 55 в backend | `compute_cycle_day_for_user`: `WHEN birth_date IS NOT NULL AND EXTRACT(YEAR FROM AGE(...)) >= 55 THEN NULL`. FSM-обоснование: cycle question идёт ДО age step, UI-гейт невозможен — backend = единственный реальный защитный слой. |
| **Cycle length 28 hardcoded** | Inline кнопка + medical range | `buttons.edit_cycle_length` теперь `⚙️ Длина: 28 дн.` через `{cycle_length}` interpolation × 13 langs. `set_user_cycle_length` validation 21-45→21-35 (medical normal; 36+ irregular требует врача). UI presets уже только 21/25/28/30/35. |

**Drift protection (60-day soft alert)** — deferred в backlog per owner-decision (over-engineering для текущего scale ~5-12 active users).

**PR:** #231 (cycle_tracking_refactor mig 375).

**Verification (8/8 checks PASSED):**
1. set_user_cycle_length RPC exists
2. compute_cycle_day_for_user содержит birth_date + 55
3. get_cycle_setup_context returns date_today
4. current_value_col removed
5. cycle_tracking_setup = 7 buttons
6. button_dont_remember × 13 langs
7. unknown_toast × 13 langs
8. edit_cycle_length contains {cycle_length} × 13 langs

---

## 📜 Original 4 design risks (как они выглядели до mig 375)

> Сохраняется ниже для исторического контекста и для других агентов которые могут наткнуться на похожие patterns в других фичах.

## Архитектура (как сейчас работает)

### Backend RPC chain

```
cmd_onb_cycle_yes (Sí, configurar)
  ↓
  status='registration_step_cycle'
  render(onboarding_cycle_setup → buttons: today/7d_ago/14d_ago/disable/duration/back)
  ↓
cmd_save_cycle_(today|7d_ago|14d_ago)
  ↓
save_user_cycle_data RPC (mig 355):
  cycle_start_date := CURRENT_DATE - {0,7,14} days
  cycle_avg_length := 28  ← HARDCODED
  cycle_tracking_enabled := TRUE
  cycle_period_choice := '<choice>'
  next_screen := 'personal_metrics_women_health'
```

### Phase computation (на каждый food log + cron)

`compute_cycle_day_for_user(telegram_id) → INT | NULL`:
```sql
SELECT CASE
  WHEN cycle_tracking_enabled = FALSE   THEN NULL
  WHEN cycle_start_date IS NULL         THEN NULL
  WHEN is_pregnant OR is_lactating      THEN NULL  -- safety
  ELSE ((today - cycle_start_date) % GREATEST(cycle_avg_length, 21)) + 1
END
```

`cycle_day` → `cycle_phase`:
- Day 1-5 → menstruation
- Day 6-13 → follicular
- Day 14-15 → ovulation
- Day 16-28 → **luteal** (← here apply +175 kcal, +5-10% fat)

### UX state buttons matrix (cycle_tracking_setup screen)

| Button | Callback | save_rpc | save_value | target_screen |
|---|---|---|---|---|
| Hoy | `cmd_save_cycle_today` | `save_user_cycle_data` | `'today'` | `personal_metrics_women_health` |
| Hace 7 días | `cmd_save_cycle_7d_ago` | `save_user_cycle_data` | `'7d_ago'` | `personal_metrics_women_health` |
| Hace 14 días | `cmd_save_cycle_14d_ago` | `save_user_cycle_data` | `'14d_ago'` | `personal_metrics_women_health` |
| 🚫 Dejar de rastrear | `cmd_disable_cycle_tracking` | `set_user_cycle_disabled` | — | `personal_metrics_women_health` |
| ⚙️ Duración | `cmd_edit_cycle_length` | — | — | `edit_cycle_length` |
| ← Atrás | `cmd_back` | — | — | nav_stack pop |

### Screen meta

```json
{"current_value_col": "cycle_period_choice", "one_menu_terminal": true}
```

`current_value_col` → renderer добавляет ✅ к кнопке save_value matching `users.cycle_period_choice` ([[concepts/checkmark-prefix-pattern]]). Это **`last input`**, не «current phase».

### Opt-out (`set_user_cycle_disabled`)

```sql
UPDATE users
   SET cycle_tracking_enabled = FALSE
   -- ВАЖНО: cycle_start_date + cycle_avg_length НЕ обнуляются
   -- (history для re-opt-in позже)
```

Это правильно — юзерша может выключить и включить позже без потери ввода.

---

## 4 Design Risks (open questions, ждут owner-decision)

### Risk 1 — Default `'7d_ago'` в онбординге = ущерб точности

**Что происходит:** Когда юзерша нажимает «Sí, configurar» на `onboarding_cycle_question`, exposed screen `cycle_tracking_setup` показывает ✅ на «Hace 7 días» **до её выбора**. Психологически это «дефолт принятый» — она нажимает ту же кнопку или просто проходит дальше.

**Backend получает:** `cycle_start_date = today - 7 days`, phase classification кикcompiles от этого момента.

**Ущерб:** 7-day error в start date = до 50% wrong-phase в течение первого месяца:
- Юзерша реально на cycle_day 21 (luteal, нужна прибавка). Default считает день 8 (follicular, прибавки нет) → голодает в luteal.
- Юзерша реально на cycle_day 5 (menstruation). Default считает день 8 (follicular). Через 14 дней реал day 19 (luteal) vs computed day 22 (luteal) — повезло, но фаза смещена.

**Возможные решения** (выбор за owner):

| Вариант | Описание | Trade-off |
|---|---|---|
| A. **«Не помню точно» 4-я кнопка** | enable=true, period_choice=NULL → cycle_day=NULL → modifier silent skip с reason='date_unknown' | Честно. Нет прибавки до уточнения. Profile может поставить позже. |
| B. **Убрать ✅ в онбординге** | `current_value_col` ренdered только в `status='registered'`. В онбординге force явный выбор | Минимум кода. Но не решает «не помню». |
| C. **Manual date picker** | Полный spinner с днём/месяцем. ±1 день точность | Максимум точности. +1 шаг онбординга, сложнее UI. |
| D. **Disclaimer текст** | Не менять default, добавить «Если не помнишь — поправь в Профиле» | 0 LOC. ~50% юзерш не поймут и останутся с default. |

### Risk 2 — Checkmark ✅ не сдвигается со временем

`cycle_period_choice` это ENUM (`'today'` / `'7d_ago'` / `'14d_ago'`) — **статическая запись** последнего ввода. Через 14 дней юзерша зайдёт в Profile → setup screen → увидит ✅ на «Hace 7 días», хотя реально она уже на cycle_day 22 (luteal). **Misleading**.

**Возможные решения:**

| Вариант | Описание |
|---|---|
| A. Удалить `current_value_col` из meta → ✅ не показывается. Экран = «обновить старт» каждый раз | Простой, честный |
| B. Динамический ✅ — рендерер вычисляет `(today - cycle_start_date) days` и ставит ✅ на ближайший пресет (today/7/14). Через 14 дней ✅ сдвигается на «Hace 14 días» | Сложнее, но UX богаче |
| C. Заменить пресеты на dynamic dates: «Сегодня (29 мая)» / «7 дней назад (22 мая)» / «14 дней назад (15 мая)» — обновляется каждый день | Конкретно, понятно |

Owner на 2026-05-29 сказал: «✅ актуально когда юзер зайдёт в Профиль и увидит состояние. **Но не в онбординге** (юзер ещё не выбирал).» — это **закрепляет вариант B из Risk 1 как minimum**: убрать ✅ в онбординге FSM.

### Risk 3 — Нет menopause-гейта

`compute_cycle_day_for_user` исключает только pregnant/lactating. Женщина **65 лет**, не беременна, не кормит — увидит cycle question в онбординге. Если случайно нажмёт «Yes» — получит default 7d_ago + 28-day cycle + +175 kcal каждые ~14 дней по фантомной фазе.

**Возможные решения:**

| Вариант | Age threshold | Обоснование |
|---|---|---|
| A. age ≥ 55 → cycle_day = NULL | 55 | Медианный menopause 51±5, +4 года buffer. Симметрично pregnancy gate |
| B. age ≥ 60 | 60 | Консерватизм — есть юзерши 56-59 с поздней menopause |
| C. age ≥ 65 | 65 | Максимум осторожности, но 60-64 уже редко имеют циклы |
| D. Не добавлять | — | Полагаемся что менопаузные юзерши сами выберут Skip |

### Risk 4 — `cycle_avg_length` = 28 hardcoded, нет в онбординге

`save_user_cycle_data` ([mig 355](migrations/355_*.sql)) hardcoded `v_avg_length := 28`. Edit длины доступен только через Profile → «⚙️ Duración» (mig 357 `edit_cycle_length`). Это **второй axis ошибки**: даже с правильной датой старта, 25-day vs 28-day cycle = смещение фазы на 3 дня/месяц, накапливается.

**Возможные решения:**

| Вариант | Описание |
|---|---|
| A. +1 screen в онбординге: «Обычная длина цикла?» — пресеты 25/28/30/35 + «Не знаю → 28» | +1 шаг, +точность |
| B. Не спрашивать (default 28, edit через Profile) | Как сейчас. Большинство не пойдёт в Profile поправлять |

---

## Анти-pattern: «опт-ин = сразу применяем»

Текущее: юзерша нажимает «Yes, configurar» → бот сразу пишет default values + рендерит экран с ✅. Это implicit save. Better pattern: opt-in **только устанавливает intent**, конкретные данные собираются на следующем экране **без preview default**.

Если owner выберет Risk 1 решение A или B — это и есть fix.

---

## Что **уже хорошо** (не трогать)

- `set_user_cycle_disabled` preserves `cycle_start_date` + `cycle_avg_length` для re-opt-in
- `compute_cycle_day_for_user` правильно учитывает pregnancy + lactating (safety NULL)
- `cycle_tracking_enabled=false` корректно blocks luteal modifier
- 28-day default `cycle_avg_length` валидируется на 21-45 range в save_user_cycle_data
- guard_audit_log пишет opt-in + opt-out events для аудита

---

## UAT записан (2026-05-29)

Owner протестил happy path с акк 786301802 (es):
- ✅ Reset через psycopg2 → status='new' (но reply-kb осталась — см. [[test-user-reset-recipe]] §reply-kb gotcha)
- ✅ /start → онбординг
- ✅ Дошёл до cycle question после maternal flow
- ✅ Нажал «Sí, configurar»
- ✅ На setup screen увидел default ✅ на 7d_ago (этот тест и был source 4 risks выше)
- ✅ Нажал «Hace 7 días» → save → переход → продолжение онбординга → завершение
- ✅ reply-kb обновилась на onboarding_success через mig 374 reattach
- ⚠️ Owner спросил про default = главный design risk

## Связано с

- [[concepts/adaptive-modifiers-architecture]] — Phase 3d luteal modifier (mig 334-335)
- [[concepts/checkmark-prefix-pattern]] — `current_value_col` рендеринг
- [[concepts/test-user-reset-recipe]] §reply-kb gotcha — почему UAT может ввести в заблуждение
- [[concepts/calc-user-targets-roadmap]] — где luteal вклад в targets
- [[concepts/safety-guard-ux-pattern]] — если решим добавить menopause warning
- [[concepts/memory-claim-vs-live-verification]] — этот документ собран live verification, не handover-claim
