---
title: "Safety Guard UX Pattern — Argued Override (Reusable)"
aliases: [safety-guard-ux, argued-override, guard-banner, age-guard-ux]
tags: [ux, safety, headless, calculate-user-targets, retention, legal]
sources:
  - "daily/2026-05-17.md"
  - "concepts/calc-user-targets-roadmap.md"
  - "concepts/user-data-collection-pattern.md"
  - "migrations/234_calculate_user_targets_age_guards.sql"
created: 2026-05-17
updated: 2026-05-17
---

# Safety Guard UX Pattern

Reusable framework для всех ситуаций, когда **формула делает что-то отличное от заявленного юзером намерения** по safety-соображениям. Первое применение — age guards mig 234. Дальнейшие триггеры (pregnancy, BMI<18.5, RED-S, diet break) обязаны следовать этому паттерну.

## 1. Главный принцип — Argued Override, не Silent Substitution

Каждый guard, который меняет поведение формулы относительно намерения юзера, должен:

1. **Сказать что изменилось.** «Ты выбрал похудеть, я поставил поддержание.»
2. **Объяснить почему.** В 1-2 предложениях, без жаргона. Со ссылкой на медицинский факт.
3. **Сказать что делать.** «Покажи врачу», «обсудим, когда тебе будет 18», или conditional opt-out.
4. **Дать выход.** Hard guard (без opt-out) только для extreme cases (pregnancy, BMI<14). Остальные — soft guard с medical override.

**Почему это критично:**
- **Trust.** Молчаливая подмена цели = «бот сломан / врёт / уйду к MyFitnessPal». Все три = churn.
- **Legal.** «Тайно изменили» — слабая позиция перед FTC. «Предупредили + явно переключили» — сильная (legal cover P0.2).
- **Educational value.** 16-летняя реально может впервые узнать про РПП-риск и Mifflin-валидность через наш banner.
- **Anti-shaming consistent.** Sassy Sage character — мудрый, прямой, без shame. Молчаливая подмена — не его стиль.
- **Обратимость.** Когда условие снимается (юзеру стукнет 18) — формула автоматически перестанет форсить. Без объяснения «почему вдруг ккал поменялись» = претензия. С объяснением = понятно.

## 2. Anatomy of a Guard — 5 UX Touch Points

Каждый guard имеет **5 поверхностей**, на которых проявляется:

```
┌──────────────────────────────────────────────────────────┐
│  1. ONBOARDING                                           │
│     Юзер вводит данные, триггерящие guard сразу.         │
│     → Inline modal: «Заметили, что [X]. Объясняем…»      │
│     → Юзер видит до того как ему посчитали таргеты.      │
├──────────────────────────────────────────────────────────┤
│  2. PROFILE PASSIVE BANNER                               │
│     Persistent (пока guard активен) yellow strip в       │
│     Profile/«Мой план». Кликабельный → modal с deep ctx. │
├──────────────────────────────────────────────────────────┤
│  3. FIRST-TRIGGER CARD (одноразово)                      │
│     При первом detection — full-screen modal с детальным │
│     объяснением + sources + кнопками («Понял», «Спросить │
│     /support», opt-out если разрешён).                   │
│     Логируется в users.shown_guards JSONB чтобы не       │
│     показывать второй раз.                               │
├──────────────────────────────────────────────────────────┤
│  4. RETROFIT CRON (для existing)                         │
│     Когда guard вводится новой миграцией, существующие   │
│     юзеры, попадающие под условие, получают one-time     │
│     prompt в чат. См. [[concepts/user-data-collection-   │
│     pattern]] для throttling и schema.                   │
├──────────────────────────────────────────────────────────┤
│  5. AUTO-RESET                                           │
│     Когда условие снимается (юзеру стукнуло 18, BMI      │
│     вырос > 18.5, беременность закончилась) → guard      │
│     автоматически gone, шлётся уведомление-«unfreeze»:   │
│     «У тебя сменилось [X]. Защита снята. Теперь          │
│     доступны прежние цели.»                              │
└──────────────────────────────────────────────────────────┘
```

## 2b. Implementation Status (2026-05-18)

5 touch-points → текущее state на проде:

