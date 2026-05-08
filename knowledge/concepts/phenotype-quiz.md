---
title: "Phenotype Quiz (Body Composition Classification)"
aliases: [phenotype-quiz, body-type-quiz, classify_phenotype, MONW-classification, phenotype-answers]
tags: [feature, db, rpc, i18n, macro-calculation, lbm-proxy]
sources:
  - "daily/2026-04-17.md"
  - "migrations/062_phenotype_quiz.sql"
  - ".claude/specs/phenotype_quiz_spec.md"
  - "daily/2026-04-18-handoff.md"
created: 2026-04-17
updated: 2026-04-19
---

# Phenotype Quiz

4-вопросный эвристический квиз для классификации телосложения пользователя без аппаратной диагностики. Результат — один из 4 фенотипов (MONW / Athlete / Obese / Default), который влияет на расчёт LBM Proxy и персонализированных макро-целей через `calculate_user_targets v3`.

## Key Points

- **Phase 1 = DB autonomous**, Phase 2 = n8n quiz flow **отложена** до завершения рефакторинга 02_Onboarding_v3 / 04_Menu. Phase 1 применена без риска сломать UI — RPC и переводы не используются, пока n8n не подключится.
- **Stateless quiz**: ответы кодируются в `callback_data` (формат `cmd_phenotype_q2_b_a` — макс. 22 символа при 64-ном лимите Telegram). Никакого хранения промежуточных ответов в БД, никаких новых `workflow_states`.
- **RPC `classify_phenotype`** — единственная точка интеграции. Внутри: классификация → UPDATE users → вызов `calculate_user_targets(id, true)` для пересчёта макро. Идемпотентна (повторный вызов с теми же ответами даёт тот же результат).
- **Обратная совместимость:** все 30 юзеров БД до миграции имели `phenotype='default'` — backfill не нужен. `COALESCE(phenotype, 'default')` в `calculate_user_targets` v3 гарантирует NULL-safety.
- **Переводы переиспользуют `profile.phenotype_*`** для названий фенотипов (уже были в БД × 13 языков) — дублирование исключено.

## Details

### Классификационная матрица

```sql
v_phenotype := CASE
    WHEN p_q1='c' AND p_q2 IN ('a','b') AND p_q3='a' AND v_bmi > 27 THEN 'obese'
    WHEN p_q1='c' AND p_q2 IN ('a','b') AND p_q3='a'                THEN 'monw'
    WHEN p_q1='a' AND p_q2='c'        AND p_q3='c'                  THEN 'athlete'
    ELSE 'default'
END;
```

**Порядок веток критичен**: `obese` проверяется ПЕРВЫМ — тот же q1/q2/q3-паттерн что `monw`, но BMI > 27 отделяет абдоминальное ожирение от "skinny fat". Поменять порядок = поломать логику.

### LBM Proxy (в `calculate_user_targets` v3)

| Phenotype | target_weight_kg | app_constants ключ |
|-----------|------------------|-------------------|
| monw | `weight × phenotype_monw_modifier` (0.85) | `phenotype_monw_modifier` |
| obese | `max(height - offset, 40)` (100 м / 110 ж) | `phenotype_obese_offset_male/female` |
| athlete | `weight_kg` | — |
| default | `weight_kg` | — |

**Следствие:** `athlete` и `default` в текущей реализации дают одинаковый `target_weight_kg`. Различие только в `training_type` (g/kg protein coefficient). Это намеренно — фенотип влияет на LBM Proxy, а не на macro ratio напрямую.

### Callback format (Phase 2)

```
cmd_start_phenotype_quiz       → Q1 screen (prev="")
cmd_phenotype_q1_a             → Q2 (prev="a",     14 chars)
cmd_phenotype_q2_b_a           → Q3 (prev="ab",    20 chars)
cmd_phenotype_q3_c_ab          → Q4 (prev="abc",   21 chars)
cmd_phenotype_q4_a_abc         → Classify (answers="abca", 22 chars)
cmd_phenotype_skip             → Classify('b','b','b','b') → default
```

Максимум 22 символа при Telegram лимите 64 — значительный запас. Parsing: `parts = cmd.split('_')`, `qNum = parseInt(parts[2].replace('q',''))`, `prev = parts[4] || ''`.

