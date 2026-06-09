# Handover 2026-06-09 — Этап 2 n8n→Python: «Добавить еду» мигрирована, Этап 3 ждёт merge

## TL;DR
Reply-кнопка **«🍽 Добавить еду»** — последний живой вход в legacy n8n `04_Menu` — переведена в Python (headless). **mig 497 APPLIED LIVE**, код в **PR #380 (CI green, НЕ merged)**. После merge+deploy → можно выводить сам `04_Menu` (Этап 3).

## Состояние n8n (на 2026-06-09)
3 workflow: `01_Dispatcher` (fallback), `04_Menu` (legacy), `04_Menu_v3` (headless dispatcher). Цель — довести до 2 (убрать 04_Menu).

## Что было сделано (Этап 2)
- **mig 497** (APPLIED LIVE, в PR #380): экран `add_food_prompt` (ui_screens + ui_screen_buttons Skip→`cmd_skip_meal`), `process_user_input` fast-path `cmd_add_food`→`add_food_prompt` (аддитивно).
- **router.py:4c**: `icon_add_food` → menu_v3 synth `cmd_add_food`. Раньше падало в legacy 04_Menu «Send Add Food Prompt».
- Переводы (`progress.add_food_prompt`, `progress.skip_button`) — уже были на 13 langs.

## Что делать дальше (Этап 3) — ПОРЯДОК ВАЖЕН
1. **Дождаться merge PR #380** (owner мержит) + deploy GitHub Actions.
2. **Prod smoke (Deploy-Test-Fix):**
   - Нажать 🍽 (или дождаться реального юзера) → в журнале `SHADOW_ROUTE ... target=menu_v3 reason=add_food_reply_text` (НЕ `target=menu`).
   - Промпт рендерится через Python (render_screen add_food_prompt), редактирует меню НА МЕСТЕ (нет накопления старых меню).
   - `04_Menu` (`JQsipPWxijse3F0b`) — 0 новых executions в n8n SQLite execution_entity.
3. **Мониторинг чистого окна** (несколько дней, 0 реальных запусков 04_Menu). Проверять и хвосты: skip_meal/edit_waist должны идти в Python (fasting/menu_v3), не в menu.
4. **Safe PUT `01_Dispatcher`** (`7jVRdAvVlzOqIMEi`): убрать executeWorkflow-ноду `Go to 04_Menu` (→ JQsipPWxijse3F0b). Рецепт — KB [[n8n-data-flow-patterns]] §Safe PUT. Снапшот перед правкой.
5. **n8n DELETE `04_Menu`** (`JQsipPWxijse3F0b`) после снапшота. n8n 3→2.
6. **Убрать мост TD-#18** (`_maybe_pre_delete_for_add_food` + call site в webhook_server.py:~479 + тест `tests/test_webhook_add_food_pre_delete.py`) — теперь obsolete. Отдельный PR.

## Durable gotchas (детали — daily/2026-06-09)
- **TD-#18 мост** оставлен как safety-net; срабатывает только в fall-through (которого на add_food больше нет) → безвреден, но удалить когда cutover стабилен.
- **process_user_input fast-path (mig 114)** — жёстко зашитый CASE callback→screen для reply-kb roots, НЕ button.meta. Новый root = IN-list + CASE.
- **§12**: ветка отставала на 3 коммита (sage/food_log) → sanity-diff `origin/main..HEAD --stat` ОБЯЗАТЕЛЕН, rebase до commit.
- **pg_get_functiondef** не ставит `;` после `$function$` → добавлять вручную.

## Риск
Низкий. Изменения аддитивные; legacy 04_Menu продолжает работать до merge (graceful). После merge оба пути функциональны (флаг `handler_menu_v3_use_python` off → add_food снова в legacy, мост TD-#18 ещё прикроет).
