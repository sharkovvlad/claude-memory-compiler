---
title: "User Data Collection Pattern — Retrofit для existing users"
aliases: [data-collection, retrofit-pattern, re-onboarding, daily-check-in]
tags: [architecture, pattern, onboarding, ux, cron, gdpr]
sources:
  - "daily/2026-05-17.md"
  - "concepts/calc-user-targets-roadmap.md"
created: 2026-05-17
updated: 2026-05-17
---

# User Data Collection Pattern

Reusable framework для добавления новых полей в `users` schema когда **уже есть зарегистрированные пользователи**. Каждый раз когда продукт расширяется новой переменной (флаг беременности, окружность талии, sleep hours, stress level, cycle phase, diet_type) — повторяется один и тот же набор design-вопросов. Этот документ фиксирует решения раз и навсегда.

## Когда применяется

Любое из:
1. Новое **обязательное** поле в users (например, `is_pregnant` для safety).
2. Новое **опциональное** поле, повышающее точность (например, `waist_cm` для RFM).
3. **Ежедневный сигнал** (sleep, stress, cycle phase для Phase 3 adaptive modifiers).

## Trifecta — три точки сбора + один cron

Каждое новое поле имеет **три места сбора** + **retrofit cron** для существующих юзеров.

```
┌─────────────────────────────────────────────────────────────────┐
│  NEW USER (registers today)                                     │
│  ├─ Onboarding step (если safety-критично)                      │
│  └─ Skip опция → smart default                                  │
├─────────────────────────────────────────────────────────────────┤
│  EXISTING USER (registered earlier, field = NULL)               │
│  ├─ Retrofit cron — шлёт one-time prompt в чат                  │
│  ├─ Profile screen → новый toggle/button                        │
│  └─ Reminder cron если skip (через 7/30 дней)                   │
├─────────────────────────────────────────────────────────────────┤
│  DAILY/EVENT-DRIVEN (sleep / stress / cycle)                    │
│  └─ Morning check-in cron (опц., может быть текст-анализ)       │
└─────────────────────────────────────────────────────────────────┘
```

## Decision matrix — куда добавлять каждое поле

| Поле | Onboarding | Profile | Daily cron | Retrofit cron | Priority |
|---|---|---|---|---|---|
| `is_pregnant` / `is_lactating` | **Да** (для F/15-50) | Да (toggle) | Нет | **Critical** (есть существующие F) | P0 safety |
| `waist_cm` | Q5 в phenotype quiz (опц) | Да (input) | Нет | Soft prompt (для obese phenotype) | P2 accuracy |
| `diet_type` (vegan/veg/omni) | Step после goal | Да (toggle) | Нет | One-time prompt всем | P1 accuracy |
| `sleep_quality` | Нет | Нет (autoreset) | **Утром daily** | N/A (daily) | P2 Phase 3 |
| `stress_level` | Нет | Нет (autoreset) | Опц daily / text-analysis | N/A | P2 Phase 3 |
| `cycle_phase` | Нет (privacy) | Да (opt-in tracker) | Calendar-based | Opt-in prompt для F | P2 Phase 3 |

## Принципы

### 1. Smart defaults вместо required fields

Новые поля **никогда** не должны блокировать существующих юзеров. Default values:
- `is_pregnant DEFAULT FALSE` (не unknown — иначе формула не знает что делать)
- `diet_type DEFAULT 'omnivore'`
- `waist_cm DEFAULT NULL` (fallback на phenotype-based formula)

Логика в `calculate_user_targets`: `COALESCE(field, default)` везде.

### 2. GDPR-sensitive — opt-in с явным объяснением

Sensitive поля (pregnancy, mental health stress, menstrual cycle) — **только opt-in**. Privacy patterns:
- Объяснение **зачем спрашиваем** (1-2 предложения, не «договор оферты»)
- Кнопка «Пропустить» / «Не хочу отвечать» = равноправный выбор
- Можно отозвать в любой момент через Profile → Privacy
- Никаких ретаргетинговых писем-напоминаний если skip

Пример sensitive prompt (RU):
> Узнаём для безопасности расчёта. Беременным и кормящим формула питания должна быть другой — обычный дефицит опасен. Если ответишь — мы автоматически переведём тебя на режим поддержания.
>
> [Беременна] [Кормлю грудью] [Ни то ни другое] [Не хочу отвечать]

### 3. 13-language messaging — copywriter agent

Любая user-facing коммуникация требует переводов на 13 языков (ar, de, en, es, fa, fr, hi, id, it, pl, pt, ru, uk).

Per новое поле нужны минимум:
- `prompt_<field>` (объяснение зачем)
- `option_<field>_<value>` (каждое значение из dropdown)
- `confirm_<field>` (подтверждение после выбора)
- `skip_<field>` (текст «можешь ответить потом в Профиле»)
- Опц `reminder_<field>` (если skip → reminder через 7-30 дней)

Spawn copywriter agent с brief'ом:
- Tone: Sassy Sage (дерзкий мудрец без shame)
- Constraints: Telegram SRE (≤35 chars/line, ≤12 lines/msg, ≤18 chars/button)
- Anti-shame red lines: никаких «худейте», «ваш вес проблема», «нужно работать над собой»
- Medical-style для safety триггеров: чёткий disclaimer «мы не заменяем врача»

См. [[concepts/sassy-sage-multilingual-glossary]] для tone calibration и [[concepts/ui-translations-bulk-update-recipe]] для technical pipeline.

### 4. Retrofit cron — паттерн

Для existing юзеров с NULL поле:

