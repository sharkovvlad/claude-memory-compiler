# Handover — Nutritionist Session Close v2 (2026-05-18 evening)

**Адресат:** следующий агент, продолжающий P0 sprint + UX maternal/safety redesign.

**Срочность вхождения:** ≤30 минут. Этот handover + проверить PR #102 state + UX KB doc = всё что нужно.

---

## TL;DR — где мы (2026-05-18 ~16:00 UTC final)

### P0 sprint roadmap state (`calc-user-targets`)

| P0 item | Status |
|---|---|
| **1. Pregnancy/lactation** | ✅ **End-to-end live в боте** — verified screenshots от owner'а. Schema + v8 calc + Profile UI + Onboarding step + i18n + Tier 1 push modal — всё работает. |
| **2. Защита <18** | ✅ **End-to-end live** — verified. Banner+modal corrects. |
| **3. Хард-лимит kcal 1200/1500** | 🟡 Backend ready. **Открыто:** bmi/min_kcal warning переводы (~351 entries × 13 langs). Brief: [bmi_min_kcal_brief](./2026-05-18_bmi_min_kcal_copywriter_brief.md). Без переводов banner_block для этих families пустой — RPC возвращает enum но banner не рендерится. |
| **4. EA > 30 kcal/kg LBM** | ⏳ **Deferred to P2** — rationale в [energy-availability-design-decision.md](../knowledge/concepts/energy-availability-design-decision.md). |

### Merged PRs этой сессии

