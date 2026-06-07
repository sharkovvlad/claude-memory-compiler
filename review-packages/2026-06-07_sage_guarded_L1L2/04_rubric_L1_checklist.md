---
title: "L1 Cultural Sanity Brief — Чек-лист для нутрициолога"
aliases: [l1-cultural-brief, cultural-sanity-checklist, l1-flag-guide]
tags: [translation, cultural, safety, clinical, l1-review, multilingual]
sources:
  - "concepts/agent-collaboration-protocol.md (Rule 9 L1+L2 model)"
  - "concepts/safety-guard-ux-pattern.md §7 Translation pipeline"
  - "concepts/sassy-sage-multilingual-glossary.md (full per-language reference)"
  - "daily/2026-05-17.md"
created: 2026-05-17
updated: 2026-05-17
---

# L1 Cultural Sanity Brief

Operational checklist для **нутрициолога** при выполнении L1 review (первый layer cultural sanity) над переводами safety guard messaging. Согласно [[concepts/agent-collaboration-protocol]] Rule 9: L1 — clinical + first-pass cultural; L2 — native reviewer per language family, активируется только для flagged keys.

**Цель документа:** дать compact reference что искать в переводе при L1 screening, без необходимости проходиться по всему [[concepts/sassy-sage-multilingual-glossary]] (он >100 KB).

**Pre-flight check для L1 reviewer (one-glance):**
- Severity vocabulary canonical: [[concepts/agent-collaboration-protocol]] Rule 1.
- Translation key naming canonical: [[concepts/agent-collaboration-protocol]] Rule 3.
- Banner emoji prefix matrix: [[concepts/safety-guard-ux-pattern]] §3 (🛡️ hard, ⚠️ soft, 💡 informational). Проверить что `banner_title` начинается с правильного prefix per severity.
- Sassy Sage tone canonical: [[concepts/sassy-sage-multilingual-glossary]] Part I §1-2 (character + universal constraints).

---

## Workflow L1 review

1. Копирайтер возвращает JSON: `{key, lang, text, severity, family}` × N keys × 13 langs.
2. Я (нутрициолог) прохожу каждую запись и помечаю:
   - `cultural-clean` — safe для deploy
   - `cultural-flag-<region>-<topic>` — escalate to L2 native reviewer
3. Flagged keys уходят native reviewer'у (1 из 6 group reviewers, см. ниже).
4. После L2 fix → re-screen → apply в `ui_translations`.

**Tier по severity** (когда L1 mandatory, optional, не нужен):

| Severity | L1 review |
|---|---|
| hard block | **Mandatory** (особенно maternal, age<18, BMI<14) |
| hard regulated | **Mandatory** (BMI<18.5, RED-S) |
| soft override | **Mandatory** (diet break, EA warnings) |
| informational | Glossary self-screen достаточно (но spot-check желателен) |
| silent accuracy | **N/A** (нет user-facing text) |

---

## 6 Language Families — Group Reviewers

