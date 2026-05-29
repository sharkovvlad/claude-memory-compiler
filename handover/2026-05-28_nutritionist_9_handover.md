# Handover для Агента Нутрициолога 9 (Track C + Track Strategic)

**Дата:** 2026-05-28
**От:** Agent предыдущей сессии (Nutritionist 8, продолжатель after nervous-cerf-566d7a)
**Кому:** Nutritionist 9

---

## Что важно понимать сразу

**Параллельно работают другие агенты.** Это значит:
- Перед началом любой работы — `git fetch origin main && git rebase origin/main` (взять свежий main, иначе твои коммиты будут конфликтовать с тем что параллельно мерджнули).
- Перед созданием новой миграции — **проверить актуальный номер**: `ls migrations/ | sort | tail -5` + `gh pr list --state open --json files --jq '.[].files[].path' | grep migrations` (увидишь файлы из открытых PR — нельзя на тот же номер).
- На сегодня Migration HEAD = **365**, твой первый свободный номер обычно 366+ (но проверяй сразу перед `git push` — за час параллельный агент может занять).

**Payment-задачами занимается отдельный агент** — не трогай ничего связанного с Stripe / Stars / TON / promo / subscription / dunning. Если по дороге найдёшь баг — флагни в handover для payment-агента, не правь сам.

**Owner — Vladislav, говорит по-русски, не любит сложные технические термины.** Когда пишешь ему план — объясняй человеческими словами что именно произойдёт и зачем. Цифры/код можно прилагать в конце как «детали для агента», но первый абзац всегда — простыми словами для человека.

---

## Обязательно прочитать перед стартом (в этом порядке)

1. `~/.claude/projects/.../memory/MEMORY.md` — общий контекст проекта (может быть устаревший на 2 дня, верифицируй live).
2. `claude-memory-compiler/daily/2026-05-28.md` — что было вчера (Stars recurring foundation).
3. `claude-memory-compiler/daily/2026-05-27.md` — позавчера (mig 361 recovery gap + Track B/C/D/E shipped).
4. Этот handover.
5. `~/Documents/NOMS/CLAUDE.md` — операционные правила (СТОП-ПРАВИЛО NLM-first, no hardcodes, и т.д.).

**Перед любой миграцией, трогающей `ui_translations.content` или JSONB:**
- Прочитай [[concepts/jsonb-shallow-merge-antipattern]] — этим багом 2 раза за неделю агенты ломали прод.

**Перед делегированием SQL subagent'у с правом apply LIVE:**
- Прочитай [[concepts/subagent-live-apply-review-rule]] — orchestrator (это ты) ОБЯЗАН прочитать SQL до того как subagent его применит.

**Перед написанием i18n значений для кнопок:**
- Прочитай [[concepts/double-emoji-button-anti-pattern]] — если у кнопки есть `icon_const_key`, эмодзи в переводе НЕ нужен (рендерер сам префиксит).

Все 3 — в index.md в секции «Start here for common tasks».

---

## Где мы сейчас (live state, проверено 2026-05-28)

- **Migration HEAD: 365** (синхрон main ↔ prod, 0 open PRs).
- **Phase 3d cycle UX** полностью работает: opt-in flow, dynamic hub label, edit cycle length presets, onboarding cycle question (FSM активен, screens рендерятся).
- **Stars Recurring** в стадии Foundation (mig 364) + RPCs (mig 365), но Stars Subscriptions DISABLED hotfix'ом — ждёт когда owner настроит BotFather. **Это не твоя задача** — payment-агент.
- **Maternal onboarding** (registration_step_maternal, pregnancy/lactation вопросы) уже на **всех 13 языках** (mig 269 + 286 + 361). MEMORY про «EN fallback maternal sub-menu» УСТАРЕЛ — уже сделано, ничего не нужно копирайтить.

---

## Что я обнаружил во время analysis (важные ПРОБЕЛЫ)

### 🔴 Пробел 1: Adaptive TDEE — НЕ реализован

**Что это означает простыми словами:**
Сейчас бот считает дневной расход калорий (TDEE) **по статичной формуле** один раз — на основе веса, возраста, активности и роста. Если юзер похудел на 5 кг и калорийная норма не пересчитывается автоматически, его план становится неточным.

