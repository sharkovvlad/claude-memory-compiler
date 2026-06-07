---
title: "Copywriter Playbook — single entry point для translation sessions"
aliases: [copywriter-playbook, translations-playbook, copywriter-entry-point]
tags: [translations, ux, copywriter, kb-index, playbook]
sources:
  - "concepts/agent-collaboration-protocol.md"
  - "concepts/safety-guard-ux-pattern.md"
  - "concepts/sassy-sage-multilingual-glossary.md"
  - "concepts/ui-translations-bulk-update-recipe.md"
  - "concepts/l1-cultural-sanity-brief.md"
  - "handover/2026-05-17_mig234_copywriter_brief.md"
  - "handover/2026-05-18_bmi_min_kcal_copywriter_brief.md"
  - "daily/2026-05-15.md … 2026-05-18.md"
created: 2026-05-18
updated: 2026-06-01
---

# Copywriter Playbook

**Single entry point** для любой copywriter / translation session в NOMS. Раньше знание было разбросано по 5+ KB-документам + 2 handover'ам — этот файл — индекс, не дубль. Если правка нужна — иди в canonical файл, не сюда.

## Когда использовать этот документ

Перед любой translation session, который пишет / меняет / адаптирует `ui_translations` ≥1 ключа на ≥2 языка:

- Safety guard warning messages (bmi/min_kcal/pregnancy/red_s/diet_break/age)
- Cultural localization passes (Phase 4 stream pattern)
- Terminology migrations (Phase 1 «стрик → серия» RU pattern)
- Onboarding / paywall / gamification rewrites

**НЕ нужен** для:
- Точечный fix 1-3 ключей в одном языке без cultural concern → `jsonb_set` миграция, без playbook.
- Структурные изменения (новые `ui_screens`, `ui_screen_buttons`) — это headless architecture, не copy.

## 0. Pre-flight (5 min, обязательно)

```bash
git fetch origin main && git rebase origin/main
gh pr list --state open                              # parallel agents?
ls migrations/ | sort -t_ -k1 -n | tail -5           # next free NNN (см. также Rule 7)
```

Прочитать (в этом порядке):
1. Текущий `daily/YYYY-MM-DD.md` (что происходило сегодня).
2. Этот playbook (refresh).
3. Task-specific brief (если есть handover).

## 1. Canonical sources — что где живёт

| Тема | Canonical file | Что владеет |
|---|---|---|
| **Severity vocabulary** (5-tier: hard block / hard regulated / soft override / informational / silent accuracy) | [[concepts/agent-collaboration-protocol]] §Rule 1 | Определение, override-поведение, opt-out matrix |
| **Translation key naming** (`warning.<family>.<severity>.<surface>`) | [[concepts/agent-collaboration-protocol]] §Rule 3 | Format, snake_case, storage schema |
| **Banner UX + emoji prefix** (🛡️ hard / ⚠️ soft / 💡 informational / 🌿 elderly variant) | [[concepts/safety-guard-ux-pattern]] §3 | Banner color, emoji prefix, dismissibility |
| **5 surfaces** (banner_title, banner_body, modal_full, opt_out_confirm, auto_resolved) | [[concepts/safety-guard-ux-pattern]] §5 | Length budgets, when surface present/absent |
| **Sassy Sage tone — universal** (character, 3-role mix, 4 principles) | [[concepts/sassy-sage-multilingual-glossary]] Part I §1 | Persona DNA — не менять без owner |
| **Universal constraints** (Telegram SRE, gender bypass, anti-shame, РПП) | [[concepts/sassy-sage-multilingual-glossary]] Part I §2 | Technical + ethical gates |
| **Per-language tone** (11 sections: DE/FR/IT/PT/ES/PL/UK/ID/HI/AR/FA) | [[concepts/sassy-sage-multilingual-glossary]] Part II | 8 subsections each: terminology / register / gender / SRE / idioms / anti-patterns / cultural taboos / RTL |
| **10-step apply pipeline** | [[concepts/ui-translations-bulk-update-recipe]] | Audit → Snapshot → Writer → Validate → Critic → Variant-aware merge → Red-flag scan → Migration → Apply → Rollback |
| **L1 cultural review checklist** | [[concepts/l1-cultural-sanity-brief]] | Flag categories, 6 family-reviewers, 6-step algorithm, anti-pattern examples |
| **L2 native review** (when, who) | [[concepts/agent-collaboration-protocol]] §Rule 9 | Tier matrix per severity, 6 reviewers max |
| **Dialog variants** (JSONB array[3], deep-merge, random-pick) | [[concepts/sassy-sage-dialog-variants]] | Variant-array structure (different from scalar) |

## 2. Decision flow — what kind of session am I in?