### 01_Dispatcher не трогаем

`isMenuCallback = callback.includes('cmd_') && !callback.includes('cmd_select_')` — `cmd_phenotype_*` и `cmd_start_phenotype_quiz` уже ловятся через generic `cmd_`. Не соответствует паттерну `cmd_select_*` (для onboarding). Route Classifier никак не трогаем.

### Статус пользователя во время квиза

Когда юзер открывает экран «Complexión» через профиль, `Build Edit Question` устанавливает `status='edit_phenotype'` (существующий паттерн `cmd_edit_*`). После завершения квиза `classify_phenotype` RPC безопасно сбрасывает:

```sql
status = CASE WHEN status = 'edit_phenotype' THEN 'registered' ELSE status END
```

— не задевая другие статусы (если юзер попал в RPC из нестандартного контекста).

### Переводы

**Новые (Phase 1, migration 062):** секция `phenotype.*` — 22 ключа × 13 языков:
- `q1-q4_prompt` (4), `q1-q4_a/b/c` (12)
- `result_title`, `result_recalculated` (2)
- `result_explanation_monw/athlete/obese/default` (4) — Sassy Sage-персонализация

**Переиспользуются (не дублированы):** `profile.phenotype_hint`, `profile.start_test`, `profile.body_type`, `profile.current`, `profile.phenotype_monw/athlete/obese/standard`.

**HTML parse_mode:** вопросы обёрнуты в `<b>`, код вставки в n8n использует `JSON.stringify(text)` для экранирования спецсимволов.

### Верификация (2026-04-17, тестовый 417002669)

| Кейс | phenotype | target_weight_kg | target_protein_g |
|------|-----------|------------------|------------------|
| MONW `(c,a,a,a)` | monw | 84.15 (99 × 0.85) | 135 |
| Athlete `(a,c,c,c)` | athlete | 99.0 | 158 |
| Default `(b,b,b,b)` | default | 99.0 | 158 |

BMI тестового юзера 26.6 < 27 → obese не проверен E2E (нужен юзер с BMI > 27 в Phase 2 E2E).

### Ловушка: CTE и подзапросы в `jsonb_build_object`

PostgreSQL 12+ inlines CTEs, и планировщик может реорганизовать порядок выполнения подзапросов в одном `SELECT jsonb_build_object(...)`. Если в одном запросе вызвать RPC-с-UPDATE и сразу же `(SELECT FROM users)` — подзапрос может прочитать pre-RPC snapshot.

**Решение:** раздельные SELECTы (RPC вызов, затем отдельный `SELECT` для проверки состояния).

### Phase 2 — архитектура (deployed 2026-04-18)

**04_Menu (sxzbSc61YuHFbV4i):**

Menu Router Rule[27] phenotype_quiz → 5 нод:
```
Menu Router [27] phenotype_quiz
  ├── Build Quiz Screen (Code)
  │     ↓
  │   IF Is Classify?
  │     ├── FALSE (show question) ─────────────┐
  │     └── TRUE  → RPC Classify Phenotype    │
  │                  → Build Quiz Result ─────┤
  │                                            ↓
  │                              Edit Phenotype Screen (HTTP editMessageText)
  │
  └── Push Nav (Quiz) [fire-and-forget, parallel]
```

- Одна `Edit Phenotype Screen` нода с двумя входами (n8n paradigm — стандартный fan-in)
- `skip` сводится к `classify('b','b','b','b')` — отдельная ветка не нужна
- Back-кнопка на всех экранах квиза — `cmd_back` (универсальный), pop'ает `phenotype_quiz` из nav_stack, parent=`edit_phenotype` → Complexión intro screen

**Command Classifier в 04_Menu:**
```javascript
else if (
  command === 'cmd_start_phenotype_quiz' ||
  command.startsWith('cmd_phenotype_q')
) {
  route = 'phenotype_quiz';
}
```

**Push Nav (Quiz):** `p_screen='phenotype_quiz'`, fire-and-forget параллельно с Build Quiz Screen (паттерн из nav-stack-architecture).

### Phase 2 Deploy Timeline (2026-04-18)

Важный кейс для будущих агентов: **этот deploy занял 4 итерации** из-за неочевидного бага.

