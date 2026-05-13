---
title: UAT 13.05 — серия edit-meal headless fixes (5 PRов + n8n hotfix)
date: 2026-05-13
author: claude/busy-volhard-39a4cf
status: CLOSED — все 5 PR'ов merged, UAT тимлида прошёл
audience: следующий агент по edit-meal flow / generic next session
---

# TL;DR

Сегодня закрыли цикл UAT 13.05 — 5 merged PR'ов плюс n8n hotfix через PUT (без коммита):

| PR | Mig | Scope |
|---|---|---|
| #61 | 209 | «Исправить» (`cmd_edit_last`) + «Поделиться» (`share_invite_link`) headless'ed через `save_via_callback` + `meta.url_template` |
| #62 | 211 | Virtual Screen `_global_floating_actions` + PUI lookup fallback chain (для inline-карточек 03_AI_Engine поверх произвольного screen) + `delete_last_meal_with_revert` RPC |
| #63 | 213 | JSONB-array Sassy variants в Python `_resolve_text` (random.choice) + `_DOUBLE_BRACE_ICON_RE` нормализация в основном render path + screen `delete_confirmed` (toast «🗑 Удалено») |
| #64 | 214 | Cosmetic emoji (double-icon cmd_cancel_edit, wrong icon delete_confirmed back) + **callback_message_id type-mismatch** (PUI `->>` text-cast vs Python int-only) — universal fix в `_coerce_message_id` принимает numeric strings |
| #65 | 215 | **Hotfix data-loss** — `set_editing_last_meal` использовал `SELECT id` вместо `SELECT meal_id` (моя ошибка в mig 209). Cascade: editing_meal_id=row PK → 03_AI_Engine `get_meal_by_id` искал по meal_id → meal_not_found → silent fail / ложный INSERT. Fix verbatim CREATE OR REPLACE: одна строка |

**n8n hotfix:** 04_Menu Command Classifier JS syntax error (`else else if` на lines 170-173). 100% fail rate с 11.05 19:18 UTC (18/18 errors в execution_entity). Single-node PUT через scp+ssh recipe. versionId `3b3ba3c4-…`.

# Что изменилось (концептуально)

## 1. Virtual screen pattern (`_<name>` namespace)

Новый headless паттерн для lookup-only screens. Inline-кнопки из standalone-источников (карточка лога еды от 03_AI_Engine) стоят поверх произвольного `current_screen` юзера → PUI стандартный lookup `WHERE screen_id=current_screen` промазывает.

Решение — INSERT virtual screen `_global_floating_actions` (render_strategy='noop', screen_id с underscore prefix) + расширение PUI lookup на **fallback chain**:
```sql
-- В PUI (mig 211 patch):
SELECT b.* INTO v_button FROM ui_screen_buttons b
 WHERE b.screen_id = v_current_screen
   AND matches_callback_template(...);

IF NOT FOUND THEN
    SELECT b.* INTO v_button FROM ui_screen_buttons b
     WHERE b.screen_id = '_global_floating_actions'
       AND matches_callback_template(...);
END IF;
```

ALTER CONSTRAINT `ui_screens_screen_id_check` regex `^[a-z]...` → `^[a-z_]...` чтобы поддержать namespace.

Полное описание — [[concepts/headless-architecture]] (extended 13.05).

## 2. `meta.url_template` — динамические URL-кнопки

SQL хранит template name (`share_invite`), Python собирает URL динамически через `urllib.parse.quote`. Зачем не SQL: percent-encoding кириллицы + спецсимволов в БД-side небезопасно.

Реализация — `services/template_engine._URL_TEMPLATE_RESOLVERS` dict. Добавление нового template — новая функция в dict, без правок render_screen / PUI.

`share_invite` собирает `https://t.me/share/url?url=…&text=…` с deep-link `https://t.me/{bot_username}?start=ref_{telegram_id}`. Описание — [[concepts/headless-architecture]] секция «meta.url_template».

## 3. JSONB-array Sassy variants в Python

Mig 169 era ввела JSONB-array variants в `ui_translations` (Sassy Sage). Random pick — обязанность **Python layer'а адаптера**, не SQL (NLM Q подтвердил). Реализован в `_coerce_translation_value(value, text_key)` helper в template_engine.py.

Также фиксили **double-brace gotcha** — `_resolve_text` ранее не нормализовал `{{icon_X}}` → `{icon_X}` (только `resolve_translation_text` это делал). После mig 213 нормализация в обоих entry-points через module-level `_DOUBLE_BRACE_ICON_RE`.

Описание — [[concepts/sassy-sage-dialog-variants]] (extended 13.05).

## 4. JSON boundary type-erosion bug (`callback_message_id`)

**Системный antipattern** который скрывался долго:

PUI инжектит callback_message_id через `p_cb_context->>'…'` — оператор `->>` возвращает **TEXT**. Int 4775 из Python → str `"4775"` в telegram_ui JSON. Python `_coerce_message_id` принимал только int → None → template_engine fallback на `delete_and_send_new` → карточка лога **удалялась + send_new** вместо seamless editMessageText.

`handlers/onboarding_v3.py` и `handlers/location.py` обходили это **пост-фактум int-инжектом** перед render_envelope. `menu_v3.py` — нет. Universal fix: `_coerce_message_id` принимает `str.isdigit()` numeric strings, `bool` исключаем явно.

Описание — [[concepts/python-vs-n8n-template-grammar]] (extended 13.05).

## 5. food_logs.id vs meal_id — critical SQL schema lesson

`food_logs.id` (PK строки) ≠ `food_logs.meal_id` (group UUID для multi-item meals — пицца+кола = 2 rows, один meal_id).

`get_meal_by_id(uuid)` ищет `WHERE meal_id = $1`. RPC которые работают с meal references должны брать **meal_id**, не id.

