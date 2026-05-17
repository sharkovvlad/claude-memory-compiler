---
title: "User Data Collection Pattern — Retrofit для existing users"
aliases: [data-collection, retrofit-pattern, re-onboarding, daily-check-in]
tags: [architecture, pattern, onboarding, ux, cron, gdpr]
sources:
  - "daily/2026-05-17.md"
  - "concepts/calc-user-targets-roadmap.md"
  - "Agent 234 critique 2026-05-17 (6/7 правок принято + 1 частично)"
created: 2026-05-17
updated: 2026-05-17
---

# User Data Collection Pattern

Reusable framework для добавления новых полей в `users` schema когда **уже есть зарегистрированные пользователи**. Каждый раз когда продукт расширяется новой переменной (флаг беременности, окружность талии, sleep hours, stress level, cycle phase, diet_type) — повторяется один и тот же набор design-вопросов. Этот документ фиксирует решения раз и навсегда.

## Когда применяется

Любое из:
1. Новое **обязательное** поле в users (например, `is_pregnant` для safety).
2. Новое **опциональное** поле, повышающее точность (например, `waist_cm` для RFM).
3. **Ежедневный сигнал** (sleep, stress).
4. **Event-driven сигнал** (cycle onset, weight check-in).

## Trifecta + 3 паттерна check-in

Каждое новое поле имеет **три места сбора** + **retrofit cron** для существующих юзеров. Также есть **3 раздельных pattern для periodic check-in** — не смешивать в одном бакете.

```
┌─────────────────────────────────────────────────────────────────┐
│  NEW USER (registers today)                                     │
│  ├─ Onboarding step (если safety-критично)                      │
│  └─ Skip опция → smart default (для safety-critical = NULL!)    │
├─────────────────────────────────────────────────────────────────┤
│  EXISTING USER (registered earlier, field = NULL)               │
│  ├─ Retrofit cron — adaptive throttle (см. ниже)                │
│  ├─ Profile screen → новый toggle/button                        │
│  └─ Reminder cron если skip (через 7/30 дней)                   │
├─────────────────────────────────────────────────────────────────┤
│  PERIODIC SIGNALS — 3 разделённых паттерна (НЕ смешивать)       │
│  ├─ Daily quick (sleep/stress, 07-09 local)                     │
│  ├─ Event-driven (cycle onset — единичная отметка + auto-calc)  │
│  └─ Weekly (weight check-in, любое время)                       │
└─────────────────────────────────────────────────────────────────┘
```

## Decision matrix — куда добавлять каждое поле

| Поле | Onboarding | Profile | Periodic | Retrofit cron | Priority | Default |
|---|---|---|---|---|---|---|
| `is_pregnant` / `is_lactating` | **Да** (для F/15-50) | Да (toggle) | Нет | **Critical** (есть существующие F) | P0 safety | **NULL** ⚠️ |
| `waist_cm` | Q5 в phenotype quiz (опц) | Да (input) | Нет | Soft prompt (для obese phenotype) | P2 accuracy | NULL |
| `diet_type` (vegan/veg/omni) | Step после goal | Да (toggle) | Нет | One-time prompt всем | P1 accuracy | `omnivore`† |
| `sleep_quality` | Нет | Нет (autoreset) | **Daily quick** | N/A | P2 Phase 3 | NULL daily |
| `stress_level` | Нет | Нет (autoreset) | **Daily quick** или text-analysis | N/A | P2 Phase 3 | NULL daily |
| `cycle_phase` | Нет (privacy) | Да (opt-in tracker) | **Event-driven** (cycle onset → auto-calc) | Opt-in prompt для F | P2 Phase 3 | NULL |
| `weight_kg` (re-measure) | Yes initial | Yes edit | **Weekly** | Existing flow | base | from onboarding |

⚠️ **`is_pregnant DEFAULT NULL` — критично, не FALSE.** См. § Smart defaults ниже.

† **`diet_type DEFAULT 'omnivore'`** — допустимо если retrofit cron активный (база заполнится за 30 дней). Альтернатива «NULL + force +10% protein margin» — overengineering. Open для обсуждения.

## Принципы

### 1. Smart defaults — критическое правило для safety полей

