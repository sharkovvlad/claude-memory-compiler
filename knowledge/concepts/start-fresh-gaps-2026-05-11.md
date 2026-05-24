---
title: "Start Fresh Flow — Identified Gaps (2026-05-11)"
aliases: [reset-to-onboarding-gaps, cmd-start-fresh-gaps, finalize-onboarding-already-completed]
tags: [tech-debt, onboarding, soft-delete, ux, sticker-architecture]
sources:
  - "live test 786301802 после mig 192 + mig 201 (2026-05-11 22:24 Madrid)"
created: 2026-05-11
status: TODO — awaits product decision
---

# Start Fresh Flow — выявленные расхождения и TODO

> Зафиксировано после live-test'а 786301802. Цель — не потерять контекст к моменту реализации Phase 6 / расширения `reset_to_onboarding`.

## TL;DR

Текущая RPC `reset_to_onboarding` (mig 079, для callback `cmd_start_fresh`) **не приводит юзера к UX-эквиваленту нового аккаунта**. 4 расхождения:

1. **`status='registration_step_1'`** вместо `'new'` — пропускает welcome screen + welcome-стикер.
2. **`level=1`** (NLM-decision апреля) **конфликтует** с idempotency guard в `finalize_onboarding_location` — finalize отвечает `already_completed`, complete_onboarding не вызывается → нет success-стикера + поздравительного сообщения.
3. **Неполный набор сбрасываемых полей** — `body_type`, `phone*`, `phenotype_answers`, `last_action_signature`, location-funnel-*, freeze-* и др. остаются от предыдущей инкарнации.
4. **Food logs остаются привязаны к telegram_id** — юзер «новой» инкарнации видит свою старую еду. Best-practice (Headspace, Strava): анонимизация (`user_id = NULL`), либо удаление. Сохранение для AI-обучения — да, но **детачнутыми**.

## Industry baseline (research 2026-05-11)

Все 6 проверенных аналогов (Duolingo, MyFitnessPal, Strava, Yazio, Lose It!, Headspace) делают **бинарно**:
- внутри grace window → полный restore «как было»;
- за окном → 100% новый юзер с welcome+бонусами+touring+стикерами заново.

Нет «частичного восстановления». NOMS позиционирование («Start fresh» при soft-delete) должно соответствовать паттерну A.

## Gap 1 — `status='registration_step_1'` пропускает welcome

**Текущее поведение (`reset_to_onboarding`):**
```sql
UPDATE users SET status='registration_step_1', ...
```
Это `edit_gender` экран — сразу выбор пола, **без** `onboarding_welcome` screen и welcome-стикера.

**Ожидаемое UX:** новый юзер при `/start` идёт через `onboarding_welcome` (приветствие + стикер `onboarding_welcome` Channel A) → `cmd_select_start` → edit_gender. После reset должно быть то же.

**Fix:** ставить `status='new'` (как у любого нового юзера).

## Gap 2 — `level=1` конфликт с `finalize_onboarding_location.already_completed`

**Точная цепочка отказа (исходная):**
1. `reset_to_onboarding` → `level=1` (NLM-decision: «не NULL, а стартовое значение»).
2. Юзер проходит онбординг → `onboarding:country` → шлёт геолокацию.
3. `02.1_Location` → `finalize_onboarding_location`:
   ```sql
   IF v_level IS NOT NULL AND v_level >= 1 THEN
       RETURN ('reason'='already_completed');
   END IF;
   ```
4. `complete_onboarding` **НЕ** вызывается → status НЕ→ `'registered'`, нет grant XP/coins/mana, нет render `onboarding_success` → **нет success-стикера + поздравительного сообщения**.

### Эволюция guard'а (mig 203 → mig 204)

**Mig 203 (Опция A — отвергнута live-тестом 2026-05-12):**
Изменили guard на `IF status='registered' AND level>=1`. Предположение — start_fresh-юзер приходит в finalize со status='onboarding:country'. **Неверно** — реальный n8n 02.1_Location flow:

