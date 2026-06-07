---
title: "JSONB Shallow Merge Anti-Pattern — `content || payload` wipes nested namespaces"
aliases: [jsonb-shallow-merge, content-pipe-payload, mig-359-recovery]
tags: [migration, jsonb, anti-pattern, i18n, p0-incident, lessons-learned]
sources:
  - "migrations/359_phase3d_cycle_in_onboarding.sql (root cause)"
  - "migrations/360_recovery_buttons_onboarding.sql (recovery)"
  - "daily/2026-05-26.md (incident timeline)"
  - "handover/2026-05-26_p0_recovery_session_close.md"
created: 2026-05-26
status: active
severity: P0-prevention
---

# JSONB Shallow Merge Anti-Pattern

> **TL;DR.** Never write `content = content || payload` when `payload` contains top-level keys whose VALUES are objects that need to merge deeply. The `||` operator REPLACES top-level keys — it doesn't recurse. This wiped ~200 buttons + ~100 onboarding keys × 13 langs in mig 359 (2026-05-26 P0 incident).

## What broke (2026-05-26 ~04:00 MSK)

Mig 359 (Phase 3d onboarding cycle question) included this UPDATE:

```sql
WITH new_strings AS (VALUES
  ('ru', $i18n$ {
    "onboarding": { "cycle_question_title": "...", "cycle_explain_body": "..." },
    "buttons":    { "onb_cycle_yes": "...", "onb_cycle_skip": "...", "onb_cycle_explain": "..." }
  } $i18n$::jsonb),
  ... 13 langs ...
)
UPDATE public.ui_translations ut
   SET content = ut.content || ns.payload    -- ← THE BUG
  FROM new_strings ns
 WHERE ut.lang_code = ns.lang_code;
```

The intent was: «deep-merge the new keys into existing buttons + onboarding namespaces».

The reality of `||` in PostgreSQL JSONB:
- Top-level keys in payload **replace** corresponding top-level keys in content.
- The replacement is **complete object substitution**, not field-wise merge.
- So `content->'buttons'` (containing ~200 keys) was replaced with payload's `buttons` (containing just 3 keys: `onb_cycle_yes/skip/explain`).

**Impact:** 182 `ui_screen_buttons` with `text_key LIKE 'buttons.%'` rendered as raw text_key strings to users. Bot UI broken across the entire fleet in 1 transaction.

## Why this is easy to miss

The `||` operator name suggests "concatenate" or "merge". In flat key-value scenarios it works correctly. The trap fires only when:
- Payload has top-level keys that are themselves **objects** (not scalars)
- Content already has matching top-level keys you want to **preserve adjacent leaves of**

For example, this works perfectly fine (top-level keys are scalars):
```sql
content = '{"name":"Vlad","age":40}'
content || '{"age":41}'::jsonb
-- result: {"name":"Vlad","age":41}  ✓ age updated, name preserved
```

But this loses data (top-level key is an object):
```sql
content = '{"profile":{"name":"Vlad","age":40}}'
content || '{"profile":{"age":41}}'::jsonb
-- result: {"profile":{"age":41}}  ✗ name LOST — top-level "profile" replaced wholesale
```

## Three safe alternatives

### (a) `jsonb_set` per leaf (mig-by-mig, idempotent)

```sql
UPDATE ui_translations
   SET content = jsonb_set(content, '{buttons,onb_cycle_yes}', '"✨ Да, настроить"'::jsonb, TRUE)
 WHERE lang_code = 'ru';
-- one row UPDATE per (lang, namespace, key) triplet
```

Pros: granular, easy to revert, can be re-applied repeatedly.
Cons: verbose for bulk inserts (one statement per leaf).

### (b) `jsonb_set` with full namespace object (replace entire namespace)

```sql
UPDATE ui_translations
   SET content = jsonb_set(
       jsonb_set(content, '{buttons}', '{...complete-buttons-obj...}'::jsonb),
       '{onboarding}', '{...complete-onboarding-obj...}'::jsonb
   )
 WHERE lang_code = 'ru';
```

Pros: compact (one statement per lang), suitable for recovery / re-seed.
Cons: caller must KNOW the complete namespace content (anything missing gets lost).
**Use this only when you have a verified complete object.**