1. **Первая попытка (20:38 UTC 2026-04-17):** добавил Rule[25] phenotype_quiz в Menu Router с новой схемой conditions (version:3, combinator, id). E2E тест — юзер нажал «Пройти тест» → попал в Friends Info. Диагностика: schema mismatch с соседними rules.

2. **Вторая попытка (20:53 UTC):** пересоздал Rule[25] по шаблону rule[24]. Deactivate/activate. Тест снова → Friends Info. Диагностика через NLM: **дубликат outputKey='back' в Rule[0] и Rule[21]** смещает slots. См. [[concepts/n8n-switch-duplicate-outputkey-bug]].

3. **Третья попытка (08:04 UTC 2026-04-18):** fix Rule[21] dedupe → `outputKey='skip_meal'`, `renameOutput=true`. Проверено: 0 дубликатов, mapping aligned. Тест снова → Friends Info. Диагностика: параллельный агент (Delete Account feature, 08:07) сделал PUT на **stale base** → затёр мой Rule[21] fix обратно к дубликату. См. [[concepts/n8n-multi-agent-workflow-editing]].

4. **Четвёртая попытка, quick fix через IF bypass (08:21 UTC):** добавил IF node "Is Phenotype Quiz?" между `Is Profile Sub-Screen?[FALSE]` и Menu Router, обходя Switch. Phenotype quiz заработал ✅. Но 4 остальных функции (Skip Meal, Save Speed, Friends Info, Payout, Delete Account) остались broken из-за того же Rule[21] дубликата.

5. **Финальная интеграция (08:33 UTC):** повторно применил Rule[21] dedupe + добавил Rule[27] phenotype_quiz в Menu Router + удалил IF bypass + восстановил `Is Profile Sub-Screen?[1] → Menu Router`. Все 28 rules теперь уникальны — НО runtime cache bug не сбросился, user повторно увидел misroute.

6. **Попытка Code multi-output (08:43 UTC, Variant 1):** заменил Menu Router Switch на Menu Dispatcher Code node с 28 outputs через `numberOutputs: 28` в parameters. n8n validator отклонил: `"Code doesn't return items properly"` — синтаксис `return [[items], [], ...]` не принимается. **Все reply-кнопки и inline-кнопки в 04_Menu сломались** на 3 минуты пока не откатил.

7. **Финальная архитектурная миграция (10:23 UTC, Variant 2 — Action Router pattern):** Полная замена Menu Router Switch на паттерн Code classifier → Switch router по конвенции NOMS. `Menu Engine` (Code, 1 output, ROUTING_MAP) → `Action Router` (Switch, 7 outputs: render_screen / rpc_fetch_render / rpc_mutate / sub_workflow / edit_picker / nav_back / terminal_ack) → 5 × Sub-Routers (≤8 outputs each). Существующие 28 downstream handlers не трогались — только роутинг. Все phenotype_quiz + delete_account + skip_meal + save_speed + friends_info + payout заработали одним deploy.

**Уроки для будущих агентов:**
1. **В multi-agent среде с общим n8n workflow** любой PUT должен сопровождаться (а) проверкой дубликатов outputKey перед PUT и (б) pre-flight GET для проверки что база не изменилась — см. [[concepts/n8n-multi-agent-workflow-editing]]
2. **Не создавать Switch nodes с >10 outputs.** Использовать Action Router pattern (Code classifier + Switch ≤8 outputs, при необходимости 2-уровневая иерархия) — см. [[concepts/action-router-pattern]]
3. **Не использовать Code multi-output в n8n** — это против конвенции NOMS, validator может отклонить. Всегда single output + Switch для роутинга.

### Variant B (Session 2, ~12:00 UTC 2026-04-18) — clone workflow эксперимент

После того как Action Router refactor полностью решил проблему (итерация 7), отдельный агент в новой сессии провёл исследование: может ли клонирование workflow обойти cache bug.

**Цель:** проверить, привязан ли runtime cache к workflow ID → если да, новый ID даст чистый cache.