1. `Save: Single Zone` (или `Save: Timezone`) — вызывает `set_user_location(..., return_status='registered')`.
2. `set_user_location` делает прямой `UPDATE users SET status = COALESCE(p_new_status, status)` → **status='registered' до finalize**.
3. `Postgres: Finalize Onboarding` → `finalize_onboarding_location()` → читает status='registered', level=1 → mig 203 guard срабатывает → `already_completed` → complete_onboarding не вызван.
4. n8n IF "Onboarding Just Completed" видит `success=false` → false-branch → юзер видит только «✅ ¡Guardado!» + 👌 без success-стикера + поздравительного сообщения.

Подтверждено для test user 786301802 в БД (2026-05-12 01:03):
- `status='registered', level=1, xp=0, nomscoins=0`
- `stickers_shown` без `onboarding_success`
- `xp_events` для tid=786301802 после 2026-05-11 — **пусто**, нет grant_xp.

**Smoke test 11.05 был неполный** — не симулировал шаг `set_user_location → status='registered'` перед finalize. Lesson: всегда моделируй ПОЛНЫЙ external flow (n8n + RPC chain), не только последний RPC.

### Gap 5 — n8n PUT v12 (12.05): `Postgres column wrap` в IF-ноде (real root cause)

Mig 204 (новый guard `xp>0 OR nomscoins>0`) дал **частичное** улучшение — `complete_onboarding` теперь выполняется (xp/coins/mana granted, level up). НО юзер всё ещё видит «✅ Сохранено + 👌» вместо onboarding_success стикера. Live test 12.05 12:48 → БД `xp=50, level=2, nomscoins=60`, но `stickers_shown` без `onboarding_success`.

**Real root cause:** n8n `Postgres: Finalize Onboarding` node (`typeVersion 2.4`) выполняет `SELECT * FROM finalize_onboarding_location(...)` и возвращает **column-wrapped output**: `[{finalize_onboarding_location: {success: true, xp_gained: 50, ...}}]`. То есть Postgres-node не «разворачивает» jsonb в plain object — она оборачивает в имя колонки (= имя функции, потому что без `AS alias`).

Следом IF-нода `IF: Onboarding Just Completed` (`typeVersion 2.2`, operator `boolean true`) проверяет `{{ $json.success }}` → **`undefined === true` → false** → false-branch (`Telegram: Notify TZ Saved → Restore Main KB`) → юзер видит «Сохранено» вместо onboarding_success.

Это **существовало с самого создания workflow** — branch[0] true (Render onboarding_success → Send onboarding_success → Render onboarding_success_menu → Send onboarding_success_menu) НИКОГДА не активировалась для онбординг-юзеров. Mig 179/203 guard'ы скрывали это (юзер падал в `already_completed` ещё раньше), но после mig 204 баг проявился.

**n8n PUT v12 (12.05.2026 10:10 UTC):**
- `IF: Onboarding Just Completed` leftValue: `{{ $json.success }}` → `{{ $json.finalize_onboarding_location.success }}`.
- `02_Continue Onboarding` (dead path, никогда не достигается через legacy `If` ноды) workflowId: `JRaKFPb5sOFL3xlc` (удалённый workflow) → `0xJXA5M4wQUSiGXT` (04_Menu_v3, active, safe pointer). Это обходит n8n PUT validation «referenced workflow must be published». Cleanup всего dead path — задача Phase 6.

Дополнительные dead-code находки (для Phase 6 cleanup):
- `If` (без суффикса) — legacy condition `return_status==='registration_step_1'`, никогда true для Phase 4 юзеров. true-branch → 02_Continue Onboarding (dead). false-branch отсутствует.
- `If Auto Continue` — то же самое legacy condition. Та же dead chain.
- `Prepare for 02 Continue`, `02_Continue Onboarding` — orphaned dead path, может быть удалён.

**Watchlist для будущих агентов:** при работе с n8n `n8n-nodes-base.postgres typeVersion 2.4` который вызывает PL/pgSQL функцию возвращающую `jsonb`, output **обернут** в `{<func_name>: <jsonb>}`. IF/Set/Code ноды должны читать `$json.<func_name>.<key>`, не `$json.<key>`. Альтернатива — SQL `SELECT public.func(...) AS <alias>` чтобы явно назвать колонку, или `SELECT * FROM jsonb_to_record(...)` чтобы развернуть.

