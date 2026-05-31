# Handover — «Еда во время онбординга → mana/trial-aware» (P0, owner-approved)

**From:** агент angry-liskov (2026-05-31), после mig 393–396 (cycle back, checkmarks, Variant 1).
**To:** Следующий агент (фокус-сессия).
**Status:** НЕ начат. Owner ответил на все 4 UX-развилки (ниже). Это полноценная фича (новая модель данных + i18n × 13 + referral) — выделена в отдельную сессию намеренно (не хвост длинной).

## Цель
Новый юзер должен попробовать распознавание еды с первой секунды, даже не завершив регистрацию — «wow с первой секунды». Сейчас текст/фото во время онбординга УЖЕ уходят в AI (router section 11 → `ai`), т.е. еда обрабатывается. Не хватает: (1) trial-гейта для незавершивших регистрацию, (2) мягкого редиректа когда попытки исчерпаны.

## Решения owner'а (2026-05-31, зафиксированы)
1. **Гейт — в router catch-all** (не в food_log handler). `UserCtx` уже несёт `mana_current`/`mana_max` (dispatcher/context.py) → router может решать без DB-touch.
2. **Фото == текст** — одинаковое поведение (mana — единый лимитер).
3. **mana/trial=0 → тост + ре-рендер текущего онбординг-экрана** (НЕ отдельный экран-заглушка). Тост вроде «Доделай регистрацию — пробные попытки кончились». Нужен current onboarding screen (по status → screen map, он уже есть в process_onboarding_input `/start` intercept CASE, строки ~129-147).
4. **Отдельный trial-лимит** (НЕ обычная mana=2/день). Явное число пробных попыток для незавершивших регистрацию + **referral-бонус маны продлевает окно**.

## Что построить
### Модель данных (новое)
- `app_constants`: `onboarding_food_trial_limit` (напр. 3) — сколько распознаваний до завершения регистрации. (+ возможно `onboarding_food_trial_referral_bonus`.)
- Счётчик использованных пробных попыток. Варианты: новая колонка `users.onboarding_food_trials_used` INT DEFAULT 0, ИЛИ COUNT по `food_logs` где юзер ещё `status LIKE 'registration_step_%'`. Колонка проще для гейта (router читает из ctx). Тогда добавить поле в `UserCtx` + `get_user_context` SELECT.
- Referral-бонус: при наличии referral'а лимит выше (или окно шире). Свериться с существующей referral-escrow логикой (cron_unlock_referral_escrow).

### Гейт (router)
- В секциях, где `status LIKE 'registration_step_%'` (или `new`) И контент = еда (text section 11 / photo — найти секцию фото выше в route()), решать:
  - `trials_used < limit` (или mana>0 по выбранной модели) → `target='ai'` (текущее поведение).
  - исчерпано → НЕ в ai. Нужно вернуть сигнал «показать тост + текущий онбординг-экран». Router DB-free и не рендерит — вероятно новый `target='onboarding'` + `reason='onboarding_food_blocked'` + флаг, а webhook_server/handler покажет тост + ре-рендер. ⚠️ Продумать: проще может оказаться гейт в handler (ai entry) — но owner выбрал router; согласовать механику тоста.
- ⚠️ **Инкремент счётчика** — на УСПЕШНОМ распознавании (в food_log/ai handler после save), не в router.

### i18n
- `errors.onboarding_food_blocked` (или `messages.*`) × 13 langs, Sage-тон, anti-shame. Через copywriter-playbook. Лежит в `migrations/NNN_*.sql` (не tools/).

### Тесты (FULL PATH route())
- Незаверш. юзер, trials<limit, текст еды → ai. Фото еды → ai.
- trials=limit → blocked path (тост + текущий экран), НЕ ai.
- Завершивший регистрацию (status='registered') — обычная mana-логика, не trial (регрессия).
- Referral-бонус расширяет лимит.

## Gotchas / факты (проверено этим агентом)
- `UserCtx` поля: `mana_current`, `mana_max`, `mana_recharges_today` есть; trial-счётчика НЕТ (добавить).
- router section 11 (`dispatcher/router.py:1060`) = catch-all free-text → `ai/text_food`. Фото-секцию найти выше (junk_content section 4 ловит sticker; photo food — отдельно).
- `users.status` FK → `workflow_states.state_code` (новые статусы регистрировать там — урок mig 393).
- Тестировать через `route()` полный путь, не прямой RPC (уроки #248/#390/#393).
- Деплой только из main; RPC/данные применять к LIVE через psycopg2; p95 после RPC changes.

## Связанное
- MEMORY current state (mig HEAD 396). daily/2026-05-31.md.
- KB: fsm-state-whitelist-discipline, copywriter-playbook, one-menu-ux.
