---
title: CLDR Plural Runtime — `{N word}` formatting across 13 langs
status: active
last_verified: 2026-06-01
related:
  - copywriter-playbook
  - ui-translations-bulk-update-recipe
  - sassy-sage-multilingual-glossary
  - jsonb-array-python-consumer-blind-spot
---

# CLDR Plural Runtime — резолв `{count} word` в правильной форме

Литеральная форма существительного после числа в шаблоне UI ломается, когда
число становится переменной. «1 days» / «1 дней» / «3 يومًا» / «1 dni» — все
четыре грамматически неверны. Это особенно болезненно когда шаблон уходит в
**push-уведомление** (dunning, reminder, streak break): юзер не может «вернуться
назад» и перечитать корректный текст.

NOMS уже сталкивался с этим в **mig 415** (PL `{streak_days} dni`,
fix внутри `crons/subscription_lifecycle.py:_pl_day_word`). **mig 418**
обобщил решение на ru/uk/pl/ar/es/fr/it/pt через единый helper и единый
placeholder.

## Архитектурный паттерн

**Один placeholder, один helper, табличные формы.**

```
шаблон (ui_translations)          Python (cron / handler)         выход
─────────────────────────         ─────────────────────────       ──────
"серия из {streak_days_word}"  →  format_count(3, "ru", DAY_FORMS["ru"])
                                                                    ↓
                                                                  "3 дня"
```

Шаблон не знает грамматики языка. Грамматика — в `DAY_FORMS` (или другой
табличке слова). Categorisation (one/few/many/other) — в `babel.PluralRule`.

### Почему не делать grammar inside шаблона

Очевидный подход: `{N} {plural:дней,дня,день}` или две версии ключа
`payment.dunning_d3_singular` / `_plural`. Оба проблематичны:

- **Inline plural mini-DSL** требует тогда парсера + escape + reviewer
  должен помнить порядок («one,few,many» или «one,two,few»?). Каждый язык
  свой.
- **Два ключа** удваивают translation surface, копирайтер пишет ту же
  фразу дважды с микро-изменением → drift между формами легко не заметить.
- Ни тот, ни другой не отвечают на arabic (6 категорий) и не работают с
  числами 100, 1000, 11-14 («teens trap» в PL/RU).

**Babel CLDR** уже знает правила для всех 200+ языков. Не дублировать его.

## Helper: `services/i18n_plural.py`

```python
from services.i18n_plural import DAY_FORMS, format_count, plural_word

# Самый частый use case:
format_count(3, "ru", DAY_FORMS["ru"])  # "3 дня"
format_count(1, "pl", DAY_FORMS["pl"])  # "1 dzień"
format_count(25, "ar", DAY_FORMS["ar"]) # "25 يومًا"

# Без префикса числа:
plural_word(5, "uk", DAY_FORMS["uk"])   # "днів"
```

`DAY_FORMS` — табличка для слова «day». Для нового слова — зеркальная табличка:

```python
YEAR_FORMS = {
    "en": {"one": "year", "other": "years"},
    "ru": {"one": "год", "few": "года", "many": "лет", "other": "лет"},
    "uk": {"one": "рік", "few": "роки", "many": "років", "other": "років"},
    "pl": {"one": "rok", "few": "lata", "many": "lat", "other": "lat"},
    "ar": {"zero": "سنة", "one": "سنة", "two": "سنتان",
           "few": "سنوات", "many": "سنة", "other": "سنة"},
    # …
}
```

CLDR категории, нужные для NOMS-langs:

| Lang   | Категории                              | Пример                |
|--------|----------------------------------------|-----------------------|
| en/de/es/fr/it/pt | `one`, `other`                | 1 day / 5 days        |
| id/hi/fa | `other` (нет инфлексии)             | 1 hari / 5 hari       |
| ru/uk  | `one`, `few`, `many`, `other`          | день / дня / дней     |
| pl     | `one`, `few`, `many`, `other`          | dzień / dni / dni     |
| ar     | `zero`, `one`, `two`, `few`, `many`, `other` | يوم / يوم / يومان / أيام / يومًا / يوم |

`other` обязателен везде — fallback, когда резолвенная категория отсутствует.

## Apply pipeline для нового шаблона

1. **Аудит** — есть ли уже похожая табличка (`DAY_FORMS`, ...).  
2. **Helper extension** — если слова нет, добавить `WORD_FORMS` в
   `services/i18n_plural.py` со ВСЕМИ 13 langs (один `other` минимум).
3. **Шаблонный placeholder** — переименовать `{N} <word>` → `{N_word}`
   через миграцию.
