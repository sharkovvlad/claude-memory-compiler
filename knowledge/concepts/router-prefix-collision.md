---
title: Router prefix collision — exclusion guard pattern
date: 2026-05-05
status: active
tags: [router, dispatcher, payment, profile_v5, callback_routing]
related:
  - python-vs-n8n-template-grammar.md
  - phase4-onboarding-migration.md  # ONBOARDING_STATUSES guard, same pattern
  - architecture-registry.md
---

# Router prefix collision — exclusion guard pattern

## Сжато

`dispatcher/router.py` использует `startswith` для группировки callback'ов по префиксу (PROFILE_V5_PICKER_PREFIXES, PAYMENT_PREFIXES, ONBOARDING-prefixes и т.д.). Когда более общий префикс одной группы является **подстрокой** более специфичного из другой — общий перехватывает callback первым и роутит его «не туда».

Канонические примеры коллизий:

| общий префикс             | специфичный            | callback-жертва           | исход без guard                           |
| ------------------------- | ---------------------- | ------------------------- | ----------------------------------------- |
| `cmd_select_` (picker)    | `cmd_select_plan_`     | `cmd_select_plan_quarterly` | menu_v3 picker → render_screen → leak `{👑}` (E2E 04.05) |
| `cmd_select_` (picker)    | `cmd_select_start`/`_lang` (онбординг) | onboarding callbacks      | menu_v3 → "⚠️ Что-то пошло не так" (mig 173) |
| `cmd_edit_` (Profile v5)  | `cmd_edit_lang` (welcome) | onboarding language picker | settings flow вместо онбординг (mig 172/173) |

Урок: чистого «правильного порядка» секций недостаточно — порядок может починить один кейс и сломать другой. Универсальное решение — **exclusion guard**: в более общем условии явно исключаем members более специфичного.

## Каноническая форма

```python
# router.py: section 4b (PROFILE_V5_PICKER_PREFIXES)
if (
    any(callback.startswith(p) for p in PROFILE_V5_PICKER_PREFIXES)
    and not any(callback.startswith(p) for p in PAYMENT_PREFIXES)
    and status not in ONBOARDING_STATUSES   # added by mig 173 / agent A
):
    base.target = "menu_v3"
    base.reason = "profile_v5_picker_callback"
    return base
```

Каждый exclusion-guard документируется отдельным `⚠️ ...:` комментом сверху, ссылка на инцидент. Без коммента — следующий агент удалит guard как «мёртвый код».

## Watchlist

При добавлении нового префикса в **любую** группу:

1. Полный список префиксов в `dispatcher/router.py:140-160`:
   - `PROFILE_V5_PICKER_PREFIXES`
   - `PAYMENT_PREFIXES`, `PAYMENT_EXACT`
   - `LOCATION_LEGACY_BUTTONS`
   - `RESTORING_CALLBACKS`
   - + неявные литералы внутри секций 4* (например `cmd_back`, `cmd_recharge_mana`)

2. Проверь startswith-пересечение нового префикса с существующими:
   ```bash
   python3 -c "
   prefixes = ['cmd_select_', 'cmd_pay_stars_', 'cmd_select_plan_', 'cmd_pay_crypto_', 'cmd_speed_', 'cmd_lang_', 'cmd_edit_', 'loc_country_', 'loc_tz_']
   for a in prefixes:
       for b in prefixes:
           if a != b and (a.startswith(b) or b.startswith(a)):
               print(f'COLLISION: {a!r} ⟷ {b!r}')
   "
   ```

3. Для каждой коллизии — добавь `and not any(callback.startswith(p) for p in <competing>)` в более общую секцию + тест в `tests/dispatcher/test_router.py`.

## DB-side leak — связанный гэп

Префикс-коллизия в роутере + двойные скобки `{{icon_*}}` в `ui_translations` дают визуальный артефакт `{👑}` при Python-рендере. Корни:

- **Mig 046 / 051** глобально REPLACE-ом конвертировали `{icon_*}` → `{{icon_*}}` для совместимости с n8n Dumb Renderer (на тот момент весь UI рендерил n8n).
- Python `services/template_engine.py` использует regex `\{([^{}:]+)\}` (одинарные скобки). Matches **внутренний** `{icon_*}`, резолвит → внешние `{` `}` остаются.
- Любой Python-cutover экрана требует одновременного flatten DB-шаблона `{{icon_*}}` → `{icon_*}` для всего раздела.

Пройденные sweep'ы:
- **Mig 168** — `shop / quests / league / referral` (Гамификация)
- **Mig 177** — `payment.*` (после E2E крауллера 04.05)

Незакрытые секции с двойными скобками (по состоянию 05.05): `onboarding`, `buttons`, `edit_food`, `progress`, `messages`, `errors`, `free_tier`, `pay`, `friends_info`, `wait`. Sweep делается **только когда секция реально мигрирует на Python**, иначе ломает legacy n8n Dumb Renderer.

См. также [python-vs-n8n-template-grammar](python-vs-n8n-template-grammar.md) для полного руководства по двум грамматикам.

## История инцидента (`{👑}` leak, 04.05.2026)

1. **04.05 20:23 UTC** — E2E Telethon crawler [tests/live/e2e_crawler.py](../../../tests/live/e2e_crawler.py) поймал в ответе на `cmd_select_plan_quarterly` текст начинающийся с `'{👑} Премиум-планы'`.
2. **05.05 20:30 MSK** — Расследование: коллизия `cmd_select_` ⊂ `cmd_select_plan_` маршрутизировала callback в menu_v3 (Python). Python `template_engine` рендерил `payment.plans_title` со значением `{{icon_premium}} Премиум-планы` → утечка. Тот же баг латентно был и в n8n 10_Payment Build Plans Display JS-нодe (`.replace('{icon_premium}', iconPremium)` — одинарная скобка, оставляет outer braces).
3. **05.05 21:00 MSK** — Зафиксировано:
   - Migration 177 — flatten `{{icon_*}}` → `{icon_*}` для 7 ключей × 13 langs = 91 row.
   - `dispatcher/router.py` секция 4b — exclusion `not any(callback.startswith(p) for p in PAYMENT_PREFIXES)`.
   - `tests/dispatcher/test_router.py` — 3 новых кейса (monthly/quarterly/yearly → payment), 2 sanity-кейса (cmd_select_male/start → menu_v3 picker).
4. Деплой: psycopg2 для миграции + SCP `dispatcher/router.py` (НЕ deploy.sh — параллельный агент работал на ветке `claude/fix-onboarding-comprehensive`, чтобы не откатить их).
5. Верификация: 0 leaks в DB, Python `_resolve_text` simulation → `👑 Премиум-планы` чисто. n8n `.replace`-симуляция → также чисто.

## Также см.

- [python-vs-n8n-template-grammar](python-vs-n8n-template-grammar.md) — две грамматики на одном `ui_translations`
- [phase4-onboarding-migration](phase4-onboarding-migration.md) — gotcha #9 про порядок секций (`is_menu_callback` секция 4l vs `cmd_start_fresh`)
- [architecture-registry](architecture-registry.md) — карта Python authoritative vs n8n fallback