**Для safety-critical полей DEFAULT NULL, не FALSE.**

Default `FALSE` означает «не беременна / не лактирует» = разрешаем дефицит. Это **аннулирует** P0.6 защиту для existing женщин, у которых поле не заполнено.

```sql
-- ❌ ОПАСНО (default аннулирует safety check)
ALTER TABLE users ADD COLUMN is_pregnant BOOLEAN DEFAULT FALSE;

-- ✅ ПРАВИЛЬНО (NULL = unknown = защитный режим)
ALTER TABLE users ADD COLUMN is_pregnant BOOLEAN DEFAULT NULL;
```

В `calculate_user_targets` логика:

```sql
-- Защитный режим: для F/15-50 с НЕИЗВЕСТНЫМ статусом — force maintain
IF v_user.gender='female'
   AND v_age BETWEEN 15 AND 50
   AND v_user.is_pregnant IS NULL
   AND v_user.goal_type = 'lose' THEN
    v_forced_goal_type := 'maintain';
    v_pregnancy_warning := 'unknown_status_protective_maintain';
END IF;
```

**Soft (accuracy) поля могут иметь content default:**
- `diet_type DEFAULT 'omnivore'` — допустимо, потому что (а) самый частый случай, (б) retrofit cron активный закроет gap, (в) недокорм белка у вегана = comfort/recovery, не life/death.

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

### 3. 13-language messaging — copywriter agent + translation-ready gate

Любая user-facing коммуникация требует переводов на 13 языков (ar, de, en, es, fa, fr, hi, id, it, pl, pt, ru, uk).

**Acceptance criterion — translation-ready gate:**

```python
# cron активируется ТОЛЬКО когда все 13 переводов готовы
ELIGIBLE_FIELDS = [
    field for field in PENDING_RETROFITS
    if all_13_langs_have_translation(f"prompt_{field}")
       and all_13_langs_have_translation(f"confirm_{field}")
       and all_13_langs_have_translation(f"skip_{field}")
]
```

Иначе AR/HI/PT юзер видит EN fallback (плохой UX). Никогда не активируем cron «частично готовым messaging».

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

### 4. Retrofit cron — adaptive throttle

**Throttle scales по размеру базы**, не fixed 100/день (не масштабируется на 10k+ юзеров).

```python
def adaptive_throttle(base_size: int, field_priority: str) -> int:
    """Возвращает max prompts per day для retrofit cron."""
    if base_size < 1000:
        return base_size  # весь rollout за день, нет throttle
    elif base_size < 10_000:
        return 500
    else:
        # 10k+: 1000/день, но priority order (pregnancy > waist > diet > sleep)
        return 1000 if field_priority == 'safety_critical' else 500
```

Шаблон SQL для подбора:

```sql
SELECT telegram_id
FROM users
WHERE status = 'registered'
  AND is_bot = FALSE
  AND <field> IS NULL
  AND <prompt_eligible_condition>  -- gender='female' AND age 15-50 для pregnancy
  AND telegram_id NOT IN (
      SELECT telegram_id FROM user_prompt_log
      WHERE field_name = '<field>'
        AND sent_at > NOW() - INTERVAL '30 days'
  )
LIMIT (SELECT adaptive_throttle FROM cron_config WHERE field='<field>');
```

- Шлём prompt через bot API
- Записываем в **unified** `user_prompt_log` (см. ниже)
- Юзер отвечает через callback → `set_user_<field>(tg, value)` → `calculate_user_targets(tg, TRUE)` recalc

**Per-user throttling:** не более 1 такого prompt в день на юзера (anti-spam).

### 5. Unified `user_prompt_log` таблица — не per-field

**Раньше:** N таблиц `is_pregnant_prompt_log`, `waist_prompt_log`, `diet_type_prompt_log` — дублирование schema, миграция на каждое поле.

**Правильно:** одна таблица:

