---
title: "Edit Picker Dual Render Pattern"
aliases: [dual-render, two-render-locations, edit-picker-checkmark, chk-helpers, build-ask-markup]
tags: [n8n, onboarding, profile, patterns, bugs, ux]
sources:
  - "daily/2026-04-17.md"
created: 2026-04-17
updated: 2026-04-17
---

# Edit Picker Dual Render Pattern

Критическое открытие: edit-пикеры в NOMS рендерятся в **двух** независимых местах в зависимости от точки входа. Патч только одного места даёт silent UI bug — пикер выглядит исправленным при онбординге, но сломан при редактировании из Профиля (или наоборот).

## Key Points

- **Место 1 — `02_Onboarding → Response Builder`**: рендер при онбординге (новый пользователь проходит шаги) И при edit flow из Профиля через callback. Используется для inline-клавиатур (`goalInlineKB`, `trainingInlineKB`).
- **Место 2 — `04_Menu → Build Ask Markup`**: рендер при переходе из edit_* status через reply-keyboard. 9 cases: `weight/height/age` (числовой ввод), `gender/activity` (reply keyboard), `goal/training` (inline), `speed` (inline, отдельно в Response Builder), `phenotype` (заглушка).
- **`chk*()` helpers** — стандартный паттерн ✅ на текущем значении: `const chkGoal = (k) => (isEdit && curGoal === k) ? '✅ ' : ''`. `isEdit = engine.is_edit === true || status.startsWith('editing:') || status.startsWith('edit_')`.
- **Reply keyboard vs inline**: ✅ работает корректно только в inline-пикерах. Reply keyboard кнопки (activity, gender) получают prefix `chkA/chkGen`, но пользователь не может "нажать" уже выбранное значение — это визуальный маркер.
- **Правило аудита**: при добавлении/изменении любого edit-поля — проверить **оба** места. Один пропуск = silent UI bug где пикер рендерится без ✅ или с устаревшим значением.

## Details

### Два маршрута попадания в пикер

**Маршрут A (онбординг / inline edit через callback):**
```
Telegram callback → Dispatcher → Route Classifier → Prepare for 02 
→ 02_Onboarding v3 → Onboarding Engine → Action Router 
→ Response Builder → goalInlineKB() / trainingInlineKB()
```

**Маршрут B (edit flow из Profile через reply keyboard):**
```
Telegram text message → Dispatcher → Route Classifier
→ status = 'edit_activity' / 'edit_gender' etc.
→ Prepare for 04 → 04_Menu → Edit Type Router
→ Build Ask Markup → case 'edit_activity': ...
```

Маршрут определяется типом входящего сообщения и текущим статусом пользователя. При inline-callback из Profile (нажатие на кнопку "Изменить активность") — используется маршрут A. При ожидании текстового ввода (статус `edit_activity`) — маршрут B.

### Реализация chk*() helpers

Добавлены в `02_Onboarding → Response Builder` (init block):

```js
const isEdit = engine.is_edit === true
  || data.status.startsWith('editing:')
  || data.status.startsWith('edit_');

const curGoal     = $('Merge Data').item.json.goal_type     || '';
const curTraining = $('Merge Data').item.json.training_type || '';
const curActivity = $('Merge Data').item.json.activity_level || '';
const curGender   = $('Merge Data').item.json.gender         || '';

const chkGoal     = (k) => (isEdit && curGoal     === k) ? '✅ ' : '';
const chkTraining = (k) => (isEdit && curTraining  === k) ? '✅ ' : '';
const chkActivity = (k) => (isEdit && curActivity  === k) ? '✅ ' : '';
const chkGender   = (k) => (isEdit && curGender    === k) ? '✅ ' : '';
```

В функциях KB: `{ text: chkGoal('lose') + label, callback_data: 'cmd_select_lose' }`.

Когда `isEdit=false` (онбординг нового пользователя) — ✅ не появляется (поведение как раньше).

### 9 cases в Build Ask Markup (04_Menu)

| Case | Тип | ✅ нужен | Статус (2026-04-17) |
|------|-----|---------|---------------------|
| `edit_weight` | Числовой ввод | Нет | — |
| `edit_height` | Числовой ввод | Нет | — |
| `edit_age` | Числовой ввод | Нет | — |
| `edit_gender` | Reply keyboard | Да | ✅ добавлен |
| `edit_activity` | Reply keyboard | Да | ✅ добавлен |
| `edit_goal` | Inline | Да | ✅ был ранее |
| `edit_training` | Inline | Да | ✅ был ранее |
| `edit_speed` | Inline | Да | В Response Builder |
| `edit_phenotype` | Заглушка (1 кнопка) | Нет | — |

### Известный долг: edit_phenotype dead-end

`status='edit_phenotype'` не имеет рабочего Back handling. Пользователь попадает в dead-end — невозможно выйти через кнопки, приходится менять статус вручную в БД. Временное решение до реализации Phenotype Quiz (Phase 2) и/или Bug 6 (hierarchical back navigation через `users.nav_stack`).

### Правило для новых edit-полей

При добавлении нового edit-поля (например `edit_phenotype` в будущем):
1. Определить маршрут: inline callback → Response Builder; reply keyboard / status-based → Build Ask Markup
2. **Проверить ОБА места** — даже если основной маршрут один, другой может быть задействован через другой entry point
3. Добавить `chk*()` helper в Response Builder init block
4. Добавить case в Build Ask Markup с `chk*()` prefix на кнопках
5. Добавить поле в `Prepare for 04` (для Merge Data в 04_Menu) и в `Prepare for 02` (для Merge Data в 02_Onboarding) если не там

## Related Concepts

- [[concepts/personalized-macro-split]] — training_type, goal_speed, activity_level — поля которые редактируются через эти пикеры
- [[concepts/profile-redesign-v5]] — Profile v5 как источник edit flow (кнопки "Изменить" в под-экранах)
- [[concepts/n8n-subworkflow-contract]] — Prepare for 02/04 должны явно передавать cur* значения (goal_type, training_type, activity_level) для chk*() helpers
- [[concepts/n8n-stateful-ui]] — inline vs reply keyboard различие; editMessageText паттерн
- [[concepts/dispatcher-callback-pipeline]] — маршрутизация edit_* callbacks через Dispatcher

## Sources

- [[daily/2026-04-17.md]] — Открытие паттерна "два места рендера" при activity picker fix; chk*() helpers реализованы в Response Builder + Build Ask Markup; 9 cases задокументированы; edit_phenotype dead-end зафиксирован
