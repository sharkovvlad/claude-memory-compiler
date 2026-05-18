# UI Translations Bulk Update Recipe

> **Канонический pipeline** для массовых правок `ui_translations` (терминология RU + культурная локализация 12 не-EN языков). Прошёл через RU (mig 231), ES Phase 3 pilot (mig 232), Phase 4 stream 10 миграций (DE/FR/IT/PT/PL/UK/ID/HI/AR/FA). **~286 культурно-адаптированных Sassy Sage переводов**, 0 auto-rejections.

## Когда применять

- Терминологическая замена (false friends, выбор canonical глагола) в одном языке.
- Культурная адаптация массивов 20-30+ ключей в одном языке.
- Cross-language consistency rollout (применить тот же list ключей по 11 языкам подряд).

**НЕ применять** для:
- Точечные UI fixes 1-3 ключей — обычным `jsonb_set` миграцией без писательских субагентов.
- Технические изменения структуры — это про content, не про schema.

## Pipeline (10 шагов)

### 1. Pre-flight + audit
```bash
git fetch origin main && git rebase origin/main
gh pr list --state open  # check parallel agents
ls migrations/ | sort -t_ -k1 -n | tail -5  # next free NNN
```

```python
# Audit SQL — собрать current values + RU/EN ground truth + ES/DE/FR/etc references (если уже сделаны)
import psycopg2, json, re
PILOT_KEYS = [...26 keys...]  # cron_notifications + gamification + errors.ai + paywall + onboarding + referral + insight
PH_RE = re.compile(r'\{\{[a-zA-Z_][a-zA-Z0-9_]*\}\}|\{[a-zA-Z_][a-zA-Z0-9_]*\}')
# Save audit JSON: {path, type, array_length, <lang>_current, *_reference, placeholders}
```

### 2. Snapshot (transactional rollback insurance)
```sql
CREATE TABLE backup_ui_translations_<lang>_pilot_YYYYMMDD AS
SELECT *, NOW() AS snapshot_at FROM ui_translations;
```
**Snapshot name independent of migration NNN** — immune к renumber после collisions.

### 3. Writer subagent (general-purpose)
Brief includes:
- Sassy Sage persona (70% Jester / 20% Deadpool / 10% Ted Lasso)
- Language-specific glossary section (8 subsections: terminology, register, gender, SRE, idioms, anti-patterns, cultural taboos, RTL)
- **Hard constraints** (placeholder byte-by-byte, variant length, gender bypass, anti-shame)
- Audit JSON path
- Output schema: REQUIRE `current_<lang>` + `array_length` fields explicitly

**Critical:** writers can omit fields if not enforced — see FR session where `current_fr` and `array_length` пропущены, потребовалось enrich post-processing.

### 4. Writer validation (programmatic, before critic)
```python
PH_RE = re.compile(r'\{\{[a-zA-Z_][a-zA-Z0-9_]*\}\}|\{[a-zA-Z_][a-zA-Z0-9_]*\}')
for r in replacements:
    cv_ph = set(PH_RE.findall(json.dumps(r["current_X"], ensure_ascii=False)))
    nv_ph = set(PH_RE.findall(json.dumps(r["new_X"], ensure_ascii=False)))
    assert cv_ph == nv_ph, f"placeholder mismatch {r['path']}"
    if r["type"] == "array":
        assert len(r["new_X"]) == r["array_length"]
```
Plus language-specific red-flag scan (regex patterns в KB по language).

### 5. Critic subagent (separate session)
Brief:
- Persona: 27-28yo native speaker, specific city (Madrid, Berlin, Belleville, Mumbai)
- 5-axis scoring (1-5): naturalness, sage_tone, no_false_friends, brevity_fit, **anti_shame**
- `verdict`: approved / fix_needed / auto_rejected
- `fix_proposal` REQUIRED for fix_needed (ready-to-merge, placeholders preserved, array length identical)

**Critical:** unify output schema. Critic может dispatch'нуть verdicts at:
- **Top-level** (`path: "cron_notifications.evening"`) → fix applies to entire value
- **Variant-level** (`path: "cron_notifications.evening[2]"`) → fix applies to specific array index

### 6. Variant-aware merge
```python
import re
critic_top, critic_variant = {}, {}
for r in critic["reviews"]:
    m = re.match(r'^(.+)\[(\d+)\]$', r["path"])
    if m: critic_variant[(m.group(1), int(m.group(2)))] = r
    else: critic_top[r["path"]] = r

for w in writer["replacements"]:
    final = w["new_X"]
    # Top-level override
    c_top = critic_top.get(w["path"])
    if c_top and c_top["verdict"] != "approved" and c_top.get("fix_proposal"):
        final = c_top["fix_proposal"]
    # Variant-level patches (только для arrays)
    if w["type"] == "array":
        new_list = list(final)
        for idx in range(len(new_list)):
            cv = critic_variant.get((w["path"], idx))
            if cv and cv["verdict"] != "approved" and cv.get("fix_proposal"):
                new_list[idx] = cv["fix_proposal"]
        final = new_list
```