```sql
-- cron_collect_<field>.py (run daily, send to ≤N users/day to avoid spam)
SELECT telegram_id
FROM users
WHERE status = 'registered'
  AND is_bot = FALSE
  AND <field> IS NULL
  AND <prompt_eligible_condition>  -- например, gender='female' AND age 15-50 для pregnancy
  AND telegram_id NOT IN (
      SELECT telegram_id FROM <field>_prompt_log
      WHERE sent_at > NOW() - INTERVAL '30 days'
  )
LIMIT 100;  -- throttle
```

Тогда:
- Шлём prompt через bot API
- Записываем `<field>_prompt_log(telegram_id, sent_at, response)` для tracking
- Юзер отвечает через callback → `set_user_<field>(tg, value)` → `calculate_user_targets(tg, TRUE)` recalc

**Throttling:** не более 1 такого prompt в день на юзера + не больше 100 юзеров/день для одного поля (anti-spam).

### 5. Cascading recalc

После apply нового поля + backfill — **обязательный** recalc `calculate_user_targets` для всех affected юзеров:

```sql
DO $$
DECLARE r RECORD;
BEGIN
    FOR r IN SELECT telegram_id FROM users
             WHERE status='registered' AND <new_field> IS NOT NULL
             AND is_bot=FALSE
    LOOP
        PERFORM calculate_user_targets(r.telegram_id, TRUE);
    END LOOP;
END $$;
```

Snapshot перед recalc — стандартный `users_targets_backup_<DATE>` (см. [[concepts/personalized-macro-split]] секция Backup).

### 6. Daily check-in pattern (для Phase 3 adaptive modifiers)

Для полей которые меняются ежедневно (sleep, stress, cycle phase):

```
07:00-09:00 local time per user → cron шлёт «Доброе утро. Как спалось?»
            ↓
       [Хорошо] [Так себе] [Плохо] [Не отвечу]
            ↓
       INSERT INTO daily_metrics (telegram_id, date, sleep_quality)
            ↓
       Перед next meal log → calculate_user_targets читает сегодняшний sleep_quality
       → применяет Phase 3 modifier (+15% protein если sleep < 6h)
```

**Гранулярность:** ≤1 check-in вопрос в день на юзера. Не превращать в опросник. Юзер всегда может skip.

**Хранение:** `daily_metrics` таблица (уже существует, см. Master Blueprint) — `symptoms`, `energy_level`, `sleep_hours`. Расширяется новыми полями для каждого Phase 3 модификатора.

## Anti-patterns (что не делать)

❌ **«Обязательное обновление профиля»** — заставлять юзера дозаполнить N полей перед следующим действием. Прерывает flow, юзеры churn'ятся.

❌ **«Push notification спам»** — повторно слать тот же prompt каждый день. Раз в 30 дней максимум.

❌ **«Privacy unaware»** — собирать pregnancy / mental health без явного opt-in и объяснения. Юридический риск + потеря доверия.

❌ **«One-size onboarding»** — добавлять каждое новое поле в обязательный шаг онбординга. Онбординг разрастается → drop-off rate растёт. Только safety-критичные fields идут в onboarding.

❌ **«Без backfill cron»** — добавили поле, новые юзеры заполняют, старые игнорируются годами. Через 6 мес 80% базы без поля → формула неточная для 80%.

❌ **«Без 13-language переводов»** — messaging только на RU/EN → не-русский/английский юзер видит белиберду или fallback который не объясняет.

## Чек-лист перед spawn'ом задачи с новым полем

1. [ ] Какое поле, тип, default, nullable?
2. [ ] Где собираем (onboarding / Profile / daily cron / retrofit)?
3. [ ] Sensitive data? Если да — opt-in flow + privacy text утверждён?
4. [ ] Smart default для существующих юзеров?
5. [ ] Retrofit cron скоп: какие existing юзеры eligible?
6. [ ] Сообщения на 13 языках готовы (или spawn copywriter agent)?
7. [ ] Throttling: ≤1 prompt/день/юзер + ≤100 юзеров/день/поле?
8. [ ] Cascading recalc plan (после apply + backfill)?
9. [ ] Snapshot стратегия для rollback?
10. [ ] Telemetry: как узнаем что cron работает (logging, метрика adoption rate)?

## Примеры применения

### Pregnancy / lactation (P0.6)
- Onboarding: новый шаг для `gender=female AND age 15-50`
- Profile: toggle в `Settings → Privacy → Health Status`
- Retrofit: cron шлёт one-time prompt всем `female 15-50` без is_pregnant
- Messaging: 5 строк × 13 языков = 65 строк
- Backfill: после ответа → `calculate_user_targets(_, TRUE)` recalc → переводит на maintain

### Waist circumference (P2.1)
- Phenotype quiz Q5 — optional, после Q4
- Profile: input field в «Body Type»
- Retrofit: soft prompt только для obese phenotype (≤100 users/day)
- Messaging: 4 строки × 13 = 52
- Backfill: recalc только для obese phenotype users

### Sleep quality daily (P2.4 Phase 3)
- Daily check-in cron 07-09 local time
- Profile: opt-in toggle «Утренние вопросы про сон»
- Storage: daily_metrics.sleep_hours / sleep_quality
- Messaging: 3 строки × 13 = 39 (привет / варианты / спасибо)
- Применение: `calculate_user_targets` читает today's sleep_quality → Phase 3 modifier

## Связанные концепты

- [[concepts/calc-user-targets-roadmap]] — какие именно поля будут добавлены
- [[concepts/sassy-sage-multilingual-glossary]] — tone calibration для messaging
- [[concepts/ui-translations-bulk-update-recipe]] — pipeline writer→critic для 13 языков
- [[concepts/personalized-macro-split]] — формула, которая использует все эти поля
