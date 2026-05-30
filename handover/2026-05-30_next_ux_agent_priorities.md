# Next UX agent — priorities & quick-start

**From:** Opus 4.7 (1M context) session 2026-05-30, EOS 17:30 МСК
**To:** Next agent picking up UX work
**Status:** Production stable. All UAT round 1-5 fixes LIVE. Owner confirmed «Всё работает».

Этот документ — короткий brief для следующего UX-агента. Полный технический контекст (миграции, baga maps, KB updates) — в `2026-05-30_uat_marathon_close.md`. Если ты не делаешь UX а копаешь FSM / payment / cron — иди туда напрямую.

---

## 30-second context

Сегодня закрыл 5 раундов UAT — 9 миграций + ~10 PR'ов + значительный Python refactor. Owner протестил полностью registration flow на uk language → всё работает.

Mig HEAD на LIVE = **388**. Все merged (кроме PR #243 ждёт owner merge — LIVE state уже правильный).

---

## Priority backlog для тебя (UX-focused)

Сортировка по «owner-visible impact» × «scope»:

### P0 — Bug #3 (deferred design task)
**«Food во время онбординга → mana-aware redirect»**

Owner: «мы не блокируем распознавание еды, даём попробовать с первой секунды. Дойдём до некоторого количества попыток (маны) даже для пользователей которые не завершили регистрацию.»

**Сейчас:** ANY текст в онбординг-states идёт через router в AI food engine (или в FSM если status=BUTTON_ONLY). Mana check в food_log handler — при mana=0 показывается mana_exhausted screen.

**Желаемое:**
- Mana > 0 → process food (текущее поведение)
- Mana = 0 → render «Доделай регистрацию, мана закончилась» + redirect на текущий онбординг-screen

**Open questions для owner before coding:**
1. Где гейт — router section 10 catch-all, или food_log handler entry?
2. Copy для redirect message × 13 langs (probably `errors.onboarding_food_blocked` key)
3. Photos vs text — одинаковое поведение? (photo processing дороже)
4. Referral bonus mana — extend trial window?

**Спросить owner-а перед началом** — это 4 UX-вопроса, не подкручивай молча.

### P1 — «Авилес» edge case (Issue 2 follow-up)
Cyrillic transliteration small foreign cities (Авилес = Avilés, Asturias). AI gpt-4o-mini confidence < 0.7 → bot 3 раза показывает error. Owner switched to geolocation.

**Options** (полнее в `2026-05-30_uat_followups_issue2_plus_4_prod_bugs.md`):
- A: lower threshold 0.7→0.5 (services/city_resolver.py:36)
- B: better AI prompt с примерами транслитерации
- C: Geoapify forward-geocode fallback при низкой confidence
- D: combo B+C

Owner ранее склонялся к C/D. Ask before coding.

### P2 — Welcome rewrite verification × 11 langs (mig 383)
Owner approved RU+EN baseline V4. Subagent сгенерировал 11 переводов в один проход. Subagent сам отметил что не все проверены носителями — особенно AR/FA/HI могут needs L2 cultural review (Fiverr ~$200, на усмотрение owner).

Не критично — V4 уже LIVE и работает. Но если owner спросит «можем ли уточнить переводы?» — да, нанять proofreader.

### P3 — Onboarding latency watch
Не bug, но `dispatch_with_render(action='start')` на cmd_start_fresh занимает ~870ms (логи 16:08:22). Часть — ghost_remove_reply_keyboard + reset_to_onboarding + dispatch_with_render chain. Можно parallelize если станет проблемой.

### Backlog от прошлого агента (всё ещё актуально)
- Phase-aware Sage commentary — BLOCKED by safety review (services/sage.py:685). Не трогай без owner override.
- Adaptive TDEE design — big feature, нужен design doc отдельной сессией.
- Allergen tracking — owner 29.05 decided «defer».
- L2 cultural review maternal (Fiverr).

---

## Patterns ESTABLISHED this session — переиспользуй

### Pattern 1: i18n same-namespace references via `{tr:...}`

Когда screen text key содержит references к sub-keys того же namespace:

❌ **Wrong** (mig 363 — broken until mig 380 fixed):
```
'delete_account': {
  'warning_body': '{cancel_warning_line}{icon_oh} <b>{farewell_title}</b>...',
  'farewell_title': 'Ідеш?',
  'bullet_streak': '🔥 Стрік: {streak} днів',
  ...
}
```
Python `_resolve_text` Pass 2 looks `{farewell_title}` в `template_vars` и `constants` — нигде нет → literal `{farewell_title}`.

✅ **Right** (mig 380):
```
'warning_body': '{cancel_warning_line}{icon_oh} <b>{tr:delete_account.farewell_title}</b>...'
```
Pass 1 `{tr:section.key}` resolves nested translations correctly.

### Pattern 2: text_input screen FSM structure

Шаблон из mig 386:
```sql
IF v_status = 'registration_step_XXX_input' THEN
    IF v_callback = 'cmd_back' THEN
        UPDATE users SET status = 'parent_status', last_active_at = NOW() WHERE telegram_id = p_telegram_id;
        RETURN render_screen(p_telegram_id, 'parent_screen');
    END IF;
    SELECT set_user_XXX(p_telegram_id, v_text) INTO v_rpc_result;
    IF success THEN
        UPDATE users SET status = '<advance or parent>' WHERE telegram_id = p_telegram_id;
        RETURN render_screen(p_telegram_id, '<next or parent screen>');
    ELSE
        RETURN render_screen(p_telegram_id, 'XXX_input')
            || jsonb_build_object('validation_error', true, 'error_key', '<i18n key>');
    END IF;
END IF;
```

**Decision rule для status post-save:**
- Primary data (e.g., cycle_start_date) → **advance** к next FSM step
- Fine-tune data (e.g., cycle_avg_length) → **stay** на parent setup screen

### Pattern 3: FSM state whitelist checklist

**ЧИТАЙ 🔥 [[fsm-state-whitelist-discipline]]** перед любым `registration_step_*` add. Checklist в концепте — 4 frozensets в router.py. Этот lesson recurred 3 раза за 2 weeks. Не делай 4-й.

### Pattern 4: Surgical RPC patch via pg_get_functiondef + DO

Для extension существующей RPC без полного rewrite:
```sql
DO $$
DECLARE v_body TEXT; v_old TEXT; v_new TEXT;
BEGIN
    v_body := pg_get_functiondef('public.RPC_NAME(arg_types)'::regprocedure);
    v_old := 'exact substring from live';
    v_new := 'modified substring';
    IF position(v_old IN v_body) = 0 THEN
        RAISE EXCEPTION 'mig XXX: anchor not found in RPC_NAME';
    END IF;
    v_body := replace(v_body, v_old, v_new);
    EXECUTE v_body;
END $$;
```

Используется в mig 385, 386, 387, 388. Безопаснее full CREATE OR REPLACE — не теряешь parallel-agent changes.

⚠️ **Whitespace exact match** — `pg_get_functiondef` оригинальный formatting. Если первый dry-run fails «anchor not found», читай exact lines via psycopg2 + `repr(lines[i])` чтобы найти настоящие пробелы.

### Pattern 5: Button-doesn't-exist-on-error-screen

Anti-pattern найден на cycle_start_date_input в этой сессии:
- Error: «Слишком давно, нажми «❓ Не помню точно»»
- Кнопка «❓ Не помню» на cycle_tracking_setup, NOT на input screen

**Rule:** если error text упоминает кнопку, эта кнопка ДОЛЖНА быть на том же screen. Иначе перепиши error на доступное действие (cmd_back).

---

## Anti-patterns — НЕ повторяй

| Anti-pattern | Symptom | Когда поймал |
|---|---|---|
| Добавить `registration_step_*` без whitelist update | callbacks silently drop → user blocked | mig 382 subagent (caught in PR #240) |
| `BUTTON_ONLY_STATUSES` для text_input screen | text → AI food engine | PR #239 (fixed #240) |
| `render_screen('main_menu')` | screen_not_found error, broken state | Bug #14 (caught #241) |
| Forget `delete_thinking` for non-food handler | thinking sticker accumulates | Bug #15 (caught #241) |
| `decision.callback_message_id` preserved on cmd_start_fresh | welcome text edit-in-place above sticker | Bug #13 (caught #240) |
| Continue working on already-merged branch without rebase | massive deletion diff on next PR | Git incident — CLAUDE.md §12.1 lesson recurred |

---

## Quick-start commands

```bash
# Live state check
psql "$DATABASE_URL" -c "SELECT max(version::int) FROM information_schema.routines"  # mig HEAD

# Reset test user 786301802 (works with bare psql now thanks to proactive ghost_remove)
psql "$DATABASE_URL" -c "SELECT public.reset_to_onboarding(786301802, false);"

# Cleaner reset (no ⏳ flash before welcome)
python3 -c "
import os, asyncio, httpx, psycopg2
from dotenv import load_dotenv; load_dotenv()
TID=786301802; BOT=os.environ['TELEGRAM_BOT_TOKEN']
async def kb_clear():
    async with httpx.AsyncClient() as c:
        r=await c.post(f'https://api.telegram.org/bot{BOT}/sendMessage', json={'chat_id': TID, 'text': '⏳', 'reply_markup': {'remove_keyboard': True}})
        mid=r.json()['result']['message_id']
        await c.post(f'https://api.telegram.org/bot{BOT}/deleteMessage', json={'chat_id': TID, 'message_id': mid})
asyncio.run(kb_clear())
psycopg2.connect(os.environ['DATABASE_URL']).cursor().execute('SELECT public.reset_to_onboarding(%s, false)', (TID,))
print('reset ok')
"

# VPS logs for test user
ssh root@89.167.86.20 "journalctl -u noms-webhooks --since '10 min ago' --no-pager | grep -E 'tid=786301802|sage err' | tail -50"

# Pre-commit sanity (CLAUDE.md §12.2)
git fetch origin main && git diff origin/main..HEAD --stat
```

---

## Files to read first (cold start, 5 minutes)

1. `/Users/vladislav/Documents/NOMS/CLAUDE.md` — operational guide
2. `~/.claude/projects/-Users-vladislav-Documents-NOMS/memory/MEMORY.md` — current state snapshot
3. **🔥 `knowledge/concepts/fsm-state-whitelist-discipline.md`** — if touching onboarding FSM
4. `knowledge/index.md` — full KB index («Start here for common tasks» наверху)
5. This handover + `2026-05-30_uat_marathon_close.md` (полный технический контекст)

---

## EOS checklist для тебя

Перед закрытием твоей сессии:
- [ ] `daily/YYYY-MM-DD.md` обновлён
- [ ] Handover если ты закрыл cutover / делал big refactor
- [ ] KB lesson если поймал новый gotcha (добавь в `concepts/` + `index.md`)
- [ ] MEMORY.md обновил mig HEAD + completed tasks
- [ ] MEMORY size < 200 lines (если больше — флагни owner-у для consolidate-memory)

Удачи! Owner adekvatnyj, чёткие feedback, любит когда задают UX questions перед coding. Не молча решай UX-decisions за него.

🌸

EOS — Opus 4.7 (1M context), 2026-05-30 17:30 МСК
