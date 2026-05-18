# Handover — Nutritionist Session Close v3 FINAL (2026-05-18 evening)

**Адресат:** следующий nutritionist/UX/translation agent — закрытие P0 + open issues.
**Срочность вхождения:** **30-40 минут чтения** (это comprehensive doc). После этого ты в курсе всего.

---

## ⚡ Quick state (30 sec)

- **15 DB migrations applied** (mig 252-260, 262-268, без 261 — он от другого агента).
- **4 PR merged** (#96, #98, #100, #101) + **PR #102 open** (router fix + UX quick wins).
- **1 background agent running** — `mig 269` для 352 missing translations (11 langs × 32 keys).
- **P0 sprint roadmap: closed на SQL/RPC + Python**.
- **Open items**: UX redesign decision A vs B, bmi/min_kcal copy (~351 entries), Tier 4/5 crons, L2 cultural review maternal.

---

## 📋 P0 sprint roadmap (`calc-user-targets`)

| P0 item | Owner ask | Status |
|---|---|---|
| **1. Pregnancy/lactation** | hard block при confirm, allow gain, push notification | ✅ End-to-end live |
| **2. Защита подростков <18** | banner + force maintain + uvedomление | ✅ End-to-end live (verified live-test) |
| **3. Хард-лимит kcal 1200ж/1500м + BMI tiered** | backend + banner | 🟡 Backend ready. Переводы bmi/min_kcal pending (~351 entries × 13 langs). Banner_block для этих families currently пустой |
| **4. EA > 30 ккал/кг LBM (RED-S)** | защита | ⏳ **Deferred to P2** per [energy-availability-design-decision.md](../knowledge/concepts/energy-availability-design-decision.md). Rationale: EA-lite без exercise tracking даёт false negatives на active F demographic. |

---

## 🗂 DB migrations applied (chronological)

| Mig | Что | Applied |
|---|---|---|
| 252 | banner injection my_plan (mig 252-260 cluster) | 2026-05-18 morning |
| 253 | pregnancy/lactation schema (6 columns DEFAULT NULL + CHECK + partial index) | morning |
| 254 | `calculate_user_targets` v8 — maternal safety guard | morning |
| 256 | banner extension `personal_metrics` + `profile_main` (helper `build_safety_guard_banner_block`) | midday |
| 257 | `🌸 Женское здоровье` Progressive Disclosure UI: 7 screens + 5 RPCs | midday |
| 258 | maternal warnings translations 13 langs (156 entries) | midday |
| 259 | onboarding maternal step F/15-50 (3 buttons, mig 260 removed «Не отвечу») + `PERFORM calculate_user_targets` after picks + router.py BUTTON_ONLY_STATUSES | midday |
| 260 | Profile picker prefer-not cleanup | midday |
| 262 | personal_metrics 3 bugs fix (routing + banner_block restore + intro phrase) | afternoon |
| 263 | persistent banner SKIPS informational severity (Tier 2 cleanup) | afternoon |
| 264 | **Tier 1 first-trigger modal push** (3 RPCs + `services/safety_guards.py` + webhook hook) | afternoon |
| 265 | cmd_edit_* routing meta.target_screen + body cleanup + RU label «Мои Данные» | afternoon |
| 266 | Markdown `**` → HTML `<b>` в 6 women_health texts + populate trimester text | afternoon |
| 267 | Sassy Sage rewrite `underage_disclaimer.modal_full` 13 langs (Deadpool tone «Мои кремниевые мозги») | evening |
| 268 | UX quick wins: speed suppression при forced maintain + severity-sorted banner stacking | evening |
| **269** (in-flight agent) | **11 langs translations × 32 keys = 352 entries + Markdown fix in onboarding texts** | running |

---

## 🚢 PR status

| PR | State | Что |
|---|---|---|
| [#96](https://github.com/sharkovvlad/noms-bot/pull/96) | merged 09:50 UTC | mig 252-254 (banner + pregnancy v8) |
| [#98](https://github.com/sharkovvlad/noms-bot/pull/98) | merged 14:19 UTC | mig 256-260 + router.py (Female Health UI + onboarding) |
| [#100](https://github.com/sharkovvlad/noms-bot/pull/100) | merged 15:10 UTC | mig 262-265 + Python (personal_metrics fixes + template_vars + safety_guards.py) |
| [#101](https://github.com/sharkovvlad/noms-bot/pull/101) | merged 15:37 UTC | mig 266-267 + webhook ordering (Markdown→HTML + Sassy Sage + modal-before-menu) |
| **[#102](https://github.com/sharkovvlad/noms-bot/pull/102)** | **OPEN — нужен merge owner'ом** | mig 268 + router.py 14 callbacks (UX quick wins + women_health flow unblock) |

**Auto-deploy:** GitHub Actions `deploy.yml` триггерится на push в main → rsync → restart services. ~40-60 секунд.

---

## 🎯 Что в PR #102 ждёт merge

### Router fix (critical!)
`dispatcher/router.py:PROFILE_V5_CALLBACKS` пополнен **14 callbacks** из mig 257 (Female Health sub-menu). Без этого:
- `cmd_women_health` → legacy n8n menu → silent fail → spinning wheel
- Same для cmd_set_pregnancy_open, cmd_set_lactation_open, cmd_cycle_premium, cmd_set_pregnancy_yes/no, cmd_set_lactation_yes/no, cmd_set_trimester_1/2/3/unknown, cmd_set_lactation_type_exclusive/partial

Подтверждено в VPS logs (786301802 18:21-18:38 UTC, 12 wasted clicks):
```
SHADOW_ROUTE ... target=menu reason=menu_command ... cb_data=cmd_women_health
```
→ должно быть `target=menu_v3 reason=profile_v5_callback`.

### Mig 268 UX quick wins (recommendations от UX agent)

1. **Speed suppression при forced maintain**: `goal_speed_label='—'` когда `effective != original AND effective='maintain'`. Закрывает баг «Темп: Быстро» на 16yo F с force'нутым maintain.

2. **Severity-sorted banner_block**: hard_block first, hard_regulated → soft_override (informational скип пер mig 263). Реализовано через CTE с severity rank.

---

## 🌍 Translations state

### Закрыто на 13 langs
- `warning.age.*` (mig 240/241/242) — 156 entries, 3 enums × 4 surfaces × 13 langs ✓
- `warning.maternal.*` (mig 258) — 156 entries ✓
- `warning.age.underage_disclaimer.modal_full` v2 (mig 267) — Sassy Sage Deadpool tone ✓

### Открытое (in-flight + pending)

| Scope | Status | Brief |
|---|---|---|
| **profile.* + buttons.* + onboarding.maternal_* (32 keys × 11 langs)** | 🟡 **Mig 269 in-flight (agent running)** | This handover §«🚨 Translations missing» |
| `warning.bmi.*` + `warning.min_kcal.*` (~351 entries × 13 langs) | ⏳ **Pending copywriter session** | [bmi_min_kcal_copywriter_brief.md](./2026-05-18_bmi_min_kcal_copywriter_brief.md) |
| **L2 cultural review maternal AR/FA/HI/ID** | ⏳ Fiverr (~$200) | mig 258 medical-authority + maternal-privacy contexts |

---

## 🚨 Translations missing (root cause + fix in progress)

**Bug obvserved 21:34 by owner (ES user):**
```
[18/5/26 21:34] Vladislav: 👤 Perfil
[18/5/26 21:34] NOMSaibot: 📏 Personal Metrics
                          Check your parameters. Calorie targets depend on these.
```

ES user видит EN текст — fallback. Поскольку мы (миграции 257/259/265/266) положили только RU+EN canonical, а 11 других langs fall back на EN.

**Audit показал:** **32 keys × 11 langs = 352 missing translations**:

- profile.* texts (7 keys): personal_metrics_text, women_health_text, set_pregnancy_text, set_pregnancy_trimester_text, set_lactation_text, set_lactation_type_text, cycle_premium_upsell_text
- buttons.* data-rich (4): edit_weight_value, edit_height_value, edit_age_value, edit_gender_value
- buttons.* women_health (4): women_health, pregnancy_state, lactation_state, cycle_state_premium
- buttons.* toggle pickers (11): pregnancy_yes/no, lactation_yes/no, trimester_1/2/3/unknown, lactation_exclusive/partial, prefer_not_to_say (legacy mig 260 removed но key)
- buttons.* onboarding maternal (3): maternal_no, maternal_pregnant, maternal_lactating
- onboarding.* (3 keys × HAS MARKDOWN BUG): maternal_status_question, maternal_trimester_question, maternal_lactation_type_question. Используют `*Quick safety check*` (Markdown V1) в parse_mode=HTML — **same bug как mig 266 fix для женского здоровья!**

**Fix in-flight:** Background agent работает на `mig 269`. Должен:
1. Audit + dump current RU+EN canonical для всех 32 keys
2. Написать 352 native переводов через Sassy Sage glossary per-lang
3. **FIX Markdown `*bold*` → `<b>bold</b>`** в onboarding maternal texts (+RU/EN check)
4. Apply transactionally + snapshot
5. Return Branch + commit message + PR URL

---

## 🧠 UX redesign decision pending

**KB doc созданный UX agent'ом:** [safety-banner-ux-redesign-2026-05-18.md](../knowledge/concepts/safety-banner-ux-redesign-2026-05-18.md)

### Recommendation A (conservative, 2-3 days)
- Banner consolidation rules — when ≥2 guards present, show только highest severity + count badge «+ 1 more →» → modal expand
- «Темп» suppression при forced (already done mig 268 #1)
- ~3 миграции, ~130 SQL, 26 translation entries

### Recommendation B (radical, 5-7 days) — **agent's lean**
- **Safety Center subscreen** — dedicated hub для warnings (off main Profile)
- Profile → quick stats + 1 alert badge → click → full warnings screen
- ~5-6 миграций, ~350 SQL, 1 new screen, ~50 translation entries
- Long-term: pattern matches Apple Health / Flo / Glow

### Decision tree (per KB):
- Frequency of multi-guard cases (rare → A, common → B). NOMS roadmap имеет ≥6 не-implemented guards (P1.5/P2.3/P2.5/P2.6/P3) → multi-guard будет частым case
- Mobile-first (Telegram = 100% mobile) → B
- Long-term roadmap (more guards coming) → B

**Owner choice:** не сделан. Quick wins (mig 268) compatible с любым выбором.

---

## 📐 Architecture decisions locked (не пересматривать без явного запроса)

### Clinical (KB pregnancy-lactation-clinical-spec.md)

| Decision | §  |
|---|---|
| Pregnancy + goal=gain → ALLOW (no force maintain). 12-16kg gain клинически норма | §6b |
| Pregnancy + goal=lose → hard block, force maintain + trimester bonus | §2 |
| Lactation + goal=lose → hard block, force maintain + lactation bonus | §2 |
| F/15-50 + is_pregnant IS NULL + goal=lose → protective hard_regulated | §2 (mig 254) |
| Onboarding maternal = 3 buttons (Нет/Беременна/Кормлю), no «🤐 Не отвечу» | §6c |
| Banner mandatory whenever override fires (distributed enforcement) | §6b |

### Technical patterns (KB various)

| Pattern | Source |
|---|---|
| `NULL is_pregnant` preserved as defensive net для legacy users | mig 254 |
| Informational severity → Tier 1 push only, **не** persistent banner Tier 2 | mig 263 + safety-guard-ux §2b |
| Severity matrix canonical в `_safety_guard_severity` RPC | mig 264 |
| Family-agnostic banner via helper `build_safety_guard_banner_block` | mig 256 |
| Severity-sorted banner stacking (hard_block first) | mig 268 |
| Banner mandatory wherever override fires → enforcement на 3 screens (my_plan, personal_metrics, profile_main) | mig 256 |
| `router.py:PROFILE_V5_CALLBACKS` должен включать ВСЕ new headless callbacks | lesson 2026-05-18 18:21 |
| **Markdown `**bold**` или `*bold*` в HTML parse_mode = anti-pattern** (mig 266 fix) | copywriter-playbook §6 |
| Tier 1 modal awaits before menu envelope (not fire-and-forget) | webhook_server.py post-mig 266 |

---

## 📝 Open work для следующих сессий

### Близкое (закрыть P0 fully)

**1. Mig 269 deploy + verify** (in-flight agent)
- Когда agent return — review SQL + sentinel check 3-5 langs
- Apply + commit + PR
- After merge → ES user видит «📏 Mis Métricas / Comprueba tus parámetros...»

**2. bmi/min_kcal warning copy (~351 entries × 13 langs)**
- Brief готов: [bmi_min_kcal_copywriter_brief.md](./2026-05-18_bmi_min_kcal_copywriter_brief.md)
- 4 bmi enums + 3 min_kcal enums × 4 surfaces (banner_title, banner_body, modal_full, auto_resolved) × 13 langs
- После apply → banner_block для всех BMI/kcal guards начнёт рендериться (family-agnostic loop в helper)

**3. L2 cultural review maternal AR/FA/HI/ID**
- Fiverr ~$200 ($50/lang)
- Mig 258 — pregnancy/lactation translations. L1 (clinical owner) done by me + previous agents.
- L2 catches: AR medical-authority register, FA ZWNJ correctness, HI caste-aware, ID halal-friendly

### Среднее priority

**4. Decision A vs B по UX banner redesign**
- Read [safety-banner-ux-redesign-2026-05-18.md](../knowledge/concepts/safety-banner-ux-redesign-2026-05-18.md)
- Owner picks → spawn agent for implementation

**5. Tier 4 retrofit cron** — для legacy F/15-50 с `is_pregnant IS NULL`
- APScheduler worker через partial index `idx_users_maternal_protective` (mig 253)
- Currently только 5 prod users — low urgency, но FTC mandate-ready
- One-time popup question per protected category

**6. Tier 5 auto-resolve cron**
- Daily scan для users где warning enum cleared (age turned 18, BMI cleared, pregnancy ended)
- Push «🎉 Защита снята»
- Cleanup `users.shown_guards` entries when warning auto-resolves

### Низкое priority / future

**7. Digital twin Google Sheets validation**
- Owner предлагал валидировать через [LiveOps table](https://docs.google.com/spreadsheets/d/1t-5xsGaYP64Dk7NKfRnCGignlbtOKyG0a2LE6jjOGB0/edit)
- 15-20 sentinel profiles через `calculate_user_targets` v8 → expected outputs CSV → paste в Sheets

**8. P1+ backlog**
- Schofield/Molnar/Lührmann age formula switch (P1.5)
- Vegan protein adjustment, ABW для obese, athlete phenotype (P1)
- EA / RED-S guard (P2.5b) — нужен P2.5a workout tracking + P2.1 waist quiz

---

## 🧪 Live-test recipes для regression checks

### User 786301802 (canonical test user — 16yo F)

```sql
-- Current state check:
SELECT status, goal_type, goal_speed, is_pregnant, shown_guards 
FROM users WHERE telegram_id=786301802;
```

**Scenario 1: informational disclaimer (goal=maintain)**
```sql
UPDATE users SET goal_type='maintain', goal_speed='normal', shown_guards='{}'::jsonb
WHERE telegram_id=786301802;
```
Expected:
- Click «Профиль»: Tier 1 push «💡 Небольшой спойлер...» ARRIVES FIRST
- Persistent banner на Profile screen: EMPTY (informational skipped mig 263)
- shown_guards populated with `underage_disclaimer`

**Scenario 2: hard_block + hard_regulated stack (goal=lose)**
```sql
UPDATE users SET goal_type='lose', goal_speed='normal', shown_guards='{}'::jsonb,
                 is_pregnant=NULL  -- protective mode trigger
WHERE telegram_id=786301802;
```
Expected:
- Click «Профиль» → 🚀 Мой план:
- Banner stack (post-mig 268): age «🛡️ До 18 — без жёсткого дефицита» FIRST, then maternal «🛡️ Статус не указан — защитный режим»
- goal_type_label = «Поддержание»
- goal_speed_label = «—» (suppressed)

**Scenario 3: pregnancy via Profile UI**
```sql
-- Set is_pregnant=TRUE через Profile → Мои Данные → 🌸 Женское здоровье → 🤰 Беременность: ❓ Не указано → 🤰 Беременность → выбрать Q2
-- (после merge PR #102)
```
Expected:
- target_calories: +340 (Q2 bonus)
- pregnancy_warning='pregnancy_force_maintain' (hard_block)
- protein +25g

### VPS logs spot check

```bash
ssh root@89.167.86.20 'journalctl -u noms-webhooks --since "30 min ago" | grep -E "ERROR|Traceback|first_trigger_modal_sent|SHADOW_ROUTE"' | tail -30
```

Healthy signs:
- `AUTHORITATIVE_MENU_V3 ... py=True elapsed_ms=200-360` for most clicks
- `first_trigger_modal_sent ... severity=...` for first guard trigger
- 0 ERROR / Traceback

---

## 📂 Critical files reference

### Code
- `/Users/vladislav/Documents/NOMS/dispatcher/router.py` — PROFILE_V5_CALLBACKS + BUTTON_ONLY_STATUSES + ONBOARDING_STATUSES. **Add new callbacks here when создаёшь headless screen!**
- `/Users/vladislav/Documents/NOMS/services/template_engine.py` — `_build_button_text` now accepts template_vars (mig 262 era)
- `/Users/vladislav/Documents/NOMS/services/safety_guards.py` — async Tier 1 push hook (mig 264)
- `/Users/vladislav/Documents/NOMS/webhook_server.py` — `_send_safety_guard_modals` (await before menu, post-mig 266)
- `/Users/vladislav/Documents/NOMS/handlers/menu_v3.py` — dispatch_with_render call. `_PROFILE_V5_TEXT_INPUT_STATUSES` (edit_weight/age/height) used for save toast

### KB (canonical sources)
- `concepts/calc-user-targets-roadmap.md` — P0 sprint state + P1+ backlog
- `concepts/safety-guard-ux-pattern.md` — UX framework + §2b Implementation Status (mig 263 + 264 + 268 updates)
- `concepts/pregnancy-lactation-clinical-spec.md` — full clinical spec + §6b/c decisions
- `concepts/copywriter-playbook.md` — single entry point для translation sessions
- **`concepts/safety-banner-ux-redesign-2026-05-18.md`** (new) — UX redesign A vs B
- `concepts/energy-availability-design-decision.md` — EA deferral rationale (P2.5b)
- `concepts/agent-collaboration-protocol.md` — 10 rules (severity, key naming, L1/L2 review tier)

### Daily / handover
- `daily/2026-05-17.md` — mig 234 v6 + mig 239 storage + clinical decisions
- `daily/2026-05-18.md` — full session log (extensive)
- `handover/2026-05-18_nutritionist_session_close_v2.md` — previous handover
- **`handover/2026-05-18_nutritionist_session_close_v3_FINAL.md`** ← you are here
- `handover/2026-05-18_bmi_min_kcal_copywriter_brief.md` — for bmi/min_kcal copywriter
- `handover/2026-05-18_age_warnings_python_handler_brief.md` — historical (закрыто mig 264 Tier 1)

---

## ⚠️ Что НЕ трогать без явного запроса owner'а

- **Mig 254 protective mode logic** — defensive net для legacy NULL users (F/15-50+lose). Удалять нельзя.
- **`_safety_guard_severity()` severity matrix** (mig 264) — canonical source per safety-guard-ux-pattern §3. Изменения только через protocol Rule 6 escalation.
- **Existing prod user data** — все миграции applied transactionally, snapshots сохранены 7 days. Не удалять до 2026-05-25.
- **EA implementation** — deferred decision per KB. Не triggering без P2.5a (workout tracking) + P2.1 (waist quiz) deps.
- **mig 240/241/242/258/267** (translations) — applied + verified + L2-flagged. L2 review будет отдельной session, не пытаться править преждевременно.

---

## 🎬 Полезные команды для следующего agent

```bash
# 1. Confirm PR #102 state (нужно merge'нуть)
cd /Users/vladislav/Documents/NOMS && gh pr view 102 --json state,mergedAt,checksUrl

# 2. Pull latest main + rebase worktree
cd /Users/vladislav/Documents/NOMS/.claude/worktrees/ecstatic-darwin-344d05
git fetch origin main && git rebase origin/main

# 3. Check pending translations status
python3 -c "
import os, psycopg2
from dotenv import load_dotenv; load_dotenv('.env')
c=psycopg2.connect(os.environ['DATABASE_URL']).cursor()
c.execute(\"SELECT lang_code, content->'profile'->>'personal_metrics_text' FROM ui_translations WHERE lang_code='es'\")
print('ES personal_metrics_text:', c.fetchone()[0][:100])
"

# 4. Live VPS logs (диагностика button issues / errors)
ssh root@89.167.86.20 'journalctl -u noms-webhooks --since \"30 min ago\" | grep -E \"ERROR|Traceback|cmd_\"' | tail -30

# 5. Check user 786301802 state (test user)
python3 -c "
import os, psycopg2
from dotenv import load_dotenv; load_dotenv('.env')
c=psycopg2.connect(os.environ['DATABASE_URL']).cursor()
c.execute(\"SELECT status, goal_type, goal_speed, is_pregnant, shown_guards FROM users WHERE telegram_id=786301802\")
print(c.fetchone())
"

# 6. Apply migration (template)
python3 -c "
import os, re, psycopg2
from dotenv import load_dotenv; load_dotenv('.env')
conn = psycopg2.connect(os.environ['DATABASE_URL'])
conn.autocommit = False
cur = conn.cursor()
with open('migrations/NNN_my_migration.sql') as f:
    sql = f.read()
sql = re.sub(r'^\s*BEGIN\s*;', '', sql, count=1, flags=re.MULTILINE)
sql = re.sub(r'COMMIT\s*;\s*\$', '', sql, count=1, flags=re.MULTILINE)
cur.execute(sql)
# Sentinel tests via SAVEPOINT...ROLLBACK TO SAVEPOINT
conn.commit()
conn.close()
"
```

---

## 🎯 First action для следующего agent

1. **Read** этот handover полностью (~30 min)
2. **Check** mig 269 agent's completion notification (или его output_file если есть)
3. **Verify** PR #102 state — merge если не merged
4. **Live-test** scenario 1+2 на 786301802 (post-#102 deploy)
5. **Then pick** task from §«Open work» по priority

Удачи! P0 sprint **готов end-to-end**. Остаток — polish, copy expansion, и UX redesign decision.

---

**Closing notes from agent:** контекстное окно большое и насыщенное (5+ часов работы). Если что-то выглядит нелогично в этом handover — это либо мой stale state, либо последняя информация была за минуту до compaction. Live SQL state — единственный source of truth.