Моя ошибка в mig 209 (`SELECT id INTO v_meal_id`) симптом скрывался: RPC сама не падала, но downstream `get_meal_by_id` возвращал meal_not_found → AI engine без контекста → silent fail для коротких correction-текстов.

Описание — [[concepts/supabase-db-patterns]] (extended 13.05 — раздел «food_logs schema semantic distinction»).

# Open tech debt (для следующего агента)

## Priority 1: cmd_cancel_edit UX — toast вместо jump

Сейчас «Нет, всё ок» на edit_food_prompt → `meta.target_screen='stats_main'` (mig 209) → юзер перепрыгивает в Мой день. Лучше — **toast 👌** БЕЗ перехода (юзер остаётся на карточке с очищенным status='registered').

Возможные реализации:
- (A) Новый screen `cancel_edit_toast` с render_strategy='noop' + carrier_text_key='edit_food.cancelled' (см. [[concepts/noop-render-strategy-pattern]]).
- (B) Handler-side post-RPC inject toast OutboundItem (как `_maybe_build_save_toast` в menu_v3.py для Profile v5 text input).
- (C) `success_reaction='👌'` injection из RPC (mig 098 паттерн).

Тимлид одобрил отложить — не блокер, но улучшение UX.

## Priority 2: 03_AI_Engine defensive guard

n8n PUT — добавить ноду между `Get Current Meal` и `AI Recalculate`: IF `success=false` (meal_not_found) → reply «Не нашёл этот лог, попробуй ещё раз» + `Clear Editing State` ноду.

**Не блокирующее** — mig 215 устранил root cause (set_editing_last_meal теперь пишет правильный meal_id). Defensive guard защитит от любого будущего scenario где editing_meal_id ломается (restore + recovery edge case, manual DB tinkering, etc).

Recipe для PUT — KB [[concepts/n8n-data-flow-patterns]] секция «Safe PUT» (workflow >50 KB → scp+ssh).

## Priority 3: meals_list screen

`cmd_show_meals` сейчас (mig 211) downgrade'на на `target_screen='stats_main'` — устраняет regression «крутящихся часиков» от legacy n8n void, но даёт **no-op refresh** вместо реального списка съеденного.

Реальная реализация требует:
- INSERT screen `meals_list` (`text_key='meals_list.title'`, `list_rpc='get_meals_today'` — он есть, mig 010 era).
- Pagination (page_size=10? как для locations).
- INSERT 1+ кнопка cmd_back на parent stats_main.
- Возможно — `cmd_edit_meal_<uuid>` per-meal edit (отличная от `cmd_edit_last` semantics — editing **конкретного** meal_id).

Это **новая feature**, не bug fix. Подходит для отдельного спринта.

## Priority 4: Phase 6.4 — decommission n8n 02.1_Location

Когда edit-flow вышел в Python (PR #59 / Phase 6.2), legacy `02.1_Location` остаётся как rollback rope. После 1-2 недель UAT — decommission:
- `app_constants.handler_location_use_python` ключ удалить.
- `dispatcher_python_authoritative_admin_only` ключ удалить (уже flipped 'false', но всё ещё читается в `get_dispatcher_flags()` RPC).
- n8n 02.1_Location DELETE workflow.
- Cleanup в `webhook_server.py:_try_authoritative_path` секция Phase 6.1.

KB [[concepts/phase6-location-migration-plan]] — план + checklist.

# Что НЕ закрыто (out of scope этой сессии — на будущее)

- **`callback_message_id` теряется через `_build_cb_context` для НЕ-inline источников** — теоретически возможно, но UAT 13.05 не воспроизвёл. После PR #64 (universal fix в `_coerce_message_id`) защита есть.
- **Phase 7+ — миграция 03_AI_Engine на Python** — big roadmap item. Текущий 03_AI_Engine работает, не блокер.

# Ключевые KB-обновления (cross-refs для index)

- [[concepts/headless-architecture]] — Virtual Screen + Fallback Lookup pattern (Option B), `meta.url_template` для URL-кнопок.
- [[concepts/supabase-db-patterns]] — food_logs.id vs meal_id semantics.
- [[concepts/sassy-sage-dialog-variants]] — Python `_resolve_text` JSONB-array support (`_coerce_translation_value`).
- [[concepts/python-vs-n8n-template-grammar]] — JSON boundary type erosion (`->>` text-cast bug).
- [[concepts/n8n-data-flow-patterns]] — execution_entity SQLite diagnostic + Command Classifier syntax hotfix recipe.
- [[concepts/specs-vs-reality-ground-truth]] — NLM RAG может быть stale, verify через live psycopg2 + execution_entity + journalctl.

# Финальное состояние

- main HEAD: mig 215 (PR #65 merged).
- Open PRs: 0 (моя серия закрыта).
- Tech debt items зафиксированы выше + в daily/2026-05-13.md Сессия 3.
- Все 5 PR'ов прошли UAT тимлида.

# Учебные lessons этой сессии

1. **Stale-base regression защита работает** — sha256 pinning через snapshot перед apply поймал бы потенциальные race condition'ы с location-агентом. Использовал во всех 5 миграциях, ноль incident'ов.
2. **NLM RAG требует валидации против live.** В этом сессии NLM дал 2 неточных совета (откатить mig 211, использовать 04.2 для cmd_edit_last). Live recon (execution_entity SQLite + journalctl + psycopg2) опроверг оба → тимлид утвердил мой контрверdict. Defensive стратегия — не доверять RAG без live verification.
3. **PR review checkpoint:** grep `editing_meal_id` против `SELECT id INTO` в новых RPC — обязательно. Я бы поймал mig 209 bug сам если бы делал self-review через эту checklist.