| Family | Languages | Common Cultural Risks |
|---|---|---|
| **Romance** | ES, PT, IT, FR | National food protection (FR cuisine, IT pasta, ES jamón, PT bacalhau), formal vs informal register, gender grammar |
| **Germanic** | DE, EN | DE: false friends (`loggen`=server-log not «trekken»), no Befehl/Stasi/DDR; EN: РПП-stigma higher US than UK |
| **Slavic** | RU, PL, UK | RU: directness OK; PL: `zalogować`=sign-in not «log food»; UK: anti-russianism (avoid Russian loanwords) |
| **Arabic-Persian** | AR, FA | Ramadan fasting (don't say «худеть» в Ramadan period), halal medical guidance, RTL bidi (LRM/RLM), FA ZWNJ |
| **Hindi** | HI | Caste-aware healthcare framing, vegetarian default (60% vegetarian), Devanagari script |
| **Indonesian** | ID | Halal context, gender-neutral grammar (bonus — нет gender issues), Ramadan |

---

## Cultural Flag Categories — что искать

### 🔴 Religious / Fasting

| Flag | Trigger | When to flag |
|---|---|---|
| `cultural-flag-AR-ramadan` / `cultural-flag-FA-ramadan` / `cultural-flag-ID-ramadan` | Любое messaging про дефицит / голод / «не ешь» | Если приходит во время Ramadan (LH-Mecca calendar) — нужна mention что recommendations не для fasting hours |
| `cultural-flag-AR-halal` / `cultural-flag-HI-vegetarian` | Любая recommendation еды (например «съешь курицу для протеина») | Avoid pork/beef references; HI default vegetarian |
| `cultural-flag-AR-medical-disclaimer` | hard block / hard regulated messaging | Medical advice в AR странах требует более formal register; «обратитесь к врачу» = «raji'i ila tabib» more formal than colloquial |

### 🔴 Gender / Reproductive

| Flag | Trigger | When to flag |
|---|---|---|
| `cultural-flag-HI-female-health` | maternal/pregnancy messaging для HI юзеров | Pregnancy в Индии — family decision не индивидуальная; framing должен respect this |
| `cultural-flag-AR-female-health` / `cultural-flag-FA-female-health` | maternal/pregnancy messaging для AR/FA юзеров | Privacy higher: «беременна» не публично; messaging должен быть private framing |
| `cultural-flag-ID-female-health` | Same | Similar — Indonesian Muslim majority |

### 🔴 Stigma / Mental Health

| Flag | Trigger | When to flag |
|---|---|---|
| `cultural-flag-HI-stigma-eating` | РПП-related warnings, BMI<18.5 messaging | India: РПП-stigma высокая, использовать medical framing не «у тебя problem» |
| `cultural-flag-JP-stigma-mental` *(не в наших 13, но если добавим JA)* | Mental health hints | Japan reluctant to discuss mental health publicly |
| `cultural-flag-ALL-РПП-trigger` | Любое messaging с words «диета», «худеть», «вес» в hard block / regulated severity | Avoid trigger language; framing «здоровый расчёт» не «диета» |

### 🟠 National Food / Cuisine

| Flag | Trigger | When to flag |
|---|---|---|
| `cultural-flag-FR-cuisine` | Любая critique французской еды (например «избегай круассанов») | FR кухня — национальная гордость; framing «balance» не «избегай» |
| `cultural-flag-IT-pasta` | Critique итальянской pasta / pizza | Same |
| `cultural-flag-ES-PT-traditional` | Critique iberian cuisine (jamón, bacalhau) | Same |

### 🟠 War / Political Context

| Flag | Trigger | When to flag |
|---|---|---|
| `cultural-flag-UK-anti-russian` | Любые Russian loanwords в UA messaging | Avoid `вкусняшка`, `молодец` — украинские эквиваленты обязательны |
| `cultural-flag-DE-historical` | Words like «Befehl», «Stasi», «DDR» | Don't use even in joking context |

### 🟢 Linguistic / Technical

| Flag | Trigger | When to flag |
|---|---|---|
| `cultural-flag-AR-bidi` | Any AR text mixing Latin/Arabic (e.g. «BMI 18.5») | Need LRM/RLM markers, иначе display broken |
| `cultural-flag-FA-zwnj` | FA text с compound words | Need ZWNJ для proper rendering |
| `cultural-flag-DE-false-friend` | DE с words «loggen», «check'en» | False friends — use `tracken` |
| `cultural-flag-PL-false-friend` | PL с word «zalogować» в meaning «log food» | `zalogować` = sign-in; use `zapisać` |
| `cultural-flag-ES-region` | ES words like «coger» (vulgar LatAm), «vale» (Spain only) | Region-neutral choice |
| `cultural-flag-PT-region` | PT-BR vs PT-PT differences | Use PT-PT default или explicit region marker |

---

## L1 Quick-Check Algorithm (для каждой text entry)

```
FOR each {key, lang, text}:
    1. Severity check: silent accuracy → SKIP. Informational → optional. Hard*/soft → mandatory.

    2. Forbidden words check (per family):
       AR/FA/ID + Ramadan window → no "худеть" / "fast" / "skip meal" → flag-ramadan
       UK + Russian loanword → flag-anti-russian
       DE + Befehl/Stasi → flag-historical
       PL + zalogować in food context → flag-false-friend

    3. Sensitive topic check:
       maternal/pregnancy → AR/FA/HI/ID = mandatory flag-female-health
       РПП-trigger words ("диета"/"вес"/"худеть") in hard block → flag-РПП

    4. National food check:
       Any critique of cuisine (avoid X) for FR/IT/ES/PT → flag-cuisine (recommend reframe to "balance")

    5. Technical check:
       AR text with Latin digits → flag-bidi (need LRM/RLM)
       FA compound → flag-zwnj

    6. Tone consistency:
       hard block severity → medical-careful register (not full Sassy Sage casual)
       informational severity → full Sassy Sage OK

    OUTPUT: cultural-clean | cultural-flag-<family>-<topic>(s)
```

---

## Quick Reference Card

**Если торопишься** — самые частые flags по severity:

### Hard block messages (mandatory L1)

| Family | Always flag for |
|---|---|
| AR/FA/HI/ID | maternal-female-health |
| AR/FA/ID | medical-disclaimer (formal register) |
| HI | РПП-stigma-eating |
| ALL | РПП-trigger words in any context |

### Hard regulated messages (mandatory L1)

| Family | Always flag for |
|---|---|
| AR/FA | medical-disclaimer |
| DE | false-friend (`tracken` not `loggen`) |
| PL | false-friend (`zapisać` not `zalogować`) |

### Soft override / Informational

| Family | Optional flag |
|---|---|
| FR/IT/ES/PT | cuisine critique (если присутствует) |
| UK | anti-russianism (always) |

---

## Anti-pattern examples (для tone calibration)

### ❌ ПЛОХО (literal translation + cultural blind)

```
[ES, hard block, maternal pregnancy]
"¡Estás embarazada! No puedes hacer dieta. Cambiamos a mantenimiento."
```
Problems: (1) Tone too casual для hard block medical context. (2) «hacer dieta» = РПП-trigger в LatAm. (3) Exclamation = condescending.

### ✅ ХОРОШО (cultural-aware, medical register)

```
[ES, hard block, maternal pregnancy]
"Para tu seguridad y la del bebé, ajustamos el plan a mantenimiento. Hablar con tu obstetra es importante para personalizar tu nutrición durante el embarazo."
```
Why better: (1) Medical register (`obstetra` specific). (2) Mentions both maternal+fetal safety. (3) Recommends physician (legal cover). (4) No РПП-trigger words.

### ❌ ПЛОХО (informational но не Sassy Sage)

```
[RU, informational, age>75]
"Уважаемый пользователь, обратите внимание, что наши формулы менее точны для вашего возраста."
```
Problems: «Уважаемый пользователь» = corporate stiff, не Sassy Sage. Юзер закроет банер не читая.

### ✅ ХОРОШО (Sassy Sage tone retained)

```
[RU, informational, age>75]
"Слушай, после 75 формулы немного промахиваются — мы знаем. Гериатр уточнит лучше."
```
Why better: Sassy Sage register, направляет к specialist, не condescending.

---

## После L1 — что отдать L2

JSON output для L2 native reviewer:

```json
{
  "key": "warning.maternal.pregnancy_force_maintain.modal_full",
  "lang": "AR",
  "draft_text": "...",
  "l1_flags": ["cultural-flag-AR-medical-disclaimer", "cultural-flag-AR-female-health", "cultural-flag-AR-bidi"],
  "l1_notes": "Maternal hard block — нужен formal medical register, private framing, LRM/RLM markers для mixed Latin/Arabic",
  "severity": "hard block",
  "family": "maternal"
}
```

L2 reviewer возвращает либо `cultural-clean` либо edited version + rationale. После L2 — merge в `ui_translations`.

---

## Связанные концепты

- [[concepts/agent-collaboration-protocol]] — Rule 9 L1+L2 model
- [[concepts/safety-guard-ux-pattern]] — §7 Translation pipeline
- [[concepts/sassy-sage-multilingual-glossary]] — full per-language reference (deep dive)
- [[concepts/pregnancy-lactation-clinical-spec]] — example messaging для maternal (hard block)