```
                       ┌── New safety guard mig applied?
                       │   ├── Yes → see [[concepts/safety-guard-ux-pattern]] §10 reusability table,
                       │   │         build translation set warning.<family>.<severity>.<surface>×13 langs
                       │   │         Severity drives L1/L2 tier (Rule 9), banner emoji (§3).
                       │   │         Example: bmi/min_kcal handover 2026-05-18.
                       │   └── No → continue ↓
                       │
                       ├── Cultural localization (existing keys, multi-lang)?
                       │   ├── Yes → [[concepts/ui-translations-bulk-update-recipe]] 10-step.
                       │   │         Phase 4 stream pattern (DE→FR→IT→PT→PL→UK→ID→HI→AR→FA).
                       │   └── No → continue ↓
                       │
                       └── Single-lang terminology pass (RU «стрик→серия»)?
                           └── Yes → Same 10-step pipeline, single lang scope. Phase 1/2 RU pattern.
```

## 3. Always-mandatory rules (checklist before writer subagent spawn)

- ✅ Severity per guard (Rule 1 vocab, no synonyms «medium»/«warning»/«alert»)
- ✅ Translation key format `warning.<family>.<severity>.<surface>` (Rule 3)
- ✅ Banner emoji prefix in `banner_title` per §3 matrix
- ✅ 5 surfaces accounted for: which present, which N/A (e.g. `opt_out_confirm` N/A для hard block; `auto_resolved` N/A для elderly_less_accurate)
- ✅ Sassy Sage tone (universal § + per-lang section in glossary)
- ✅ Telegram SRE budgets per surface (banner_title ≤40, banner_body ≤140, modal_full ≤12 lines × ≤35 chars, button ≤18)
- ✅ Gender bypass strategy per language (table in [[concepts/ui-translations-bulk-update-recipe]] "Gender bypass patterns" + per-lang section в glossary)
- ✅ L1 mandatory pre-deploy для hard block / hard regulated / soft override; informational glossary-self-screen OK
- ✅ **«Streak»/«стрик» НЕ транслитерировать в non-EN** (owner rule 2026-06-01). Слово `streak` допустимо ТОЛЬКО в `en`; в остальных 12 языках транслит («стрик», «стрік») не несёт смысловой нагрузки → использовать смысловой эквивалент: RU «серия дней» / «дней в ударе», UK «серія», DE «Serie», ES «racha», FR «série», и т.д. Тот же принцип для любых англицизмов-без-смысла. См. §5.
- ✅ Snapshot before apply: `backup_ui_translations_<scope>_<date>` (immune к mig# renumber)
- ✅ Pre-push sanity: `git diff origin/main..HEAD --stat` (cap diff scope, abort if чужие файлы — см. [[concepts/release-protocol]] и Rule 7)

## 4. Output deliverables (canonical per ui-translations-bulk-update-recipe)

Per session:
1. **Audit JSON** — `tools/<scope>_audit_<date>.json` (current values + reference data + placeholders)
2. **Writer JSON** — `tools/<scope>_writer_<date>.json` (replacements with `new_<lang>`, `current_<lang>`, `array_length`)
3. **Critic JSON** — `tools/<scope>_critic_<date>.json` (verdict + 5-axis score + fix_proposal for non-approved)
4. **Migration file** — `migrations/NNN_<scope>_<lang>.sql` (jsonb_set + snapshot guard + leftover-pattern assertion + COMMIT)
5. **Apply trace** — psycopg2 transactional apply + spot-check SELECT 3-4 keys
6. **PR description** — writer rating, critic anti-shame avg, # cultural flags, snapshot table name, rollback recipe

## 5. Known cross-language insights (don't re-discover)

- **`log` = DevOps false friend в 7 языках** — DE `loggen`/`tracken`, PL `zalogować`=sign-in/`zapisać`, FR `logguer`/`noter`, IT `loggare`/`registrare`, PT-BR/`anotar`, HI/`note karo`, ID/`catat`.
- **`streak`/«стрик» — англицизм-пустышка в non-EN** (owner rule 2026-06-01). Транслит «стрик/стрік» = ноль смысла для носителя. EN-only; везде ещё — смысловой эквивалент («серия дней», «дней в ударе», «racha», «Serie», «série»). Обобщение Phase 1 RU-паттерна «стрик→серия» на все языки.
  - **Конвейер mig 413 (2026-06-01, PR #269) — 3 execution-урока:**
    1. **Live-аудит сужает scope.** Задание было «11 langs», live-греп `ui_translations` дал транслит лишь в **5** (de/fa/hi/id/uk, 16 ключей, 61 строка). ar/es/fr/it/pl/pt/ru уже были compliant. Не верь априорному списку — грепай прод (вырезав плейсхолдеры `{...}`/`{tr:...}`/`{icon_streak}`, иначе 240+ false positives на именах ключей).
    2. **Целевое слово бери из уже-compliant ключей того же языка** (не выдумывай): de→Serie (из `profile_gamification.streak`), uk→серія, id→runtun (из `beruntun`), fa→رکورد, hi→सिलसिला/silsila. Даёт внутреннюю консистентность бесплатно.
    3. **Смена слова меняет грамматический род → правь согласования.** de m→f (dein→deine, den→die, er→sie), uk m→f (пішов→пішла, його→її), hi f→m (ki→ka, gayi→gaya, latki→latka, आपकी…की→आपका…का, अपनी→अपना). Замена одного существительного «насухо» ломает грамматику предложения.
  - **Naturalized давний loanword ≠ свежий геймерский англицизм.** fa `رکورد` (record, полностью натурализован, в персидской графике) допустим как замена, в отличие от свежего `استریک`. Правило бьёт по бессмысленному транслиту, не по любым заимствованиям.
- **Gender-neutral grammar BONUS:** ID + FA — нет gender в глаголах, prosaдает «slash problem» полностью.
- **Hinglish-Latin escape для HI:** 100% Latin script — gender escape + Devanagari SRE relief одновременно.
- **AR LRM/RLM markers критичны** для mixed Latin/Arabic (BMI 18.5 в AR text).
- **FA ZWNJ (U+200C)** обязателен в compound prefixes (می‌خواهم, می‌شه). Без — text rendering broken.
- **UK anti-russianism via read-aloud test** — RU-loanwords automatic fail.
- **War-blackout UK post-2022:** no `атак/оборон/фронт/штурм` metaphors.
- **National food sacralization** (anti-judgment): FR pain/fromage/vin, IT pasta/pizza, PT-BR açaí/feijoada, AR mansaf/kabsa, HI samosa/dal, FA kabab/tahdig.
- **Macarena calque** removed в 11 langs → local biology+culture (Oktoberfest DE, polonez PL, gopak UK, dabke AR, Bollywood HI).

## 6. Anti-patterns (do NOT)

- ❌ Google Translate / DeepL без cultural pass
- ❌ Slash gendered forms (`listo/a`, `zrobiłeś/aś`) — use passive/1st-person/imperative
- ❌ Shaming weight / body / food choice — НИКОГДА
- ❌ `opt_out_confirm` для hard block (нет self-consent)
- ❌ Skip emoji prefix в banner_title — visual cue теряется
- ❌ Apply без snapshot — нет rollback path
- ❌ Apply из worktree без `git rebase origin/main` (см. CLAUDE.md §12)
- ❌ `./deploy.sh` (этот flow — translation only; deploy via PR + GitHub Actions auto-deploy)

## 7. Active scope on 2026-05-18

| Family | Status | Mig | Translation entries | Notes |
|---|---|---|---|---|
| `age` (3 enums × 4 surfaces × 13) | ✅ Applied | 240/241/242 | 156 (143 + 13 N/A) | Reference pattern; mig 234 was first |
| `bmi` (4 enums × 4 surfaces × 13) + `min_kcal` (3 enums × 4 surfaces × 13) | ⏳ Pending copywriter | 246 (RPC live) | ~351 entries | Brief: [[handover/2026-05-18_bmi_min_kcal_copywriter_brief]] |
| `pregnancy` / `lactation` | ⏳ Blocked on UX wireframe | P0.6 | TBD | Clinical spec ready: [[concepts/pregnancy-lactation-clinical-spec]] |
| Phase 4 cultural localization (11 langs) | ✅ Applied | 232-251 | ~286 keys | Pipeline mature; 0 auto-rejections |
| `red_s` / `diet_break` / Schofield/Lührmann silent accuracy | 📋 Backlog | P1/P2 | TBD | See [[concepts/calc-user-targets-roadmap]] |

## 8. Когда что НЕ работает по этому playbook'у — escalate

- Conflict с другим agent (Rule 6) → 🚨 owner + KB fixation.
- Severity ambiguous (не уверен hard regulated vs soft override) → нутрициолог clinical decision.
- Cultural taboo не покрыт glossary → flag к L2 native + дополнить glossary §7 per-lang.
- Banner emoji prefix не работает (some surface где prefix не уместен) → KB edit в [[concepts/safety-guard-ux-pattern]] §3 (с owner approval).

## Связано

- [[concepts/agent-collaboration-protocol]] — 10 правил multi-agent coordination (Rule 1/3/9 most-cited here)
- [[concepts/safety-guard-ux-pattern]] — UX framework (severity → banner/emoji/opt-out)
- [[concepts/sassy-sage-multilingual-glossary]] — tone per 11 languages
- [[concepts/ui-translations-bulk-update-recipe]] — 10-step apply pipeline
- [[concepts/i18n-cldr-plural-runtime]] — `{N word}` через babel CLDR; placeholder `{streak_days_word}` / `{count_word}` вместо запечённой literal-формы для langs с >1 категории (ru/uk/pl/ar/es/fr/it/pt). При тексте с числом + существительным — используй helper, не пиши «{N} дней» в шаблоне.
- [[concepts/l1-cultural-sanity-brief]] — L1 reviewer operational checklist
- [[concepts/migration-collision-guard]] — parallel-agent NNN-protection
- [[concepts/release-protocol]] — git discipline (rebase ДО commit, sanity-check ДО push)
