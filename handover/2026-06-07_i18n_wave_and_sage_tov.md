# Handover — i18n wave + Sage ToV review (2026-06-07)

Сессия большая: 5 миграций (478/481/482/485/486), все смержены; разбор тона Номса; вскрыт payout/shop баг. Это стартовый брифинг для следующего агента.

## Что сделано (всё LIVE + merged)

| Mig | PR | Что | Статус |
|---|---|---|---|
| 478 | #349 | Литеральный `\n` в luteal-пушах (`reminder_luteal_morning`, `cycle_widget_active`) en/ru | ✅ merged |
| 481 | #353 | Заполнены English-leak дыры 11 langs (лиговые cron-пуши, UI цикла, shop-кнопки) + EN `#{2}`→`#2` | ✅ merged |
| 482 | #354 | `sage.guarded.*` (maternal/underweight/underage) 13 langs, **Pet-free**, L1/L2-reviewed | ✅ merged |
| 485 | #360 | Trial-dunning копирайт pt/pl/id/hi/ar/fa (был английский) | ✅ merged |
| 486 | #361 | payout/shop EN-слот: русский → английский (18 ключей) | ✅ merged |

## 🔴 Главное незакрытое: payout/shop = РУССКИЙ в 11 языках

**18 ключей** (`payout.*`×10, `shop.*`×8 — весь флоу вывода средств + покупок) держат **русский текст** во ВСЕХ не-ru языках (de/fr/es/it/pt/pl/uk/id/hi/ar/fa). Mig 486 починил только **EN** (источник+fallback). Остаток — **198 строк (11 langs)**, переводить С исправленного английского.
- **Spawn-task заведён** (task `task_80a40766`) — отдельная сессия.
- Детектор бага: скан en content на `[А-Яа-я]{3,}` (русские слова в английском слоте).

## 🔴 Sage ToV — найдено, промпт НЕ трогал (owner gate)

Судья `/sage-tov` прогнан (17 реакций, отчёт `~/Documents/NOMS/sage_transcripts/sage_tov_review_2026-06-07.md`). **~16/17 реакций = «добавь куриное филе/творог, не хватает белка»** — проактивный навигатор (PR#340) over-fire'ит, стал рефлексом на каждое сообщение → штамп + потеря характера. 4 правки промпта готовы в отчёте. **Owner: «пока не трогать промпт».** Применять только с явного go, потом A/B-прогон судьи. Баг: 1 реакция не сгенерилась (fallback) — проверить отдельно.

## Прочее открытое
- `profile.set_trimester_text` RU = битый заголовок `<b></b>` (нужен «Триместр беременности»).
- sage.guarded AR/FA: gender 1pl + RTL-маркеры — опциональный native-полиш (пакет `review-packages/2026-06-07_sage_guarded_L1L2/`).
- E2E-проверка что всё это реально рендерится — не делалась (приоритет №4 owner-плана).

## 🔑 Durable-уроки (повторяющиеся грабли)
1. **bulk ui_translations:** `jsonb_set(content,'{ns}', COALESCE(content#>'{ns}','{}')||new, true)` per namespace. **НИКОГДА** `content = content || jsonb_build_object(ns,...)` — top-level shallow-merge стирает siblings ns (CI guard `pr-jsonb-merge-guard`, P0 26.05 стёр 282 ключа). Не писать литерал `content ||` даже в SQL-комменте — гард грепает токен.
2. **rebase ПЕРЕД commit** (не fetch): ветка от старого main → sanity-diff `origin/main..HEAD --stat` поймал −420 строк в чужом `services/sage.py`/тестах. §12.2.
3. **L2-ИИ-ревьюер ≠ авторитет:** машинно проверять патч (cross-script `[Ѐ-ӿ]` в латинских langs, плейсхолдер-parity, LRM-codepoints) ДО применения. Один ревьюер галлюцинировал «кириллицу в pl» и сам внёс `W sam раз` (русское). Другой — честный (HI/AR gender), приняли.
4. **English-identical скан шумный:** фильтровать бренды (NOMS/Premium/XP), эндонимы (`answers.lang_*`), шаблоны вёрстки (`*main_text` с `{tr:}`/плейсхолдерами) — это НЕ непереводы. Сырой 94 → реальных ~15.
5. **«Pet»/«Пет» запрещён** (owner rule), CI-guard `pr-phantom-pet-guard` enforced. KB [[concepts/phantom-pet-entity]].

## Связано
- KB [[concepts/phantom-pet-entity]], [[concepts/jsonb-shallow-merge-antipattern]], [[concepts/copywriter-playbook]], [[concepts/sage-food-log-llm-integration]], [[concepts/release-protocol]].
- daily/2026-06-07.md (детали по каждому шагу).
