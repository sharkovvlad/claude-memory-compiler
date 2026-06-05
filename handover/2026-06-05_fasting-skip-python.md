# Handover 2026-06-05 — Фича «осознанная пауза / голодание» переписана на Python и LIVE

**Scope:** брифы B+D (аудит нутрициолога) построены с нуля на Python, включены в проде, копирайт на 13 языках. 3 PR (#328 фаза 1, #330 фаза 1.1, #334 копирайт v3), миграции 459/460/461/465. Флаг `handler_fasting_use_python=true` LIVE.

## Что это даёт юзеру
Кнопка «⏸️ Пропускаю» под «Добавить еду» → осознанная пауза/интервальное голодание как **равноправный выбор**, не «ошибка». Anti-shame + автономия. 2-й пропуск за день → опрос причины (пост / нет аппетита / занят / не отвечать) → адаптация. Стрик защищён, Sage не паникует.

## Архитектура (durable — рецепт нового Python-target)
Новый target = **4 провода** (используй как чек-лист для любого нового Python-обработчика):
1. `dispatcher/router.py`: добавить в `TARGETS` + callback-set (`FASTING_CALLBACKS`) + секцию в `route()` **ДО** generic-menu (4l).
2. `webhook_server.py`: `_X_flag_from_ctx` (читает `app_constants.handler_X_use_python`) + import обработчика + блок диспатча (зеркало payment-блока) с graceful fallback.
3. `handlers/fasting.py`: `handle_fasting(update, ctx, decision, rpc_fn=None)` → `ResponseEnvelope`. `forward_target='X'` или exception → `forward_to_n8n`.
4. `app_constants.handler_X_use_python` (default `false`, флипается отдельно после деплоя кода).

## Бэкенд (mig 459)
- Колонки: `food_logs.skip_reason`; `users.fasting_intent_asked` / `fasting_protocol`(16:8/18:6/omad/flexible) / `fasting_window_start|end`.
- RPC: `get_fasting_eligibility` (SOFT safety: promote-or-not по pregnancy/lactation/<18/BMI<18.5; v2 в mig 460 отдаёт `intent_asked`), `record_skip_reason` (причина на сегодняшний fasting-лог + РПП-сигнал = повтор `no_appetite`≥3/14д), `set_fasting_protocol`.
- **Экономика КАК ЕСТЬ** (owner): `log_fasting_meal` не трогали — +15 XP / −1 мана / стрик. Возвращает `xp_gained`+`streak` → футер строится из result, не из stale ctx.

## Решения owner (durable)
- Геймификация без изменений. Safety = МЯГКО (разовый пропуск не блокировать). Scope с протоколами (бэкенд готов, UI — Phase 2).
- **🔴 ОТКЛОНЕНО (нарушает рубрику sage-tov, запрещено в системном промпте Sage `services/sage.py:~1159`):** «Breaking Fast» рефид-оценка («поджелудочной шок» + «начни с белка» = алярмизм органов + предписание след. еды) и «Science Bytes» аутофагия (романтизирует пост + недоказанные мед-утверждения). Если кто-то предложит вернуть — НЕ брать без safety-review.
- «Нет аппетита» держать ОТДЕЛЬНО от «сытости» (иначе теряется РПП-сигнал).

## Sage
`services/sage.py:_compute_day_status` → новый статус `fasting_logged` (эвристика `meals≥1 & kcal==0`, БЕЗ правки горячего `get_day_summary`; `kcal_in`/`meals_count` уже в `_build_my_day_prompt`) + хинт «не нудить поесть, не паниковать, не славить длительность». **fasting_logged = внутр. статус тона, только в день 0-ккал; на обычном дне не срабатывает.**

## Копирайт (13 языков, mig 465)
RU/EN авторские + 11 субагентов по glossary. Иконка `icon_fasting` 🤐→⏸️ (hot-reload). v3 после live-теста owner: убран жаргон «макросы», опрос с пояснением «зачем + необязательно», decline «Не хочу отвечать», ответы называют последствие. **Урок: новая причина = добавь и REASON_CB+ack+router, И button-row в клавиатуре `_handle_skip` (баг: кнопку `busy` забыли в клавиатуре, причина была).**

## Деплой/состояние
- LIVE: PR #328/#330/#334 merged+deployed (последний sha=ed355a5, /health 200). Флаг `handler_fasting_use_python=true`. Откат = флаг в `false` (hot-reload).
- Тесты: `tests/handlers/test_fasting.py` (19) + router 144 зелёные.

## 🟡 Phase 2 (owner-deferred, TODO в `.claude/specs/fasting_skip_spec.md`)
1. **Хук вовлечения «Настроить режим 16:8/18:6»** после «⏳ Пощусь» → `set_fasting_protocol` (RPC готов) + окно. Превращает пропуск в персональный режим = engagement (фича пассивна сейчас).
2. **Фича 24-часового голодания** (таймер окна + обязательный disclaimer `skip_fasting_disclaimer` готов + жёстче safety).
3. **Глушение meal-напоминаний в день поста** — `cron_get_reminder_candidates`: `NOT EXISTS fasting today` в ветки meal_morning/lunch/dinner (сейчас обед/ужин прилетают постящемуся — дыра).
4. Вариативность `skip_ack_*` (dialog-variants) после телеметрии.

## Engagement-оценка (для owner)
Сильно на УДЕРЖАНИИ (защита стрика снимает триггер оттока + anti-shame доверие). Слабо на ВОВЛЕЧЕНИИ (пассивна, опрос=трение без явной пользы → рычаг = хук протоколов, п.1). Watch: XP/стрик за пропуск у уязвимых — телеметрия `skip_reason`.

Детали по шагам — `daily/2026-06-05.md` (секции «фаза 1», «фаза 1.1», «копирайт v3»). Спека — `.claude/specs/fasting_skip_spec.md` (machine-local).