| # | Touch-point | Status | Where |
|---|---|---|---|
| 1 | Onboarding inline modal | ⏳ in flight | mig 259 (in background agent — F/15-50 maternal question) |
| 2 | Profile passive banner | ✅ implemented | mig 252 (my_plan) + mig 256 (personal_metrics + profile_main) — distributed enforcement через helper `build_safety_guard_banner_block` |
| 3 | First-trigger card (modal_full) | ❌ NOT implemented | Требует Python hook reading `users.shown_guards` JSONB. modal_full тексты уже в `ui_translations` (mig 240/258). |
| 4 | Retrofit cron | ❌ NOT implemented for maternal | Требует APScheduler worker filtering F/15-50 с `is_pregnant IS NULL` (partial index `idx_users_maternal_protective` готов в mig 253). |
| 5 | Auto-reset | ❌ NOT implemented | Daily cron scan для users где warning enum cleared (age→18, BMI cleared, pregnancy ended). `auto_resolved` тексты уже в `ui_translations`. |

**Distributed banner enforcement principle (touch-point #2):** banner ОБЯЗАН быть на всех screens где user видит/меняет goal_type или данные формулы. Не только `my_plan`. Cм. mig 256 — закрыл pad с `personal_metrics` + `profile_main`. Если добавляется новый профильный screen — обязательно добавить `{banner_block}` placeholder + extend business_data_rpc через helper.

## 3. Severity Levels (5-tier) — какой UX подходит для какого guard'а

> **Canonical source:** [[concepts/agent-collaboration-protocol]] Rule 1. Эта секция — UX-extension с banner specifics + emoji prefix; severity vocabulary владеет protocol-документ.

Никаких альтернативных синонимов («medium», «warning», «alert») как отдельных категорий — каждый guard обязан указать severity по этой таблице.

| Severity | Override юзерского намерения | Banner | Banner emoji prefix | Banner color | Opt-out |
|---|---|---|---|---|---|
| **hard block** | Да | non-dismissible | 🛡️ | red | **Никогда** |
| **hard regulated** | Да | non-dismissible | 🛡️ | red | **Только врач + audit log** (не self-consent) |
| **soft override** | Да | dismissible | ⚠️ | yellow | Voluntary с confirmation flow |
| **informational** | Нет | dismissible | 💡 (или 🌿 для elderly) | blue | N/A (нет override формулы) |
| **silent accuracy** | Нет | **НЕТ** | N/A | N/A | N/A |

**Emoji prefix rule:** `banner_title` value в `ui_translations` **обязан** начинаться с emoji prefix согласно severity. Это даёт юзеру моментальный visual cue до чтения текста. Copywriter agent проверяет в L1 review. Применено в mig 240/241/242 (age warnings) и mig 246+ (bmi/min_kcal).

### Trigger Table (re-classified per 5-tier)

| Trigger | Severity | Что меняется | Why this tier |
|---|---|---|---|
| `<18 + lose` | **hard block** | goal_type → maintain | Ребёнок не consent'ит на дефицит (FTC/California legal-protected). РПП-риск. |
| `<18 + gain/maintain` | **informational** | Только banner («формулы адаптированы, мы не заменяем педиатра») | Нет override; legal cover banner для disclaimer. |
| `>75` | **informational** | Только banner («таргеты менее точны, обсуди с гериатром») | Нет override; формула в mig 234 не меняется, в mig 236+ → silent accuracy switch. |
| `pregnancy=TRUE + lose` | **hard block** | Force maintain + добавить +300-500 kcal по триместру | Medical floor; нейротоксична для плода. Pregnancy не self-consent'ится. |
| `BMI<14 + любой goal` | **hard block** | Force maintain + recommend medical | Extreme cachexia, выживание; не self-consent. |
| `BMI<18.5 + lose` | **hard regulated** | goal_type → maintain | Underweight; требует врач'а как gate, не voluntary self-consent. |
| `BMI>60 + fast` | **hard regulated** | Clamp deficit на slow (-10%) + recommend medical | Морбидное ожирение; ускоренный дефицит = риск осложнений, нужен врач. |
| `BMI>60` (slow/normal) | **informational** | Banner «обсуди план с врачом» | Не override, telemetry. |
| `EA < 30 kcal/kg LBM` (RED-S) | **soft override** | Auto-raise calories до EA threshold | Voluntary acknowledgment; RED-S — long-term risk. |
| `diet break > 56 days` | **soft override** | 7-14 дней forced maintain | Voluntary nullification возможен (осознанный choice). |
| `min_kcal < BMR` или `< 1200ж/1500м` | **soft override** | Clamp до floor + warning «ниже BMR опасно» | Floor breach часто = misinput. Opt-out возможен только с medical doc. |
| `athlete phenotype no-op` (P1) | **informational** | Banner «athlete-specific formula coming» | Telemetry, не override. |
| `formula switch <18 Schofield/Molnar` (mig 236) | **silent accuracy** | Внутренний BMR switch | Юзер не выбирал Mifflin; не override, banner НЕТ. |
| `formula switch >75 Lührmann` (mig 236) | **silent accuracy** | Внутренний BMR switch | Аналогично. |
| `Katch-McArdle при known LBM` (P2) | **silent accuracy** | Switch BMR на Katch-McArdle | Аналогично. |
| `ABW для obese` (P1) | **silent accuracy** | Switch target_weight на Adjusted Body Weight | Аналогично. |

## 4. Decision Tree для нового guard'а

Перед spawn'ом новой миграции с guard ответь на 8 вопросов:

1. **Что триггерит?** (e.g., age<18, BMI<14, is_pregnant=TRUE, ea<30)
2. **Severity?** (hard block / hard regulated / soft override / informational / silent accuracy — по 5-tier matrix)
3. **Что меняем в формуле?** (force goal_type, raise calories, clamp speed, internal BMR switch)
4. **JSON-поле telemetry?** (`<trigger>_warning`, value=<enum string>)
5. **Auto-reset variant?** (full release / tier softening / tier escalation — см. §5b)
6. **Opt-out flow?** (если да — `user_overrides` table, audit log, кто confirm'ит: юзер с medical doc / только врач / N/A)
7. **Translation pipeline tier?** (по Rule 9 cultural review — L1/L2/N/A в зависимости от severity, см. §6)
8. **Banner показывается?** (НЕТ для silent accuracy; иначе по severity)

## 5. Translation Keys — единый naming convention

> **Canonical naming spec:** [[concepts/agent-collaboration-protocol]] Rule 3 (`warning.<family>.<severity>.<surface>` format + storage spec). Эта секция — surface details + length budgets.

Каждый guard имеет до **5 surfaces** (× 13 языков = до 65 строк):

```
warning.<family>.<severity>.banner_title      # 20-40 chars; emoji prefix obligatory (§3 matrix)
warning.<family>.<severity>.banner_body       # 1-2 sentences, ≤140 chars
warning.<family>.<severity>.modal_full        # 5-10 lines детального explanation + sources
warning.<family>.<severity>.opt_out_confirm   # «Понимаю риск, мой врач одобряет» (только soft override)
warning.<family>.<severity>.auto_resolved     # «У тебя сменилось X — защита снята» (NULL для elderly_less_accurate)
```

**Note:** `opt_out_confirm` отсутствует для hard block / hard regulated (нет self-consent override). `auto_resolved` опционален для informational severity, где условие не имеет естественного «снятия» (например `elderly_less_accurate`).

**Примеры для mig 234:**
- `warning.age.underage_forced_maintain.banner_title`
- `warning.age.underage_forced_maintain.banner_body`
- `warning.age.underage_forced_maintain.modal_full`
- `warning.age.underage_forced_maintain.opt_out_confirm` (none — hard guard для lose)
- `warning.age.underage_forced_maintain.auto_resolved` («Тебе исполнилось 18, защита снята»)
- `warning.age.underage_disclaimer.banner_title`
- `warning.age.underage_disclaimer.banner_body`
- ...
- `warning.age.elderly_less_accurate.*`

**Tone (Sassy Sage):**
- Прямо, без морализаторства.
- Медицинский ↔ дружеский баланс. Не «вы должны», а «давай так».
- Никогда не «худеть нельзя» — всегда «давай отложим / посоветуемся».
- Anti-shame red lines: никаких «твой вес проблема», «нужно работать над собой».

См. [[concepts/sassy-sage-multilingual-glossary]] для tone calibration.

## 6. Auto-reset variants — НЕ только full release

Когда условие меняется, guard может (а) сняться полностью, (б) softened на менее жёсткий tier, (в) escalated на более жёсткий tier. Caller (Python handler + auto-reset cron) обязан обрабатывать все три.

### Variant A: Full release

Условие, триггерившее guard, полностью disappeared. Guard gone.

Примеры:
- `age` достигает 18 → ВСЕ age-related guards снимаются (`underage_forced_maintain`, `underage_disclaimer`)
- `is_pregnant` flag юзер сам выключает → pregnancy guards снимаются (с health-check follow-up)
- `BMI` растёт с 13 до 19+ → BMI-related hard block снимается

**UX:** one-shot Telegram message «Защита снята. <X> сменилось. Доступны прежние цели.» + clear из `users.shown_guards`.

### Variant B: Tier softening (downgrade)

Условие частично resolved — guard смягчается, но НЕ снимается полностью.

Примеры:
- Юзер 14 → 15 на `<18 + gain` — ранее force maintain (если бы был жёсткий guard для 13-14), теперь только disclaimer.
- BMI 13 → 16 → guard переходит из **hard block** в **hard regulated**.
- Diet break: 56 → 70 дней дефицита → guard escalates (см. variant C); но если юзер берёт 7-дневный break и возвращается → soft override gone, остаётся только informational «good job, maintained your break».

**UX:** notification «<X> улучшилось. Защита смягчена с <hard> на <soft>. Что изменилось: …». Banner стиль меняется (например, red → yellow).

### Variant C: Tier escalation (upgrade)

Условие усугубилось — guard становится более жёстким.

Примеры:
- Юзер на goal=lose ушёл > 56 дней дефицита → diet break **soft override** активируется (если не был раньше).
- BMI 17 → 14 → guard escalates с **hard regulated** на **hard block**.
- Pregnancy detected (юзер заполнил флаг) → активируется **hard block** даже если ранее был `<18 + disclaimer`.

**UX:** stronger notification + force user через soft modal ON next interaction («Заметили изменение. Меняем план питания. Пожалуйста, прочитай…»). Banner color & wording reflect новый severity.

### Implementation: auto-reset cron

```
Daily cron (03:00 UTC):
  FOR each registered user:
    FOR each <trigger>_warning из shown_guards:
      Re-evaluate trigger condition (re-run calculate_user_targets):
        IF condition gone → variant A (full release)
        IF condition softer → variant B (tier softening)
        IF condition harsher → variant C (tier escalation)
      Записываем в guard_audit_log событие auto_resolved / tier_changed
      Шлём notification если variant ≠ no_change
```

## 7. Translation pipeline (per Rule 9 coordination protocol)

> **Canonical source:** [[concepts/agent-collaboration-protocol]] Rule 9 (two-layer L1+L2 model, full tier matrix). [[concepts/l1-cultural-sanity-brief]] — operational checklist для L1 reviewer. [[concepts/sassy-sage-multilingual-glossary]] — tone reference per language.

Скиммируемая выдержка для агентов работающих в этом документе:

| Severity | L1 (нутрициолог) | L2 (native per family, 6 max) |
|---|---|---|
| **hard block** | Mandatory | Mandatory if L1 flags |
| **hard regulated** | Mandatory | Mandatory if L1 flags |
| **soft override** | Mandatory | Optional |
| **informational** | NOT required (glossary self-screen) | N/A |
| **silent accuracy** | N/A | N/A |

**Anti-pattern:** literal/word-for-word translation (Google Translate / DeepL без cultural pass). Каждый язык получает **adapted** message — idioms, gender policy, Telegram SRE, cultural taboos, RTL/script. См. [[concepts/l1-cultural-sanity-brief]] §"Cultural Flag Categories" для что искать при review.

## 8. Storage Schema

> **Status: applied 2026-05-17, migration 239** ([PR #89](https://github.com/sharkovvlad/noms-bot/pull/89)). Все три объекта (`users.shown_guards`, `user_overrides`, `guard_audit_log`) живут на проде. Schemas verified through `information_schema` + `pg_indexes` + `pg_constraint`. См. также [[daily/2026-05-17]].

### `user_shown_guards` (JSONB on `users` table)

```sql
ALTER TABLE users ADD COLUMN IF NOT EXISTS shown_guards JSONB DEFAULT '{}'::jsonb;
-- structure: { "underage_forced_maintain": "2026-05-17T10:30:00Z", "underage_disclaimer": "...", ... }
```

При первом показе full-screen modal'а — записываем timestamp. На следующий вызов API show only banner, не modal.

### `user_overrides` (новая таблица)

```sql
CREATE TABLE user_overrides (
    id BIGSERIAL PRIMARY KEY,
    telegram_id BIGINT REFERENCES users(telegram_id) ON DELETE CASCADE,
    trigger_name TEXT NOT NULL,  -- e.g. 'underweight_lose', 'diet_break_56'
    override_value BOOLEAN NOT NULL,  -- TRUE = пользователь подтвердил «я понимаю риск»
    reason_text TEXT,             -- свободный текст, опц. («тренер одобрил», «врач одобрил»)
    set_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ,       -- опц. (некоторые override'ы временные)
    UNIQUE(telegram_id, trigger_name)
);
```

При запросе `calculate_user_targets` — caller (Python handler) делает дополнительный SELECT и **отменяет** guard на UI-стороне, если override active. Сама RPC continue возвращать `<trigger>_warning` — telemetry preserved.

### `guard_audit_log` (для FTC/legal traceability)

```sql
CREATE TABLE guard_audit_log (
    id BIGSERIAL PRIMARY KEY,
    telegram_id BIGINT,
    trigger_name TEXT NOT NULL,
    event TEXT NOT NULL,  -- 'triggered', 'shown', 'opt_out', 'auto_resolved'
    metadata JSONB,
    occurred_at TIMESTAMPTZ DEFAULT NOW()
);
```

Caller пишет event при каждом show / override / resolve. Это **критично** для будущих legal claims «бот не предупредил подростка».

## 9. Implementation Contract — что должен делать Caller

`calculate_user_targets` возвращает `calculations.<trigger>_warning`. Caller (Python handler in `handlers/`) обязан:

1. **Прочитать все `*_warning` поля** в JSON ответе.
2. **Для каждого != NULL warning:**
   - Проверить `user_overrides`: если active → skip UI (но **всё равно log в guard_audit_log** для audit trail).
   - Проверить `users.shown_guards`: если первый раз → show modal full → update shown_guards.
   - В Profile screen / day summary → show banner.
3. **При render Profile «Мой план»:**
   - Если `effective_goal_type != original_goal_type` → show tooltip «Цель: <effective> (исходно <original>)».
   - Banner color: red для hard, yellow для soft, blue для informational.
4. **При detected auto-reset** (например, юзеру стукнуло 18) → отправить one-shot Telegram message «защита снята» + clear из `users.shown_guards`.

## 10. Reusability — будущие applications

Этот pattern применяется КО ВСЕМ следующим guards (severity по 5-tier matrix из §3):

| Guard | Trigger | Severity | Когда implement |
|---|---|---|---|
| Age guard (underage lose) | `<18 + lose` | **hard block** | ✅ mig 234 |
| Age disclaimer | `<18 + gain/maintain` | **informational** | ✅ mig 234 |
| Elderly disclaimer | `>75` | **informational** | ✅ mig 234 |
| Pregnancy / lactation | `is_pregnant=TRUE` | **hard block** | P0.6 |
| BMI extreme low | `BMI<14` | **hard block** | P0.4 (объединено с P0.3 в одной mig) |
| Underweight lose | `BMI<18.5 + lose` | **hard regulated** | P0.4 |
| BMI extreme high + fast | `BMI>60 + fast` | **hard regulated** | P0.4 |
| BMI extreme high (general) | `BMI>60` | **informational** | P0.4 |
| Min kcal floor | `target < BMR` или `< 1200ж/1500м` | **soft override** | P0.3 (объединено с P0.4) |
| RED-S risk | `EA < 30 kcal/kg LBM` | **soft override** | P2.5 |
| Diet break | `56+ days deficit` | **soft override** | P2.6 |
| Athlete formula no-op | `phenotype='athlete'` | **informational** | P1 (athlete telemetry) |
| Formula switch <18 | Internal Schofield/Molnar | **silent accuracy** | P1.5 (mig 236+) |
| Formula switch >75 | Internal Lührmann | **silent accuracy** | P1.5 |
| ABW для obese | Internal Adjusted Body Weight | **silent accuracy** | P1 |
| Katch-McArdle при LBM | Internal switch | **silent accuracy** | P2.3 |

**Когда любой агент будет писать новый guard — он сверяется с этим pattern**, не пишет UX с нуля.

## 11. Architecture Beyond SQL — что должен сделать команда после mig

Каждый guard — это **не только миграция**. После SQL apply нужно:

1. **Translation keys** в `ui_translations` — copywriter agent (Sassy Sage tone × 13 languages × 5 keys = 65 строк per warning).
2. **Python handler updates** — все callers `calculate_user_targets` (Profile screen, day_summary, cron reminders) парсят `*_warning` поля и рендерят banner.
3. **Screen meta updates** — `ui_screens.meta.show_guard_banner` (bool) для headless rendering.
4. **`user_overrides` schema** (если хоть один guard допускает opt-out — таблица создаётся раз).
5. **`guard_audit_log` schema** (раз создаётся, потом дописывают callers).
6. **Onboarding hooks** — для guards, которые могут triggered at registration (age, BMI, pregnancy) — отдельный screen в onboarding flow.
7. **Retrofit cron** — если guard вводится для existing юзеров и они могут попасть под условие → see [[concepts/user-data-collection-pattern]] для throttling.
8. **Auto-reset cron** (daily) — проверяет users где условие resolved → clear shown_guards + send «unfreeze» message.
9. **Live-test scenario** — добавить guard-trigger sentinel в `tests/live/` чтобы Telethon-краулер проверял UX (banner показывается, modal открывается, opt-out работает).

**Без этих 9 пунктов мiграция — мёртвый код.** Калькулятор может быть идеальным, но юзер про guard не узнает, claims «no medical disclaimer» легитимны, retention падает.

## 12. mig 234 — конкретный плановый rollout

После apply mig 234 (текущая сессия) — **6 параллельных задач** для полной integration:

1. **Copywriter agent** (spawn): 5 keys × 13 langs × 3 warnings = **195 строк** в `ui_translations`. Brief: Sassy Sage tone, Telegram SRE constraints, anti-shame red lines, medical disclaimer pattern. Время: 1 сессия.
2. **Profile screen Python handler** — парсить `age_warning` → render yellow strip + tooltip над `effective_goal_type`. Время: 0.5 сессии.
3. **`user_shown_guards` migration** (mig N+1) — добавить JSONB поле на `users`. Время: 0.2 сессии.
4. **First-trigger modal handler** — Python обработчик нового callback'а `show_age_warning_modal`. Время: 0.3 сессии.
5. **Onboarding hook** — если юзер вводит birth_date <18 → перед registration confirmation показать info screen. Время: 0.5 сессии (требует onboarding-flow знаний).
6. **Auto-reset cron** — daily check users где `birth_date + 18 years = today` → send unfreeze message + clear shown_guards. Время: 0.3 сессии.

**Параллелизуемые задачи 1, 2, 6 (разный код).** 3, 4, 5 — последовательно.

Полный list — в `claude-memory-compiler/handover/2026-05-17_mig234_post_apply_tasks.md` (будет создан после mig 234 merge).

## 13. Anti-Patterns — что НЕ делать

❌ **Silent override без UI.** Подменили goal, юзер не видит — претензия гарантирована.

❌ **Hard block без medical override.** «У вас BMI 16, мы заблокировали приложение» = юзер удаляет аккаунт. Только pregnancy и BMI<14 заслуживают hard block.

❌ **Один banner на всех языках/тонах.** Robotic «MEDICAL DISCLAIMER: …» = не Sassy Sage, не работает.

❌ **Modal каждый раз.** Modal один раз (или раз в N месяцев). Banner — persistent.

❌ **Bypass через RPC.** Если cron / internal job вызывает `calculate_user_targets` напрямую — `*_warning` должен прокидываться в логи / dashboards. Иначе мы не знаем, скольких юзеров реально защитили.

❌ **«Через 1 месяц напишем UI».** Apply миграции без UI — opaque defect. Эффект для юзера = 0, эффект для legal = 0. Wasted migration.

❌ **Hardcoded texts вместо ui_translations.** Все banner-тексты обязательно через ключи + 13 языков. Английский fallback для подростка из PT/AR/HI = плохая ситуация.

## Связано

- [[concepts/calc-user-targets-roadmap]] — какие guards будут добавлены
- [[concepts/user-data-collection-pattern]] — связанный pattern для retrofit полей (pregnancy, waist, diet_type)
- [[concepts/personalized-macro-split]] — формула, в которой триггерятся guards
- [[concepts/sassy-sage-multilingual-glossary]] — tone для guard messaging
- [[concepts/ui-translations-bulk-update-recipe]] — pipeline writer→critic для 13 языков
- [[concepts/headless-architecture]] — как UI рендерит banner'ы через `ui_screens.meta`
- [[concepts/migration-collision-guard]] — почему один atomic guard = одна миграция
