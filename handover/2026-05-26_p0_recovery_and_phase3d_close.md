# Handover — P0 recovery + Phase 3d cycle UX закрыт

**Date:** 2026-05-26
**From:** Agent nervous-cerf-566d7a (session 8, продолжение Phase 3 sprint)
**To:** Next agent

---

## TL;DR

День начался с Phase 3d UAT (cycle opt-in flow) → закрыли 3 миграции (352, 356, 357) + amend mig 359 for onboarding integration. Затем **в 04:00 MSK P0 incident**: subagent applied mig 359 ad-hoc через `ut.content || ns.payload` shallow merge → wiped 182 buttons + 100 onboarding keys × 13 langs. Recovery mig 360 + fix mig 359 + double-emoji cleanup за ~2 часа. PR #207 пушнут, ждёт merge.

**3 KB lessons зафиксированы** для будущих агентов:
- [[jsonb-shallow-merge-antipattern]] — `content || payload` anti-pattern + 3 safe alternatives
- [[subagent-live-apply-review-rule]] — orchestrator MUST review SQL before subagent applies LIVE
- [[double-emoji-button-anti-pattern]] — `icon_const_key` + emoji-in-value = double render

Все 3 — в index.md в 4 lookup-секции.

## Что в проде на 2026-05-26 (post recovery)

