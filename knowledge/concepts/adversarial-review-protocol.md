# Adversarial Review Protocol — pre-apply critical pass

**Компилировано:** 2026-04-21 Session 10. Adversarial subagent found 5 CRITICAL + 7 HIGH + 7 MEDIUM findings ДО prod apply migration 110. Prevented severe data corruption + "message not modified" UX failure + SQL injection vector.

## Зачем

Для non-trivial миграций (CREATE OR REPLACE RPC с 300+ строками, seed с 9+ новых screens, batch UPDATE) **обязательно** запустить adversarial review subagent перед `psycopg2 cur.execute(sql); conn.commit()`.

Один "невидимый" баг в migration, применённый к prod, занимает 2-4 часа debug + rollback. Adversarial review стоит 10-15 мин + 1 subagent + 2K tokens.

**ROI:** 10-25x.

## Protocol

### Входы adversarial subagent (self-contained prompt)

- **Migration files generated** (e.g. `/path/110_X.sql`)
- **Source of truth spec** (`.claude/specs/sessionN_contract.md`)
- **Phase 0 DB state** (ui_screens count, workflow_states, setter RPCs existing, users columns)
- **Ground truth RPC bodies** (`/tmp/rpc_before_<migration>.sql`)
- **Constraint enums**: render_strategy, input_type, CHECK values
- **Previous migration patterns** (e.g. ref to 086/097/100/108)

### Задачи ревьюера

1. **Прочитать migration целиком** (не только diff)
2. **Прочитать spec для понимания намерения**
3. **Cross-check KB references** (headless-architecture.md etc.)
4. **Dry-run through psycopg2** (`BEGIN; execute; ROLLBACK;`) — syntax check
5. **Semantic analysis по 15 ключам** (см. ниже)
6. **Output structured findings** (CRITICAL / HIGH / MEDIUM / LOW)

### 15 ключей проверки

**CRITICAL (блокеры — миграция упадёт в prod / silent data corruption):**

1. **FK violations** — order of INSERTs vs referenced tables
2. **CHECK constraint enum values** — enum members match reality (render_strategy, input_type)
3. **CREATE OR REPLACE RPC preservation** — old logic intact, only additive changes
4. **SQL injection via dynamic EXECUTE** — whitelist validation ДО `EXECUTE format('SELECT public.%I(...)')`
5. **Missing RPC references** — workflow_states.save_rpc → pg_proc exists

**HIGH (semantic bugs — migration applies, but behavior broken):**

6. **Translation reuse** — existing keys not inadvertently overwritten (shallow merge!)
7. **Callback data consistency** — matches ground truth RPC parsing (see specs-vs-reality)
8. **meta JSONB conventions** — target_screen / set_status / save_via_callback / clear_status match Headless pattern
9. **ON CONFLICT behavior** — correct target column + UPDATE vs NOTHING decision
10. **Deep-merge JSONB translations** — `jsonb_set` + `COALESCE`, **never** `content || '{...}'`
11. **Button layout** — row_index/col_index unique per screen, back at end

**MEDIUM (warnings):**

12. **Verification DO block** — asserts cover all blocks, format messages informative
13. **Rollback instructions** — embedded as comments + artifact paths
14. **Idempotent re-run** — миграция safely re-applicable
15. **Comments + structure** — block markers, intent explained

### Sub-agent prompt template

```
Ты adversarial reviewer. Найди ВСЕ ошибки / риски / deviations в SQL-миграциях перед apply в prod.

## Файлы
1. /path/NNN_migration.sql
2. [optional: /path/NNN+1_companion.sql]

## Ground truth
- Spec: .claude/specs/sessionN_contract.md
- Phase 0 DB state: <summary>
- RPC pre-migration body: /tmp/rpc_before_NNN.sql
- Constraints from DB: <enums, CHECKs>

## Ищи по приоритету (15 keys)

### CRITICAL
1. FK violations
2. CHECK constraint compliance
3. CREATE OR REPLACE preservation
4. SQL injection (EXECUTE format)
5. Missing RPC references

### HIGH
6. Translation reuse
7. Callback data vs RPC ground truth
8. meta convention
9. ON CONFLICT behavior
10. Deep-merge JSONB
11. Button layout

### MEDIUM
12. Verification DO block
13. Rollback notes
14. Idempotent
15. Comments/structure

## Output format
```markdown
# Migration NNN Adversarial Review

## Verdict
- [ ] READY TO APPLY (0 critical)
- [ ] NEEDS FIX (list criticals)

