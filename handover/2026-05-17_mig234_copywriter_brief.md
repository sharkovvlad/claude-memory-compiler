# Copywriter Brief — mig 234 age guards messaging (13 langs)

> **STATUS: Historical (executed). Applied via mig 240/241/242 (2026-05-17/18).**
>
> **Для актуального copywriter playbook см. [[concepts/copywriter-playbook]] — single entry point для будущих guard translation sessions.** Этот brief сохранён как исторический пример (age warnings были first guard family migrated).
>
> Inline content ниже частично дублирует canonical KB (severity, tone rules, L1 process). При расхождениях — canonical KB winning. Canonical pointers:
> - Severity vocabulary + naming: [[concepts/agent-collaboration-protocol]] Rule 1 + Rule 3
> - Banner emoji prefix matrix: [[concepts/safety-guard-ux-pattern]] §3
> - Sassy Sage tone: [[concepts/sassy-sage-multilingual-glossary]] Part I
> - 10-step apply pipeline: [[concepts/ui-translations-bulk-update-recipe]]
> - L1 review checklist: [[concepts/l1-cultural-sanity-brief]]

**Trigger:** mig 234 (`calculate_user_targets` v6) merged 2026-05-17. RPC возвращает `age_warning` в одном из 4 значений (`underage_forced_maintain` | `underage_disclaimer` | `elderly_less_accurate` | NULL). UI banner показывается if not NULL. **Translation keys нужны для активации UI слоя.**

Полный pattern — [[concepts/safety-guard-ux-pattern]]. Coordination protocol — [[concepts/agent-collaboration-protocol]].

## Scope: 156 actual translation entries

3 warnings × 4 surfaces × 13 languages = 156 entries.

Не «5 surfaces» — `opt_out_confirm` отсутствует для всех 3 warnings (hard block без opt-out + informational не имеют override). Остаются: `banner_title`, `banner_body`, `modal_full`, `auto_resolved`.

### Three warnings

| Warning enum | Severity (Rule 1) | Who sees it | Что меняется в формуле |
|---|---|---|---|
| `underage_forced_maintain` | **hard block** | `<18 + goal_type=lose` | goal_type → maintain. Дефицита нет. |
| `underage_disclaimer` | **informational** | `<18 + goal=gain/maintain` | Ничего. Только banner с medical disclaimer. |
| `elderly_less_accurate` | **informational** | `>75` (любая цель) | Ничего в v6. mig 236+ переключит на Lührmann (silent accuracy). |

### Four surfaces

1. **`banner_title`** — короткий заголовок banner'а (20-40 chars max, romance langs +30% sjатие).
2. **`banner_body`** — 1-2 предложения объяснения (≤140 chars, чтобы влезло на mobile screen без collapse).
3. **`modal_full`** — детальный текст для first-trigger modal (5-10 lines max, ≤12 lines Telegram SRE). Включает: что случилось, почему, что юзеру делать, ссылка на /support.
4. **`auto_resolved`** — one-shot Telegram message когда условие снимается (юзеру стукнуло 18 для underage, или 76 для elderly). 1-3 lines.

### Translation key format

`warning.age.<warning_enum>.<surface>` — см. Rule 3 naming convention.

Примеры:
- `warning.age.underage_forced_maintain.banner_title`
- `warning.age.underage_forced_maintain.banner_body`
- `warning.age.underage_forced_maintain.modal_full`
- `warning.age.underage_forced_maintain.auto_resolved`
- `warning.age.underage_disclaimer.*` (4 keys)
- `warning.age.elderly_less_accurate.*` (4 keys)

= **12 keys × 13 langs = 156 translation entries**.

## Russian baseline drafts (отправная точка, НЕ финал)

Эти drafts — для tone reference. Финальные тексты на 13 языках **адаптируются по культуре**, не дословный перевод.

### `warning.age.underage_forced_maintain.*`

```
banner_title (≤40 chars):
«⚠️ Тебе нет 18 — план изменён»

banner_body (≤140 chars):
«Жёсткий дефицит до 18 небезопасен. Я поставил поддержание веса. Так формулы работают точнее для растущего тела.»

modal_full (5-10 lines):
«Слушай, я обязан сказать честно.

До 18 лет жёсткий дефицит калорий не рекомендуется без врача — это про здоровый рост, гормоны и кости.

Я переключил твою цель на «поддержание». Расчёт по-прежнему персональный.

Если врач/диетолог уже одобрил план — напиши /support, разрешим.

После 18 защита снимется автоматически.»

auto_resolved (1-3 lines):
«🎉 Тебе исполнилось 18. Защита снята — теперь доступна цель «похудеть» если хочешь.»
```

### `warning.age.underage_disclaimer.*`

```
banner_title (≤40 chars):
«👨‍⚕️ Формулы адаптированы под возраст»

banner_body (≤140 chars):
«Тебе нет 18. Я считаю по адаптированным формулам, но не заменяю педиатра/диетолога.»

modal_full (5-10 lines):
«Короткое FYI.

Стандартные формулы калорий валидированы на взрослых (18+). Для тебя я использую адаптированные — учитываю активный рост.

Расчёт точный, но он не заменяет педиатра или диетолога-подростковика. Если есть вопросы или сомнения — обсуди с врачом.

Это не запрет, это disclosure.»

auto_resolved (1-3 lines):
«Тебе исполнилось 18 — теперь стандартные формулы для взрослых.»
```

