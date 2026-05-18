# Brief: Copywriter — bmi / min_kcal warning переводы (13 langs)

**Дата:** 2026-05-18
**Trigger:** mig 252 (banner injection в my_plan) merged → ждёт переводы для bmi/min_kcal families. Mig 246 v7 на проде с 2026-05-18 утра — `bmi_warning` и `min_kcal_warning` enum'ы возвращаются из RPC, но текст не отрисовывается (banner_block для них пустой).
**Estimated effort:** 1 сессия копирайтера + 1 сессия L1+L2 cultural review = ~1-2 дня.

---

## Что писать (точная схема)

`ui_translations.content -> 'warning' -> '<family>' -> '<enum>' -> '<surface>'`

### Family `bmi` — 4 enums × 4 surfaces × 13 langs = **208 entries**

| Enum | Severity | Что означает |
|---|---|---|
| `extreme_cachexia_recommend_medical` | hard block | BMI<14 — extreme cachexia, force maintain + recommend medical |
| `underweight_lose_override` | hard regulated | BMI<18.5 + lose → force maintain (без opt-out, требует врача) |
| `extreme_obesity_clamp_slow` | hard regulated | BMI>60 + fast/normal lose → clamp deficit на slow |
| `extreme_obesity_informational` | informational | BMI>60 (slow/maintain) → banner «обсуди план с врачом», нет override |

### Family `min_kcal` — 3 enums × 4 surfaces × 13 langs = **156 entries**

| Enum | Severity | Что означает |
|---|---|---|
| `bmr_floor_triggered` | hard regulated | Расчётный target < BMR → клампим до BMR |
| `medical_floor_1200_triggered` | hard regulated | Расчётный target < 1200 (женщины) → клампим до 1200 |
| `medical_floor_1500_triggered` | hard regulated | Расчётный target < 1500 (мужчины) → клампим до 1500 |

### Surfaces (одинаковые для всех 7 enums)

| Surface | Что это | Длина target |
|---|---|---|
| `banner_title` | заголовок жёлтой strip'ы в `my_plan` (HTML `<b>...</b>` оборачивается в render) | ≤35 chars Telegram SRE |
| `banner_body` | объяснение под title — argued override (что изменилось, почему, что делать) | 80-160 chars в идеале |
| `modal_full` | full-screen modal на первый trigger — детальный context + sources + medical disclaimer | до 600 chars, abzac'ы на blank lines |
| `auto_resolved` | one-time message когда условие снимается (юзер набрал вес, BMI вырос >18.5) | 50-100 chars |

**Итого:** 364 entries (208 + 156).

`auto_resolved` для **informational** severity = опционально (mig 240 пример: `elderly_less_accurate.auto_resolved` оставлен NULL). Для `extreme_obesity_informational` — тоже можно NULL. Это снижает scope до **~351 entries**.

---

## Reference: формат + tone

### Pattern из mig 240/241/242 (age warnings) — копировать структуру 1:1

Канонический пример из mig 240 EN:

```json
"warning": {
  "age": {
    "underage_forced_maintain": {
      "banner_title": "🛡️ Under 18 — set to maintain",
      "banner_body": "Under 18, aggressive cuts aren't safe — bones, hormones, growth. Switching to maintenance. Plan stays personal.",
      "modal_full": "Straight talk. Under 18,\naggressive cuts without a doctor\nare risky — growth, hormones,\nbones.\n\nSwitching the plan to "maintain"\n— stays personal.\n\nDoctor signed off on a deficit?\n/support, we'll unlock it.\n\nWhen you turn 18, protection lifts.",
      "auto_resolved": "🎉 You turned 18!\nProtection lifted — \"lose\"\nis available again."
    }
  }
}
```

### Tone — Sassy Sage (NOT a medical authority lecturer)

**Read first:** [Sassy Sage Multilingual Glossary](../knowledge/concepts/sassy-sage-multilingual-glossary.md) — глоссарий на 11 не-EN языков.

**Принципы:**
- Argued override, не silent — *скажи что меняется + почему + что делать*
- Anti-shaming — никакой критики тела/выбора
- Direct, no jargon — *«bones, hormones, growth»* > *«impaired osteogenesis»*
- Educational — юзер должен понять *почему*, не просто *что*
- No condescension — взрослый разговор, не патронаж

### Severity → emoji prefix matrix

| Severity | banner_title prefix | Visual |
|---|---|---|
| hard block | 🛡️ | red banner (non-dismissible) |
| hard regulated | 🛡️ | red banner (non-dismissible) — medical gate |
| soft override | ⚠️ | yellow (dismissible) |
| informational | 💡 или 🌿 | blue (informational only) |

`bmi.extreme_cachexia_recommend_medical` = hard block → `🛡️ ` prefix.
`bmi.underweight_lose_override` = hard regulated → `🛡️ ` prefix.
`bmi.extreme_obesity_clamp_slow` = hard regulated → `🛡️ ` prefix.
`bmi.extreme_obesity_informational` = informational → `💡 ` prefix.
`min_kcal.*` все hard regulated → `🛡️ ` prefix.

---

