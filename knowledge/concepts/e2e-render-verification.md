---
title: "E2E render verification — «залил → реально показывается»"
aliases: [e2e-render-verification, e2e-i18n-check, render-rollback-test]
tags: [testing, e2e, i18n, render, headless, rollback, method]
sources:
  - "daily/2026-06-08.md"
created: 2026-06-08
updated: 2026-06-08
---

# E2E render verification

Метод проверки, что изменение в `ui_translations` / экране **реально доходит до пользователя правильно** на нужном языке — без реального аккаунта, без отправки в Telegram, без персистентных изменений в БД. Закрывает петлю «залил перевод → а покажется ли он».

Инструмент: **`tools/e2e_render_check.py <screen_id> [langs…]`** (в main NOMS-репо).

## Зачем именно так (а не «нажать в телефоне»)

Многие user-facing строки — **условные/edge-сюрфейсы**: блокировка удаления аккаунта (нужна активная Stripe-подписка), экран триместра (нужен `is_pregnant`), `sage.guarded.*` (беременная/underweight + LLM hard-skip), лиговые cron-пуши (по понедельникам). Поднять реального юзера в каждое состояние — невозможно/инвазивно/спам. Поэтому проверяем на **слое рендера** с управляемым входом.

## Ключевое: рендер двухступенчатый (headless)

1. **`render_screen(tid, screen_id)`** — SQL RPC. Возвращает **headless**-структуру: `text_key` (напр. `profile.set_trimester_text`), кнопки с `text_key`, `template_vars`, `meta.language_code`. **Текст ещё НЕ собран** — только ссылки на ключи.
2. **`services/template_engine.py::_resolve_text(text_key, translations, template_vars, constants)`** — Python. Превращает `text_key` → финальную строку: `translations` = `ui_translations.content` для языка (= источник `v_user_context`), `constants` = `app_constants` (key/value), `template_vars` = из render. Делает 2 прохода: `{tr:ns.key}` → nested, `{var}`/`{icon}` → vars/constants, нормализует `{{icon_x}}`→`{icon_x}` (mig 213).

Проверять надо **обе** ступени — иначе видишь только `text_key`, а не то, что увидит юзер.

## Безопасность: rollback-транзакция

- `psycopg2` с `autocommit=False`. На тест-юзере (по умолчанию owner `786301802`, `E2E_TID` override) делаем `UPDATE users SET language_code=…`, рендерим, **`conn.rollback()`** после каждого языка.
- `render_screen` пишет `nav_stack`/`last_active` — тоже откатывается.
- В конце ассерт: язык тест-юзера восстановлен. Ноль персистентных изменений, ноль сообщений в Telegram. Owner-аккаунт не страдает (rollback гарантирует).

## Рецепт (ядро `e2e_render_check.py`)

```python
conn = psycopg2.connect(url); conn.autocommit = False; cur = conn.cursor()
from services.template_engine import _resolve_text
constants = dict(<SELECT key,value FROM app_constants>)
for lang in ["en", "pl", "ar"]:            # en=контроль, ar=RTL
    cur.execute("UPDATE users SET language_code=%s WHERE telegram_id=%s", (lang, TID))
    render = <SELECT render_screen(TID, screen)>
    ui = render["telegram_ui"]; text_key = ui["text_key"]; tvars = ui["template_vars"]
    translations = <SELECT content FROM ui_translations WHERE lang_code=lang>
    final = _resolve_text(text_key, translations, tvars, constants)
    conn.rollback()                        # ← undo, per lang
```

**Ассерты:** язык локализован (≠ en-контроль); `<b>` сбалансирован; нет утечки `text_key` (значит перевод нашёлся); нет литеральных `{placeholder}`/`{{icon}}` (значит подстановка сработала). Для RTL (ar/fa) — наличие арабицы.

## Python-layer сюрфейсы (render_screen не покрывает)

Текст, который собирает Python напрямую (не headless-экран), проверяй вызовом билдера со стаб-контекстом:
- **cron-пуши** (`crons/reminders.py`, `crons/league_cycle.py`) — вызвать билдер сообщения с `lang` + stub user dict.
- **`sage.guarded.*`** (`services/sage.py`) — селектор фоллбэка по lang + cohort; либо просто проверить, что `_resolve_text` тянет нужный ключ из content (механизм тот же).

## Когда этого мало

Это проверка **контента рендера**. Для доставки/клавиатур/реальных нажатий — живой Telethon-краулер `tests/live/e2e_crawler.py` (owner-only DFS по inline-kb). Для cron по расписанию — проверяй билдер, не жди понедельника.

## Результат первого прогона (2026-06-08)

`personal_metrics_set_pregnancy_trimester` × en/pl/ar/de → все локализованы, `<b>` цел, плейсхолдеры заполнены, RTL ar ок, rollback восстановил язык. Подтвердил, что mig 488/492 (set_trimester_text) реально доходят до юзера.

## Related Concepts
- [[concepts/copywriter-playbook]] — где и как менять `ui_translations` (10-step pipeline).
- [[concepts/jsonb-shallow-merge-antipattern]] — безопасный apply переводов.
- [[concepts/headless-picker-pattern]] — headless-архитектура (render_screen отдаёт структуру, не текст).