### `warning.age.elderly_less_accurate.*`

```
banner_title (≤40 chars):
«🌿 Возрастная коррекция планируется»

banner_body (≤140 chars):
«После 75 наши расчёты менее точны (саркопения, индивидуальная вариативность). Стоит обсудить план с гериатром.»

modal_full (5-10 lines):
«Хочу сказать прямо.

Формулы калорий точны для широкого возрастного диапазона, но после 75 они начинают промахиваться — мышечная ткань и обмен веществ работают иначе.

Я пользуюсь Mifflin-St Jeor — он недооценивает обмен у пожилых на 5-10%.

Рекомендация: обсуди план с гериатром или диетологом. Это твой план, не наш.

В будущей версии (скоро) переключусь на более точную формулу автоматически.»

auto_resolved:
N/A (>75 = нет «отката» возраста, разве что вернуться меньше 75 не реалистично)
```

**Note:** `elderly_less_accurate.auto_resolved` можно оставить пустой или заменить на something вроде «спасибо что доверяешь нам годами» при истечении 3-5 лет use'а. Решать копирайтеру — может быть NULL для этой surface.

## Constraints — обязательные

### Sassy Sage tone

См. полный glossary [[concepts/sassy-sage-multilingual-glossary]]. Кратко:
- Прямо, без морализаторства
- Дружеский ↔ медицинский баланс — не «вы должны», а «давай так»
- Никогда «худеть нельзя» — всегда «давай отложим / посоветуемся»
- Anti-shame red lines: НИКОГДА «твой вес проблема» / «нужно работать над собой» / «ты слишком молод» / «ты слишком стар»
- Подросток + пожилой = **уважительный, не патронизирующий** tone

### Telegram SRE budgets

- `banner_title` ≤ 40 chars (mobile screen header)
- `banner_body` ≤ 140 chars (single bubble без collapse)
- `modal_full` ≤ 12 lines, каждая ≤ 35 chars (Telegram default mobile)
- `auto_resolved` ≤ 3 lines, каждая ≤ 35 chars
- Кнопки (если в modal) ≤ 18 chars

**Romance langs (ES/PT/IT/FR) +30%** — нужно sтаритьcя в budget, идиоматическое сжатие (короче чем literal перевод).

### Cultural adaptation per language family

Это **обязательно**, не word-for-word translation:

**Romance (ES, PT, IT, FR):**
- ES: `apesta` → региональное, **избегать**. Использовать «un bajón».
- PT-BR vs PT-PT — выбрать PT-BR baseline (большая база юзеров).
- IT: `pediatra` для подростков — formal but warm
- FR: `médecin de famille` или `pédiatre` — choose based on context
- `coger` (ES, LatAm) — вульгарно, **избегать**

**Germanic (DE, EN):**
- DE: `loggen` = **false friend** (sign-in), не «record meal». Использовать `tracken` или `eintragen`
- DE: подростковый tone — `du` (не `Sie`)
- EN: Sassy Sage = casual but caring, не corporate

**Slavic (RU, PL, UK):**
- RU: gender-neutral passive («поставлено» вместо «ты поставил») — gender политика
- PL: `zalogować` = sign-in, не log. Использовать `zapisać` / `wpisać`
- UK: **anti-russianism via read-aloud** — текст должен звучать естественно для украинского уха. Russian word interference = автоматический fail.

**Arabic-Persian (AR, FA):**
- AR: bidi LRM/RLM critical для emoji + цифр. RTL formatting обязательно
- FA: ZWNJ для combinations типа «می‌خواهد»
- Pregnancy/halal/Ramadan context — НЕ упоминать в этих 3 warnings (нет связи с pregnancy / fasting в age guards), но если возникнет — flag для L2
- Подростковый tone в AR — formal modesty (не slang), respect старших норма

**HI (Hindi):**
- Devanagari script, register: not too formal not too colloquial
- Anti-caste-aware tone — не предполагать family doctor access («посоветуйся с врачом» более общее чем «у вашего семейного врача»)
- L2 flag if uncertain

**ID (Indonesian):**
- Casual but respectful — Indonesian Telegram users skew young, but family-respect culture важен
- Pregnancy/halal context — НЕ возникает в age guards

### Anti-patterns — что НЕ делать

❌ Прогон через Google Translate / DeepL без cultural pass.
❌ Дословный перевод английских idioms (например `«Heads up»` → дословно не переводится в RU, нужен `«Короткое FYI»` или `«Имей в виду»`).
❌ Слишком formal corporate tone — Sassy Sage = умный друг, не юрист.
❌ Patronizing подростка / пожилого («ты ещё слишком молод чтобы понять» / «в вашем возрасте надо беречь себя»).
❌ Shaming weight / body / appearance — НИ В КАКОМ контексте.