---

**Mig 204 (применён 2026-05-12) — Опция C: discriminator по rewards balance:**

```sql
-- Idempotency guard (mig 204): уже completed онбординг ⟺ получил XP/coins.
IF v_xp > 0 OR v_nomscoins > 0 THEN
    RETURN already_completed;
END IF;
```

Почему работает:
- `reset_to_onboarding` (mig 203) ставит `xp=0, nomscoins=0` — это **invariant marker** «not yet completed».
- Profile v5 edit-юзер имеет `xp >= 50, nomscoins >= 50` (granted при первом complete_onboarding) → guard блокирует.
- `set_user_location` НЕ трогает xp/nomscoins → пере-set status='registered' до finalize'а уже не ломает discriminator.
- Defense in depth: `OR` (не `AND`) — если зеркальный bug zeros только один из двух полей, guard всё равно отрабатывает.

Verify тесты mig 204 (SAVEPOINT/ROLLBACK):
- ✅ Real flow (reset → set_user_location('registered') → finalize) → complete_onboarding выполняется (xp_gained=50, coins_granted=50, leveled_up=True, mana_gift=5).
- ✅ Profile v5 edit (registered, xp=500, nomscoins=200) → блок (already_completed).
- ✅ Retroactive fix: юзер в limbo state (registered, xp=0, nomscoins=0) — finalize выдаёт rewards (важно для 786301802 после mig 203 limbo).
- ✅ `user_not_found` regression unchanged.

### Альтернативы, отвергнутые при выборе mig 204

| Опция | Описание | Почему отвергнута |
|---|---|---|
| Изменить `reset_to_onboarding` → `level=NULL` | Откатить NLM-decision апреля | Downstream-зависимости от level>=1 (Tamagotchi UI, leaderboards). Большой scope. |
| Поменять `set_user_location` чтобы не переключал status='registered' при онбординге | Перенести status transition в complete_onboarding | Меняет contract универсальной функции. Profile v5 edit-flow также использует — риск регрессии. |
| Использовать `previous_status` | Detection через `previous_status IN ('onboarding:country', 'onboarding:timezone')` | `previous_status` сейчас не обновляется автоматически — у test user `previous_status=NULL`. Требует synchronized update во всех call paths. |
| Boolean флаг `onboarding_completed` | Отдельная колонка | YAGNI — `xp=0 AND nomscoins=0` уже работает как invariant. |

## Gap 3 — Неполный набор сбрасываемых полей

Поля которых **нет** в текущем `reset_to_onboarding`, но юзер ожидает обнуления при `cmd_start_fresh`:

- `body_type` — связан с phenotype, должен идти вместе.
- `phenotype_answers` (jsonb), `phenotype_q1/q2/q3/q4` (generated, авто).
- `phone, phone_confirmed_at, phone_source` — phone сбрасывается.
- `last_action_signature` (default `'{}'`), `last_action_ms` (debounce state).
- `last_bot_message_type`, `last_text_indicator_date`, `last_indicator_index` (UI/indicator state).
- `country_code_declared, country_code_billing, country_code_override, timezone_declared, location_set_at` (location funnel state).
- `pending_freeze_notification_at` (mig 191 ghost notification).
- `editing_meal_id` (food edit ghost).
- `xp_logs_today, xp_corrections_today, xp_today_date, last_log_date, last_streak_kept_date` (daily counters).
- `stickers_shown = '{}'::jsonb` (mig 201) — **обязательно** иначе welcome/success стикеры не покажутся повторно.

Поля которые **сохраняются** (не сбрасывать):
- `telegram_id, first_name, username, created_at`, `is_bot` (identity).
- `email` (auth handle).
- `subscription_status` (платная инфо).
- `referrer_id`, `referral_count`, `paid_referral_count` (history-вклад в чужие аккаунты).
- **`phone`, `phone_confirmed_at`, `phone_source`** (решение 2026-05-11): сохраняем, связано с реферальным/payout flow. Пересмотр — Опция 2 (см. ниже).
- `food_logs` (отдельная таблица, см. Gap 4).
- `xp_events`, `payment_transactions`, `referral_escrow` (история).
- `ambassador_*`, `is_trainer`, `trainer_commission_rate` — **обсудить** (роли могут зависеть от профиля; скорее всего сбросить, но нужен product-decision).

