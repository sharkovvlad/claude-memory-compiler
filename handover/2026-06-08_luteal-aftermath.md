---
title: "Luteal incident aftermath — handover"
date: 2026-06-08
scope: adaptive-modifiers, reminder-system
status: open
---

# Handover 2026-06-08 — после luteal-инцидента

## Что произошло (5 секунд)

Male admin получил пуш про лютеиновую фазу + +175 ккал. Корни: каскад полей не существовал; gender-гейт отсутствовал; cron шёл info-only, текст «added +N kcal» был ложью для **всех** Premium-женщин 8 месяцев. Полный разбор — `concepts/adaptive-modifiers-architecture.md` §«2026-06-08 incident & defence-in-depth».

## Что в LIVE

- **mig 491 (PR #367 MERGED):** cron реально пишет daily_modifier. Placeholder `{kcal_delta}` в 13 langs.
- **mig 494 (PR #366 MERGED):** trigger `trg_users_cascade_clear_female` + gender-гейт в `compute_cycle_day_for_user`.

## Что осталось (priority order)

### 1. Вынос medical-дельт в `app_constants`

Owner подтвердил 2026-06-08. Сейчас 100/175/3/7 захардкожены в `apply_daily_modifier` (`migrations/474_protein_calibration_gain_floor_sleep.sql:801-810`).

**План:**
- Миграция (свободный номер — проверь через guard): `INSERT INTO app_constants (key, value)`:
  - `modifier_luteal_early_kcal_delta` = `100`
  - `modifier_luteal_early_fat_pct` = `3`
  - `modifier_luteal_late_kcal_delta` = `175`
  - `modifier_luteal_late_fat_pct` = `7`
- В `apply_daily_modifier` заменить хардкод на `SELECT value::numeric FROM app_constants WHERE key = ...` (с fallback на текущие числа).
- Hot-reload через `app_constants_cache` trigger — без рестарта сервиса.

**Verification:** до/после миграции `apply_daily_modifier(786301802, 'luteal', 'luteal_late')` возвращает тот же `calories_delta=175`.

### 2. Решение по `follicular` / `ovulation` в CHECK constraint

Сейчас (`migrations/301_adaptive_modifiers_foundation.sql:110`):
```sql
CHECK (modifier_type = 'luteal' AND trigger_value IN ('follicular','ovulation','luteal_early','luteal_late'))
```

В `apply_daily_modifier` веток для `follicular`/`ovulation` нет — проходят мимо `IF/ELSIF` с нулями. `cron_get_reminder_candidates('luteal_morning')` вычисляет `luteal_phase` только для дней 15–28. То есть на практике эти два значения **никогда не вызываются** — dead branches.

**Рекомендация (требует обсуждения с owner):** сузить CHECK до `IN ('luteal_early','luteal_late')`. Защищает от случайного будущего вызова с baseline (где результат — пустая запись с нулями).

Альтернатива: оставить и добавить комментарий «reserved for Phase 3e fine-tune». Архитекторский call.

### 3. Не дублировать

Отдельная параллельная сессия уже работает над инвентаризацией 11 reminder-типов + ежедневным дайджестом в админ-чат (`task_678a0dab`, спав-таск создан 2026-06-08). Не лезь туда.

## Ссылки

- KB: [[concepts/adaptive-modifiers-architecture]] — обновлён 2026-06-08 секцией Scientific basis + Incident
- KB: [[concepts/cycle-tracking-ux-and-accuracy]]
- Daily: `daily/2026-06-08.md` — полный разбор
- Локальный источник цифр: `~/Documents/NOMS/Нутрициолог (другой ИИ)/Глубокий анализ формулы расчета целей NOMS.md:91` (PMC13066135)
- LIVE mig: 491, 494
