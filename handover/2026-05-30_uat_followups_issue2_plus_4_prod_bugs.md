# Handover — Issue 2 UAT follow-up + 4 prod bugs (2026-05-30)

**From:** Sonnet session (28-30.05) — Topic 1/2/3 close + Issue 1/2/3 + P0/P1 + Issue 2 city resolver
**To:** Next NOMS agent
**Status:** ✅ 10 PR'ов merged (#219, #220, #221, #222, #223, #224, #225, #226, #228, #233). 1 open task: разобраться с UAT findings ниже.

---

## TL;DR

Session 28-30.05 закрыла все 3 owner-topics (⚠️ БЖУ / backups / cron audit) + 3 UAT bugs (Issue 1/2/3) + P0 mig 372 (sleep/stress _global_floating_actions) + P1 mig 374 (reply-kb reattach) + **Issue 2 mig 379** (AI city resolver, 3-tier Pattern A). Все merged.

UAT после merge #233 (Issue 2) выявил **5 items для следующего агента**:
- 1 follow-up по Issue 2 (edge case с маленьким Spanish городом)
- 4 prod bugs unrelated к моим PR'ам (delete account screen / reply-kb persistence / sticker order / welcome tone)

---

## Полный список merged PR'ов session 28-30.05

| PR | Mig | Что | Status |
|---|---|---|---|
| #219 | 366 | Cron F1+F2+F3 — sleep/stress кнопки + zen-filter + activity mutex | ✅ merged |
| #220 | 367 | Drop 3 food_log backup tables + CI guard pr-backup-table-guard.yml | ✅ merged |
| #221 | 368 | macro_warn hour-gate Python presentation layer (hide ⚠️ UNDER до 15:00 local) | ✅ merged |
| #222 | 369 | INTERVAL '30 min' → app_constants.reminder_activity_mute_minutes | ✅ merged |
| #223 | 370 | sleep/stress Sage variants × 13 langs (3-variant rotation) + Python helper array+scalar | ✅ merged |
| #224 | 371 | buttons.share_location × 13 langs (fix English fallback) | ✅ merged |
| #225 | — | Python-only Sage META time-warning if local_hour>=16 | ✅ merged |
| #226 | 372 | 🚨 **P0 fix** — sleep/stress callbacks в `_global_floating_actions` (mig 366 regression) | ✅ merged |
| #228 | 374 | **P1 reply-kb reattach** — `pending_kb_reattach` single-shot transient flag (4-part: ALTER + meta + PUI + render_screen) | ✅ merged |
| #233 | 379 | **Issue 2** — AI city resolver onboarding (Pattern A 3-tier + Profile sync edit_country) | ✅ merged |

---

## NEW KB concepts (3 + 1 extension)

| Concept | Purpose |
|---|---|
| [[cron-reminder-suppression-tunables]] (NEW) | timing/threshold values для cron suppression живут в `app_constants` (category=cron/ux), не RPC body |
| [[cron-pushed-callback-fallback-pattern]] (NEW) | 3 safety mechanisms (dispatcher whitelist > PUI fast-path > `_global_floating_actions`) + decision flow для cron-pushed inline buttons |
| [[sassy-sage-dialog-variants]] (EXTENDED 29.05) | cron_notifications variants pattern для Python pipeline + `->` vs `->>` PostgREST gotcha |
| `knowledge/index.md` — обновлён со всеми 3 entries в Cron-секцию + Start-here lookup table |

**Не создано (judgment calls — single-use patterns):**
- mig 368 hour-gate Python presentation pattern — documented в commit message
- mig 374 single-shot flag pattern — documented в migration body
- mig 379 callback encoding cmd_X:cc:tz_safe pattern — documented в location.py comment

Если pattern reused второй раз — обязательно extract в KB.

---

## 🔴 UAT findings для next agent

### 1. Issue 2 follow-up — «Авилес» (Cyrillic Avilés) edge case

**Что произошло:** Owner UAT на UK lang, прошёл регистрацию до «Звідки ти?». Написал «Авилес» (свой город — Avilés, Asturias, Spain, transliterated с Cyrillic). AI city_resolver вернул confidence < 0.7 → bot выдал error fallback «🤔 Не вловив, що це за місто. Спробуй ще раз...» **3 раза**. Owner switched to geolocation share, дошёл до конца.

**Trace:** `services/city_resolver.py:parse_city("Авилес", "uk")` → AI gpt-4o-mini не recognizes small foreign cities в Cyrillic transliteration с достаточной confidence.

**Possible fixes (variants для owner approval):**

| # | Approach | Trade-off |
|---|---|---|
| **A** | Lower confidence threshold 0.7 → 0.5 (`_MIN_CONFIDENCE` в city_resolver.py:36) | Quick win. Может increase false positives для «hi»/«не знаю» chat phrases. Тестировать. |
| **B** | Improve AI system prompt — добавить explicit examples с transliterated cities (Авилес→Avilés, Гранада→Granada, Бильбао→Bilbao etc.) | Better quality, не trade-off с false positives. ~10-20 min work. |
| **C** | Add Geoapify forward-geocode fallback — если AI confidence < 0.7, попробовать Geoapify, если оно знает город — use it | Best quality, но extra API call (~150ms latency, free tier). Использует existing `services/geolocation.py`. |
| **D** | Combo B + C | Belt + suspenders. ~30 min. |

**Owner ask:** скорее всего C или D — owner wants robust city recognition for small cities.

**Files:**
- `services/city_resolver.py:36` — `_MIN_CONFIDENCE = 0.7` (для variant A)
- `services/city_resolver.py:25-50` — `_SYSTEM_PROMPT` (для variant B)
- `services/geolocation.py:reverse_geocode` — existing. Нужна `forward_geocode(text, lang)` extension для variant C/D

