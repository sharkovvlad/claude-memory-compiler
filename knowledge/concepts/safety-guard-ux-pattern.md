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

## 3. Severity Levels — какой UX подходит для какого guard'а

| Severity | Что значит | UX-pattern | Opt-out |
|---|---|---|---|
| **Hard block** | Жизненная угроза | Force override + non-dismissible banner + medical disclaimer | Нет |
| **Soft override** | Долгосрочный риск, юзер может не понимать | Force override + dismissible banner + объяснение | Только с medical confirmation |
| **Informational** | Точность снижена, но не опасно | Banner с информацией, цель не меняется | Опционально |

| Trigger | Severity | Что меняется | Opt-out возможен? |
|---|---|---|---|
| `<18 + lose` | Soft override | goal_type → maintain | Нет (РПП-риск) |
| `<18 + gain/maintain` | Informational | Только banner | Не нужен (нет override) |
| `>75` | Informational | Только banner | Не нужен |
| `pregnancy=TRUE + lose` (будущее) | Hard block | Force maintain + добавить +300-500 kcal | Нет (медицинский lock) |
| `BMI<14 + любой goal` (будущее) | Hard block | Force maintain | Нет |
| `BMI<18.5 + lose` (будущее) | Soft override | goal_type → maintain | Да (если врач одобрил) |
| `EA < 30 kcal/kg LBM` (будущее) | Soft override | Auto-raise calories | Да |
| `diet break > 56 days` (будущее) | Soft override | 7-14 дней forced maintain | Да (если осознанно нарушает) |

## 4. Decision Tree для нового guard'а

Перед spawn'ом новой миграции с guard ответь на 7 вопросов:

1. **Что триггерит?** (e.g., age<18, BMI<14, is_pregnant=TRUE, ea<30)
2. **Severity?** (hard/soft/informational)
3. **Что меняем в формуле?** (force goal_type, raise calories, clamp speed)
4. **JSON-поле telemetry?** (`<trigger>_warning`, value=<enum string>)
5. **Auto-reset condition?** (юзер стукнул 18, BMI стало >18.5, …)
6. **Opt-out flow?** (если да — поле в `user_overrides`, audit log)
7. **Texts на 13 языках?** (5 translation keys × 13 langs = 65 строк → copywriter agent)

## 5. Translation Keys — единый naming convention

Каждый guard имеет **5 translation keys** (× 13 языков = 65 строк):

```
warning.<trigger_family>.<severity>.banner_title      # 20-40 chars
warning.<trigger_family>.<severity>.banner_body       # 1-2 sentences, ≤140 chars
warning.<trigger_family>.<severity>.modal_full        # 5-10 lines детального explanation + sources
warning.<trigger_family>.<severity>.opt_out_confirm   # «Понимаю риск, мой врач одобряет» (только для soft)
warning.<trigger_family>.<severity>.auto_resolved     # «У тебя сменилось X — защита снята»
```

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

## 6. Storage Schema

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

## 7. Implementation Contract — что должен делать Caller

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

## 8. Reusability — будущие applications

Этот pattern применяется КО ВСЕМ следующим guards:

| Guard | Trigger | Severity | Когда implement |
|---|---|---|---|
| Age guards | <18 / >75 | Soft / Inform | ✅ mig 234 (готова) |
| Underweight lose | BMI<18.5 + lose | Soft override | P0.5 (next session) |
| BMI extremes | BMI<14 / BMI>60 | Hard / Soft | P0.4 |
| Pregnancy/lactation | is_pregnant=TRUE | Hard block | P0.6 |
| RED-S risk | EA<30 kcal/kg LBM | Soft override | P2.5 |
| Diet break | 56+ days deficit | Soft override | P2.6 |
| Min kcal floor | target < BMR | Soft override | P0.3 |

**Когда любой агент будет писать новый guard — он сверяется с этим pattern**, не пишет UX с нуля.

## 9. Architecture Beyond SQL — что должен сделать команда после mig

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

## 10. mig 234 — конкретный плановый rollout

После apply mig 234 (текущая сессия) — **6 параллельных задач** для полной integration:

1. **Copywriter agent** (spawn): 5 keys × 13 langs × 3 warnings = **195 строк** в `ui_translations`. Brief: Sassy Sage tone, Telegram SRE constraints, anti-shame red lines, medical disclaimer pattern. Время: 1 сессия.
2. **Profile screen Python handler** — парсить `age_warning` → render yellow strip + tooltip над `effective_goal_type`. Время: 0.5 сессии.
3. **`user_shown_guards` migration** (mig N+1) — добавить JSONB поле на `users`. Время: 0.2 сессии.
4. **First-trigger modal handler** — Python обработчик нового callback'а `show_age_warning_modal`. Время: 0.3 сессии.
5. **Onboarding hook** — если юзер вводит birth_date <18 → перед registration confirmation показать info screen. Время: 0.5 сессии (требует onboarding-flow знаний).
6. **Auto-reset cron** — daily check users где `birth_date + 18 years = today` → send unfreeze message + clear shown_guards. Время: 0.3 сессии.

**Параллелизуемые задачи 1, 2, 6 (разный код).** 3, 4, 5 — последовательно.

Полный list — в `claude-memory-compiler/handover/2026-05-17_mig234_post_apply_tasks.md` (будет создан после mig 234 merge).

## 11. Anti-Patterns — что НЕ делать

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