**Adaptive TDEE** — это когда бот:
1. Смотрит вес юзера за последние 14-30 дней (нужна таблица истории веса).
2. Смотрит сколько он съел за эти 14-30 дней (есть в `food_logs`).
3. Вычисляет фактический расход из дельты «съел − ((вес_конец − вес_начало) × 7700)» (7700 ккал в 1 кг жира).
4. Постепенно сдвигает расчётный TDEE юзера к фактическому (например 70% old формула + 30% measured).

**Что в проде сейчас:**
- ❌ Нет колонки `users.tdee_adaptive` или подобной.
- ❌ Нет таблицы `weight_history` (юзеры обновляют вес, но история не хранится отдельно).
- ❌ Нет RPC `recalculate_tdee_from_history`.
- ✅ Есть `calculate_user_targets` — статическая формула (Schofield-HW / Molnar / Lührmann по mig 292).
- ✅ Есть `food_logs.calories` за всё время.

**Что нужно сделать (high-level):**
1. **Дизайн-spec** — обсудить с owner'ом + НЛМ-проверка (CLAUDE.md §СТОП-ПРАВИЛО). Решения:
   - Окно усреднения (14, 21, 30 дней? чем длиннее — стабильнее, но медленнее реагирует).
   - Минимальный набор данных для запуска (≥7 дней еды + ≥2 замера веса).
   - Smoothing factor (например EWMA, exponential weighted moving average).
   - Safety floor: не давать TDEE упасть ниже BMR × 1.0 (RPP safety).
2. **Mig N — schema**:
   - `weight_history` table (telegram_id, recorded_at, weight_kg).
   - `users.tdee_adaptive_value` + `users.tdee_adaptive_confidence` + `users.tdee_last_recalc_at`.
   - Trigger или cron, добавляющий запись в `weight_history` при `users.weight_kg` UPDATE.
3. **Mig N+1 — RPC `recalculate_tdee_from_history(p_telegram_id)`**:
   - Считает фактический energy balance из history.
   - Обновляет `users.tdee_adaptive_value` если данных достаточно.
   - Логирует в `daily_modifiers` или новой таблице.
4. **Cron** — `AdaptiveTdeeCron` 02:00 UTC daily.
5. **`calculate_user_targets` patch** — если `tdee_adaptive_value` IS NOT NULL — использовать его, иначе статическую формулу.
6. **UX** — в `my_plan` screen показывать «🤖 План адаптируется по твоему фактическому расходу» когда adaptive активен, плюс badge confidence.
7. **i18n × 13 langs** для нового UX-текста (subagent).

**Размер:** большая работа, ~3-5 миграций + 1 cron + Python no changes. Спецификации в roadmap нет — **нужен дизайн-документ перед тем как кодить.** Я бы предложил owner'у сначала обсудить — может он хочет другую механику.

---

### 🔴 Пробел 2: Dynamic Katch-McArdle switching — НЕ реализован полностью

**Что это означает простыми словами:**
Katch-McArdle — это самая точная формула BMR (базового метаболизма) **когда известен процент жира в организме (body_fat_pct)**. Сейчас у нас есть 2 пути:

**Путь A (уже работает):** RFM (Relative Fat Mass) — оценка body_fat_pct из роста и обхвата талии. Точность ±5%. После mig 295 (P2.3) у юзеров с заполненным `waist_circumference` BMR считается через Katch-McArdle на основе вычисленной RFM.

**Путь B (нет):** клинически точный body_fat_pct — от DEXA-сканера, BodPod, или каллиперов с лабораторной точностью. Точность ±1-2%. **Сейчас юзер не может ввести «у меня измерили 18% жира на DEXA» — нет поля и UI.**

**Что нужно сделать:**
1. **Schema**: `users.body_fat_pct_clinical` + `users.body_fat_pct_clinical_source` (enum: dexa / bodpod / calipers / bia_lab) + `users.body_fat_pct_clinical_measured_at`.
2. **UI**: новый раздел в `personal_metrics` или `my_plan` settings — «📊 Клинический процент жира». Кнопка → text_input → save_user_clinical_body_fat RPC.
3. **`calculate_user_targets` patch** — priority chain:
   - Если `body_fat_pct_clinical` < 90 дней назад → использовать его в Katch-McArdle (max accuracy).
   - Иначе если есть `waist_circumference` → RFM-производный Katch-McArdle (mig 295).
   - Иначе → Schofield-HW / Molnar / Lührmann fallback.