**Ход эксперимента:**
1. POST `/workflows` → clone `04_Menu` → новый `workflow_id = LgoqJtuosQxQ4PWo` (versionId `ee216eaf`), 135 нод
2. **Проблема 1 — SubworkflowPolicyDenialError:** клон унаследовал `callerPolicy: 'workflowsFromSameOwner'`. Fix: PUT `settings.callerPolicy = 'any'`
3. Activate clone, PUT Dispatcher с новым workflowId, тест phenotype quiz
4. **Проблема 2 — тот же cache bug:** execution 9394 → Menu Router → `main[23]` (Friends Info) вместо `main[27]`. Shift = -4 (в отличие от -27 в ранних попытках — кэш частично изменился за время deactivate/activate циклов)

**Вывод:** cache bug привязан к **node UUID** (`menu-router-5690fc82`), не к workflow ID. POST `/workflows` копирует node UUIDs 1:1 → клон наследует тот же битый кэш. Новый workflow_id не помогает.

**Rollback:** деактивировать клон → активировать оригинал `sxzbSc61YuHFbV4i` → вернуть Dispatcher workflowId. Выполнен за 3 минуты.

К этому моменту фенотип квиз уже работал через Action Router refactor (итерация 7) — Variant B был чисто исследовательской сессией.

Подробности: [[concepts/n8n-switch-duplicate-outputkey-bug]] и [[concepts/n8n-multi-agent-workflow-editing]].

### E2E Verification Recipe

После изменений в 04_Menu — обязательная проверка через n8n API + ручной тест:

**Автоматическая (n8n self-hosted API через SSH, cloud отменён 2026-04-30):**
```bash
# Последние 5 executions 04_Menu
ssh root@89.167.86.20 "curl -s -H 'X-N8N-API-KEY: \$N8N_TARGET_API_KEY' \
  'http://127.0.0.1:5678/api/v1/executions?workflowId=sxzbSc61YuHFbV4i&limit=5'" \
  | python3 -m json.tool

# Полный trace конкретного execution (includeData=true)
ssh root@89.167.86.20 "curl -s -H 'X-N8N-API-KEY: \$N8N_TARGET_API_KEY' \
  'http://127.0.0.1:5678/api/v1/executions/<ID>?includeData=true'"
```

Признак routing failure: в данных execution branch `main[0]` получает items при условиях, которые не должны туда попадать — это Switch total failure (см. [[concepts/n8n-switch-duplicate-outputkey-bug]]).

**Ручной тест (тестовый аккаунт `417002669`):**
- Reply-кнопки: Мой день / Прогресс / Профиль / Добавить еду
- Inline 2-го уровня: Профиль → Мой план / Настройки / Личные метрики
- Progress Hub: Квесты / Лига / Банда / Магазин
- Phenotype: Профиль → Мой план → Телосложение → "Пройти тест" → Q1..Q4 → result

**SQL verification после прохождения квиза:**
```sql
SELECT telegram_id, phenotype, phenotype_answers, target_weight_kg, target_protein_g, status
FROM users WHERE telegram_id = 417002669;
```

**Rollback snapshot:** `/tmp/04_menu_pre_v2.json` (versionId 11326b05) — стабильное состояние до Action Router миграции. PUT этого файла возвращает 04_Menu в рабочее состояние (Menu Router Switch, до Action Router pattern).

### Планируемые следующие итерации

- **Онбординг-интеграция**: добавить тест после `registration_step_goal` в 02_Onboarding_v3 (когда picker unification будет готов — `ui_pickers` таблица + `get_picker_config` RPC).
- **Историческая динамика**: добавить `phenotype_history` таблицу если пользователям понадобится тренд (как их фенотип меняется с изменением веса/композиции).
- **Адаптивные модификаторы** (Phase 3 по спеку): сон/стресс/ПМС → +15% белка / +10% углеводов / +200 kcal. Отдельная фича.

## Related

- [[personalized-macro-split]] — `calculate_user_targets v3`, training_type + phenotype + goal_speed
- [[picker-unification-strategy]] — решение "phenotype — тест, не picker" зафиксировано
- [[n8n-stateful-ui]] — editMessageText, callback_message_id
- [[supabase-db-patterns]] — migration method через n8n temp Postgres workflow
- [[n8n-switch-duplicate-outputkey-bug]] — обнаружен при deploy (Phase 2), баг блокировал route
- [[n8n-multi-agent-workflow-editing]] — stale base PUT откатил фикс между итерациями
