# Handover — UX redesign sweep session close (2026-05-25)

**From:** UX-агент / single-session sweep (Sage v2 prompts, mobile compaction, profile/progress redesigns)
**To:** Next NOMS agent
**Status:** ✅ Все 11 PR'ов из сессии в `origin/main`. Migration HEAD = 355 (с учётом параллельного mig 352 другого агента).

---

## TL;DR

Большой sweep по UX-полировке трёх главных reply-keyboard экранов после Stage 7 cutover:
- **stats_main** (☀️ Мой день) — mig 348/350/351
- **progress_main** (🚀 Прогресс) — mig 353/354
- **profile_main** (👤 Профиль) — mig 353/355
- **Sage v2** prompt shortening — mig 349

+ 2 bug fixes без mig:
- **#193** `cmd_stress_high` silent drop (TypeError в hybrid handler) + 5 sleep test fixes + Stress toast restore
- **#194** Sage fog-prompt regression после Stage 7 (handle_ai_input / _handle_edit_meal_input молчали при is_food=False)

---

## Что live в проде сейчас

### Templates изменены (× 13 langs)
- `stats.main_text` — mig 348/350/351 (БЖУ X/Y построчно, ✅±10% коридор / ⚠️ outside, sleep/stress strip вверху для premium, blank-line trim)
- `progress.main_text` — mig 353/354 (стрик отдельной строкой с label «Дней в ударе», mana под XP/coins, mana-line СКРЫТА для premium)
- `profile.main_text` — mig 355 (inline title `👤 Vlad · 📅 с MM.YYYY`, activity/training/phenotype строки, 🎯 Норма в конец, default phenotype reuse phenotype_standard)
- `sage.system_prompt_my_day` — mig 349 (100-250 → 80-150 chars × 13 langs)

### Sage v2 cache
- Mig 349 invalidated 3 cached юзеров → следующий stats_main view = static fallback + async regen с новым prompt'ом.
- Я pre-populate'нул cache для 417002669 (admin) и 786301802 — оба сейчас имеют свежий AI ≤150c.

### New app_constants
- `icon_battery = 🔋`, `icon_dna = 🧬` (mig 353)
- `macro_status_band_pct = 10` (mig 348)

### New translation keys (всего 156 + 44 i18n L2 refresh в mig 355)
- `profile.logs_remaining_free` × 13 (mig 353)
- `profile.since_prefix` × 13 (mig 355)
- `profile.activity_label` + `activity_<value>` × 13 × 5 (mig 355)
- `profile.training_<value>` × 13 × 6 (mig 355, включая legacy `none`/`sedentary`)
- `phenotype.result_explanation_*` × 11 langs L2 refresh (mig 355, owner-provided)

---

## Pending TODOs

### 1. 🔴 Menu latency optimization (HIGH priority, owner-flagged)

**Memory:** `~/.claude/projects/-Users-vladislav-Documents-NOMS/memory/project_menu_latency_watch.md`

Live ssh tail 26.05 admin 8 кликов подряд показал:
- routing корректен (8/8 — никаких подмен)
- **p95 click→render ~330ms** (target <300)
- **double `GET /v_user_context`** на каждый callback: `sync_user_profile` (telegram_proxy fire-and-forget) + `_try_authoritative_path` (ensure user). 170ms из 330ms total — pure DB roundtrip × 2.

**Optimization candidate:** share ctx через context manager или asyncio.Lock + shared fetch. Cut p95 на ~50%.

**Также:** owner reported subjective lag для Progress / Profile / `cmd_profile_subscription` / `cmd_my_plan` / `cmd_settings` (vs. fast stats_main). Подозревает n8n leftover. Проверить `dispatcher/forward.py:TARGET_TO_PATH` cross-reference с logs — какие target'ы реально идут через n8n.

### 2. 🟡 Phenotype always-show vs hide-for-default (owner — обсуждает с нутрициологом)

Mig 355 always-show с label «Стандартное» для default (reused `phenotype_standard`). Owner обсуждает с нутрициологом нужно ли это или для не-спортсменов phenotype = noise. Owner вернётся с решением — может быть mig 356 toggle.

### 3. 🟡 PR #203 (mig 355) await merge

Owner UAT прошёл (`«Меню посмотрел мне все нравится»`). PR ждёт merge. После merge — auto-deploy не нужен (миграция уже в БД через psycopg2).

### 4. 🟢 Race condition визуальная (low priority, no fix needed)

Owner reported «нажал Прогресс — пришёл Профиль». Live логи опровергли (8/8 кликов правильно routed). Race происходит в Telegram client'е при быстрых tap'ах — два update'а параллельно, второй ответ перерисовывает первый. **Не bug routing, восприятие.** Mitigation — per-user lock в webhook_server (есть открытая ветка `claude/td-17-per-user-lock`, может быть частично готова).

### 5. 🟢 Stage 7c cleanup (still pending, не наш scope)

После 1-2 нед stable global cutover. См. handover/2026-05-25_python_ai_engine_complete.md от Stage 7 agent'а.

### 6. 🟢 Member since edge case

`first_name_truncated` использует `SPLIT_PART(first_name, ' ', 1)` + truncate ≤12c. Не покрывает Chinese/Japanese unicode names без space. Low priority — если фейл случится, видимо в логах.

---

## Architectural lessons captured this session

### 1. Premium-hide line pattern (NEW KB) — [[concepts/premium-hide-line-pattern]]
Использован в 4 mig подряд (343/348/353/354/355). Pre-resolved SQL string с встроенным leading/trailing `\n`. Empty case не создаёт orphan blank line. Шаблон для любых conditional-hide строк.