## Scientific anchor — на чём строить body

### BMI guards

- **BMI<14:** Extreme cachexia (Pichard 2004), survival threshold. Не дефицит и не «худеть», а *выживание*. Recommend medical mandatory.
- **BMI<18.5:** Underweight по WHO (2000). Дефицит у underweight → muscle wasting + amenorrhea + osteopenia (RED-S risk). Body опасно вычитать ещё.
- **BMI>60:** Class III obesity++ (super-super-morbid). Быстрый дефицит (>20%) → cardiac arrhythmia + gallstone + sarcopenia (Anderson 2001). Slow rate (~10%) safer + всё равно medical supervision needed.

### Min kcal

- **BMR floor:** target_kcal < BMR → метаболический даунрегуляция (Müller 2015 minimum effective dose). Кламп до BMR = absolute floor для жизненных функций.
- **1200 floor (женщины):** Long-standing clinical convention (NHLBI 2000); ниже — risk amenorrhea + osteopenia (RED-S Loucks 2004).
- **1500 floor (мужчины):** Same convention scaled to higher LBM. Хроническое <1500 у мужчины → тестостерон ↓ + муск масса ↓ (Trexler 2014).

### Sample EN (для отправной точки переводу)

```
bmi.extreme_cachexia_recommend_medical:
  banner_title: "🛡️ BMI critically low — medical first"
  banner_body: "BMI under 14 isn't about dieting. Body's surviving. Plan switches to maintain, but please book a clinician — this isn't something an app can solve."
  modal_full: "Real talk. BMI under 14 is\nextreme cachexia — survival\nterritory, not weight loss.\n\nPlan goes to maintenance.\nThis isn't condescension —\nit's the wrong tool for the job.\n\nPlease see a doctor or RD\nthis week. /support if you\nwant me to share resources.\n\nWhen BMI clears 18.5,\nprotection lifts."
  auto_resolved: "🎉 BMI in healthy range now.\nProtection lifted — you can\nchoose your goal freely again."

bmi.underweight_lose_override:
  banner_title: "🛡️ Underweight — let's hold steady"
  banner_body: "BMI under 18.5 with a deficit risks bone loss and cycle disruption. Switching to maintain. If a clinician greenlit a deficit, /support and we'll unlock."
  modal_full: "Honest talk. Under BMI 18.5,\na further deficit risks:\n- bone density loss\n- menstrual cycle disruption\n- muscle wasting\n\nPlan goes to maintenance.\n\nA clinician greenlit you on\na deficit? Tell us via /support.\n\nWhen BMI clears 18.5,\nprotection lifts automatically."
  auto_resolved: "🎉 BMI 18.5+ now.\nProtection off — your\noriginal goal is available."

bmi.extreme_obesity_clamp_slow:
  banner_title: "🛡️ Fast deficit — slowing to safe"
  banner_body: "BMI over 60 with a fast cut risks cardiac issues and gallstones. Clamping deficit to ~10% (slow). Talk to a clinician for the bigger picture."
  modal_full: "Direct: BMI over 60 with\nfast/aggressive deficit risks:\n- cardiac arrhythmia\n- gallstone formation\n- accelerated muscle loss\n\nDeficit clamped to slow (~10%).\nStill effective, much safer.\n\nWeight-loss surgery, GLP-1,\nbariatric clinic — these are\nteam sports, not solo.\n\nWhen BMI drops below 60,\nfaster pace becomes available."
  auto_resolved: "Pace unlocked — you can\nchoose normal or fast again."

bmi.extreme_obesity_informational:
  banner_title: "💡 Worth a clinician check-in"
  banner_body: "BMI over 60 deserves a team — RD, bariatric clinician, primary care. The plan still works, but pros catch things I can't."
  modal_full: "Friendly nudge. BMI over 60\nis a multi-system situation:\n- cardiovascular load\n- sleep apnea risk\n- liver, kidney, joints\n\nThe plan I built is fine —\nbut a clinician catches\nthings I can't see.\n\nThis is informational, not\na lock. Plan stays as you set it."

min_kcal.bmr_floor_triggered:
  banner_title: "🛡️ Below BMR — bumping up"
  banner_body: "Calculated target was below your BMR — that's the energy floor for basic body functions. Raising to BMR. Same deficit, safer floor."
  modal_full: "Quick context. BMR is what\nyour body burns at rest —\nheartbeat, brain, organs.\nGoing below for long disrupts\nthyroid, hormones, and\nrebound risk.\n\nI clamped target to BMR.\nDeficit recalculated.\n\nIf you want a bigger deficit\nfor a short cut, /support\nand we'll talk through risks."

min_kcal.medical_floor_1200_triggered:
  banner_title: "🛡️ 1200 kcal floor for women"
  banner_body: "Below 1200 kcal long-term risks amenorrhea, bone loss, and metabolic adaptation. Clamping to 1200. If a clinician approved lower, /support."
  modal_full: "Real numbers. Under 1200 kcal\nfor women carries serious\nrisks even with high deficit\ngoals:\n- menstrual cycle loss\n- bone density loss\n- chronic fatigue, mood\n- metabolic slowdown\n\nClamped target to 1200.\n\nDoctor or RD approved a\nlower number for a defined\nperiod? /support, we'll\nunlock with audit trail."

min_kcal.medical_floor_1500_triggered:
  banner_title: "🛡️ 1500 kcal floor for men"
  banner_body: "Below 1500 kcal sustained risks muscle loss, testosterone drop, and rebound. Clamping to 1500. Clinician-approved lower? /support."
  modal_full: "Direct. Under 1500 kcal for\nmen sustained risks:\n- muscle mass loss\n- testosterone reduction\n- chronic fatigue\n- post-diet rebound\n\nClamped target to 1500.\n\nDoctor or RD approved a\nlower number for a specific\ncut? /support, we'll unlock."
```

