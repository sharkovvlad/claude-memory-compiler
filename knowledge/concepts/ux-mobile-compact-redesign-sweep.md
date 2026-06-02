---
title: "UX Mobile Compact Redesign Sweep (mig 347-355)"
aliases: [mobile-compact, stats-redesign-sweep, progress-profile-redesign, macro-corridor-indicator]
tags: [ux, headless, mobile, stats, profile, progress, redesign]
sources:
  - "daily/2026-05-25.md"
created: 2026-05-25
updated: 2026-05-25
---

# UX Mobile Compact Redesign Sweep (mig 347-355)

Owner UAT sweep после завершения Phase 3 Adaptive Modifiers. Серия из 9 миграций за один вечер, переработавшая 3 главных headless экрана (stats_main / progress_main / profile_main) под мобильный compact layout. Совмещена с Phase 3 wellbeing integration и Sage tuning.

## Key Points

- **9 миграций (347-355) + 2 bug-fix PR'а** за один вечер. Все headless — zero Python handler changes для layout.
- **БЖУ: Letter→Icon→X/Y pattern** (mig 348, 353): вместо `Б 47/120г ✅` → `💪 47/120 ✅` (иконка из `app_constants` вместо буквенного маркера, `/` разделитель вместо «г»). Экономит ~5 символов на каждом макро → помещается в строку на мобиле.
- **±10% коридор вместо фиксированных порогов** (mig 348, 351): macro status ✅ при отклонении ≤10% от target. Пустой emoji если в коридоре (mig 348), затем ⚠️ для soft signal вне коридора (mig 351, по запросу owner'а).
- **Premium-hide line pattern** (mig 353, 354): SQL pre-resolve строки с leading/trailing `\n`, пустая строка = orphan blank line убрана. Переиспользуется на 3 экранах. Отдельный KB: [[concepts/premium-hide-line-pattern]].
- **Checkmark extension для daily_metrics** (mig 347): `render_screen` теперь может читать `current_value_col` из `daily_metrics` через `meta.current_value_source='daily_metrics'`, не только из `users`. Для sleep_checkin / stress_checkin ✅ checkmark.

## Details

### Хронология миграций

| Mig | PR | Экран | Что |
|---|---|---|---|
| 347 | #195 | sleep/stress checkin | checkmark ✅ extension: `current_value_source='daily_metrics'` в `render_screen` |
| 348 | #196 | stats_main | 7/8 mobile правок: БЖУ построчно X/Y, ±10% коридор + neutral, sleep/stress strip premium-only вверху, blank line trim |
| 349 | #197 | stats_main (Sage) | system_prompt_my_day 100-250 → 80-150 chars × 13 langs |
| 350 | #198 | stats_main | streak строку вернули с label «Дней в ударе: N дн.» (mig 348 чрезмерно минимизировала) |
| 351 | #199 | stats_main | ⚠️ для БЖУ при выходе из ±10% коридора (mig 348 ставила empty) |
| 353 | #201 | progress + profile | mana/logs_limit/phenotype premium-hide line pattern |
| 354 | #202 | progress | hide «🔋 Мана: Безлимит» для premium |
| 355 | #203 | profile | v2: inline title, activity/training/phenotype строки, 🎯 Норма в конец, 156 i18n rows + 44 phenotype explanation L2 refresh |

### Checkmark for daily_metrics (mig 347)

Расширение [[concepts/checkmark-prefix-pattern]] — новый `meta.current_value_source` field на `ui_screens.meta`:

- **missing / `'users'`** (default) — existing behaviour, `render_screen` reads `v_user` rowtype
- **`'daily_metrics'`** — `render_screen` reads `SELECT (%I)::text FROM daily_metrics WHERE telegram_id=$1 AND date=CURRENT_DATE LIMIT 1`

NULL row → no checkmark (graceful). Применено к `sleep_checkin` (`sleep_quality_qualitative`) и `stress_checkin` (`stress_label_qualitative`).

### БЖУ corridor indicator (mig 348 + 351)

Заменяет фиксированные пороги `macro_threshold_ok_pct=30` / `macro_threshold_warn_pct=85` / `macro_threshold_over_pct=110` из app_constants на ±10% коридор:

```
actual ∈ [target×0.9 .. target×1.1] → ✅ (в норме)
actual ∉ corridor                    → ⚠️ (soft signal, mig 351)
```

Раньше: <30% → empty, 30-85% → ✅, 85-110% → ⚠️, >110% → 🔴. Новая система проще и feedback-driven (owner: «если я на 5% не дотянул до белка — ✅ нормально»).

### Profile v2 layout (mig 355)

Полная переработка `profile.main_text`:
- Inline title `👤 {first_name} · 📅 с {month} {year}` (вместо двухстрочного header)
- Activity / training / phenotype строки добавлены в profile body (ранее только в `my_plan`)
- Phenotype `default` → показывает `phenotype_standard` label (вместо скрытия)
- `🎯 Норма: {target_calories} ккал/день` перенесено в конец (anchor, не header)
- 156 i18n rows (новые ключи × 13 langs) + 44 phenotype explanation L2 refresh

### Latency observations

8 live кликов админа 00:46-00:47 MSK: p95 ~330ms. **Double `GET /v_user_context`** на каждый callback: `sync_user_profile` + `_try_authoritative_path` независимо вызывают. 170ms из 330ms — pure DB roundtrip. Hot-path optimization candidate.

## Архитектурные паттерны

### Premium-hide line

SQL pre-resolve строки с embedded `\n` (LEADING или TRAILING). Empty string при condition → no orphan blank line. Универсальный pattern для conditional UI строк в headless templates. Подробно: [[concepts/premium-hide-line-pattern]].

### Iterative UX convergence

Owner → agent → deploy → UAT → feedback → next mig. 9 миграций за ~4 часа. Каждая ≤50 LOC SQL (шаблон + бизнес-RPC patch). Ноль Python. Headless architecture позволяет UI-итерации без деплоя кода.

## Bug fixes (non-migration)

- **PR #193** — `cmd_stress_high` TypeError: `SimpleNamespace` dict-spread с дубликат kwarg → `dataclasses.replace`. + toast «✅ Учтено» для stress_high (mig 343 contract).
- **PR #194** — Sage fog-prompt regression: `handle_ai_input` + `_handle_edit_meal_input` returned `ResponseEnvelope.empty()` for `is_food=False` → now resolves `errors.ai_not_food` / `errors.ai_failed` с variant pick.

## Related Concepts

- [[concepts/stats-main-headless]] — stats_main base architecture (Phase 3A)
- [[concepts/premium-hide-line-pattern]] — SQL pre-resolve conditional lines
- [[concepts/checkmark-prefix-pattern]] — ✅ current selection indicator (extended mig 347)
- [[concepts/adaptive-modifiers-architecture]] — wellbeing hub (mig 331) context
- [[concepts/headless-architecture]] — why 9 migs without Python = possible
- [[concepts/my-day-llm-insight]] — Sage system prompt length reduction (mig 349)

## Sources

- [[daily/2026-05-25.md]] — Evening session: 9 migrations (347-355) redesigning stats_main/progress_main/profile_main for mobile compact layout. 2 bug-fix PRs (#193 stress_high TypeError, #194 Sage fog-prompt). Checkmark daily_metrics extension. БЖУ ±10% corridor. Premium-hide line pattern. Profile v2 layout.