4. **Decay logic**: клинические измерения старше 90 дней — confidence снижается, postepenno возвращаемся к RFM пока не введут свежее.
5. **i18n** × 13 langs — Sage tone про «лабораторная точность» без medical jargon.
6. **Safety**: clamp 5-50% (sanity), не разрешать input если разница с RFM > 10pp (warn про «проверь данные»).

**Размер:** средняя работа, ~2 миграции + 1 RPC + UI button + i18n. Меньше чем Adaptive TDEE.

---

### 🟡 Пробел 3: Phase-aware Sage commentary — НЕ реализован

**Что это означает простыми словами:**
В Phase 3d мы добавили tracking менструального цикла (мig 334-360). Бот знает фазу цикла (`users.cycle_phase`) и день (`compute_cycle_day_for_user`). Но Sage (наш ИИ-комментатор который пишет one-liner в Мой День) **не знает про фазу и не комментирует её**.

**Хотим:** когда юзерша в лютеиновой фазе и наелась углеводов — Sage может тонко сказать «лютеиновая фаза любит углеводы, это нормально». Когда в фолликулярной — может комментировать энергию. **Без medical jargon, без shame.**

**Что в проде сейчас:**
- ✅ `cycle_phase` column есть, но 0 юзеров (никто ещё цикл не настроил — недавно зашло)
- ✅ `compute_cycle_day_for_user(p_telegram_id)` RPC работает
- ❌ Sage prompt (в `services/sage.py`) не получает фазу/день в payload
- ❌ Нет phase-aware seeds в Sage prompt

**Что нужно сделать:**
1. **Patch Sage prompt в `services/sage.py`** — добавить в payload `cycle_phase` + `cycle_day_in_phase` для opted-in юзерш (если female AND non-pregnant AND non-lactating AND cycle_tracking_enabled).
2. **System prompt инструкция** — «if cycle_phase=luteal AND macro_excess_carbs — невзначай отметь что лютеиновая фаза любит углеводы. Без medical terms. Без shame. Опционально, не каждый день.»
3. **Phase-aware seeds** — 2-3 примера в Sage prompt per фаза (фолликулярная / овуляция / лютеиновая / менструация). Subagent для copywriter × 13 langs.
4. **Без миграции если только prompt-tweak.** Только Python + copywriter.

**Размер:** маленькая работа — 1 Python patch + 1 prompt update + copywriter (1-2 hours).

---

### 🟡 Пробел 4: BMI/min_kcal warnings — copywriter pending

**Что это означает простыми словами:**
Когда у юзера BMI слишком низкий (underweight) или калорийная норма слишком жёсткая (например 1200 ккал для женщины), бот должен показывать предупреждения — anti-РПП safety. Тексты этих предупреждений написаны в copywriter brief за 2026-05-18, но в проде ключи `warning.*` отсутствуют (для RU = `not-dict`, т.е. namespace пустой/нет).

**Что нужно сделать:**
- Найти brief: `claude-memory-compiler/handover/2026-05-18_bmi_min_kcal_copywriter_brief.md`
- Subagent копирайтер сгенерирует строки × 13 langs (≥5/5 critic, anti-shame, gender-neutral)
- Mig N — `jsonb_set` per leaf (`warning.bmi.underweight.banner_title`, `warning.bmi.underweight.banner_body`, и т.д.)
- L1 cultural sanity check ([[concepts/l1-cultural-sanity-brief]])
- Owner approve → apply LIVE
- L2 native review (AR/FA/HI/ID) опционально через Fiverr ~$200, но мог не быть нужен — owner решит

**Размер:** средняя работа, 1 миграция + copywriter subagent (1 день).

**КВ для копирайтера:** [[copywriter-playbook]] (entry-point), [[safety-guard-ux-pattern]] §5 (5 surfaces), [[sassy-sage-multilingual-glossary]] Part II per-lang tone.

---

### ✅ ЗАКРЫТО (но было в MEMORY как TODO)

