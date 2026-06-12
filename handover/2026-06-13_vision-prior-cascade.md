---
title: "Vision prior cascade — halal + diet + soft-prior memory (3 PR за сессию)"
date: 2026-06-13
tags: [handover, vision, ai-recognition, cascade, pre-launch-insurance]
prs: [395, 397, 399]
migrations: [505]
---

# Vision prior cascade — handover для следующего агента

Одна сессия 2026-06-13 (вечер + ночь), три last-PR'а на одной линии — расширение `services/ai_recognition.py:_build_location_hint` тремя независимыми soft-priors. Все три — **pre-launch insurance под LATAM/EU**, dormant для текущих 7 US/UA/ES users.

## Что зашло в прод

| PR | Что | mig | Статус |
|---|---|---|---|
| [#395](https://github.com/sharkovvlad/noms-bot/pull/395) | Halal-prior двухзональный (genuinely-ambiguous meat → chicken/beef/lamb для AR/FA/ID; visible pork → honest) | — | MERGED + auto-deployed |
| [#397](https://github.com/sharkovvlad/noms-bot/pull/397) | Diet-prior через `ctx.diet_type` (vegetarian/vegan plant-based; vegan excludes dairy/eggs; guest's plate anchor) | — | MERGED + auto-deployed |
| [#399](https://github.com/sharkovvlad/noms-bot/pull/399) | Vision soft-prior memory — pairs `(ai_label, user_label, count)` injected в hint, top-5 | **505** LIVE | **OPEN** (на merge) |

## Архитектурный принцип — soft-prior cascade

Все три prior'а — независимые блоки в `_build_location_hint`, объединённые одним контрактом:

> «PRIMARY evidence = photo. Soft tiebreaker для ambiguous, **never override clear visual evidence.**»

Порядок блоков в hint'е (как сейчас в коде):
1. **Base** — country + local_time + regional-dish-name guidance (омонимы tortilla/kebab/pancake).
2. **Halal-prior** (PR #395) — genuinely-ambiguous meat textures в 15 Muslim countries → halal-safe. Anchor: visible pork (ham/bacon/salami/whole cut) — honest.
3. **Vision soft-prior memory** (PR #399) — «Past corrections from this user: ai_label → user_label (×count); …». Anchor: «NEVER use this list to override clear visual cues».
4. **Diet-prior** (PR #397) — vegetarian/vegan plant-based для ambiguous. Vegan excludes dairy/eggs. Anchor: clearly visible meat (chicken breast slice, steak cross-section, fish skin/eyes/bones) — honest, guest's plate scenario.

Каждый блок — текстовый append к одной строке hint'а; conditional на ctx (country/diet_type) или наличие данных (vision_priors non-empty).

## Production baseline на момент patches

Live probe 30д до сессии (см. `daily/2026-06-13.md`):
- **7 active real users** (US/UA/ES — все non-Muslim, все omnivore).
- 203 photo logs, **0 photo edits** (vision-memory не triggerится).
- text/voice memory rows total: 1 (за 9 дней с mig 457).

Все три prior'а активируются по условию (country / diet_type / past corrections), которое для текущих юзеров не выполняется. Это **намеренная dormant insurance**, не активный фикс.

## Когда начнёт работать

Триггеры по PR:
- **#395 halal-prior:** первый юзер регистрируется с `country_code ∈ {SA,AE,EG,KW,JO,MA,PK,MY,ID,BH,OM,QA,TR,IR,IQ}`.
- **#397 diet-prior:** первый юзер выбирает `diet_type ∈ {vegetarian, vegan}` через `cmd_edit_diet` picker.
- **#399 vision-memory:** любой юзер нажимает [Исправить] на photo log + меняет food_name single-item.

## Дизайн-решения, которые я отверг (и почему)

### #395 halal-prior — рассмотрел и отказался

- ❌ **Blanket halal-default без визуальной проверки** (исходный brief): все AR/FA/ID → chicken/beef всегда. Конфликтует с calorie accuracy: pork shoulder 240 ккал/100г vs beef brisket 330. Юзер доверяет данным. Honest classification > paternalism.
- ❌ **HI vegetarian-default:** ~30% Индии non-veg (mutton/chicken-рынок огромный), default «paneer вместо mystery meat» = data regression для non-veg юзера. Перенесено в diet_type-based prior (PR #397).
- 🔴 **1st draft 06-13 morning** содержал absolutist «pork shoulder vs beef brisket are visually distinct, never override». Owner справедливо указал: реально shredded slow-cooked мясо или мясо в соусе — genuinely ambiguous. Walk-back в тот же день, KB §«обновлён в тот же день» помечает это явно.

### #397 diet-prior — рассмотрел и отказался

- ❌ **IN vegetarian-default по country:** ~30% non-veg сегмент. Перенесено на `ctx.diet_type` (per-user сигнал).
- ❌ **Diet-prior без guest's plate anchor:** vegetarian юзер с гостем = misclassification. Sharing анchor `clearly visible meat → identify honestly` mirrors halal-prior pattern.

### #399 vision-memory — рассмотрел и отказался

- ❌ **hash(image_bytes) + telegram_id** (Q1 вариант (a) брифа): Telegram пересжимает каждое фото → bytes hash меняется при retry. Real-world hit rate ≈0%. Сложность для мёртвого механизма.
- ❌ **label-override** (Q1 вариант (b) брифа): автоматическая подмена «pork shoulder» → «beef brisket». **Точная копия `яблоко→pera` trust-killer'а** (PR #329). Для vision хуже — юзер не видит подмены.
- ❌ **Hybrid hash + label** (Q1 вариант (c) брифа): hash мёртв, label-override опасен, hybrid combines worst of both.
- ✅ **Soft-prior** (мой вариант (d)): хранит pairs (ai_label, user_label, count), top-N injected в hint. Модель видит signal, decision сама. Согласовано с «PRIMARY evidence = photo» контрактом всех трёх PR'ов.
- ❌ **token-subset refinement gate** из text path (PR #329): vision corrections почти всегда replacements (категориальные), gate вернёт False почти всегда — мёртвый. Защита от trust-killer перенесена на prompt level («NEVER override clear visual cues»).

## Что в KB

- [[concepts/food-recognition-prompt-lab]]§Disambiguation contract — 6 пунктов всех трёх prior'ов + явные anchor-тесты для каждого. §Compensating mechanism + §«Почему soft-prior вместо hash/label-override» + §«Production baseline на момент patch».
- [[concepts/cascade-macro-enrichment-fatsecret]]§10 «Phase 2 — Vision soft-prior memory» — конкретика mig 505 (schema, RPC, GDPR), design-decisions, что НЕ покрыто в MVP.

## Что мониторить после launch

Когда первый юзер из Muslim country / vegetarian / [Исправить]-power-user появится:

```sql
-- halal-prior triggered (по логам)
SELECT food_name, COUNT(*) FROM food_logs
WHERE source='photo' AND created_at > now()-interval '48 hours'
  AND telegram_id IN (
    SELECT telegram_id FROM users
    WHERE country_code IN ('SA','AE','EG','KW','JO','MA','PK','MY','ID','BH','OM','QA','TR','IR','IQ')
  )
  AND lower(food_name) ~ 'pork|свинина|خنزير'
GROUP BY 1;
-- ожидаем низкое количество pork — но не строго 0 (visible pork остаётся honest)

-- diet-prior triggered
SELECT food_name, COUNT(*) FROM food_logs
WHERE source='photo' AND created_at > now()-interval '48 hours'
  AND telegram_id IN (SELECT telegram_id FROM users WHERE diet_type IN ('vegetarian','vegan'))
GROUP BY 1;
-- ожидаем plant-based dominant для ambiguous

-- vision soft-prior memory accumulation
SELECT telegram_id, ai_label_normalized, user_label, correction_count
FROM user_food_corrections_vision
WHERE correction_count > 1
ORDER BY correction_count DESC LIMIT 20;
-- count>1 rows = реальный repeat-pattern, hint работает
```

## Open для следующей сессии

1. **#399 на merge** — owner может смерджить когда увидит этот handover.
2. **VPS-bench p95** для mig 505 lookup/upsert — после реального traffic'а. Mac-bench был sanity (lookup ~85ms, upsert ~258ms, projected VPS lookup ~30-40ms).
3. **Multi-item vision logs** — не покрыты в memory (MVP limitation как text path). Если когда-нибудь нужно — отдельный sprint.
4. **Adaptive cap top-N** — сейчас 5 фиксированно. Power-user edge case на будущее.
5. **MEMORY.md = 21.8KB / 132 lines** — slightly над 20KB limit. Owner-call: запустить `/anthropic-skills:consolidate-memory` или wait, или сжать руками. Свежие важные записи (Sage ToV finale, Vision prior cascade) лучше не трогать.

## Quick start для нового агента

Если копаешь vision-recognition или food-recognition — читать **в этом порядке**:
1. [`services/ai_recognition.py:_build_location_hint`](../services/ai_recognition.py) (lines ~460-580) — все три prior'а живут здесь.
2. [`services/user_food_memory.py`](../services/user_food_memory.py) — text/voice (mig 457) + vision (mig 505) APIs.
3. [[concepts/food-recognition-prompt-lab]] — единый KB hub.
4. Этот handover для understanding почему именно так, а не иначе.

Если копаешь user-correction loops в общем — KB hub [[concepts/cascade-macro-enrichment-fatsecret]]§10.