```sql
CREATE TABLE user_prompt_log (
    id BIGSERIAL PRIMARY KEY,
    telegram_id BIGINT NOT NULL REFERENCES users(telegram_id),
    field_name TEXT NOT NULL,         -- 'is_pregnant', 'waist_cm', 'diet_type'
    sent_at TIMESTAMPTZ DEFAULT NOW(),
    response_value TEXT,              -- сериализованный ответ юзера (или NULL если skip)
    response_at TIMESTAMPTZ,          -- когда ответил (или NULL если ещё нет)
    message_variant TEXT,             -- для A/B testing разных формулировок
    UNIQUE (telegram_id, field_name, sent_at)
);

CREATE INDEX idx_user_prompt_log_field_recent ON user_prompt_log (field_name, sent_at DESC);
CREATE INDEX idx_user_prompt_log_user ON user_prompt_log (telegram_id, sent_at DESC);
```

Преимущества:
- Одна schema, одна миграция (раз и навсегда)
- A/B testing messaging cross-fields из коробки
- Аналитика response rate / time-to-respond / variant performance
- Easier reasoning о «какие промпты юзер уже видел сегодня»

### 6. Cascading recalc

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

### 7. Canary rollback strategy

**Любой retrofit cron rollout — canary 10% базы с метриками.**

Шаги:
1. **10% базы** случайной выборкой (`telegram_id % 10 = 0`)
2. **24-48h наблюдение** метрик:
   - Churn rate vs baseline за тот же период (cron jobs, last_active_at)
   - Response rate (сколько % ответили vs skip)
   - Negative feedback (юзеры пишут в support / /help / /complaint)
3. **Trigger rollback:** если churn rate -5%+ относительно baseline → STOP, пересмотр messaging → retry с новой версией
4. **Trigger continue:** если churn в норме → catch-up на оставшиеся 90% по adaptive throttle

Без canary первый rollout = молниеносный негативный feedback loop, который может стоить тысяч юзеров.

### 8. Daily / Event-driven / Weekly — 3 разделённых паттерна

**Не смешивать в одном бакете** «Daily check-in». Семантика и UX разные:

#### Daily quick (sleep/stress, 07-09 local time)

- Раз в день, утром, 1 quick вопрос
- Storage: `daily_metrics(telegram_id, date, field, value)`
- Применение: `calculate_user_targets` читает сегодняшний sleep_quality → Phase 3 modifier
- Skip allowed без штрафов

#### Event-driven (cycle onset — единичная отметка)

- Юзер один раз отмечает start of period
- Cron auto-calculates `cycle_phase` от calendar (luteal phase = за 7-10 дней до next onset based on cycle_length)
- НЕ daily вопрос (не «у тебя сегодня лютеиновая фаза?»)
- Storage: `users.last_period_start DATE`, `users.cycle_length INT`
- Privacy-sensitive — opt-in, GDPR

#### Weekly (weight check-in)

- Раз в неделю, любое время удобное юзеру
- Smart timing: cron шлёт reminder если 7+ дней без weight entry
- Storage: уже существует через `sync_user_weight` flow
- Pattern: «Раз в неделю спрашиваем «как вес?» — не достаём ежедневно»

**Гранулярность общая:** ≤1 prompt в день на юзера (across всех patterns). Если juzer одновременно eligible для sleep daily + cycle prompt + weight reminder — priority queue, шлём наиболее срочный.

## Anti-patterns (что не делать)

❌ **«Обязательное обновление профиля»** — заставлять юзера дозаполнить N полей перед следующим действием. Прерывает flow, юзеры churn'ятся.

❌ **«Push notification спам»** — повторно слать тот же prompt каждый день. Раз в 30 дней максимум на per-field basis. Общий per-user cap 1/день across всех полей.

❌ **«Privacy unaware»** — собирать pregnancy / mental health без явного opt-in и объяснения. Юридический риск + потеря доверия.

❌ **«One-size onboarding»** — добавлять каждое новое поле в обязательный шаг онбординга. Онбординг разрастается → drop-off rate растёт. Только safety-критичные fields идут в onboarding.

❌ **«Без backfill cron»** — добавили поле, новые юзеры заполняют, старые игнорируются годами. Через 6 мес 80% базы без поля → формула неточная для 80%.

❌ **«Без 13-language переводов»** (translation-ready gate) — messaging только на RU/EN → не-русский/английский юзер видит белиберду или fallback который не объясняет.