4. **Python resolve** — `if "{N_word}" in text: text = text.replace("{N_word}",
   format_count(N, lang, WORD_FORMS.get(lang, WORD_FORMS["en"])))`.
5. **Unit tests** — для каждого языка с >1 формой, минимум:
   one (n=1), few (n=3 для slavic), many (n=11 «teens trap»),
   и для AR — two (n=2), few (n=5), many (n=25), other (n=100).
6. **Integration test** — sample template + sample n → exact substring assert.

## Острые места

### «Teens trap» (PL/RU/UK)

Числа 11-14 НЕ попадают в `few` (категория для 2-4), они идут в `many`:

```python
plural_word(12, "ru", DAY_FORMS["ru"])  # "дней" (НЕ "дня")
plural_word(13, "pl", DAY_FORMS["pl"])  # "dni"  (НЕ "dzień")
```

CLDR-правило это учитывает (`n mod 100 not in 12..14`), но если самому
писать `n % 10 in 2..4 → few` без teens-exception — будет баг.

### Arabic 6 категорий — обязательно

`{N} يومًا` грамматически корректно ТОЛЬКО для n ∈ 11..99. Для n ∈ 3..10
нужно `أيام`, для n=1 — `يوم`, для n=2 — `يومان`. Урезанная табличка
`{"one": "يوم", "other": "أيام"}` для AR будет неправильна почти везде.

### Polish `many` категория

CLDR PL `many` rule — длинный (`n is not 1 and n mod 10 in 0..1 or
n mod 10 in 5..9 or n mod 100 in 12..14`). Если в `_CLDR_RULES["pl"]`
указать только `one` + `few`, babel вернёт `other` для 0/5/100 — что
работает для `dni` (`few` == `many` == `other` == "dni"), но СЛОМАЕТСЯ
для слов, где формы расходятся (`rok/lata/lat`).

**Правило:** при добавлении нового lang в `_CLDR_RULES` либо
указывать ВСЕ категории, либо проверить (unit-тестом) что `other`
покрывает все случаи в существующей табличке слова.

### Babel в зависимостях

`babel>=2.12` уже в `requirements.txt` с mig 415 (для PL). Helper
импортирует `babel.plural.PluralRule` — без него ImportError на старте
крона. Если зависимость пропала — `_cldr_category` ловит исключение и
возвращает `"other"` (безопасный fallback).

## Где ещё ждёт миграции

Аудит DB (2026-06-01) показал ещё **5 шаблонов** с тем же паттерном
`{N} word`:

| Ключ                              | Placeholder | Langs с bug'ом   | Owner-приоритет |
|----------------------------------|-------------|------------------|-----------------|
| `payment.days_remaining`         | `{days}`    | en, pl, ar, es, fr, it, pt (ru/uk через «дн.» — safe) | low (rare display) |
| `payment.renewal_reminder`       | `{days}`    | same             | low |
| `payment.days_remaining_template`| `{days_left}` | same           | low |
| `food_log.header_*_multi`        | `{count}`   | ru/uk/pl/ar/es/fr/it/pt (en тоже!) | medium (часто) |
| `referral.cta_active_2`          | `{count}`   | same             | medium (на referral экране) |

Шаблон применения: для `food_log.header_*_multi` нужна табличка
`ITEM_FORMS` (или `POSITION_FORMS`/`ENTRY_FORMS` — что копирайтер выберет).
`referral.cta_active_2` — `AGENT_FORMS` / `RECRUIT_FORMS`. Они out of scope
для mig 418, отдельные миграции.

## Lessons

- **Hand-coded `_pl_day_word` (mig 415) был стартовой точкой, не финальной.**
  Через 2 недели owner попросил расширения; если бы helper был сразу общим
  (`plural_word(n, lang, forms)`), достаточно было бы добавить таблички.
  Single-lang hand-coded helpers — debt, не решение. **Правило:** если
  правишь grammar runtime для одного языка — сразу делай helper general.
- **DB-аудит ДО написания helper'а.** Если бы я делал helper только для
  `streak_days`, пропустил бы `{days}`, `{count}` — они в той же категории
  и должны переиспользовать `plural_word()`. Аудит дал картину для
  follow-up миграций.
- **Race-condition на migration-номер.** Параллельный агент в worktree'е
  занял 416/417 пока я работал. Rebase + sanity-check `git diff
  origin/main..HEAD --stat` (правило 12.2 global) спасли — переименовал
  416 → 418 (+ 4 internal references). См. [[migration-collision-guard]].
