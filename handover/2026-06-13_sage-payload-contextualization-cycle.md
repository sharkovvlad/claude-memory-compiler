---
title: "Handover — Sage payload contextualization cycle (PR-3b/3c/3d)"
date: 2026-06-13
scope: sage-tone, payload-context, nutrition-individualization
status: Phase 1 SHIPPED, Phase 2-3 pending
---

# Sage payload contextualization — цикл PR-3b → 3c → 3d

## Зачем весь цикл

Owner (2026-06-13): сделать советы Номса **индивидуальными и нутрициологически полезными**, а не generic. Аудитория — **не только качки**: люди, держащие вес; люди, желающие питаться сбалансированно и научно. Тон голоса Sage = ключ к retention. Главный посыл — **«меньше шума → каждое слово весит больше»**.

Три фазы по принципу «один PR — одна тема — один dry-run digest»:

| Фаза | PR | Что | Статус |
|---|---|---|---|
| 1 | [#401](https://github.com/sharkovvlad/noms-bot/pull/401) | Payload видит «кто перед ним»: Goal, Last log min, Card P/S, silent_presence | **SHIPPED, mig 507 LIVE** |
| 2 | [#403](https://github.com/sharkovvlad/noms-bot/pull/403) | Sage видит **тренд**, не один день: `get_weekly_pattern` RPC + Card Q + WEEKLY PATTERN AWARENESS | **SHIPPED, mig 509 LIVE** |
| 3 | PR-3d | Sage уважает юзера: «цель vs реальный рацион» divergence hint | **pending — следующий** |

## Phase 1 (PR-3b) — что уже живёт

См. `daily/2026-06-13.md` § «PR-3b». Кратко:
- `Goal: {goal_type}` в food_log payload (был только в my_day)
- `Last log: X min ago` в `_build_day_context_lines` (multi-photo detection)
- Card P (proud, adult ack) в оба промпта; Card S (silent presence) в food_log
- FORBIDDEN refinement: infantile praise (forbidden) vs adult ack (required)
- `_silent_presence_meta` — HARD GUARD, **master flag `sage_silent_presence_enabled` default `false`**
- mig 507: 4 keys в app_constants
- 246 sage tests green, dry-run × 2 чистый, p95 builder=8.5μs

**Полная архитектура silent_presence** — [[concepts/sage-silent-presence-mode]].

## 🔴 ПЕРВОЕ что сделать следующему агенту

1. **Watch 24-48ч безусловных изменений PR-3b** (Goal/Last log/Card P/FORBIDDEN — они уже работают на всех). Метрики на admin chat 417002669:
   - Доля emotion=proud (Card P должна давать adult-tone, не «Great job!»)
   - Streak naming в RU/UA — должно быть «N дней подряд» / «серия», НЕ «стрик» (PR-3b побочно это починил через adult-tone anchor — проверить, держится ли)
   - Нет ли infantile-praise leak (ES scenario 3 в dry-run был на грани)
2. **Потом изолированно включить silent_presence**: `UPDATE app_constants SET value='true' WHERE key='sage_silent_presence_enabled';` (hot-reload, мгновенно). Смотреть `ai_coach_logs.day_context.metas_fired` на tag `silent_presence` + не глушит ли он совет там где он нужен (false positives). Откат — та же строка с `'false'`.

## Phase 2 (PR-3c) — SHIPPED [#403](https://github.com/sharkovvlad/noms-bot/pull/403), mig 509

**Реализовано:** RPC `get_weekly_pattern(p_telegram_id)` (7-дневный rollup `food_logs`, user-local tz, 2.07ms server). Helper `_format_weekly_pattern` → «Recent pattern (7d): …» в ОБЕ surface (food_log + my_day gather, RTT-нейтрально). Сигналы: `consecutive_days_at_target` (proud → Card P), `avg_meals_per_day` (кето/IF), `dominant_skew` (тренд → Card Q). 16 тестов + 280 sage green. Dry-run × 4.

**🔴 Durable для PR-3d:** dry-run поймал — кето-юзер получал push углеводов несмотря на pattern-строку «large single logs NORMAL». **Новый payload-сигнал как чистый контекст под-весится моделью**; нужна directive-инструкция в промпте КАК его использовать (добавлен блок `WEEKLY PATTERN AWARENESS`). Пара: context-строка + prompt-инструкция (как card+META). **PR-3d divergence-сигнал тоже потребует directive-блок, не только payload-строку.** ОБЯЗАТЕЛЬНО dry-run — unit не ловят под-весивание.

**Known-soft:** macro-skew call-out soft когда сегодняшние цифры противоречат недельному тренду (anti-shame > форсинг). Тюнинг-направление.

## Phase 3 (PR-3d) — детальный план + caution

**Цель:** Sage намекает, когда «цель vs реальность» расходятся. Owner-инсайт: юзер ставит завышенную цель (lose), но ест как на maintain неделями — привычки перевешивают; ИЛИ завышает activity_level (заявил «тяжёлые тренировки», по факту сидячий). Sage уважает достаточно, чтобы предложить **пересмотреть цель/метрики, а не себя ломать**.

⚠️ **Самый деликатный PR — легко скатиться в shaming.** Тут максимум dry-run сценариев (стандартные 8 + 3-4 кастомных: lose+maintain-eating; aggressive_lose+actual_normal; sedentary-as-active mismatch). Если хоть один скатывается в shame — переделать.

- Сигнал «goal-vs-actual divergence» — например 3+ недели средний дневной приём ≈ TDEE для maintain при цели lose.
- Новая Card «goal reassessment hint» — тон **предложения, не упрёка**: «Месяц на бумаге худеешь, по логам — удерживаешь. Это не провал. Может цель сменить, а не себя ломать?»
- Возможно META `goal_divergence_meta` (только при ≥3 недель pattern).
- **Вариант (a)** — текстовый намёк, юзер сам идёт в профиль. **Вариант (b)** — fix-кнопка «обновить activity_level» прямо в reply — отложен как desired future (spawn task_c783554d). Сначала (a).

## Связанные spawn-tasks (другие окна/агенты)

- **task_072c523c** — Streak naming hardening (UK хардкод «Стрік» в `ui_translations`, payload-side mitigation). Severity ↓ после PR-3b (модель в RU теперь пишет нативно), но UK хардкод остался.
- **task_c783554d** — Sage explainable nutrition wisdom (Phase 5: Sage объясняет почему совет такой, формулы/BMR) + Telegram rich formatting (32k chars, expandable_blockquote). Research, не production.

## Durable lessons этой сессии

1. **Voice card ≠ META** — card = always-in-prompt reference example; META = conditional trigger что на неё ссылается. [[concepts/sage-silent-presence-mode]]§Card-S-≠-META.
2. **Несколько tone-изменений в одном PR → новые behavior-фичи гейти за flag, включай по очереди** — иначе watch-период не атрибутируется. Рацио default-off silent_presence.
3. **Правка системного промпта может решить проблему, казавшуюся требующей META** — Card P + FORBIDDEN refinement дали adult-tone anchor → модель сама перестала транслитерировать «streak» в RU (побочный win).
4. **`tools/sage_dry_run.py` hardcoded sys.path** на чужой worktree — wrapper в `/tmp/` с assert. [[concepts/sage-tone-dry-run-protocol]]§Gotcha.

## Источник правды

- KB hub: [[concepts/sage-payload-meta-override-pattern]] (весь META-каскад, 10 живых META)
- KB: [[concepts/sage-silent-presence-mode]] (Phase 1 фича)
- KB gate: [[concepts/sage-tone-dry-run-protocol]] (MANDATORY pre-merge)
- daily: `daily/2026-06-13.md`
- code: `services/sage.py` (`_build_user_prompt` ~1715, `_build_my_day_prompt` ~1948, META функции ~1300-1500)
