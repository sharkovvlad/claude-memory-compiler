# Sage tone dry-run protocol — ОБЯЗАТЕЛЬНЫЙ pre-merge check

> **🔥 HUB. Owner-mandated 2026-06-13.** Любая правка `_DEFAULT_SYSTEM_PROMPT_*` или новой payload-META в `services/sage.py` обязана пройти **synthetic dry-run** ДО merge. Не после, не «когда найдём время». ДО.

## Зачем

Tone-of-voice правки **нельзя** валидировать только unit-тестами. Юнит-тесты проверяют:
- Какие META сработали (boolean flags в `metas_fired`)
- Структуру payload'a (правильные строки в нужных местах)
- Что snapshot текст в системном промпте не дрогнул

Что **юнит-тесты не ловят**:
- Как gpt-4o-mini **реально** реагирует под новый набор инструкций
- **Language leak** (Hindi-юзер получает RU-output — PR #396 lesson)
- **Soft-hint ignored** (модель пушет еду несмотря на Card D — PR #396 lesson)
- **Culture mis-substitution** (модель калькирует «свиную рульку» AR-юзеру)
- **Praise calibration** (модель выбирает proud, но wording = «Great job!»)
- **Curse of instructions** (модель «осторожничает» под heavy META-стеком → коллапс emotion в smirk)

Эти классы проблем **только** видны при реальном LLM-вызове через тот же gpt-4o-mini, что и прод.

## Когда запускать (hard triggers)

- Любая правка `_DEFAULT_SYSTEM_PROMPT_EN` ИЛИ `_DEFAULT_SYSTEM_PROMPT_MY_DAY_EN`
- Добавление **новой** META (функция `_*_meta()` + integration в `_build_*_prompt`)
- Изменение порядка META в payload (cascade reorder)
- Любое изменение `CULTURE GUARD`, `VOICE EXAMPLES`, `DAY STATUS HINTS`, `FORBIDDEN`, `PROACTIVE NAVIGATION`, `RULE 7b TONE SHAPE`
- Изменение `_compute_day_status` (новый day_status enum или изменённый порог)

**Когда НЕ нужно:**
- Изменения в `_fire_sage_telemetry`, `_pick_pre_baked`, helper-функциях не-promptного контура
- Bug-фиксы в food parsing / latency / RPC wrapping
- Refactor без functional change

Triage rule: если ваше изменение **может** изменить output модели хотя бы на одном (region × day_status × hour × emotion) пересечении — гоните dry-run.

## Что входит в dry-run

### Минимум 8 сценариев

| # | Surface | Country | Lang | Status | Hour | Что проверяем |
|---|---|---|---|---|---|---|
| 1 | food_log | UA | ru | closed | 22h | late_night_close, RU character close, streak ref |
| 2 | my_day | UA | ru | quiet_steady | 19h | NO push, character ack — owner-mandate «просто поддержать без совета» |
| 3 | my_day | ES | es | in_progress | 14h | CULTURE: pollo asado / queso fresco, no English calque |
| 4 | my_day | SA | ar | cold_start | 11h | HALAL: NO pork/alcohol, halal chicken/labneh/dates |
| 5 | my_day | IN | hi | severe_deficit | 22h | **LANGUAGE LOCK + vegetarian default + late_night** |
| 6 | my_day | DE | de | target_met | 20h | proud emotion → adult acknowledgement, NOT «Great job!» |
| 7 | my_day | FR | fr | protein_drought | 18h | CULTURE: poulet rôti, lentilles; varied lever |
| 8 | food_log | ID | id | over | 23h | HALAL: nasi/tempe, NO pork; late_night HARD close |

**Опциональные** (добавляйте при изменениях, которые специфично трогают эти случаи):
- BR/PT (closed lunch) — for LATAM launch
- AR-MENA в Ramadan (h=20, расширенное cutoff) — если есть Ramadan-логика
- DE formal/informal — `Sie/du` calibration check
- HI vegan (не только vegetarian)
- PL twaróg + kasza — Slavic-non-RU
- JP/KR — если когда-то выйдем

### Эталонный скрипт

См. `tools/sage_dry_run.py` (если файла нет — скопировать из `/tmp/sage_dryrun.py` от 2026-06-13 + добавить в `tools/`). Структура:

```python
from services import sage
from openai import AsyncOpenAI

SCENARIOS = [...]  # 8 минимум, каждый со stub ctx + payload/day_summary

async def run_scenario(client, sc):
    ctx = StubCtx(**sc["ctx_overrides"])
    with patch.object(sage, "_local_time_context",
                      return_value=(sc["hour"], sc["meal_period"])):
        # build payload через реальные функции
        if sc["surface"] == "food_log":
            prompt = sage._build_user_prompt(ctx, sc["payload"], ...)
            system = sage._DEFAULT_SYSTEM_PROMPT_EN
        else:
            prompt = sage._build_my_day_prompt(ctx, sc["day_summary"], ...)
            system = sage._DEFAULT_SYSTEM_PROMPT_MY_DAY_EN

    # реальный LLM-вызов
    resp = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role":"system","content":system},
                  {"role":"user","content":prompt}],
        temperature=0.9,
        response_format={"type":"json_object"},
    )
    return resp.choices[0].message.content
```

Запуск: `python3 tools/sage_dry_run.py` → читает `.env` → 8 LLM-calls (~$0.05 total на gpt-4o-mini) → JSON в `/tmp/sage_dryrun_results.json`.

### Что смотреть в каждом результате

Per scenario:
1. **`emotion`** — соответствует ли day_status? (quiet_steady → sage; target_met+streak → proud; etc)
2. **`next_meal_suggested`** — false где должно быть (closed budget, quiet_steady, Rule 7b, late_night)
3. **Language** — output на target language? (Hindi-юзер — реально на Hindi, не на RU)
4. **Food references** — culturally appropriate? (AR → halal, HI → veg, ES → pollo asado)
5. **Wording** — без штампов («как насчёт», «чтобы добрать», «лишних калорий», «Great job!»)
6. **Self-references** — нет «metabolic navigator», «I will help you»
7. **Functional claims** — нет «X поддержит Y», «улучшает Z»

## Как фиксировать результаты

### Перед merge

1. Прогнать dry-run **дважды** (LLM stochastic — temperature=0.9): убедиться что **оба** прогона зелёные. Если один пройдёт, другой нет — это нестабильное место, эскалировать.
2. Положить **markdown digest** в PR description с таблицей before/after по тем сценариям, которые ваш PR непосредственно затрагивает. См. PR #396 description как образец.
3. Сравнить с **prior baseline** (предыдущий dry-run по тем же сценариям) — найти регрессии. Если scenario N был ✅, теперь 🟡 — это **regression**, не improve. Откатывать или fix.

### После merge

1. В daily `claude-memory-compiler/daily/YYYY-MM-DD.md` — секция «Sage dry-run §Scenario N изменение» с link на PR.
2. Если найдена **новая** проблема, не покрытая 8 базовыми сценариями — добавьте сценарий в этот документ (раздел «Минимум 8»), чтобы следующий агент его прогонял.

## Lessons (что dry-run уже отловил)

### 2026-06-13 (PR #396, hotfix)

- **Language leak (IN/hi)** — Hindi-юзер получил Russian output. Single-line `Response language: hi` тонул под heavy CULTURE GUARD (~500 tokens RU/UA references). Fix — `_language_lock_meta` финальной директивой. **Без dry-run этот баг лет бы на проде** при первом non-RU юзере. Unit-тесты не ловили.
- **quiet_steady push (UA/ru)** — модель пушет «может, приготовить гречку с овощами» несмотря на Card D + DAY STATUS HINT. PROACTIVE NAVIGATION rule перебивает soft hint. Fix — `_quiet_steady_no_push_meta` как HARD guard. **Owner-mandate «просто поддержать без совета»** реализован только после dry-run.
- **DE proud → patronizing wording** — модель выбирает emotion=proud правильно, но wording скатывается в «voller Erfolg!», «perfekte Bilanz», 👏 emoji. **Это infantilizing praise**, который мы пытались блокировать generic FORBIDDEN. **Calibration**: нужно явно разрешить adult acknowledgement и дать proud Card с правильным эталоном. → PR-3b TODO.

### 2026-06-08 (PR #375, ToV-meta v1)

- 90.5% smirk monoculture, 31% «куриного филе», 31% «как насчёт» — это статистика 200 live реакций. Если бы был dry-run на этапе ToV-meta v1 — мы бы увидели эти штампы **до** того как они проросли в 200 реакций.

## Why this is HARD rule, not «nice-to-have»

Цена ошибки tone-of-voice **высокая**:
- Любой non-RU юзер, увидевший русский текст → leave + bad review
- AR-юзер, увидевший «свиная рулька» в эталоне → trust violation (haram)
- Юзер на восьмой день streak, получивший «Great job!» вместо adult ack → infantilizing → bad UX
- РПП-юзер, увидевший push «как насчёт куриного» → potential trigger

Cost dry-run = $0.05 + 5 минут wall-clock. Cost скрытого регресса = sale-blocker для launch и/или real user harm.

**Поэтому это HARD GATE pre-merge,** не optional.

## Gotcha — hardcoded `sys.path` в `tools/sage_dry_run.py` (2026-06-13, PR-3b)

`tools/sage_dry_run.py:40` содержит `sys.path.insert(0, "…/worktrees/vigorous-cray-157241")`
— абсолютный путь к **конкретному** worktree того агента, который продвинул скрипт
в repo (PR #398). Если ты в **другом** worktree, скрипт импортнёт `services.sage`
из ЧУЖОГО (устаревшего) кода → dry-run прогонит НЕ твои изменения, и ты увидишь
ложно-зелёный результат.

**Workaround** (пока скрипт не починен): сделай локальный wrapper в `/tmp/`, который
делает `sys.path.insert(0, "<ТВОЙ worktree>")` **ДО** `from services import sage`,
и добавь `assert hasattr(sage, "<твоя новая функция>")` сразу после импорта —
это поймает импорт из чужого worktree немедленно. Образец — `/tmp/dry_run_pr3b_wrapper.py`
(daily 2026-06-13).

**Правильный fix на будущее** (todo): заменить hardcoded путь на
`sys.path.insert(0, str(Path(__file__).resolve().parents[1]))` — тогда скрипт всегда
импортит sage из СВОЕГО repo, в каком бы worktree ни лежал.

## Related Concepts

- [[concepts/sage-payload-meta-override-pattern]] — главный hub по META-каскаду
- [[concepts/sage-silent-presence-mode]] — silent_presence META (PR-3b), прошла этот gate
- [[concepts/sage-food-log-llm-integration]] — host архитектура
- [[concepts/sassy-sage-dialog-variants]] — fallback'ы и вариативность

## Sources

- `tools/sage_dry_run.py` — эталонный скрипт (если отсутствует — скопировать из `/tmp/sage_dryrun.py` daily 06-13)
- `tests/services/test_sage_language_lock_and_quiet_steady.py` — unit-тесты на МЕТА, найденные через dry-run
- `daily/2026-06-13.md` § «Dry-run digest + PR-3a» — first application
- PR [#396](https://github.com/sharkovvlad/noms-bot/pull/396) — hotfix language_lock + quiet_steady_no_push, два бага найдены только через dry-run