Это **EN reference**. Каждый язык — cultural adaptation, не literal translation.

---

## Workflow per [ui-translations-bulk-update-recipe](../knowledge/concepts/ui-translations-bulk-update-recipe.md)

10 шагов:
1. **Audit** — verify enum keys нет в БД (`SELECT lang_code FROM ui_translations WHERE content -> 'warning' -> 'bmi' IS NOT NULL;` → 0 rows expected)
2. **Snapshot** — `CREATE TABLE backup_ui_translations_bmi_min_kcal_20260518 AS SELECT * FROM ui_translations;`
3. **Writer subagent (per lang)** — выдать EN reference + Sassy Sage glossary секцию + cultural flags таблицу. Output JSON per lang.
4. **Validation** — JSON parse + length check + enum coverage
5. **Critic subagent (per lang)** — Sassy Sage tone score + cultural flag detection. Auto-reject score <5.
6. **Variant-aware merge** — для AR/FA проверить bidi LRM/RLM markers + ZWNJ
7. **Red-flag scan** — medical-authority phrases (AR/FA/HI/ID), РПП-trigger words, gendered (UK/PL/IT)
8. **Migration NNN_bmi_min_kcal_warnings.sql** — pattern из mig 240 (jsonb_set с sibling-safe merge)
9. **Apply** транзакционно через psycopg2 + verification SELECT
10. **Rollback recipe** в комментариях миграции (`content #- '{warning,bmi}'` + аналог для min_kcal)

---

## L1 + L2 cultural review (mandatory per agent-collaboration-protocol Rule 9)

**L1 (clinical/nutritionist owner):** Sassy Sage tone + clinical accuracy. Flag suspicious phrases.

**L2 (native reviewer per language family):**
- `medical-authority` flag для AR/FA (formal medical register, halal medical advice, Ramadan context для intermittent fasting parallels) → all 7 enums × AR + FA = 14 entries × surfaces
- `medical-authority` flag для HI/ID (caste-aware healthcare, halal/vegetarian-aware nutrition) → hard block only
- `cultural-clean` для RU/EN/DE/FR/IT/ES/PT/PL/UK + informational HI/ID → no L2 required

**Severity matrix per agent-collaboration-protocol Rule 9:**
- hard block / hard regulated = L1 mandatory + L2 mandatory для flagged langs
- informational = L1 mandatory, L2 optional
- silent accuracy = N/A (нет UI)

---

## Coordination

**Mig number:** проверить через `git fetch origin main && ls migrations/ | tail` + `gh pr list --state open` — typical для текущего темпа = mig 255+ (252 banner, 253-254 pregnancy, 255+ свободны).

**Parallel work:**
- Pregnancy mig (#253/254 in flight) — параллельно. Их `pregnancy_warning`/`lactation_warning` enum'ы автоматически render'ятся через mig 252 banner_block как только переводы появятся (та же миграция или отдельная).
- Возможно стоит объединить bmi + min_kcal + maternal в одну гранд-миграцию (12 enums × 4 surfaces × 13 langs ≈ 624 entries) — но это огромная страница. Лучше split: bmi + min_kcal в одной (это уже сделано в mig 246, related), maternal отдельной.

---

## Acceptance criteria

- 351-364 entries в `ui_translations` под `warning.bmi.*` и `warning.min_kcal.*` для 13 lang_codes
- Post-apply SELECT: 13 langs × 7 enums = 91 keys должны быть populated (по `banner_title`)
- Live-test (Telethon или manual): для каждого BMI tier — sentinel user → my_plan → ожидать banner с правильным enum text
- L1+L2 sign-off в PR description

## Связано

- [mig 252_my_plan_safety_guard_banners.sql](../migrations/252_my_plan_safety_guard_banners.sql) — banner injection mechanic
- [mig 240_ui_translations_age_warnings.sql](../migrations/240_ui_translations_age_warnings.sql) — pattern reference (jsonb_set sibling-safe merge)
- [concepts/safety-guard-ux-pattern.md](../knowledge/concepts/safety-guard-ux-pattern.md) §3 severity matrix
- [concepts/sassy-sage-multilingual-glossary.md](../knowledge/concepts/sassy-sage-multilingual-glossary.md) — tone reference
- [concepts/ui-translations-bulk-update-recipe.md](../knowledge/concepts/ui-translations-bulk-update-recipe.md) — 10-step pipeline
