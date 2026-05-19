# Handover: Pet/Пет persona cleanup (i18n)

> **Создан:** 2026-05-18 (закрытие Phase 4 UX-копирайтинга). Предыдущий агент проработал план UX-копирайтинга и закрыл Phase 0-4 (RU терминология + 11 культурных миграций для ES/DE/FR/IT/PT/PL/UK/ID/HI/AR/FA, PR #95 ждёт merge). Этот handover — про **отдельный inheritance bug**, обнаруженный на финале сессии. Идеально подходит новому агенту: clean scope, ~30-45 минут работы.

---

## 0. TL;DR

**Что:** В `ui_translations` фигурирует mythical entity **«Pet» / «Пет» / «Metabolo-Pet»**, которая никак не объяснена в архитектуре. NOMS говорит юзеру «Pet тебя поблагодарит» — а кто этот Pet, юзер не знает (см. жалобу владельца со скриншотом ES чата). Это persona-confusion: согласно `CLAUDE.md` проекта **NOMS сам и есть metabolic companion**, отдельной Pet-сущности нет.

**Scope:** 3 ключа × ~10 языков = ~30 instances в БД.
**Действие:** одна миграция (~252+), writer→critic→merge pipeline (готовый в KB).
**Парадигма:** заменить «Pet/Пет» на **1-е лицо NOMS** или на **«твой метаболизм»**. Recommendation: **Variant A (1-е лицо NOMS)**.

---

## 1. Контекст (full story)

### 1.1 Что обнаружил владелец
На скриншоте Telegram-чата (день «Мой день» — daily report screen) ES-пользователь увидел:
```
💬 Noms: "Proteína baja. Pollo, huevos o queso — el Pet te lo agradece."
```
Цитата владельца: *«Какой Pet если у нас есть персонаж конкретный — Номс? Там же говорит от своего имени, причём тут какой-то питомец?»*

### 1.2 Почему это inheritance bug
- **Проектная парадигма** (`CLAUDE.md` проекта, line ~10):
  > NOMS — это твой карманный **метаболический компаньон**.
- То есть `NOMS = metabolic companion = the «Pet»`. Когда бот говорит *«Pet thanks you»*, это формально означает «я (NOMS) благодарю тебя, говоря о себе в третьем лице» — на UX выглядит как **вторая никем не объяснённая сущность**.
- «Пет» в RU original скорее всего legacy от ранней Tamagotchi-style идеи (gamification entity, отдельная от bot). В текущей архитектуре эта вторая сущность нигде не explained — нет в onboarding, нет в `ui_screens`, нет в `xp-model` KB.
- Phase 3-4 writers (11 языков) **наследовали** «Pet» из current value (правило хирургичности — не трогать то, что не просили), не зная что это inheritance bug. Critics не triggered ни одной из 5 осей (naturalness OK, anti-shame OK).

### 1.3 Cross-language inconsistency
- DE: `Metabolo-Pet` (writer сохранил existing brand-term)
- RU: `Метабол-пет`
- ES/IT/FR/EN/etc: просто `Pet` / `el Pet`
- ID: `Pet metabolik-mu` / `Pet senang`
- PT-BR: `pet metabólico`
- Нет согласованности → дополнительное подтверждение что это не designed feature, а leftover.

---

## 2. Точные данные (ground truth — recon выполнен)

### 2.1 Affected keys (3)
```
report.insight_protein_low    (scalar string)
report.insight_balanced       (scalar string)
gamification.streak_30        (JSONB array of 3 strings, variant 2 contains Pet)
```

### 2.2 Affected languages (10 из 13)
**Содержат Pet/Пет/Metabolo-Pet:** ar, de, en, es, fa(?), fr, hi(?), id, it, pl, pt, ru, uk
**Точно подтверждено в recon:** de, en, es, fr, id, it, pl, pt, ru, uk (10). AR/FA/HI требуют отдельной проверки — recon на substring `Pet` пропустил RTL/Devanagari аналоги. Используй скрипт ниже.

### 2.3 Full current state — берётся отсюда
`/tmp/pet_keys_dump.json` — экспорт всех 3 ключей × 13 языков, готовый для writer-input.

Если файл удалён, регенерация:
```python
import os, json, psycopg2
from dotenv import load_dotenv
load_dotenv("/Users/vladislav/Documents/NOMS/.env")
conn = psycopg2.connect(os.environ["DATABASE_URL"])
cur = conn.cursor()

KEYS = ["report.insight_protein_low", "report.insight_balanced", "gamification.streak_30"]
LANGS = ['ar','de','en','es','fa','fr','hi','id','it','pl','pt','ru','uk']

out = {}
for key in KEYS:
    parts = key.split('.')
    out[key] = {}
    for lc in LANGS:
        cur.execute("SELECT content #> %s FROM ui_translations WHERE lang_code=%s", (parts, lc))
        out[key][lc] = cur.fetchone()[0]

# Сохрани в tools/pet_audit_<YYYYMMDD>.json
```

### 2.4 Live samples (для контекста, не для копирования)
```
[en] report.insight_protein_low:
  "Low on protein. Chicken, eggs, or cottage cheese — Pet will thank you."

[es] report.insight_balanced:
  "¡Buen equilibrio! Seguí así — el Pet da el visto bueno."

[ru] gamification.streak_30 variant 2:
  "Месяц ежедневного трекинга! 🎉 Твой Метабол-пет растёт. Ты официально крут!"

[de] gamification.streak_30 variant 2:
  "Ein Monat tägliches Tracking. Dein Metabolo-Pet ist gewachsen — willkommen im Klub derer, die durchziehen."

[pt] gamification.streak_30 variant 2:
  "🎉 Um mês de anotação diária. Teu pet metabólico cresceu — agora você faz parte do clube de quem termina o que começa."
```

---

## 3. Решение (рекомендация Variant A)

### 3.1 Variant A — заменить на 1-е лицо NOMS (RECOMMENDED)

NOMS говорит от своего имени. Pet удаляется как сущность.

**Шаблоны замен:**

| Контекст | Old | New (паттерн) |
|---|---|---|
| `report.insight_protein_low` | «Pet will thank you» | «**я** скажу тебе спасибо» / «**я** буду рад» / просто комплимент белку без Pet |
| `report.insight_balanced` | «Pet approves» | «**одобряю**» / «**мне нравится**» / «**высший пилотаж**» |
| `gamification.streak_30 v2` | «Metabolo-pet is growing» | «**твой метаболизм** взрослеет» / «**ты прокачал** метаболизм» / «**мы с тобой** в одной команде» (NOMS=we) |

**Примеры финальных переводов:**
```
EN protein_low:
  "Low on protein. Chicken, eggs, or cottage cheese — I'll thank you for it."

ES protein_low:
  "Proteína baja. Pollo, huevos o queso — me lo vas a agradecer."

RU protein_low:
  "Маловато белка. Курица, яйца, творог — спасибо скажешь."  (impersonal, NOMS implied)
  ИЛИ
  "Маловато белка. Курица, яйца, творог — я знаю что говорю."  (NOMS 1st person)

DE streak_30 v2:
  "Ein Monat tägliches Tracking. Dein Stoffwechsel ist gewachsen — willkommen im Klub derer, die durchziehen."
  (Metabolo-Pet → Stoffwechsel — biology, не fake entity)
```

**Почему A:**
- Чисто, никаких phantom-entities
- Парадигма «NOMS = твой компаньон» сохраняется
- Не требует onboarding-объяснений
- Sassy Sage tone сохраняется (всё ещё дерзко)

### 3.2 Variant B — развернуть metaphor «твой метаболизм»

Раскрыть Pet как метафору метаболизма, везде заменить на explicit «metabolism»/«метаболизм»/«Stoffwechsel»/etc.

```
EN: "Low on protein. Your metabolism will thank you."
```

**Минусы:** теряется warmth gamification. «Pet thanks» humorous, «metabolism thanks» — biology textbook.

### 3.3 Variant C — оставить Pet, но добавить onboarding-объяснение

NOT recommended — добавляет work и второй entity всё равно остаётся confusing.

---

## 4. Pipeline (стандартный recipe)

**Главный document:** [[concepts/ui-translations-bulk-update-recipe]] — канонический 10-шаговый pipeline. Прочитай **до начала работы**. Все паттерны там.

### 4.1 Краткая последовательность

1. **Pre-flight:**
   ```bash
   git fetch origin main && git rebase origin/main
   gh pr list --state open  # check parallel agents
   ls migrations/ | sort -t_ -k1 -n | tail -5  # next free NNN, likely 252+
   ```
   На момент создания handover: HEAD=251 (Phase 4 FA). PR #95 open но скорее всего смерджен к моменту твоей работы → проверь свежий main.

2. **Audit** — экспортировать current state из 13 langs × 3 keys (см. §2.3 для скрипта). Сохрани в `tools/pet_audit_<YYYYMMDD>.json`.

3. **Snapshot:**
   ```sql
   CREATE TABLE IF NOT EXISTS public.backup_ui_translations_pet_cleanup_<YYYYMMDD> AS
   SELECT *, NOW() AS snapshot_at FROM public.ui_translations;
   ```
   (13 rows, по одной на язык.)

4. **Writer subagent (general-purpose)** — см. §5 ниже для готового prompt template.

5. **Validation (programmatic, before critic):**
   ```python
   PH_RE = re.compile(r'\{\{[a-zA-Z_][a-zA-Z0-9_]*\}\}|\{[a-zA-Z_][a-zA-Z0-9_]*\}')
   for r in replacements:
       cv_ph = set(PH_RE.findall(json.dumps(r["current_X"], ensure_ascii=False)))
       nv_ph = set(PH_RE.findall(json.dumps(r["new_X"], ensure_ascii=False)))
       assert cv_ph == nv_ph
       if r["type"] == "array":
           assert len(r["new_X"]) == r["array_length"]
   ```
   Только `gamification.streak_30` — variant array (length=3), остальные — scalars.

6. **Critic subagent (отдельная сессия)** — см. §6.

7. **Variant-aware merge** — см. recipe §6 в [[concepts/ui-translations-bulk-update-recipe]]. Critic может dispatch верdict на top-level или `path[N]` для variant. Merger должен parse оба варианта.

8. **Manual red-flag scan:**
   - Не должно остаться `Pet` / `Пет` / `Metabolo-pet` / `pet metabolic` ни в одном из 3 ключей по всем 13 языкам.
   - Anti-shame не должен пострадать (биология OK, judgement choices NOT OK).

9. **Migration generation:** per-key `jsonb_set` × 3 keys × 13 langs = ~39 UPDATE statements в одной транзакции BEGIN/COMMIT + variant length assertion + no-Pet-leftover assertion (recursive walk).

10. **Apply via psycopg2 + spot-check + commit + PR.**

### 4.2 Migration template
```sql
-- Migration NNN: Pet/Пет persona cleanup — replace phantom Pet entity with 1st-person NOMS
-- Snapshot for rollback: public.backup_ui_translations_pet_cleanup_<YYYYMMDD>
-- Context: handover/2026-05-18_pet_persona_cleanup.md
-- Scope: 3 keys × 13 langs (10-13 actual instances depending on RTL Pet equivalents)
-- Parameter: writer→critic→merge pipeline, Variant A (1st-person NOMS)

BEGIN;

DO $$ BEGIN
  IF to_regclass('public.backup_ui_translations_pet_cleanup_<YYYYMMDD>') IS NULL THEN
    EXECUTE 'CREATE TABLE public.backup_ui_translations_pet_cleanup_<YYYYMMDD> AS SELECT *, NOW() AS snapshot_at FROM public.ui_translations';
  END IF;
END $$;

-- Per-key updates (39 statements: 3 keys × 13 langs)
UPDATE public.ui_translations SET content = jsonb_set(content, '{report,insight_protein_low}', '"…"'::jsonb, false) WHERE lang_code = 'en';
-- ...

-- Variant-array length assertion for streak_30
DO $$ DECLARE actual_len INT; BEGIN
  FOR lc IN SELECT lang_code FROM ui_translations LOOP
    SELECT jsonb_array_length(content #> '{gamification,streak_30}') INTO actual_len FROM ui_translations WHERE lang_code = lc;
    IF actual_len <> 3 THEN RAISE EXCEPTION 'streak_30 array len % for %', actual_len, lc; END IF;
  END LOOP;
END $$;

-- No-leftover Pet assertion (RECURSIVE walk)
DO $$ DECLARE leftovers INT; BEGIN
  WITH RECURSIVE walk(lang_code, path, val) AS (
    SELECT lang_code, ARRAY[]::text[], content FROM ui_translations
    UNION ALL
    SELECT w.lang_code, w.path || elem.key, elem.value FROM walk w, jsonb_each(w.val) elem WHERE jsonb_typeof(w.val) = 'object'
  )
  SELECT count(*) INTO leftovers FROM walk
  WHERE jsonb_typeof(val) IN ('string','array')
    AND array_to_string(path,'.') IN ('report.insight_protein_low', 'report.insight_balanced', 'gamification.streak_30')
    AND (val::text ~* '\\mPet\\M' OR val::text ~* '\\mПет\\M' OR val::text ~* 'Metabolo-?[Pp]et' OR val::text ~* 'pet metabólic' OR val::text ~* 'pet metabolic' OR val::text ~* 'питомец');
  IF leftovers > 0 THEN RAISE EXCEPTION 'Pet survived in % keys', leftovers; END IF;
END $$;

COMMIT;
```

### 4.3 Rollback
```sql
UPDATE public.ui_translations SET content = b.content
FROM public.backup_ui_translations_pet_cleanup_<YYYYMMDD> b
WHERE ui_translations.lang_code = b.lang_code;
```
**По всем 13 языкам** (не per-language), потому что мы трогаем все языки в одной миграции.

---

## 5. Writer subagent prompt (готовый template)

> Скопируй этот prompt в `Agent` tool call с `subagent_type: "general-purpose"`. Замени `<YYYYMMDD>` на сегодняшнюю дату.

```
Ты профессиональный мультиязычный копирайтер для NOMS (Telegram-бот трекинга
питания `@nomsaibot`). Знаешь Sassy Sage tone в 13 языках.

## ЗАДАЧА (одна миграция, 3 ключа × 13 языков = ~39 значений)

Удалить mythical entity «Pet/Пет/Metabolo-Pet/pet metabólico» из 3 ключей
`ui_translations`. Заменить на 1-е лицо NOMS (Variant A) или на «твой
метаболизм» (Variant B fallback где A не звучит).

## КОНТЕКСТ
NOMS — твой карманный метаболический компаньон (см. CLAUDE.md проекта).
Bot = the Pet. Когда бот говорит «Pet тебя поблагодарит» — это
self-reference третьим лицом, что confusing на UX. Юзер жалуется.

## INPUT
- `/Users/vladislav/Documents/NOMS/.claude/worktrees/<your-worktree>/tools/pet_audit_<YYYYMMDD>.json` —
  3 ключа × 13 языков current state.
- `claude-memory-compiler/knowledge/concepts/sassy-sage-multilingual-glossary.md` —
  обязательно загляни в секции языков чтобы tone был на месте.

## ТРИ КЛЮЧА

1. `report.insight_protein_low` (scalar string, daily report когда юзер ел мало белка)
2. `report.insight_balanced` (scalar string, daily report когда баланс БЖУ хороший)
3. `gamification.streak_30` (JSONB array of 3 strings, празднование 30-дневной серии — Pet только в variant 2)

## CONSTRAINTS (CRITICAL)

🔴 **Placeholder byte-by-byte:** `{streak}` сохранять как есть (только в streak_30).
🟡 **Variant length:** streak_30 = 3 элемента ровно.
🟡 **Sassy Sage tone:** дерзкий мудрец, 70% Шут + 20% Дэдпул + 10% Тед Лассо.
🟡 **Anti-shame:** шутки над биологией/ситуацией, НЕ над юзером.
🟢 **Каждый язык — свой register/sleng:**
   - DE: du, tracken (НЕ loggen)
   - FR: tu, noter (НЕ logguer), food = patrimoine не trogать
   - IT: tu, registrare/segnare, cucina sacra
   - ES: tú LatAm-friendly, apuntar
   - PT-BR: você, anotar, no race-loaded idioms
   - PL: ty, zapisać (НЕ zalogować)
   - UK: ти, no war metaphors post-2022
   - ID: kamu, halal-safe, gender-neutral grammar
   - HI: tum, Hinglish-Latin acceptable, vegetarian-safe (НЕ chicken-celebration!)
   - AR: tu, MSA+Egyptian flavor, bidi LRM где placeholders/numbers
   - FA: to, ZWNJ orthography для compounds (می‌-)
   - RU: дерзкий, geek-сленг, «записать/запись» (НЕ «залогировать»)
   - EN: оставь native EN tone, не over-translate

## RECOMMENDED MAPPING (но адаптируй под каждый язык)

Старое: «Pet will thank you / Pet thanks you / Pet approves»
Новое:
  - Самый чистый: «I'll thank you for it» / «я скажу спасибо» / «спасибо скажешь»
  - Альтернатива: «your metabolism will thank you» / «твой метаболизм скажет спасибо»
  - Avoid: artificial bot-cheerleader «NOMS approves» (тавтология — NOMS уже говорит)

Старое (streak_30 v2): «Your Metabolo-pet is growing»
Новое:
  - «You evolved your metabolism» / «Ты прокачал метаболизм»
  - «Your metabolism levels up with you» / «Метаболизм растёт вместе с тобой»
  - Drop fake entity, оставить gamification-vibe через progress metaphor

## OUTPUT (строго)

Сохрани в `tools/pet_replacements_<YYYYMMDD>.json`:
```json
{
  "generated_at": "<YYYYMMDD>",
  "scope": "pet_persona_cleanup",
  "variant_strategy": "A_first_person_noms",
  "replacements": [
    {
      "path": "report.insight_protein_low",
      "lang_code": "en",
      "type": "string",
      "current_value": "Low on protein. Chicken, eggs, or cottage cheese — Pet will thank you.",
      "new_value": "Low on protein. Chicken, eggs, or cottage cheese — I'll thank you for it.",
      "placeholders_before": [],
      "placeholders_after": [],
      "rationale": "Pet → I (NOMS 1st person). Tone preserved, anti-shame ok."
    },
    {
      "path": "gamification.streak_30",
      "lang_code": "ru",
      "type": "array",
      "array_length": 3,
      "current_value": ["…", "Месяц… Твой Метабол-пет растёт…", "…"],
      "new_value": ["… (unchanged)", "Месяц… Твой метаболизм взрослеет вместе с тобой…", "… (unchanged)"],
      "placeholders_before": ["{streak}"],
      "placeholders_after": ["{streak}"],
      "rationale": "Variant 2: Метабол-пет → твой метаболизм. Variants 1 и 3 unchanged (no Pet)."
    }
  ]
}
```

**Critical для streak_30:** variants 1 и 3 (которые БЕЗ Pet) — НЕ ТРОГАЙ, копируй
1:1 (правило хирургичности). Только variant 2 (с Pet) переписать.

## ПРОЦЕСС

1. Прочитай `tools/pet_audit_<YYYYMMDD>.json` (3 × 13 = 39 entries).
2. Для каждого entry где есть Pet/Пет/Metabolo-pet — перепиши.
3. Для entries БЕЗ Pet/Пет (если такие есть — AR/FA/HI могли использовать другое слово) — проверь визуально: возможно там mismo-entity на local script. Если нет phantom-entity — отметь `verdict: "no_change_needed"` и пропусти.
4. Запиши JSON.
5. В финальном ответе под 300 слов: total entries changed, per-language strategy summary, 3 hardest cases.

Native instinct, precise. Я проверю руками.
```

---

## 6. Critic subagent prompt (готовый)

```
Ты — мультиязычный native UX-копирайтер (носитель 13 языков на native level
для оценки tone, не grammar). Профессиональный critic-копирайтер.

## ЗАДАЧА
Critic-pass по результатам Pet cleanup — оцени каждое из ~30 переписанных
значений по 5 осям.

## INPUT
1. Writer output: `tools/pet_replacements_<YYYYMMDD>.json`
2. Sassy Sage glossary: `claude-memory-compiler/knowledge/concepts/sassy-sage-multilingual-glossary.md`
3. Pet audit (для context): `tools/pet_audit_<YYYYMMDD>.json`

## СЕТКА (1-5 each)
1. **Naturalness** — звучит как native или как калька?
2. **Sassy Sage tone** — дерзкий мудрец сохранён, или плоско?
3. **No phantom entity** — Pet/Пет/Metabolo-pet полностью убран? **Это главная ось.**
4. **Brevity** — длина сохранена ±20%, не overflow.
5. **Anti-shame compliance** — нет judgement выбора еды? (5/5 required, < 5 = auto-reject)

**verdict:** approved / fix_needed / auto_rejected
**fix_proposal:** обязателен если fix_needed, ready-to-merge string

## ОСОБОЕ ВНИМАНИЕ
- **EN/DE/FR/IT — могут ли «Pet» оставаться как cute name?** Verdict: НЕТ.
  Mainтени sass через biology/sage-wisdom, не через phantom-entity.
- **RU «Пет» / «Метабол-пет»** — legacy, должно уйти полностью.
- **AR/FA/HI** — проверь что замена не создала RTL/Devanagari issues
  (LRM marks где placeholders, ZWNJ где compounds).
- **gamification.streak_30 v1 и v3** — должны остаться UNCHANGED (правило
  хирургичности). Если writer их изменил — flag fix_needed.

## OUTPUT
`tools/pet_critic_<YYYYMMDD>.json` — стандартная structure (см.
[[concepts/ui-translations-bulk-update-recipe]] §5).

Final: stats + 3 worst + 3 best + writer rating.
```

---

## 7. Поиск Pet equivalents в AR/FA/HI/UK

Recon на substring `Pet` или `Пет` мог пропустить:
- **AR:** возможно `حيوان` (animal) / `رفيق` (companion) — проверь
- **FA:** возможно `حیوان خانگی` (pet) — проверь
- **HI:** возможно `पालतू` (paltu = pet) или просто `Pet` в Latin
- **UK:** возможно `домашня тварина` или `улюбленець`

```python
# Расширенный recon для не-Latin equivalents
cur.execute("""
WITH RECURSIVE walk(lang_code, path, val) AS (
  SELECT lang_code, ARRAY[]::text[], content FROM ui_translations
  UNION ALL
  SELECT w.lang_code, w.path || elem.key, elem.value
  FROM walk w, jsonb_each(w.val) elem WHERE jsonb_typeof(w.val) = 'object'
)
SELECT lang_code, array_to_string(path,'.'), val::text
FROM walk
WHERE array_to_string(path,'.') IN ('report.insight_protein_low', 'report.insight_balanced', 'gamification.streak_30')
ORDER BY array_to_string(path,'.'), lang_code;
""")
# Просмотри глазами AR/FA/HI/UK — ищи аналоги Pet
```

---

## 8. Когда что использовать (decision matrix)

| Situation | Action |
|---|---|
| `report.insight_protein_low` для DE/FR/IT/ES/EN/etc | Variant A (1st-person NOMS) |
| `report.insight_balanced` | Variant A — drop Pet entirely, добавь NOMS-approval |
| `gamification.streak_30 v2` (празднование) | Variant B («your metabolism evolved») — biology stronger в celebration context |
| AR/FA где RTL bidi сложно | Variant B (simpler, no «I» self-reference которое может быть гендерно-маркировано) |

---

## 9. Post-merge follow-up (Phase 5)

После применения миграции (next session или этого же агента):
1. **E2E spot-check:** запусти бота на test user `tid=786301802` (admin), смени `users.language_code` через psycopg2, прогоняй сценарии `Мой день` → daily report → проверь что в `insight_*` нет Pet.
2. **Monitor support inbox 72ч** на Pet/persona жалобы.
3. **Drop snapshot через 7 дней** стабильности (`DROP TABLE backup_ui_translations_pet_cleanup_<date>`).

---

## 10. Контекстная нагрузка / token budget

Этот task — **clean focused scope, idealen для fresh agent**:
- 1 миграция
- ~30 replacements
- 1 writer + 1 critic call
- 1 PR

Должно быть **30-45 минут wall-clock**, ~100-150k token budget.

---

## 11. Pointers в KB и проекте

| Где смотреть | Что взять |
|---|---|
| [[concepts/ui-translations-bulk-update-recipe]] | **Обязательно прочитать первым** — canonical pipeline |
| [[concepts/sassy-sage-multilingual-glossary]] | Tone-doc для 11 не-EN языков, secs 1-8 per lang |
| `/Users/vladislav/Documents/NOMS/CLAUDE.md` | NOMS personality + git дисциплина §12 |
| `~/.claude/projects/.../memory/MEMORY.md` | Состояние проекта на 2026-05-18 |
| `claude-memory-compiler/daily/2026-05-18.md` | Phase 4 closure log + Pet bug discovery |
| `claude-memory-compiler/daily/2026-05-17.md` | Phase 3-4 sessions, writer→critic insights |
| `/tmp/pet_keys_dump.json` | Готовый dump 3 ключей × 13 langs (если ещё не удалён) |
| `/Users/vladislav/.claude/plans/proud-tickling-willow.md` | План UX-копирайтинга (Phase 5 — это твой scope) |
| `migrations/231_ru_terminology_streak_to_seria.sql` | Reference pattern для terminology jsonb_set |
| `migrations/232_es_terminology_pilot_phase3.sql` | Reference pattern для cultural adaptation single-lang |
| `migrations/247_uk_terminology_phase4_wave_b.sql` | Reference pattern для UK с RU-loanword scrub |

---

## 12. Pitfalls (учиться на ошибках предыдущего агента)

1. **Variant-aware merge** — critic может dispatch verdict на top-level (`path: "gamification.streak_30"`) или variant-level (`path: "gamification.streak_30[2]"`). Если merger ищет только top-level, variant fixes silently dropped (IT mig 243 lesson).

2. **Writer field omission** — некоторые writers пропускают `current_X` / `array_length` в output (FR случай). В prompt EXPLICITLY перечисли required fields с примером.

3. **Self-acknowledged-but-unfixed bugs** — writer может flag'нуть проблему в `rationale` («gender bug here») но всё равно оставить старое value. Critic auto-catches. Не доверяй writer-only output, всегда critic-pass.

4. **Migration collision** — параллельные агенты могут занять «твой» NNN. Перед commit: `git fetch origin main`, `gh pr list --state open`. Если коллизия после push: reset + sed update of SQL comments + recommit + `--force-with-lease`. KB [[concepts/migration-collision-guard]].

5. **Pre-push sanity** — `git diff origin/main..HEAD --stat` должен показать **только 1 файл миграции**. Если 30+ файлов — СТОП, ты не на тот branch / stale worktree.

6. **Anti-shame protocol** — даже если переписываешь чисто Pet, проверь что не добавил accidentally judgement of food choices. «Pet thanks you for the chicken» можно переделать в «I'll thank you for the chicken» (ок) или в «No more boring chicken» (NOT ok — judgement). Stay biology, not preferences.

7. **`current_value` всегда дай критику** — даже если ты ничего не менял в variant 1/3 streak_30, дай в JSON структуру с current=new (одинаковыми) и `verdict: no_change`. Критик может flag breakage if you skip them.

---

## 13. Финальный checklist для агента

Перед PR:
- [ ] `git status` clean
- [ ] `git fetch origin main && git rebase origin/main` — успешно
- [ ] Audit file сохранён, 3 ключа × 13 langs покрыты
- [ ] Snapshot table создан и содержит 13 rows
- [ ] Writer output записан, все 30+ entries имеют `placeholders_after = placeholders_before`
- [ ] Critic-pass прошёл, fix_proposal'ы применены, anti_shame 5/5 для всех
- [ ] Manual scan: no Pet/Пет/Metabolo-pet leftovers в 3 keys
- [ ] streak_30 variants 1 и 3 НЕТронуты (jsonb deep compare)
- [ ] Migration applied via psycopg2, COMMIT прошёл
- [ ] Spot-check 4 keys через `content #> path` — visual quality OK
- [ ] `git diff origin/main..HEAD --stat` — ровно 1 файл миграции
- [ ] Commit message с context + Co-Authored-By
- [ ] PR created, CI checks pass
- [ ] Daily log updated
- [ ] MEMORY.md updated (Phase 5 entry или дополнение к UX-копирайтингу)

---

## 14. Контакт

- Owner: `sharkov.vlad@gmail.com` (всё в чате)
- Plan: `/Users/vladislav/.claude/plans/proud-tickling-willow.md`
- Prior agent context: `claude-memory-compiler/daily/2026-05-17.md` + `daily/2026-05-18.md`

---

**Удачи, преемник.** Pipeline прошёл 12 раз — works. Если что-то странное — проверяй live БД через psycopg2 (`.env` → `DATABASE_URL`), не доверяй stale assumptions.
