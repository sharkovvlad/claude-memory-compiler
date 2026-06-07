# Handover — `sage.guarded.*` L1/L2 review brief (Tier 2)

**Дата:** 2026-06-07
**Статус:** DRAFT готов, НЕ в проде. Ждёт L1 (нутрициолог anti-shame) + L2 (native, минимум AR/FA/HI) перед деплоем.
**Артефакт:** `tools/sage_guarded_draft_2026-06-07.json` (11 langs × 3 семьи × 3 варианта = 99 строк).
**Генератор:** `tools/sage_guarded_draft_gen.py` (правки тут → регенерация).

## Что это и зачем

`sage.guarded.{maternal,underweight,underage}` — преднабитые fallback-ответы Sage для **уязвимых когорт**, когда LLM-путь жёстко отключён (`services/sage.py:649-682`):
- **maternal** — беременные / кормящие
- **underweight** — BMI-гард (дефицит массы)
- **underage** — несовершеннолетние

Сейчас в БД эти ключи есть **только на en+ru** → 11 остальных языков получают **английский fallback**. Т.е. беременная/underweight/подросток с языком ≠ en/ru видит англоязычный ответ. Это и закрываем.

Хранение: JSONB **массив[3]** на семью (variant pattern, `random.choice` per user). Деплой — `jsonb_set content '{sage,guarded,<family>}'` массивом.

## Pre-screen критиком (выполнен) — вердикт «годится для L1/L2, переписи не требует»

**0 BLOCKER · 4 WARN · 4 NIT.** Прямого shame / body-talk / РПП-триггеров / культурных табу **не найдено ни в одном языке**. Сильные стороны: maternal нигде не звучит как давление «ешь за двоих»; underage везде про рост/энергию/спорт; UK без русизмов и war-метафор; AR/FA без религиозных оборотов/pork/alcohol; HI без beef/pork/caste.

### Для L1 (нутрициолог) — обязательно решить

1. **🔴 EN-эталон `underweight[0]` = «Pet enjoys every gram» тащит ВЕСОВУЮ лексику** в самую уязвимую (BMI-гард) когорту. Это дефект **источника**, честно унаследованный во все 11 языков (de `jedes Gramm`, ar `كل غرام`, …). **Это та же строка, что СЕЙЧАС в проде на en/ru.** Решение owner/L1: переписать EN на формулировку без единиц измерения (напр. «Pet enjoys every bite / savours every mouthful») → затем перелокализовать все 12 языков (вкл. правку прод-en/ru). Самый весомый пункт — единственный, что касается всех языков + живого прода.

### Для L2 (native) — по языкам

2. **WARN ar/underweight+underage:** generic-masc императивы `كُلْ` / `اعتنِ` — gender-leak на когорте неизвестного пола (glossary §3 AR: generic-masc = «последний резерв»). Переписать на verbal-noun/passive (`تغذية جيدة`, `العناية بالنفس مهمة`).
3. **WARN AR/FA bidi:** `Pet` — латинский остров внутри RTL. Проверить рендер в Telegram iOS/Android, особенно `underweight[0]` где `Pet` в середине строки рядом с тире. Возможно нужны LRM-маркеры (§8 AR/FA).
4. **NIT it/underweight[0]:** `Pet gode ogni grammo` — `gode` имеет разговорный сексуальный оттенок → `assapora` / `si gusta`.
5. **NIT uk/underage[0]:** `Ростеш сильним` — instrumental м.р. (родовая форма для underage). Лучше gender-free `Набираєш сил`.
6. **NIT (все langs): имя компаньона «Pet»** оставлено латиницей (ru = «Пет»). Подтвердить локализованное имя per lang.

### Уже внесено в драфт по итогам критика
- ✅ uk/underweight[2]: `Їж досхочу` → `Їж добре` (убрал коннотацию «ешь больше» у underweight).
- ✅ `_meta.open_questions` уточнены (ar generic-masc + Pet/bidi).

## Apply-рецепт (ПОСЛЕ ревью)

1. Внести правки L1/L2 в `tools/sage_guarded_draft_gen.py`, регенерировать JSON.
2. Миграция `migrations/NNN_sage_guarded_i18n_11langs.sql`: per-lang `jsonb_set(content,'{sage,guarded,<family>}', '<json-array>'::jsonb, true)`. Убедиться что `{sage,guarded}` существует (mig 312 создавал для en/ru; для остальных — `COALESCE … || jsonb_build_object`).
3. psycopg2 transactional apply + verify: 0 missing по `sage.guarded.*` для всех 13 langs; placeholder-free (в этих строках плейсхолдеров нет); literal-`\n` нет.
4. PR + auto-deploy.

## Связано
- KB [[concepts/sassy-sage-multilingual-glossary]] (per-language §3 gender / §7 taboo), [[concepts/copywriter-playbook]] §3 (L1/L2 gating), [[concepts/l1-cultural-sanity-brief]].
- Аналогичный pending Fiverr-бриф: `handover/2026-06-01_fiverr_dunning_l1_review_brief.md` (можно объединить сессию — те же AR/FA/HI приоритеты).
