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

### ⛔ Pet-free (owner rule 2026-06-07) — УЖЕ внесено в драфт

Слово «Pet»/«Пет» **запрещено** (KB [[concepts/phantom-pet-entity]]). Драфт **переписан Pet-free на всех 13 языках**, включая исправленные **en+ru, которые ЗАМЕНЯЮТ текущие прод-строки** (в проде `sage.guarded.*` en/ru ещё содержат «Pet» в 5 элементах: maternal[0,1], underweight[0], underage[0,2] — правятся той же миграцией). Заодно убрана «every gram» лексика из underweight[0] (см. ниже).

### Для L1 (нутрициолог) — обязательно решить

1. **🟢 (решено в драфте) `underweight[0]` = «every gram»** тащил весовую лексику у BMI-гард-когорты. Переписан без единиц: en «Nourishing — every bite is a win.» + локализации без «грамм/gram/گرم». L1 — подтвердить формулировку.

### Для L2 (native) — по языкам

2. **WARN ar/underweight+underage:** generic-masc императивы `كُلْ` / `اعتنِ` — gender-leak на когорте неизвестного пола (glossary §3 AR: generic-masc = «последний резерв»). Переписать на verbal-noun/passive (`تغذية جيدة`, `العناية بالنفس مهمة`).
3. **WARN AR/FA bidi:** `Pet` — латинский остров внутри RTL. Проверить рендер в Telegram iOS/Android, особенно `underweight[0]` где `Pet` в середине строки рядом с тире. Возможно нужны LRM-маркеры (§8 AR/FA).
4. **NIT it/underweight[0]:** `Pet gode ogni grammo` — `gode` имеет разговорный сексуальный оттенок → `assapora` / `si gusta`.
5. **NIT uk/underage[0]:** `Ростеш сильним` — instrumental м.р. (родовая форма для underage). Лучше gender-free `Набираєш сил`.
6. ~~имя компаньона «Pet»~~ — снято: Pet удалён полностью (см. Pet-free выше), локализовать нечего.

### Уже внесено в драфт по итогам критика + owner rule
- ✅ **Pet удалён** на всех 13 языках (вкл. en/ru) — owner rule, KB [[concepts/phantom-pet-entity]].
- ✅ underweight[0] «every gram» → без весовой лексики (критик WARN1).
- ✅ uk/underweight[2]: `Їж досхочу` → `Їж добре` (убрал коннотацию «ешь больше»).
- ✅ uk/underage[0]: `Ростеш сильним` (родовая форма) → `Набираєш сил` (gender-free, критик NIT).
- ⏳ AR underweight/underage generic-masc императивы (`كُلْ`/`اعتنِ`) — L2(ar) переписать на безличные.

## Apply-рецепт (ПОСЛЕ ревью)

1. Внести правки L1/L2 в `tools/sage_guarded_draft_gen.py`, регенерировать JSON.
2. Миграция `migrations/NNN_sage_guarded_i18n_13langs.sql`: per-lang `jsonb_set(content,'{sage,guarded,<family>}', '<json-array>'::jsonb, true)` для **всех 13 языков** (en/ru = REPLACE прод-строк с Pet; 11 — новые). Убедиться что `{sage,guarded}` существует (mig 312 создавал для en/ru; для остальных — сначала `jsonb_set(content,'{sage,guarded}', COALESCE(content#>'{sage,guarded}','{}'), true)`). ⚠️ НЕ использовать `content = content || …` (jsonb-shallow-merge guard + KB [[concepts/jsonb-shallow-merge-antipattern]]).
3. psycopg2 transactional apply + verify: 0 missing по `sage.guarded.*` для всех 13 langs; placeholder-free (в этих строках плейсхолдеров нет); literal-`\n` нет.
4. PR + auto-deploy.

## Связано
- KB [[concepts/sassy-sage-multilingual-glossary]] (per-language §3 gender / §7 taboo), [[concepts/copywriter-playbook]] §3 (L1/L2 gating), [[concepts/l1-cultural-sanity-brief]].
- Аналогичный pending Fiverr-бриф: `handover/2026-06-01_fiverr_dunning_l1_review_brief.md` (можно объединить сессию — те же AR/FA/HI приоритеты).