- **Migration HEAD: 360** (recovery applied LIVE, файл в PR #207)
- **Phase 3d cycle UX полностью работает:** opt-in flow + hub dynamic label `[🌸 День N/L]` + post-save toast + opt-out + edit cycle length (mig 357 presets 21/25/28/30/35)
- **Onboarding cycle question** (mig 359) — DDL + RPCs + screens применены, но требует merge PR #207 для активации router whitelist (`registration_step_cycle` в `BUTTON_ONLY_STATUSES` + `ONBOARDING_STATUSES`)
- **`buttons` namespace × 13 langs:** 76-78 keys восстановлены, все 74 needed keys present, double-emoji prefix очищен (19 keys)
- **`onboarding` namespace:** 2 keys (cycle_question_title + cycle_explain_body) + welcome/ask_country/ask_timezone/finished × 13 langs

## Open PRs (ждут merge)

| PR | Title | Status |
|---|---|---|
| #207 | fix(p0): mig 360 recovery + mig 359 forward+fix + router whitelist | ✅ CI green, ⏳ merge нужен |

После merge PR #207 → GitHub Actions auto-deploy → Python router изменения подъедут → onboarding cycle question заработает для новых female non-pregnant non-lactating юзеров.

## Что НЕ закрыто (intentional defer)

### Tier 1 — критичный follow-up

1. **CI guard для shallow-merge anti-pattern.** Документировано в [[jsonb-shallow-merge-antipattern]] §«CI guard (TODO)». Pre-merge grep check для `content || payload` в migrations + flag for human review. Не реализован — defer на следующего агента.

2. **Phase 3d test plan** owner еще не прошёл полностью:
   - T2-T7 после merge #207 (см. предыдущий handover scenarios)
   - Onboarding cycle question — нужен fresh test user (created from scratch) чтобы попасть в registration_step_cycle. Owner может reset 786301802 через `test-user-reset-recipe.md`.

### Tier 2 — features owner explicitly endorsed earlier

3. **Mig 358+ — Phase-aware Sage commentary** (Tier 2.F). Спецификация была в моём handover earlier. Sage prompt получает `cycle_phase` + `cycle_day_in_phase`, тонко комментирует без medical jargon. Copywriter subagent для phase-aware seeds × 13 langs. Defer.

### Tier 3 — gotchas из incident

4. **`Mig 357 PR (если был открыт) — переплелся с recovery.** Mig 357 sql files в worktree уже forwarded в main через PR #206 (merged ранее). Live state OK. Если новый агент видит mig 357 как orphan — проигнорировать (он в main).

5. **`users.cycle_period_choice` column** — added by stopped subagent #1 (checkmark direction, abandoned). Column живёт в проде, populated by save_user_cycle_data RPC, не используется в render (renderer hook не подключён). Harmless audit trail. **НЕ удалять без анализа** — может быть полезен для analytics.

## Critical files для следующего агента

| Файл | Что |
|---|---|
| `MEMORY.md` | Состояние проекта на 2026-05-26 |
| `claude-memory-compiler/daily/2026-05-26.md` | Полный журнал сессии: 4 mig + recovery + double-emoji fix |
| `claude-memory-compiler/knowledge/concepts/jsonb-shallow-merge-antipattern.md` | NEW — P0 lesson, READ THIS перед любой mig touching ui_translations |
| `claude-memory-compiler/knowledge/concepts/subagent-live-apply-review-rule.md` | NEW — orchestrator rule, READ THIS перед делегированием SQL subagent'у |
| `claude-memory-compiler/knowledge/concepts/double-emoji-button-anti-pattern.md` | NEW — i18n value не должен дублировать `icon_const_key` |
| `migrations/356/357/360` | Phase 3d cycle UX полная цепочка |
| `migrations/359_phase3d_cycle_in_onboarding.sql` | Onboarding cycle question (DDL applied, file in PR #207) |

## Lessons learned (для KB полного контекста)

### Lesson A — JSONB shallow merge wipes nested namespaces

`content || payload` REPLACES top-level keys, doesn't deep-merge. If payload has object-valued keys (`{"buttons": {...}, "onboarding": {...}}`), the ENTIRE buttons namespace gets wiped. Use jsonb_set per leaf OR `jsonb_each LATERAL` pattern. See [[jsonb-shallow-merge-antipattern]].

**Mig 359 (broken):**
```sql
UPDATE ut SET content = ut.content || ns.payload FROM new_strings ns WHERE ut.lang_code = ns.lang_code;
```

**Mig 359 (fixed):**
```sql
WITH new_strings AS (...),
     expanded AS (
       SELECT ns.lang_code, each.ns_key AS namespace, each.ns_value AS inner_payload
         FROM new_strings ns,
              LATERAL jsonb_each(ns.payload) AS each(ns_key, ns_value)
     )
UPDATE ut SET content = jsonb_set(
    content, ARRAY[expanded.namespace],
    COALESCE(content->expanded.namespace, '{}'::jsonb) || expanded.inner_payload,
    TRUE
) FROM expanded WHERE ut.lang_code = expanded.lang_code;
```

### Lesson B — Subagent LIVE-apply requires review

Briefs like «Apply via psycopg2 + verify» grant permission without checkpoint. SAVEPOINT catches syntax/RPC errors, NOT semantic data overwrites. Orchestrator MUST read SQL before authorizing apply for non-trivial writes (esp. JSONB merges, RPC bodies, schema mutations). See [[subagent-live-apply-review-rule]].

### Lesson C — TaskStop ≠ rollback

Killing subagent process via `TaskStop` does NOT undo DB writes already committed in autonomous transactions. After `TaskStop`, always audit live state — what columns/rows/RPCs exist now — before assuming "no changes made". See [[subagent-live-apply-review-rule]] §Layer 2.

### Lesson D — Double emoji on buttons with icon_const_key

If button has `ui_screen_buttons.icon_const_key='icon_X'`, the i18n value MUST NOT have emoji prefix — renderer prepends `constants[icon_X] + ' '` automatically. Double prefix = `⚙️ ⚙️ Настройки`. Already in CLAUDE.md rule 2, now also as KB concept for visibility. See [[double-emoji-button-anti-pattern]].

## Test plan для следующей сессии

```
[1] Merge PR #207 → wait auto-deploy ~2 min
[2] Open bot as 417002669 (post-mig-360 recovery state)
    EXPECTED: все reply-kb + inline buttons render с правильными localized labels
    NO double emoji (см. screenshot до recovery vs после)

[3] T2-T7 retry для Phase 3d cycle UX (см. предыдущий handover)
[4] Onboarding cycle question — нужен fresh test user
[5] Sleep/stress на 786301802 (female, ранее тестировали на 417002669)
```

## Где документация для нового агента

- **Перед стартом ВСЕГДА:** `MEMORY.md` + сегодня + вчера `daily/`
- **Перед mig touching ui_translations:** [[jsonb-shallow-merge-antipattern]] + [[ui-translations-bulk-update-recipe]]
- **Перед делегированием subagent с DB execute:** [[subagent-live-apply-review-rule]] + [[agent-collaboration-protocol]]
- **Перед hand-craft button i18n:** [[double-emoji-button-anti-pattern]] + [[copywriter-playbook]]
- **NLM первым делом** перед любым SQL/планом (CLAUDE.md §СТОП-ПРАВИЛО)

— nervous-cerf-566d7a, EOS 2026-05-26 ~10:35 MSK