## L1 cultural review (per Rule 9)

**Ты (копирайтер) делаешь pre-screen.** Per Rule 9 two-layer model:

- L1: первичная cultural sanity check через [[concepts/sassy-sage-multilingual-glossary]]
- L2: native cultural reviewer per region (Romance/Germanic/Slavic/Arabic-Persian/HI/ID = 6 reviewers max)

Для каждого key пометь в выходном JSON одно из:

- **`cultural-clean`** — safe to deploy, glossary passed.
- **`cultural-flag-<region>-<topic>`** — escalate to L2 review. Topics: `pregnancy-context`, `medical-authority`, `shame-risk`, `register-mismatch`, `idiom-uncertainty`, `religious-context`.

**Severity rule:**
- `underage_forced_maintain` (hard block) — **mandatory L1 для всех 13 langs + mandatory L2 для AR/FA/HI/ID** (anti-РПП framing varies culturally)
- `underage_disclaimer` и `elderly_less_accurate` (informational) — **glossary self-screen достаточно**, L2 not required (но flag if uncertain)

## Output format

Создай файл `tools/mig234_warnings_translations_20260517.json` (вне git, как FR pilot pattern из daily/2026-05-17.md).

```json
{
  "warning.age.underage_forced_maintain": {
    "banner_title": {
      "ar": {"text": "...", "cultural_flag": "cultural-clean"},
      "de": {"text": "...", "cultural_flag": "cultural-clean"},
      "en": {"text": "...", "cultural_flag": "cultural-clean"},
      "es": {"text": "...", "cultural_flag": "cultural-clean"},
      "fa": {"text": "...", "cultural_flag": "cultural-flag-FA-medical-authority"},
      "fr": {"text": "...", "cultural_flag": "cultural-clean"},
      "hi": {"text": "...", "cultural_flag": "cultural-flag-HI-medical-authority"},
      "id": {"text": "...", "cultural_flag": "cultural-clean"},
      "it": {"text": "...", "cultural_flag": "cultural-clean"},
      "pl": {"text": "...", "cultural_flag": "cultural-clean"},
      "pt": {"text": "...", "cultural_flag": "cultural-clean"},
      "ru": {"text": "...", "cultural_flag": "cultural-clean"},
      "uk": {"text": "...", "cultural_flag": "cultural-clean"}
    },
    "banner_body": { ... 13 langs ... },
    "modal_full": { ... 13 langs ... },
    "auto_resolved": { ... 13 langs ... }
  },
  "warning.age.underage_disclaimer": { ... 4 surfaces × 13 langs ... },
  "warning.age.elderly_less_accurate": { ... 4 surfaces × 13 langs ... }
}
```

После этого — отдельный INSERT-script для apply в `ui_translations`:
```sql
INSERT INTO ui_translations (key, lang_code, value) VALUES
  ('warning.age.underage_forced_maintain.banner_title', 'ar', '...'),
  ...
ON CONFLICT (key, lang_code) DO UPDATE SET value = EXCLUDED.value;
```

В отдельном файле `tools/mig234_warnings_apply.sql`.

## Output deliverables

1. `tools/mig234_warnings_translations_20260517.json` — 156 переведённых строк с cultural_flag pomerkami
2. `tools/mig234_warnings_apply.sql` — INSERT script готов к apply
3. **Summary report** в conversation: какие keys получили `cultural-flag-*` (escalate to L2), какие `cultural-clean`. По family aggregation.

## Не делать

❌ НЕ apply'й в БД сам — это делает mig-engineer после nutritionist L1 final check + L2 для flagged.
❌ НЕ создавай миграцию — apply пойдёт отдельной mig в следующую сессию.
❌ НЕ перезаписывай существующие keys в `ui_translations` без `ON CONFLICT DO UPDATE` (но keys всё равно новые, не должны существовать).
❌ НЕ дублируй work с агентами проекта [[plans/proud-tickling-willow]] (RU терминология стрик→серия) — это другой scope, твои keys (`warning.age.*`) с ними не пересекаются.

## Контекст

- Mig 234 SQL: `migrations/234_calculate_user_targets_age_guards.sql` (smerged 2026-05-17, PR #86)
- Pattern: [[concepts/safety-guard-ux-pattern]] §3 (severity), §6 (auto-reset variants), §7 (translation pipeline L1/L2)
- Tone glossary: [[concepts/sassy-sage-multilingual-glossary]] (8 подразделов на язык)
- Roadmap: [[concepts/calc-user-targets-roadmap]] P0.1 (mig 234 done)

## Ready check

Перед start подтверди:
1. ✅ Прочитал [[concepts/sassy-sage-multilingual-glossary]]
2. ✅ Понял разницу между hard block (`underage_forced_maintain`) и informational (others)
3. ✅ Понял что `opt_out_confirm` отсутствует во всех 3 warnings
4. ✅ Output format JSON + SQL apply file
5. ✅ Cultural flag per key (cultural-clean / cultural-flag-<region>-<topic>)

После start — работа в одну сессию, ~2-4 часа prompt time. Если нужны clarifications — ask before start, не в середине.