## Gap 4 + Опция 2 (TODO техдолг) — Food logs + phone orphan при start_fresh

### 4.1 Food logs

**Текущее:** `food_logs.user_id` остаётся привязан к `telegram_id` после reset. Юзер новой инкарнации видит еду старой.

**Best-practice (Headspace anonymization-and-retain):**
- При `cmd_start_fresh`: `UPDATE food_logs SET user_id = NULL WHERE user_id = X` (или специальный `anonymized_user_id`).
- Логи остаются в БД для AI-обучения, но без PII-привязки.
- GDPR-compliant (right to erasure по PII, не по агрегатам).

### 4.2 Phone (решение 2026-05-11)

**Текущее:** `users.phone, phone_confirmed_at, phone_source` сохраняются после reset.

**Контекст:** phone связан с **реферальным** и **payout** flow (когда юзер получал payout как ambassador/trainer). Сохранение даёт continuity для тех функций.

**Открытый вопрос:** если юзер чистый «start fresh» (хочет всё с нуля), это может быть UX-сюрприз — «я же сбросил всё, почему phone сохранился?». Связано с GDPR (право удалить персональные данные).

**Решение откладывается.** Большая UX-задача:
- Нельзя ломать insights / streak history визуально для юзера.
- Phone в payout-цепочке может быть критичен для bookkeeping.
- Нужен отдельный sticker pattern «вы вернулись» или явный confirm.

Требует отдельной сессии и тестов.

**Связанные таблицы для аудита:** `food_logs`, `meal_corrections`, `xp_events` (события связанные с этими логами), `streak_events`, `payout_requests` (если phone в payout flow).

## Конфликты которых **нет** (проверено)

- ✅ Mig 201 (stickers_shown semantics) — корректно сбрасывается через `stickers_shown='{}'::jsonb`. Welcome/success стикеры покажутся повторно.
- ✅ Mig 198 (Channel A render_screen Step 8b) — read+mark атомарно. После reset render_screen увидит «не показан» и эмитит `sticker_category`.
- ✅ Mig 192 (process_onboarding_input 10c — render_screen напрямую) — не зависит от reset-flow.
- ✅ `subscription_status` блокер на `delete_user_account` (KB soft-delete-account.md) — Phase 3 защита, не пересекается с reset.

## Скрипт для ручного reset 786301802 (тестовый, не миграция)

Текущая версия согласована (см. сообщение пользователя 2026-05-11). Замечания применены: `status='new'`, `level=1` (с расчётом на fix Опция A в finalize), `stickers_shown='{}'`, `phenotype='default'`, полный набор полей.

**Упущения которые стоит добавить в test SQL:**
```sql
body_type = NULL,
phone = NULL,
phone_confirmed_at = NULL,
phone_source = NULL,
```

`xp_events` / `food_logs` для тестового юзера НЕ трогать (нужны для проверки Gap 4 при future implementation).

## План реализации (когда дойдут руки)

1. **Mig 20X** — Update `reset_to_onboarding` RPC: расширить набор полей + `status='new'`.
2. **Mig 20Y** — Update `finalize_onboarding_location` guard (Опция A: `status='registered' AND level>=1`).
3. **Mig 20Z (отдельно, TODO)** — food_logs detach + cascade tables. Требует отдельной сессии.
4. **Tests:** `tests/sql/test_reset_to_onboarding.py` — сценарии: (a) post-reset render_screen → onboarding_welcome со стикером; (b) пройти онбординг до конца → onboarding_success со стикером; (c) registered юзер edit_country → finalize → already_completed (regression guard).

## Related Concepts

- [[concepts/start-fresh-flow]] — current implementation
- [[concepts/soft-delete-account]] — Phase 3 gate, deletion lifecycle
- [[concepts/sticker-architecture-adr]] — Channel A + one-time semantics (mig 201)
- [[concepts/phase4-onboarding-migration]] — FSM в SQL, status diagram
