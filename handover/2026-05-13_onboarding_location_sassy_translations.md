---
title: Sassy-варианты location onboarding — что чинить и почему юзер видит сухой текст
date: 2026-05-13
author: claude/busy-volhard-39a4cf
audience: claude/phase6-2-location-edit (PR #59) + любой следующий агент по locations
status: handover — read-only расследование, ничего не правил
---

# TL;DR

В БД лежат заранее подготовленные **Sassy Sage** варианты переводов для онбординг-локации (motivational, объясняют ценность), но они **dead code**:

1. `process_onboarding_input` для `status='onboarding:country'/'onboarding:timezone'` рендерит **сухие** screens `edit_country` / `edit_timezone` (`questions.edit_country` = «Откуда ты?»), а не новые Sassy-экраны `onboarding_country_picker` / `onboarding_timezone_picker` (`onboarding.ask_country` = «Я умею отличать хамон от докторской колбасы...»).
2. Sassy-варианты в БД используют **double-brace `{{icon_X}}`** (legacy n8n Mustache), а Python `_resolve_text` понимает только **single-brace `{icon_X}`** — даже если их подключить, юзер увидит literal-скобки вокруг эмодзи.
3. Текст «зачем нужна локация» (`ask_country`) и «как нажать GPS-кнопку» (`ask_share_location`) разорваны на два экрана; второй показывался legacy `02.1_Location` ПОСЛЕ нажатия [Авто] — в Python пути этот второй экран не появляется.

Юзер: видит «Откуда ты?» → [Авто][Список], кликает [Авто] → бот молча просит location в `sendChatAction` без объяснения. Отсюда reluctance делиться геопозицией.

---

# Где что лежит (точные адреса)

## Translations

`ui_translations.content->'onboarding'->`:

| ключ | тип | используется ли сейчас? |
|---|---|---|
| `ask_country` | JSONB array (3 Sassy variants) | нет — orphan |
| `ask_timezone` | JSONB array (3 variants) | нет — orphan |
| `ask_share_location` | JSONB array (3 variants — про большую GPS-кнопку) | нет — orphan (legacy 02.1_Location ранее показывал) |
| `timezone_auto` | string | legacy 02.1_Location |
| `btn_other_country` | string | legacy 02.1_Location |
| `ask_utc` | string | legacy fallback |
| `skip_hint` | string | возможно используется |

`ui_translations.content->'questions'->`:

| ключ | значение RU | используется |
|---|---|---|
| `edit_country` | «Откуда ты?» | `edit_country` screen (дry, sustained Profile v5) |
| `edit_timezone` | «Какой у тебя часовой пояс?» | `edit_timezone` screen |

13 языков: `[ar, de, en, es, fa, fr, hi, id, it, pl, pt, ru, uk]`.

### Образцы Sassy variants (RU)

`onboarding.ask_country` (массив):
- `«{{icon_globe}} Я умею отличать хамон от докторской колбасы, но мне нужна подсказка. Где мы находимся?»`
- `«{{icon_globe}} Разная география — это разные штрих-коды и продукты. Давай настроим локальную базу!»`
- `«{{icon_globe}} Чтобы советы были точными...»`

`onboarding.ask_timezone`:
- `«{{icon_clock}} Ого, какая большая страна!...»`
- `«{{icon_clock}} Давай синхронизируем часы. Метаболизм не любит джетлага, даже цифрового.»`
- `«{{icon_clock}} В твоей стране время течет по-разному...»`

`onboarding.ask_share_location`:
- `«{{icon_pin}} Не листай список вручную. Просто нажми кнопку внизу {{icon_down}} — я сам всё найду!»`
- `«{{icon_magic}} Магия GPS работает...»`
- `«{{icon_globe}} Хочешь быстрее? Большая кнопка «Отправить местоположение»...»`

EN — параллельная структура, тоже массивы, тоже `{{icon_X}}`.

## Screens

`ui_screens`:

| screen_id | text_key | meta |
|---|---|---|
| `edit_country` | `questions.edit_country` | `{pagination:{page_size:12}, callback_prefix:'loc_country_'}` |
| `edit_timezone` | `questions.edit_timezone` | `{callback_prefix:'loc_tz_', requires_country:true}` |
| `onboarding_country_picker` | `onboarding.ask_country` | `{page_size:12, dynamic_picker:'country', callback_prefix:'loc_country_'}` |
| `onboarding_timezone_picker` | `onboarding.ask_timezone` | `{page_size:12, dynamic_picker:'timezone', callback_prefix:'loc_tz_', requires_country:true}` |

Два последних созданы [migrations/207_phase6_1_location_onboarding.sql](migrations/207_phase6_1_location_onboarding.sql) (block B), но `process_onboarding_input` в том же миграции (block C) **продолжает рендерить `edit_country`** в секции `IF v_status = 'onboarding:country'` (строка 574) и `IF v_status = 'onboarding:timezone'` (строка 577). Аналогично в branches `cmd_quiz_skip` (строка 380) и `cmd_quiz_continue` (строка 520).

## Constants (для placeholder'ов)

`app_constants`: `icon_globe` (🌍), `icon_clock` (⏰), `icon_pin` (📍), `icon_down` (👇), `icon_magic` (✨). Все есть.

## Template engine

`services/template_engine.py`:
- `_resolve_text` (L110-149): regex `\{([^{}:]+)\}` — **single-brace only**. Это основной путь рендера `text_key` экрана.
- `_VAR_PLACEHOLDER_RE = re.compile(r"\{([^{}:]+)\}")` (L80).
- `resolve_translation_text` (L301-351, public helper): нормализует `{{icon_X}}` → `{icon_X}` через `re.sub(r"\{\{(icon_[a-z_]+)\}\}", r"{\1}", raw)` (L328). Но это **отдельный entry-point**, не вызывается из основного `render_envelope → _resolve_text`.
- `_build_button_text` (L152-182): через `_resolve_text` — тоже single-brace only.
- `_resolve_carrier_text` (L431-474): tolerant `r"\{\{?(icon_[a-z_]+)\}?\}"` — принимает оба. Этот путь только для carrier.

**Вывод:** в основном render path `text_key → _resolve_text`, double-brace **НЕ работает**.

---

# Что нужно сделать (рекомендация, выбирай сам)

## Минимум-минимум (включить Sassy + исправить grammar)

1. **Миграция** — нормализовать `{{icon_X}}` → `{icon_X}` для трёх ключей × всех вариантов × 13 lang. JSONB-операция: один `UPDATE ui_translations SET content = jsonb_set(...)` с walk через jsonb_array_elements + regex_replace. Не забывай — APPEND/REPLACE для **массивов** в Sassy variants: тут нужно REPLACE поэлементно (нормализация существующих, не добавление новых вариантов), но БЕЗ потери variation. Pattern — KB [[concepts/python-vs-n8n-template-grammar]] секция «Variant-массивы».
2. **Миграция (та же)** — поменять text_key экранов `onboarding_country_picker.text_key` остаётся `onboarding.ask_country` (как уже стоит), **но** изменить `process_onboarding_input` чтобы рендерить `onboarding_country_picker` / `onboarding_timezone_picker` вместо `edit_country` / `edit_timezone` в:
   - `IF v_status = 'onboarding:country' THEN RETURN render_screen('onboarding_country_picker');`
   - `IF v_status = 'onboarding:timezone' THEN RETURN render_screen('onboarding_timezone_picker');`
   - `cmd_quiz_skip` branch: → `onboarding_country_picker`
   - `cmd_quiz_continue` branch: → `onboarding_country_picker`
3. **`handle_location` в handlers/location.py**: проверить что dynamic_picker рендерит keyboard **на любой text_key**, не только `questions.edit_country`. Если оно дергает `_resolve_text` для text_key экрана — после фикса grammar Sassy-варианты будут работать.

## Идеально (полный мотивационный flow)

4. **Объединить «зачем» + «как нажать»** на одном экране:
   - Вариант A — переписать варианты `onboarding.ask_country` так чтобы каждый сам включал и motivation, и hint про GPS-кнопку. Тогда `ask_share_location` можно либо удалить (если legacy 02.1_Location уже не используется в Python authoritative пути), либо оставить как dead-code на случай rollback.
   - Вариант B (предпочтительнее) — расширить `ui_screens.meta` ключом `subtitle_text_key`, template_engine научить рендерить `text_key + "\n\n" + subtitle_text_key`. Это переиспользуется для других экранов где нужен пояснительный subtitle. **Тут точно потребуется правка `template_engine.py` + миграция meta** — большое изменение, может стоит отдельной фазой.

   Я бы сделал **Вариант A** в этой же миграции, **B** — отдельной задачей в роадмапе.

## Дополнительная чистка (всплыло в исследовании, не location-специфичная)

5. `onboarding.msg_trial_ended`, `msg_trial_limit`, `msg_welcome_back` содержат **`\\n` literal** (двойной backslash) вместо реального newline. В чате юзер видит `\n` как два символа. Фикс — `regexp_replace(value, '\\n', E'\n', 'g')` через `jsonb_set` для затронутых ключей × 13 lang.

   Если возьмёшь — добавь в свою же миграцию (это data-bug, не location-функционал). Если не возьмёшь — я отдельно сделаю в bug-fix миграции 209+.

---

# Резерв номеров миграций — координация

- `origin/main` HEAD migration: **208** (208_onboarding_success_unified_carrier.sql).
- Открытые PR без миграций: #58 (Noop Pattern cleanup), #59 (Phase 6.2 location edit Profile v5 — handlers/location.py only, без SQL).
- **Я (busy-volhard-39a4cf) зарезервировал номер 209** под предстоящий fix bugs «Исправить» / «Поделиться» (если буду применять SQL fix). Файл ещё не закоммичен, но как только начну — `touch migrations/209_*.sql && git add` чтобы коллизия выявилась рано.
- **Если ты (location-agent) запускаешь миграцию по этому handover'у — бери 210+.** Перед `git push` обязательно `git fetch origin main && ls migrations/` ещё раз — другой агент может опередить.

Lesson 2026-05-11 про коллизии 200/200 (sticker vs phenotype) — в [MEMORY.md](../../../.claude/projects/-Users-vladislav-Documents-NOMS/memory/MEMORY.md). Не повторяем.

---

# Что я НЕ делал (важно)

- Ничего не правил в `ui_translations` / `ui_screens` / `process_onboarding_input` — это твоя зона.
- Не трогал `handlers/location.py` — там #59 в активной работе.
- Не делал PR на location-фикс.
- Read-only исследование: psycopg2 SELECT через DATABASE_URL, journalctl на VPS, grep по коду.

Мой scope в текущей сессии — фикс багов `cmd_edit_last` + `share_invite_link` (`stats_main` / `friends_info`). Эти баги ортогональны твоему location flow, не пересекаются по таблицам кроме общего `process_user_input` (я добавляю branches для cmd_edit_last/share_invite_link, ты — никак не трогаешь process_user_input на этой задаче).

---

# Контакт

Если что-то непонятно или находки выглядят странно — открой issue / спроси в next session. Все факты собраны через live psycopg2 + journalctl на 2026-05-13 ~UTC. Snapshot устаревает быстро (TTL дня), перепроверяй live перед миграцией.