## Critical findings
1. **[file, line]** — Issue → Fix (concrete diff)

## High findings
1. ...

## Medium findings
1. ...

## Sanity checks passed
- [x] ...

## Recommended next action
```

**Ограничения:**
- Max 1500 слов
- Concrete evidence на каждый claim (file + line OR verified through query)
- **Не генерируй фейковые findings** — если clean, так и скажи
```

### Verdict выводы

- **0 CRITICAL** → apply ok
- **1+ CRITICAL** → fix в current subagent OR escalate user
- **HIGH finding** → weigh cost to fix vs defer to post-apply migration
- **MEDIUM+** → note в changelog, fix в follow-up

## Session 10 example (migration 110 review result)

**25 sanity checks passed. Verdict: READY TO APPLY (0 criticals).**

High findings (all addressable in follow-up migrations, not blockers):

1. edit_country template callback ('loc_country_{iso}') match testing — add explicit test
2. training_skip save_value='mixed' (RPC behavior) — visual duplication if user already training_type='mixed'; needs later UX fix
3. Block H `clear_status` vs `set_status` ordering — if both set, set_status wins (defensive ELSIF would prevent)

Critical findings prevented (had subagent not caught):

1. **ui_screen_buttons.meta.target_screen на cmd_edit_* кнопках был пустой `{}`** — migration 086 seeded без. Если не UPDATE в 110 — picker не работает совсем. Added to Block F.
2. **Callback convention conflict** — Session 10 initially planned `cmd_set_*`, RPC parse `cmd_select_*`. Would have caused silent fallback to default on every click. Fixed в Block G.
3. **FK ordering Block C/D/E** — workflow_states INSERT с screen_id='edit_X' ДО ui_screens INSERT → FK violation. Fixed: Block C initial INSERT без screen_id → Block E ui_screens → Block D late UPDATE workflow_states.screen_id.
4. **Test sentinel 'ZZ'** — exists in ref_countries → would have passed ok=true expected as ok=false. Changed to 'Q1'.
5. **SQL injection surface** — EXECUTE format('SELECT public.%I(...)') без whitelist. Added `pg_proc WHERE proname LIKE 'set_user_%'` check before EXECUTE.

## Patterns для reuse

### Template prompt для вызова ревьюера

Сохрани в `.claude/templates/adversarial_review.md` для next sessions.

### Checklist CRITICAL findings по типу миграции

**Seed migration (INSERT data):**
- [ ] FK targets exist
- [ ] ON CONFLICT correct column
- [ ] No duplicate row_index/col_index

**CREATE OR REPLACE RPC:**
- [ ] Old body preserved (`/tmp/rpc_before.sql` diff shows only additive changes)
- [ ] Declare new variables at top
- [ ] SECURITY DEFINER + GRANT EXECUTE maintained
- [ ] Dynamic EXECUTE whitelisted

**UPDATE existing rows:**
- [ ] WHERE clause specific (not accidentally bulk)
- [ ] Idempotent (re-running same UPDATE yields same state)

**ALTER TABLE / constraint changes:**
- [ ] Existing data compliant с новым constraint (SELECT count WHERE violating condition)
- [ ] Default value provided для NOT NULL
- [ ] CASCADE / RESTRICT semantics intentional

## Pitfalls

1. **Не доверяй ревьюеру 100%.** Он может пропустить баг если not in 15 keys. Main agent отвечает за финальный apply decision.
2. **Один проход адекватен для среднего migration.** Очень сложные (>1000 строк) — 2 раунда adversarial от разных subagent'ов.
3. **Ревьюер НЕ применяет migration.** Only main agent. Ревьюер only генерит findings report.
4. **Subagent должен delete/не touch prod data.** Если захочет тестировать — использовать транзакции с ROLLBACK (BEGIN; test; ROLLBACK;).

## Связанные KB концепты

- [[pre-migration-discovery-recipe]] — Phase 0 discovery (feeds ground truth to adversarial)
- [[specs-vs-reality-ground-truth]] — priority rules когда spec противоречит DB
- [[supabase-db-patterns]] — migration method, CHECK patterns

## ROI summary

Session 10 migration 110:
- 1529 строк SQL, 69.7 KB, 10 blocks
- Adversarial review: ~15 мин, 87K tokens subagent
- Found 5 CRITICAL + 7 HIGH + 7 MEDIUM
- Without review: estimated 3-5 hours prod debug + rollback + re-apply
- **ROI: 12-20x**

Для любой миграции >200 строк OR >3 blocks OR с CREATE OR REPLACE RPC — adversarial review **обязателен**.