- **Maternal sub-menu labels** — все 13 langs PRESENT в `onboarding.maternal_status_question`. Mig 269 + 286 + 361 покрыли. Можно вычеркнуть из MEMORY tech debt.
- **CI guard for jsonb shallow-merge** — DONE (PR #211, daily 2026-05-27).
- **Phase 3d cycle UX** — все 4 mig (352→356→357→360) в проде. Можно тестить.

---

## Stage 7c cleanup (Track B, оставил тебе)

**Что это означает простыми словами:**
NOMS постепенно переезжает с n8n (визуальный flow-builder) на Python. AI-распознавание еды (Stage 7) полностью переехало 25.05 — флаг `handler_ai_engine_use_python=true`. Но **старые n8n-воркфлоу `03_AI_Engine` и `06_Indicator_Clear` ещё активны** — на всякий случай как fallback.

После 1-2 недель стабильной работы (то есть после ~01.06.2026) можно их **deactivate** (не удалять — пусть будут в архиве как backup рецепт).

**Что нужно сделать:**
1. **Pre-check (важно)** — убедиться что n8n `03_AI_Engine` действительно не получает execution requests:
   ```bash
   ssh root@89.167.86.20 'curl -s -H "X-N8N-API-KEY: $KEY" http://127.0.0.1:5678/api/v1/executions?workflowId=<03_AI_Engine_id>&limit=5'
   ```
   - Если последний execution > 7 дней назад → safe to deactivate.
   - Если есть recent executions → значит кто-то ещё route'ит в n8n, флагнуть owner'у.

2. **Pull live workflow JSON** через n8n API:
   ```bash
   curl GET /workflows/<id>
   ```

3. **Safe PUT** для deactivate (per [[concepts/n8n-data-flow-patterns]] §Safe PUT):
   - Read current → set `active: false` → PUT (whitelist `{name, nodes, connections, settings}`)
   - **Никаких других изменений** в PUT body.

4. **DELETE `/internal/food_log/render` endpoint** в `webhook_server.py` — это старый fallback из dispatcher era, не нужен после Stage 7 GLOBAL.

5. **Cleanup executeWorkflow refs в `01_Dispatcher`** — Route Classifier node ещё может ссылаться на 03_AI_Engine. Через Safe PUT удалить эти branches.

6. **Через ещё неделю (если deactivated стабильно)** — DELETE workflows через n8n API.

**Размер:** маленькая работа но **CRITICAL precision**:
- `01_Dispatcher` и `03_AI_Engine` — high-conflict zones, очень легко сломать дёргание сторон.
- **Перед каждым PUT — GET свежий** ([[concepts/n8n-data-flow-patterns]] §3 Safe PUT).
- НЕ деплоить из worktree — только из `main` основного клона ([[release-protocol]]).

---

## Что НЕ трогать (Payment агент займётся)

Owner сказал что Track A — Payment — занимается отдельный агент. Если по дороге найдёшь баг в этих областях — **флагни в комментарии в коде или в handover для payment-агента, не правь сам:**

- Stripe / Stars / TON / payment_method anywhere
- `subscription_status_redesign` (mig 362) tweaks
- Crypto/promo screens One-menu pattern leak
- `set_user_status` RPC для promo flow
- Stage 6 n8n cleanup (`10_Payment` workflow + Route Classifier refs)
- BotFather Stars Subscriptions re-enable
- Dunning UX / trial 7d flow / payment success deep-link
- Payment P2 (upgrade/downgrade, EU VAT, receipts, refunds)

---

## Что нужно протестировать (хвосты)

### Onboarding cycle question — fresh test user UAT

**Простыми словами:** Mig 359 добавил новый шаг в онбординг — после вопросов про беременность/лактацию женский юзер без них теперь получает экран «🌸 Хочешь отслеживать цикл?» с тремя кнопками. **Это не тестировалось end-to-end** потому что нужен фрешер юзер (не registered).

**Как протестировать:**
1. Прочитать [[concepts/test-user-reset-recipe]] — там скрипт обнуления юзера до состояния `new`.
2. Сбросить 786301802 (или другого тестового) до `new`.
3. Owner проходит онбординг с нуля: язык → страна → таймзона → вес/рост/возраст → пол=female → беременность=нет → лактация=нет → **должен появиться экран про цикл**.
4. Если экран не появляется → router whitelist гарантировал что `registration_step_cycle` в `ONBOARDING_STATUSES` (PR #207 уже смерджена) — debug через `dispatcher/router.py`.
5. Owner кликает «✨ Да, настроить» → должен попасть на `cycle_tracking_setup` → выбирает «Сегодня» → save → переход на `registration_step_3` (вес/etc.).

**Что-то типа bug нашёл:** `users.cycle_phase` column есть, но populated=0 — значит **никто ещё цикл не настроил**. После UAT и продакшн-юзерш-female появится data, тогда Sage Phase-aware будет иметь cycle_phase для работы.

---

## Migration numbers checklist

Перед каждым `git push` нового мига:
1. `git fetch origin main`
2. `ls migrations/ | sort | tail -5` — последние 5 в main
3. `gh pr list --state open --json files --jq '.[].files[].path' | grep migrations/` — открытые PR
4. Свободный номер = max(main last, open PR max) + 1
5. **Уже после `git push --force-with-lease`** — проверить CI Migration Collision Guard в PR (auto-runs, посмотрит на live main + всех открытых PR).

Если в момент твоего push'а появилась коллизия (другой агент успел запушить тот же номер раньше) — pre-push hook остановит. См. [[concepts/migration-collision-guard]] §Override (только после coordination с owner).

---

## Помни общие правила

- **NLM первым делом** — перед SQL/планом 3-4 вопроса в блокнот `NOMS Supabase Data` (CLAUDE.md СТОП-ПРАВИЛО). Проверять имена колонок, типы, RPC сигнатуры. Доверять live (через `pg_get_functiondef`) если NLM противоречит.
- **No hardcodes** — эмодзи из `app_constants`, тексты из `ui_translations`, числа из `app_constants`. Никогда raw в коде.
- **Plan first → owner approve → implement** — особенно для big tasks (Adaptive TDEE, dynamic Katch-McArdle). НЕ начинать кодить без подтверждения owner'а.
- **Subagent для большого scope** ([[copywriter-playbook]] proven workflow). НО subagent НЕ применяет SQL LIVE без твоего review ([[subagent-live-apply-review-rule]]).
- **p95 latency benchmark** обязателен после RPC/SQL changes (10 прогонов через persistent psycopg2 connection с VPS, не Mac).
- **Rebase before commit + sanity-check diff vs main + force-with-lease** (CLAUDE.md §12).

---

## Recommended sequencing (моё мнение, не приказ)

Если owner спросит «с чего начать» — я бы предложил порядок:

### Шаг 1 (быстро, ~1-2 часа) — Test the unverified stuff
- Onboarding cycle question UAT (нужен fresh test user)
- Stage 7c pre-check (n8n execution log analysis — есть ли активность)

### Шаг 2 (средне, ~1 день) — Phase-aware Sage commentary
- Small Python patch в `services/sage.py` + copywriter seeds × 13 langs
- Visible UX win, малый risk, готовит почву для adaptive features

### Шаг 3 (средне, ~1 день) — BMI/min_kcal warnings copywriter
- Brief давно лежит, copywriter subagent → migration → apply
- Закрывает safety pending из MEMORY

### Шаг 4 (средне, ~1 день) — Stage 7c cleanup
- After pre-check confirms safety, deactivate n8n workflows + cleanup endpoints
- Reduces operational complexity

### Шаг 5 (крупно, ~3-5 дней) — Dynamic Katch-McArdle
- Schema + UI + RPC patch + i18n
- Перед стартом — design discussion с owner

### Шаг 6 (крупно, ~1-2 недели) — Adaptive TDEE
- Самая крупная задача. Перед стартом — детальный design doc.
- Требует weight_history table + cron + smoothing logic + safety floors.
- Спросить owner'а: priority и какой smoothing factor он хочет.

---

## Если что-то не понимаешь — спроси owner'а

Owner — не engineer, объясняй простыми словами. Если на каком-то слове задумался — переформулируй как для человека «у нас есть журнал съеденного и журнал замеров веса; если посчитать сколько фактически тратил — получим точнее чем формула». Численные детали и SQL-команды — в конце сообщения, не в начале.

---

**EOS handover.**

— Agent предыдущей сессии, 2026-05-28