❌ **«DEFAULT FALSE для safety-critical»** — default «не беременна» аннулирует pregnancy check для всех existing F юзеров. **Используй DEFAULT NULL** + защитный режим в формуле для IS NULL.

❌ **«Per-field prompt log таблицы»** — N миграций для N полей. Используй unified `user_prompt_log`.

❌ **«Без canary»** — 100% rollout сразу. Один плохой messaging → churn 10k+ юзеров. Canary 10% → 24-48h → continue or rollback.

❌ **«Fixed throttle 100/день»** — не scale на 10k+. Используй adaptive throttle.

## Чек-лист перед spawn'ом задачи с новым полем

1. [ ] Какое поле, тип, default, nullable? **Safety-critical → DEFAULT NULL обязательно.**
2. [ ] Где собираем (onboarding / Profile / daily cron / event-driven / weekly / retrofit)?
3. [ ] Sensitive data? Если да — opt-in flow + privacy text утверждён?
4. [ ] Smart default для существующих юзеров? (NULL для safety, content для accuracy)
5. [ ] Retrofit cron скоп: какие existing юзеры eligible?
6. [ ] Сообщения на 13 языках готовы (или spawn copywriter agent)? **Translation-ready gate перед enabling cron.**
7. [ ] Throttling: adaptive (по размеру базы) + ≤1 prompt/день/юзер total?
8. [ ] Cascading recalc plan (после apply + backfill)?
9. [ ] Snapshot стратегия для rollback?
10. [ ] **Canary 10% plan** — какие метрики мониторим (churn, response rate, negative feedback) + rollback trigger?
11. [ ] Логирование в **unified** `user_prompt_log` (не per-field)?
12. [ ] Telemetry: как узнаем что cron работает (logging, метрика adoption rate)?

## Примеры применения

### Pregnancy / lactation (P0.6)
- **Default:** `DEFAULT NULL` ⚠️ critical (НЕ FALSE)
- Onboarding: новый шаг для `gender=female AND age 15-50`
- Profile: toggle в `Settings → Privacy → Health Status`
- Retrofit: cron шлёт one-time prompt всем `female 15-50` без is_pregnant, adaptive throttle, priority='safety_critical'
- Messaging: 5 строк × 13 языков = 65 строк, translation-ready gate before enable
- Защитный режим для IS NULL: F/15-50 → force maintain + soft warning
- Canary: 10% женщин base 24-48h
- Backfill: после ответа → `calculate_user_targets(_, TRUE)` recalc → переводит на maintain

### Waist circumference (P2.1)
- **Default:** NULL
- Phenotype quiz Q5 — optional, после Q4
- Profile: input field в «Body Type»
- Retrofit: soft prompt только для obese phenotype, adaptive throttle, priority='accuracy'
- Messaging: 4 строки × 13 = 52
- Backfill: recalc только для obese phenotype users
- Без canary (low-risk soft accuracy fix)

### Sleep quality daily (P2.4 Phase 3) — **Daily quick pattern**
- Daily check-in cron 07-09 local time
- Profile: opt-in toggle «Утренние вопросы про сон»
- Storage: daily_metrics.sleep_hours / sleep_quality (НЕ users column)
- Messaging: 3 строки × 13 = 39 (привет / варианты / спасибо)
- Применение: `calculate_user_targets` читает today's sleep_quality → Phase 3 modifier

### Cycle phase (P2.4 Phase 3) — **Event-driven pattern**
- Опт-ин в Profile (gender=female only)
- Юзер отмечает start of period **один раз** при onset
- Cron auto-calc cycle_phase каждый день on basis last_period_start + cycle_length
- Storage: `users.last_period_start DATE`, `users.cycle_length INT`
- НЕ daily prompt — privacy-sensitive
- Применение: расчёт показывает «лютеиновая фаза» → +150-200 kcal modifier

## Связанные концепты

- [[concepts/calc-user-targets-roadmap]] — какие именно поля будут добавлены
- [[concepts/sassy-sage-multilingual-glossary]] — tone calibration для messaging
- [[concepts/ui-translations-bulk-update-recipe]] — pipeline writer→critic для 13 языков
- [[concepts/personalized-macro-split]] — формула, которая использует все эти поля
