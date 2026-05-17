# Brief: Python handler для age_warning UI rendering

**Дата:** 2026-05-17
**Trigger:** mig 234 (RPC v6) + mig 239 (storage) + mig 240/241 (UI texts) merged на проде. Осталось дописать Python-handler чтобы баннеры реально показывались юзеру.
**Estimated effort:** 0.5-1 сессия.

## Что уже готово в БД (точные имена)

### 1. RPC возвращает 3 новых поля

`public.calculate_user_targets(p_telegram_id BIGINT, p_force_recalc BOOLEAN DEFAULT FALSE) RETURNS JSONB`

В JSONB-ответе под ключом `calculations`:

```json
{
  "calculations": {
    ...,
    "age_warning": "underage_forced_maintain" | "underage_disclaimer" | "elderly_less_accurate" | null,
    "original_goal_type": "lose" | "gain" | "maintain",
    "effective_goal_type": "lose" | "gain" | "maintain"
  }
}
```

**Правило:** если `effective_goal_type != original_goal_type` — формула форсированно изменила цель (только `underage_forced_maintain` это делает). UI должен показать tooltip над целью.

### 2. Тексты в `ui_translations`

Схема: `ui_translations(lang_code TEXT PK, content JSONB, created_at TIMESTAMPTZ)`. Одна строка на язык.

Путь к текстам:
```
content -> 'warning' -> 'age' -> <enum_value> -> <surface>
```

Где:
- `<enum_value>` ∈ `{underage_forced_maintain, underage_disclaimer, elderly_less_accurate}` (точные строки, как в `age_warning`)
- `<surface>` ∈ `{banner_title, banner_body, modal_full, auto_resolved}`

**Важно:** `elderly_less_accurate.auto_resolved` — ключ ОТСУТСТВУЕТ в JSONB (не null, а нет вообще). Python-код должен делать `.get()` без `KeyError`.

**SQL для чтения текста:**
```sql
SELECT content -> 'warning' -> 'age' -> 'underage_forced_maintain' -> 'banner_title'
FROM ui_translations WHERE lang_code = $1;
```

Или batch для всех 13 языков — single query, не loop.

### 3. Storage из mig 239 (когда модал показан)

Таблицы:
- `users.shown_guards JSONB` — `{"underage_forced_maintain": "2026-05-17T10:30:00Z", ...}`. Если ключ есть — модал юзеру уже показывался, второй раз не открывать.
- `user_overrides(telegram_id, trigger_name, override_value, reason_text, set_at, expires_at)` — таблица для opt-out'ов. Для age guards opt-out не предусмотрен (hard block без воркфлоу врача).
- `guard_audit_log(telegram_id, trigger_name, event, metadata, occurred_at)` — события (`triggered`, `shown`, `auto_resolved`). FTC legal trace.

### 4. Headless screen meta (если решите рендерить через `ui_screens`)

Сейчас отдельного `ui_screens` записи под age guard нет — баннер можно рендерить inline в `profile` / `my_plan` screens. Если решите делать отдельный modal screen — нужна новая запись в `ui_screens`.

## Что нужно написать в Python

### A. Парсинг RPC ответа (вероятно в `dispatcher/` или `handlers/profile.py`)

```python
def parse_age_warning(rpc_calculations: dict) -> dict | None:
    """
    Возвращает dict с полями для UI render, или None если warning не активен.
    """
    warning = rpc_calculations.get("age_warning")
    if not warning:
        return None
    return {
        "enum": warning,  # e.g. "underage_forced_maintain"
        "original_goal_type": rpc_calculations.get("original_goal_type"),
        "effective_goal_type": rpc_calculations.get("effective_goal_type"),
        "goal_was_overridden": (
            rpc_calculations.get("original_goal_type")
            != rpc_calculations.get("effective_goal_type")
        ),
    }
```

### B. Загрузка текстов (use `v_user_context` view если возможно)

`v_user_context` view агрегирует translations и constants для конкретного юзера. **Сначала проверь** добавляет ли он `warning.age.*` в выдачу — если да, используй его (один RTT). Если нет — отдельный SELECT из `ui_translations` по `lang_code` юзера.

### C. Render banner в `profile` / `my_plan` screen

В headless архитектуре баннер — это либо отдельная HTML-секция в `messages.main_text`, либо отдельный screen перед основным. Решение по UX — твоё. Минимум: добавить в `profile.main_text` строку перед остальным контентом если `age_warning != NULL`.

Цвет/emoji индикатор:
- `underage_forced_maintain` — 🛡️ red banner (hard block)
- `underage_disclaimer` — 👨‍⚕️ yellow banner (informational)
- `elderly_less_accurate` — 🌿 blue banner (informational)

См. [safety-guard-ux-pattern.md §3](../knowledge/concepts/safety-guard-ux-pattern.md) — 5-tier severity matrix.

### D. First-trigger modal (опционально, но желательно)

При первом detection — показать `modal_full` через `delete_and_send_new` strategy:
1. Прочитать `users.shown_guards`
2. Если `enum` уже там — пропустить modal, только banner.
3. Если нет — отправить modal с `modal_full` текстом + кнопкой «Понял».
4. После нажатия — `UPDATE users SET shown_guards = shown_guards || jsonb_build_object(<enum>, NOW())`.
5. INSERT в `guard_audit_log(event='shown', ...)`.

### E. Auto-resolved notification (cron)

Daily cron job:
```sql
SELECT telegram_id, shown_guards FROM users
WHERE shown_guards ? 'underage_forced_maintain'
   OR shown_guards ? 'underage_disclaimer'
```
Для каждого — пересчитать `calculate_user_targets`. Если `age_warning` сменился с не-null на null (юзеру стукнуло 18) — отправить `auto_resolved` текст + очистить ключ из `shown_guards`.

**Для `elderly_less_accurate`** — `auto_resolved` отсутствует (см. mig 240 решение), просто не очищать.

## Тестовые сценарии

Создать юзеров-sentinel'ов через `BEGIN; INSERT; ... ROLLBACK;`:
- F/16/165/55 + goal=lose → должен получить `underage_forced_maintain` + banner + modal
- F/16/165/55 + goal=gain → `underage_disclaimer` + banner (без forced override)
- M/80/175/75 + goal=maintain → `elderly_less_accurate` + banner (без forced override)
- F/30/165/65 + goal=lose → no warning, no banner (control)

## Что НЕ нужно делать

- Не трогать саму RPC `calculate_user_targets` — она готова (v6).
- Не править существующие тексты в `ui_translations` — только читать.
- Не делать opt-out flow для age (это hard block, дети не consent'ят — см. `safety-guard-ux-pattern.md`).
- Не путать `underage_*` (hard и informational) — это **разные** enum'ы с разной severity.

## Связано

- mig 234 (RPC v6) — `migrations/234_calculate_user_targets_age_guards.sql`
- mig 239 (storage) — `migrations/239_safety_guard_storage.sql`
- mig 240 (UI texts) — `migrations/240_ui_translations_age_warnings.sql`
- mig 241 (L2 fixes) — `migrations/241_ui_translations_age_warnings_l2_fixes.sql`
- Pattern: [safety-guard-ux-pattern.md](../knowledge/concepts/safety-guard-ux-pattern.md)
- Roadmap: [calc-user-targets-roadmap.md](../knowledge/concepts/calc-user-targets-roadmap.md) P0.8