| PR | Migrations + code | Merged at |
|---|---|---|
| [#96](https://github.com/sharkovvlad/noms-bot/pull/96) | mig 252-254 (banner injection + pregnancy schema + v8 RPC) | 2026-05-18 09:50 UTC |
| [#98](https://github.com/sharkovvlad/noms-bot/pull/98) | mig 256-260 + router.py (banner extension + female health UI + onboarding step) | 14:19 UTC |
| [#100](https://github.com/sharkovvlad/noms-bot/pull/100) | mig 262-265 + Python (personal_metrics fix + button template_vars + Tier 1 hook v1) | 15:10 UTC |
| [#101](https://github.com/sharkovvlad/noms-bot/pull/101) | mig 266-267 + webhook ordering (Markdown→HTML + Sassy Sage translations + modal-before-menu) | 15:37 UTC |
| **[#102](https://github.com/sharkovvlad/noms-bot/pull/102)** | **mig 268 + router.py fix (14 callbacks к PROFILE_V5_CALLBACKS + UX quick wins)** | **OPEN — нужен merge** |

**Total DB migrations applied:** 252, 253, 254, 256, 257, 258, 259, 260, 262, 263, 264, 265, 266, 267, 268 (15 migrations).

---

## Что в [PR #102](https://github.com/sharkovvlad/noms-bot/pull/102) ждёт merge

### Router fix (critical)
`dispatcher/router.py:PROFILE_V5_CALLBACKS` пополнен 14 callbacks из mig 257 (Female Health sub-menu). Без этого `cmd_women_health` etc. идут в legacy n8n menu workflow → silent fail → spinning wheel (live-test 786301802 показал 12 wasted clicks 18:21-18:38 UTC).

### Mig 268 UX quick wins
1. **Speed suppression при forced maintain** — `goal_speed_label='—'` когда effective!=original AND effective='maintain'. Fixed bug «Темп: Быстро» при force'нутом maintain.
2. **Severity-sorted banner_block** — hard_block first, hard_regulated → soft_override → (informational skipped per mig 263). Закрывает UX agent recommendation #2.

После merge auto-deploy → buttons «Женское здоровье» и под-кнопки работают, banner ordering исправлен.

---

## UX agent recommendation (long-term)

**KB doc:** [safety-banner-ux-redesign-2026-05-18.md](../knowledge/concepts/safety-banner-ux-redesign-2026-05-18.md)

**Recommendation B (radical):** Safety Center subscreen — separate hub для warnings (не на главном Profile screen). Estimated: 5-7 дней, ~5-6 миграций, ~350 строк SQL, 1 new screen + ~50 translation entries.

**Recommendation A (conservative):** banner consolidation rules (count badge + modal expand). Estimated: 2-3 дня, ~3 миграции, ~130 строк SQL, 26 translation entries.

**Owner lean:** не выбран (см. KB §«Decision tree»). Quick wins (mig 268) уже применены — compatible с любым выбором.

---

## Open work для следующих сессий

### Высокий priority (close P0 fully)

1. **bmi/min_kcal translations** (~351 entries × 13 langs)
   - Brief готов: [bmi_min_kcal_copywriter_brief.md](./2026-05-18_bmi_min_kcal_copywriter_brief.md)
   - Pattern: mig 240/241/242 (age warnings) jsonb_set sibling-safe merge
   - Spawn copywriter agent с reference [copywriter-playbook.md](../knowledge/concepts/copywriter-playbook.md)
   - **После apply:** banner для bmi/min_kcal начнёт рендериться автоматически (family-agnostic loop в helper)

2. **Maternal sub-menu labels — 11 langs native translations**
   - Mig 257 RU+EN canonical в migration, 11 langs EN fallback
   - 18 translation keys (см. mig 257 sentinel section)

3. **Onboarding maternal step — 11 langs native translations**
   - Mig 259 RU+EN canonical, 11 langs EN fallback
   - 7 translation keys: `onboarding.maternal_*` + `buttons.maternal_*`

4. **Sassy Sage modal_full polish review** — mig 267 русский canonical был ОТЛИЧНЫЙ (Deadpool-mode «Мои кремниевые мозги»). Other 12 langs adapted by agent #1 — recommend native L2 review для AR/FA/HI/ID (medical-authority + maternal-privacy). Fiverr ~$200.

### UX Safety Banner redesign (after owner picks A vs B)

- Recommendation A или B per UX agent KB
- Quick wins #1 + #2 (mig 268) уже applied — sunk cost = 0
- Quick win #3 (body length audit) — copywriter mini-session, не делано

### Tier 4 + Tier 5 backstops (per safety-guard-ux-pattern §2)

- **Tier 4 retrofit cron** — для legacy F/15-50 NULL is_pregnant. APScheduler worker с partial index `idx_users_maternal_protective` (mig 253). Currently 5 prod users — low urgency, но FTC mandate-ready.
- **Tier 5 auto-resolve cron** — daily scan для cleared warnings (age→18, BMI cleared, pregnancy ended) → push «🎉 Защита снята».

### P1+ backlog (deferred)

- **EA / RED-S guard** (P2.5b) — нужен workout tracking (P2.5a) + waist quiz (P2.1)
- **Schofield/Molnar/Lührmann age formula switch** (P1.5)
- **Vegan protein adjustment, ABW для obese, athlete phenotype** (P1)
- **Digital twin Google Sheets** validation pending (owner предлагал валидировать через [LiveOps table](https://docs.google.com/spreadsheets/d/1t-5xsGaYP64Dk7NKfRnCGignlbtOKyG0a2LE6jjOGB0/edit))

---

## Key technical decisions локкнутые в этой сессии

| Decision | Source |
|---|---|
| Pregnancy + goal=gain → ALLOW (no force maintain) | clinical spec §6b |
| Maternal onboarding = 3 buttons (Нет/Беременна/Кормлю), no «Не отвечу» | clinical spec §6c |
| Banner mandatory whenever override fires (distributed enforcement) | clinical spec §6b |
| NULL is_pregnant = protective mode (defensive net для legacy) | mig 254 v8 |
| Informational severity skip persistent banner (Tier 2), push only via Tier 1 | mig 263 + safety-guard-ux §2b |
| Family-agnostic banner helper — new family auto-picked via translation | mig 256 |
| router.py PROFILE_V5_CALLBACKS должен включать ВСЕ headless callbacks | live-test lesson 2026-05-18 |
| Markdown** в HTML parse_mode = anti-pattern (mig 266 fix) | copywriter-playbook §6 (add) |
| Modal_full text для underage_disclaimer = Sassy Sage Deadpool-mode | mig 267 owner canonical |
| Tier 1 modal arrives BEFORE menu (awaited не fire-and-forget) | webhook_server.py mig 266 commit |

---

## Live-test verified examples (для regression spot check)

- **User 786301802 (16yo F)** with goal=maintain → informational `underage_disclaimer`:
  - Persistent banner: empty (informational skipped)
  - Tier 1 push: «💡 Небольшой спойлер...» Sassy Sage text once
  - Profile screen clean (no clutter)
- **User 786301802 changed to goal=lose+fast** → force'нут maintain via age+maternal guards:
  - Banner stacks: 🛡️ До 18 (hard_block, first) + 🛡️ Статус не указан (hard_regulated, second) — severity-ordered post-mig 268
  - goal_type_label=Поддержание, goal_speed_label=— (suppressed)

---

## Контекст для следующего agent — что в KB

**Canonical entry-points** (read first):
- `concepts/calc-user-targets-roadmap.md` — P0 sprint status (closed) + P1+ backlog
- `concepts/safety-guard-ux-pattern.md` §2b Implementation Status (mig 263 + 268 + Tier 1)
- `concepts/copywriter-playbook.md` — single entry point для translation sessions
- `concepts/pregnancy-lactation-clinical-spec.md` — full clinical spec
- **`concepts/safety-banner-ux-redesign-2026-05-18.md`** (new) — UX agent research для long-term decision
- `concepts/energy-availability-design-decision.md` — EA deferral rationale

**Daily logs:**
- `daily/2026-05-17.md` — mig 234 v6 age guards + mig 239 storage + clinical decisions
- `daily/2026-05-18.md` — full session log: mig 246 v7 + 252-260 maternal + 262-268 fixes (extensive)

---

## Что НЕ трогать без явного запроса

- Mig 254 protective mode logic — defensive net для legacy. НЕ removing.
- `_safety_guard_severity()` severity matrix (mig 264) — canonical source per safety-guard-ux-pattern §3.
- Existing prod user data — все mig'и applied transactionally, snapshots сохранены 7 days.
- EA implementation — deferred decision, не triggering без P2.5a+P2.5b deps.

---

Полезные команды для следующего agent:

```bash
# Confirm PR #102 state
cd /Users/vladislav/Documents/NOMS && gh pr view 102 --json state,mergedAt

# Live VPS logs (last 30 min) — для debug новых button issues
ssh root@89.167.86.20 'journalctl -u noms-webhooks --since "30 min ago" | grep -E "ERROR|Traceback|cmd_|SHADOW_ROUTE"' | tail -30

# Check user 786301802 current state
python3 -c "import os, psycopg2
from dotenv import load_dotenv; load_dotenv('.env')
c=psycopg2.connect(os.environ['DATABASE_URL']).cursor()
c.execute(\"SELECT status, goal_type, is_pregnant, shown_guards FROM users WHERE telegram_id=786301802\")
print(c.fetchone())"
```

Удачи преемнику. P0 sprint **закрыт на SQL/RPC + Python**. UX polish — open.