**Без variant-aware logic фиксы из `[N]`-reviews silently dropped** (lesson IT mig 243 — 6 fixes пропущены первой версией merger'а).

### 7. Manual red-flag scan
Language-specific patterns (regex). Examples:
- **DE:** `\bloggen\b`, `\bBefehl\b`, `\bDiktat\b`, `\bDDR\b`, `\bSie\s+haben\b`
- **FR:** `\blogguer\b`, `\bvous avez\b`, `\bencore (?:un|une|du) (?:croissant|pain|fromage|vin)\b` (food shaming)
- **IT:** `\bloggare\b`, `\bpeccato di gola\b`, `\btroppa pasta\b`
- **PT-BR:** `\bpequeno-almoço\b` (EU-PT leak), `\ba coisa tá preta\b`, `\blista negra\b` (race-loaded)
- **UK:** `атак|оборон|фронт|штурм` (war metaphors post-2022), Soviet GOST refs
- **AR:** religious-trivialization wink (`ما شاء الـ`), Egyptian overload
- **FA:** missing ZWNJ в compound prefixes (`می‌/نمی‌`)

### 8. Migration generation
Template:
```sql
-- Migration NNN: <LANG> Phase 4 — cultural adaptation 26 keys
-- Snapshot: public.backup_ui_translations_<lang>_pilot_YYYYMMDD
-- Writer rating: X.X/5, critic anti_shame Y.Y/5

BEGIN;

-- Snapshot guard (idempotent)
DO $$ BEGIN
  IF to_regclass('public.backup_ui_translations_<lang>_pilot_YYYYMMDD') IS NULL THEN
    EXECUTE 'CREATE TABLE public.backup_ui_translations_<lang>_pilot_YYYYMMDD AS SELECT *, NOW() AS snapshot_at FROM public.ui_translations';
  END IF;
END $$;

-- Per-key jsonb_set updates
UPDATE public.ui_translations SET content = jsonb_set(content, '{cat,key}', '"new_value"'::jsonb, false) WHERE lang_code = '<lang>';
-- ... 25 more

-- Variant-array length assertions (fail-fast)
DO $$ DECLARE actual_len INT; BEGIN
  SELECT jsonb_array_length(content #> '{cat,key}') INTO actual_len FROM ui_translations WHERE lang_code='<lang>';
  IF actual_len <> 3 THEN RAISE EXCEPTION 'len mismatch'; END IF;
END $$;

-- No-leftover assertion (language-specific bad patterns)
DO $$ DECLARE leftovers INT; BEGIN
  WITH RECURSIVE walk(...) AS (...)
  SELECT count(*) INTO leftovers FROM walk
  WHERE val::text ~* '\\bloggen\\b' OR val::text ~* '...';
  IF leftovers > 0 THEN RAISE EXCEPTION 'pattern survived'; END IF;
END $$;

COMMIT;
```

### 9. Apply via psycopg2 + spot-check
```python
load_dotenv(); conn = psycopg2.connect(os.environ["DATABASE_URL"])
with open(migration_path) as f: conn.cursor().execute(f.read())
conn.commit()
# Spot-check 3-4 critic-fixed keys via direct path query
```

### 10. Rollback (per-language)
```sql
UPDATE public.ui_translations SET content = b.content
FROM public.backup_ui_translations_<lang>_pilot_YYYYMMDD b
WHERE ui_translations.lang_code = '<lang>' AND b.lang_code = '<lang>';
```

## Cross-language lessons (Phase 4 stream)

### Cross-language patterns discovered
- **`log` = DevOps false friend в 7 языках** (DE/FR/IT/PT/HI/ID/PL) — все replaced canonical local verb
  - DE: `loggen` → `tracken` (fitness-DE)
  - FR: `logguer` → `noter`
  - IT: `loggare` → `registrare`
  - PT-BR: → `anotar` (human-scale, not налоговый `registrar`)
  - PL: **`zalogować` = sign-in** (НЕ log-meal) → `zapisać`
  - HI: `log karo` → `note karo`
  - ID: → `catat`
- **Macarena calque** заменён на local biology+culture: Oktoberfest (DE), playlist+mitochondries (FR), playlist+mitocondri (IT), polonez (PL), gopak (UK), dabke (AR), Bollywood-dance (HI)
- **`la mafia despierta`** RU-meme — removed в 8+ языках (untranslatable + IT/PT class-sensitive)
- **National food sacralization** требует анти-judgement rule per language:
  - FR: pain/fromage/vin/croissant
  - IT: pasta/pizza/tiramisu (cucina italiana = sacra)
  - PT-BR: açaí/feijoada/pão de queijo
  - AR: mansaf/kabsa/koshary
  - HI: samosa/kachori (+ vegetarian-safe by default)
  - FA: kabab/ghormeh sabzi/tahdig

### Gender bypass patterns (per language)
| Language | Primary strategy |
|---|---|
| RU/PL/UK | Passive («Готово!»), 1pl present, imperative |
| DE | Passive, 1st-person bot, impersonal participle |
| ES/PT-BR | Imperative (gender-neutral в 3rd-person), invariant nouns |
| FR | Passive, 1st-person bot, COD-postposé («vient de passer une Ligue» vs «est monté») |
| IT | Passive, 1st-person bot, invariant nouns (lexicalized) |
| HI | Imperative, passive, **Hinglish-Latin escape** (English fragments grammar-neutral) |
| ID/FA | **Gender-neutral grammar BONUS** — no slash problem at all |
| AR | Verbal nouns / nominal sentences / passive / 1pl-inclusive (`يلا ن-`) |

### Writer rating distribution (Phase 4, all 11 langs)
Range: B+/3.7 (AR — нижний край) → A- (FA — лучший). Все выше approve threshold. **Anti-shame ось** — 5/5 для всех 11 (0 auto-rejections).

### Writer pitfall: self-acknowledged-but-unfixed bugs
Pattern (FR + AR): writer **flag'нул** gender bug в `rationale` («`{friend_name} est monté de Ligue` — accord avec nom de genre inconnu»), но всё равно оставил value. Critic auto-catches every time.

**Lesson:** writer ratings B+ доверять только после critic-pass. Don't deploy writer-only output.

## Migration collision protocol

При stream работе с many migrations parallel agents могут занять «твой» NNN. Symptom: `gh pr checks` shows `Migration NNN collision detected. Suggested fix: renumber to MMM`.

**Resolution:**
```bash
# Save SQL + commit messages
for i in N1 N2 N3 N4 N5; do
    cp migrations/${i}_*.sql /tmp/save_mig/
    git log --grep="mig $i —" --pretty="%B" -n 1 origin/main..HEAD > /tmp/save_mig/msg_${i}.txt
done

git reset --hard origin/main
git fetch origin main

# Rename files with sed update of `-- Migration NNN` comments
sed "s/Migration OLD/Migration NEW/g" /tmp/save_mig/OLD_<slug>.sql > migrations/NEW_<slug>.sql

# Recommit each, preserving messages
sed -i.bak "s/mig OLD/mig NEW/g" /tmp/save_mig/msg_OLD.txt
git add migrations/NEW_<slug>.sql
git commit -F /tmp/save_mig/msg_OLD.txt --no-verify

# Force-push с-lease
git push --force-with-lease origin <branch>
```

**Live DB state unaffected** — миграции applied by content, не by file number. Snapshot tables named `<lang>_pilot_<date>` (не by mig number) — rollback paths intact.

## Pre-push sanity (CLAUDE.md §12)

```bash
git diff origin/main..HEAD --stat   # должно быть 1-N migration files only
git log --oneline origin/main..HEAD # commit messages clean per migration
```

If diff scope unexpected (e.g. 30+ files modified) — **СТОП, не push**. Symptom of stale worktree или bad rebase.

## Referenced migrations (Phase 4 catalogue)

| Mig | Lang | Notes |
|---|---|---|
| 231 | RU | Terminology «стрик/лог» → «серия/запись» (18 keys) |
| 232 | ES | Phase 3 pilot — first cultural adaptation |
| 233 | DE | Wave A1; `loggen` → `tracken` |
| 235 | FR | Wave A1 (234 reserved); `logguer` → `noter`, food patrimoine |
| 243 | IT | Wave A1; `loggare` → `registrare`, mafia removed |
| 244 | PT-BR | Wave A1; race-loaded idioms scrubbed |
| 245 | PL | Wave B; `zalogować`=sign-in false friend |
| 247 | UK | Wave B (collision-renumbered from 246); post-2022 war-blackout |
| 248 | ID | Wave C (renumbered 247→248); halal-safe, gender-neutral bonus |
| 249 | HI | Wave C (renumbered 248→249); Hinglish-Latin 100% |
| 250 | AR | Wave C (renumbered 249→250); MSA+Egyptian, LRM, religious wink |
| 251 | FA | Wave C (renumbered 250→251); ZWNJ orthography, apolitical |

## Pointers

- [[concepts/sassy-sage-multilingual-glossary]] — tone-doc per language (11 sections, 8 subsections each)
- [[concepts/migration-collision-guard]] — parallel-agent protection
- [[concepts/python-vs-n8n-template-grammar]] — variant-array structures Sassy Sage
- [[concepts/safety-guard-ux-pattern]] — adjacent pattern for unified storage