### (c) `jsonb_each LATERAL` + `jsonb_set` with `coalesce(content->ns, '{}') || inner_obj` (deep-merge via leaf-level `||`)

```sql
WITH new_strings AS (VALUES
    ('ru', $i18n$ { "buttons": {...}, "onboarding": {...} } $i18n$::jsonb),
    ...
),
expanded AS (
    SELECT ns.lang_code,
           each.ns_key      AS namespace,
           each.ns_value    AS inner_payload
      FROM new_strings ns,
           LATERAL jsonb_each(ns.payload) AS each(ns_key, ns_value)
)
UPDATE ui_translations ut
   SET content = jsonb_set(
       ut.content,
       ARRAY[expanded.namespace],
       COALESCE(ut.content -> expanded.namespace, '{}'::jsonb) || expanded.inner_payload,
       TRUE
   )
  FROM expanded
 WHERE ut.lang_code = expanded.lang_code;
```

Pros: handles bulk multi-lang multi-namespace payloads compactly + safely.
**The `||` here is at LEAF level — between two flat key=value objects (`buttons.X → string`).** That's the intended shallow-merge use case, no data loss.
Cons: more complex SQL. Worth it when seeding multiple namespaces × multiple langs in one mig.

## Detection heuristics for code review

When reviewing a migration that writes to `ui_translations.content` (or any JSONB column with nested namespaces):

1. **Grep for `|| .*::jsonb` and `content ||`.** Stop reading; verify what's on the RHS.
2. If RHS has any key whose value is `{` (an object): **REJECT**. Demand pattern (a), (b), or (c) above.
3. If RHS is a flat scalar payload (`{"key":"value","key2":42}`) and target's top-level keys aren't objects: `||` is acceptable.

## CI guard (TODO — preventative, not yet implemented)

Add a pre-merge check on `migrations/*.sql`:
```bash
grep -nE "content\s*\|\|\s*('|\$|jsonb)" migrations/$1 | \
  grep -vE "(--|coalesce.*->|inner)" && \
  echo "::warning::potential shallow-merge anti-pattern (concept: jsonb-shallow-merge-antipattern)"
```
Flag for human review, not auto-block. Document the FIVE accepted exceptions inline (coalesce-inner, scalar-only, etc).

## Related concepts

- [[ui-translations-bulk-update-recipe]] — canonical seed/update workflow (10-step pipeline)
- [[safe-create-or-replace-recipe]] — sister recipe for RPC mutations
- [[pre-migration-discovery-recipe]] — pull live state before touching
- [[agent-collaboration-protocol]] — §Rule on subagent SQL review (links here)

## Incident record

| When | Mig | Symptom | Impact | Recovery |
|---|---|---|---|---|
| 2026-05-26 04:00 MSK | 359 (worktree-applied, no PR) | content->'buttons' + 'onboarding' wiped to 3+2 keys × 13 langs | 182 buttons rendered raw text_key | mig 360: multi-pattern parser → 5 SQL patterns reconstructed → hand-crafted gaps → jsonb_set per leaf |

**Time-to-detect:** 5h (between apply 04:00 and owner UAT noticing). Owner reported via screenshot.
**Time-to-recover:** ~2h (parser dev + hand-craft + apply + verify).

Could have been prevented by:
- Code review of mig 359 SQL before authorizing subagent's `apply LIVE` (this is the human-side fix → see [[agent-collaboration-protocol]])
- CI grep check (preventative, TODO above)
- Knowing this anti-pattern at write-time (this concept doc).

## Gotcha: CI guard грепает и комментарии (2026-06-07, mig 487)

CI-чек «Scan migrations for `content || payload`» — это **текстовый grep**, не SQL-парсер. Он фейлит PR, если паттерн `content ||` встречается в файле **где угодно**, включая SQL-комментарии. mig 487 имел строку-комментарий `-- … NEVER content || … (shallow-merge guard)` (описывал, что мы НЕ делаем) → чек упал, хотя сам SQL чист (`jsonb_set`). Фикс — переформулировать комментарий без литерала `content ||` («no whole-object shallow merge»). **Durable: не упоминай запрещённый паттерн дословно даже в комментарии-объяснении.**