### 2. Mig 343 toast contract (был неизвестен)
`button.meta.callback_alert_i18n_key` → SQL `process_user_input` резолвит → `telegram_ui.callback_alert_text` → Python `render_envelope` прикрепляет к ACQ → Telegram показывает toast popup. **Уже работает для save_via_callback кнопок.** Если делаешь hybrid handler (Python bypass'ит SQL save), toast надо эмитить руками через `OutboundItem(strategy='answer_callback_only', callback_alert_text=...)`. Pattern в `handlers/menu_v3.py:_handle_stress_high`.

### 3. `current_value_source='daily_metrics'` extension (mig 347)
checkmark-prefix-pattern теперь поддерживает источник не только из `public.users`, но и `daily_metrics WHERE date=CURRENT_DATE`. Subagent обновил [[checkmark-prefix-pattern]] KB.

### 4. State pollution в integration tests
`SAVEPOINT/ROLLBACK` не cleanup prod-rows за CURRENT_DATE если test TID = реальный админ-юзер. Add explicit DELETE в фикстуре ПОСЛЕ SAVEPOINT. Pattern в `test_phase3b_sleep_ux.py` / `test_adaptive_modifiers_foundation.py`.

### 5. `RouteDecision` dataclass + `SimpleNamespace(**vars(d), kwarg=...)` = TypeError
Duplicate kwarg `callback_query_id`. Use `dataclasses.replace(decision, callback_query_id="")` вместо SimpleNamespace dict-spread. Lesson commit `4111cb9`.

### 6. Mig 329 changed `get_day_summary.target_protein_g` semantics
До: base. После: adjusted (= adjusted_targets.protein_g). Тесты на base должны брать из `users.target_protein_g` напрямую. Sage v2 `services/sage.py:451` (`adjusted_targets or targets`) — потребитель expects adjusted.

### 7. Sage v2 system prompt живёт в `ui_translations.<lang>.sage.system_prompt_my_day`
**НЕ** в таблице `ai_prompts` (там только food_recognition / food_recalculate / food_recalculate). Если ищешь Sage tuning — сначала здесь. См. mig 349.

---

## Files touched этой сессии (compact list)

### Code (Python)
- `handlers/menu_v3.py` — `_handle_stress_high` TypeError fix + toast
- `handlers/food_log.py` — `_build_fog_envelope` helper + 2 call sites
- `tests/integration/test_phase3b_sleep_ux.py` — fixture cleanup + T11 base fix
- `tests/integration/test_adaptive_modifiers_foundation.py` — fixture cleanup + T16 base fix

### Migrations
- `migrations/347_checkmark_sleep_stress_checkin.sql` (PR #195)
- `migrations/348_stats_main_mobile_redesign.sql` (PR #196)
- `migrations/349_sage_my_day_prompt_shorter.sql` (PR #197)
- `migrations/350_stats_main_streak_keep_label.sql` (PR #198)
- `migrations/351_stats_main_macro_warn_outside_band.sql` (PR #199)
- `migrations/353_progress_profile_mobile_redesign.sql` (PR #201)
- `migrations/354_progress_mana_hide_premium.sql` (PR #202)
- `migrations/355_profile_v2_activity_training_phenotype.sql` (PR #203)

### KB
- **NEW:** `knowledge/concepts/premium-hide-line-pattern.md` + entry в `index.md`
- **UPDATED** (subagent): `knowledge/concepts/checkmark-prefix-pattern.md` — current_value_source extension

### Memory
- `~/.claude/projects/.../memory/project_menu_latency_watch.md` — created + 2 update entries

---

## Subagent reports

1. **a15cd45117e9199b0** (checkmark mig 347) — design pivot: extended `meta.current_value_source` instead of `v_user_context` columns. Clean PR.
2. **a1612982d5910663e** (stats_main redesign mig 348) — 7/8 fixes. NO-OP'd #4 (Sage prompt) ошибочно — искал в `ai_prompts` table вместо `ui_translations.sage.system_prompt_my_day`. Закрыто в mig 349 main-agent'ом.
3. **a1df0b1e4a0e62fc9** (progress + profile redesign mig 353) — clean.
4. **a68606acb5740a59c** (fog-prompt investigation) — root cause + fix proposal.
5. **ab02a8c9b1d5c5110** (phenotype quiz investigation) — false alarm. Owner ответил правильно, классификация корректно даёт `default`.
6. **aa9e905745f5c3e77** (profile v2 mig 355) — clean. Reused canonical icons вместо owner-mockup.

---

## Команды для quick onboarding следующего агента

```bash
# Свежий main
cd ~/Documents/NOMS
git checkout main && git pull --ff-only

# Today's daily journal
cat claude-memory-compiler/daily/2026-05-25.md | tail -60

# Этот handover
cat claude-memory-compiler/handover/2026-05-25_ux_redesign_sweep_close.md

# Live render для UAT (admin)
psql $DATABASE_URL -c "SELECT public.render_screen(417002669, 'profile_main');" -F$'\t'
psql $DATABASE_URL -c "SELECT public.render_screen(417002669, 'progress_main');" -F$'\t'
psql $DATABASE_URL -c "SELECT public.render_screen(417002669, 'stats_main');" -F$'\t'

# Latency monitor (для приоритета #1)
ssh root@89.167.86.20 'journalctl -u noms-webhooks --since "30 min ago" | grep -E "AUTHORITATIVE_MENU_V3|SHADOW_ROUTE" | tail -50'
```

---

**Migration HEAD:** 355. **Translation gaps:** 0 (всё закрыто). **p95 profile_main:** 48ms VPS / 138ms Mac. **Open PR:** #203 (mig 355) ждёт merge — auto-deploy не критичен.

— UX-агент, 2026-05-25 EOS