### 2. 🔴 Delete account screen — переводы пропали (existing prod bug)

**Симптом:** Owner ES UAT — при попытке удалить аккаунт показывается screen с speaker bubble «Noms: «»» (пустой текст в кавычках!) + 2 buttons «Eliminar» + «Cancelar». Перевод текста (вероятно `delete_account.confirm_text` или эквивалент) **отсутствует** или сломан.

**Investigation entry points:**
- `grep -rn "delete_account" migrations/ ui_translations table` — найти screen + i18n key
- `SELECT content->'delete_account' FROM ui_translations WHERE lang_code='es'` — проверить namespace
- Mig 359 incident (26.05) был P0 wipe i18n — возможно delete_account был среди affected keys и не восстановлен полностью? Check `migrations/360_*` recovery scope.

### 3. 🔴 После удаления — Reply-kb осталась видимая (existing prod bug)

**Симптом:** Owner удалил аккаунт → bot выдал «Tu cuenta está eliminada. Pulsa /start para restaurar o empezar de nuevo» — но внизу всё ещё видна reply-keyboard [Añadir comida / Mi día / Progreso / Perfil]. После soft-delete должно быть `ReplyKeyboardRemove`.

**Likely fix:** в delete_account handler envelope добавить `OutboundItem(strategy="send_new", ..., reply_markup={"remove_keyboard": True})`.

**Investigation:**
- `grep -rn "delete_account\|cmd_delete_account\|soft_delete" handlers/ services/` — найти где обрабатывается удаление
- См. KB [[concepts/soft-delete-account]]
- Сравнить с lang_change или logout flows где reply-kb убирается правильно

### 4. 🔴 Welcome screen — стикер + текст переставлены местами (existing prod bug)

**Симптом:** Owner после /start (свежий аккаунт ES UAT) видит:
1. Text «¡Hola! Soy NOMS — tu nutricionista IA» + inline buttons [Empezar / Idioma]
2. **THEN** стикер 👋 NOMS

Должно быть наоборот: стикер ПЕРВЫМ (привлекает внимание), потом text + buttons.

**Investigation:**
- Это flow первого `/start` → welcome screen
- Stiker auto-fires через render_screen.sticker_category? Если да — может быть SQL order issue
- KB [[concepts/telegram-sticker-pipeline]] / [[concepts/noop-render-strategy-pattern]]
- Возможно order envelope items wrong в `handlers/onboarding_v3.py` welcome handler

### 5. 🟡 Welcome text — не Sage tone × 13 langs (existing UX debt)

**Симптом:** «¡Hola! Soy NOMS — tu nutricionista IA» (current ES) — слишком generic. Owner просит rewrite в Sage voice (дерзкий мудрец) для всех 13 langs.

**Это is **first message** от бота — критический impression.** Owner emphasized «должно быть крутым и понятным с первого взгляда».

**Approach (per [[copywriter-playbook]]):**
- Draft owner-approved RU+EN baseline (Sage tone: «🤖 Привет. Я NOMS — твой AI-нутрициолог без skuки и shame. Жрём по уму или штрафной за неправильный завтрак?» — нечто такое)
- Owner approve baselines
- Copywriter subagent → 11 langs per [[sassy-sage-multilingual-glossary]] Part II
- Mig × 13 langs обновление translations

**Affected key:** find via grep — probably `onboarding.welcome.title` or `start.welcome` в ui_translations.

---

## 📋 Recommended order for next agent

1. **Quick win #2 + #3** (delete account screen + reply-kb removal) — likely 1 small mig + Python tweak. Same domain (delete flow).
2. **#4 sticker order** — investigate render order, possibly small fix in onboarding handler.
3. **Issue 2 follow-up (#1)** — propose A/B/C/D variants to owner, implement chosen.
4. **Welcome tone rewrite (#5)** — owner-approved draft + copywriter subagent + mig.

Items 1-3 are bug fixes (short). Item 5 is bigger UX work (~1-2h).

---

## State summary

- **Migration HEAD:** 379 (mig 375-378 by other agents в течение 29.05; mig 379 by my session)
- **MEMORY.md:** updated, includes mig 366-374 cycle
- **Daily:** 2026-05-29.md + 2026-05-30.md (this session start)
- **No outstanding worktrees** of mine — все merged, branches deletable

---

## Important context для следующего агента

- **Stage 7 (Python AI Engine) — GLOBAL since 29.05** (mig 373 + PR #227 by other agent). Owner cutover'нул.
- **mig 375-378 другие агенты** — cycle UX refactor, xp_correction_bonus, DIAAS UX, ai_correction_audit. См. их daily entries.
- **Stage 7c cleanup** — open tech debt (deactivate n8n 03_AI_Engine, etc.) — per [[stage7-global-cutover]]
- **Menu latency optimization** — open: double GET v_user_context per callback (170ms из 330ms) — handover 2026-05-25_ux_redesign_sweep_close.md

---

## My KB doc updates checklist

- ✅ daily/2026-05-29.md — appended my session entry
- ✅ daily/2026-05-30.md — created (this session start)
- ✅ MEMORY.md — updated mig HEAD + recent shipped
- ✅ knowledge/concepts/cron-reminder-suppression-tunables.md (NEW)
- ✅ knowledge/concepts/cron-pushed-callback-fallback-pattern.md (NEW)
- ✅ knowledge/concepts/sassy-sage-dialog-variants.md (EXTENDED)
- ✅ knowledge/index.md — entries added
- ✅ handover/2026-05-30_uat_followups_issue2_plus_4_prod_bugs.md (THIS file)

---

— Sonnet session 28-30.05, EOS 13:30 МСК
