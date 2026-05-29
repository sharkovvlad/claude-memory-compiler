---
title: "Session-Close Discipline — обязательный чек-лист перед «готово»"
aliases: [session-close, eos, end-of-session, closing-discipline, handover-discipline]
tags: [methodology, agent-discipline, enforcement, lessons-learned, p1-prevention]
sources:
  - "CLAUDE.md (NOMS project) §Закрытие сессии — что зафиксировать"
  - "daily/2026-05-29.md (Nutritionist 10 sessions multi-thread)"
  - "handover/2026-05-29_*.md (multiple)"
  - "Owner feedback 2026-05-29 22:45 МСК: «уходит много времени каждый раз когда мы начинаем новую сессию и разбираем те завалы которые оставил за собой предыдущий агент»"
created: 2026-05-29
status: active
severity: P1-prevention
---

# Session-Close Discipline — обязательный чек-лист перед «готово»

> **TL;DR.** CLAUDE.md (раздел «Закрытие сессии») формально требует 5 действий перед EOS, но это правило **систематически нарушается**. Owner с 29.05.2026 явно flagнул: каждая новая сессия начинается с разбора завалов предыдущей. Эта статья = **enforcement layer**: explicit self-check checklist + примеры failures + pattern для самопроверки.

## Корневая проблема

CLAUDE.md загружается **в начале** сессии в system reminder. К концу длинной сессии (50+ tool calls, 2+ часа) instruction inertia уже потеряна — агент torопится «доделать» и пропускает session-close steps.

**Result:** через 24 часа следующий агент тратит **20-40 минут** на разбор:
- Что реально сделано (живой код / БД vs claims в недокументированном handover)
- Какая миграция HEAD реально (MEMORY устарела на N дней)
- Какие PR open / merged / collision'ят
- Что ещё в Track X не закрыто

Реальный случай (29.05): MEMORY говорила «Stage 7 GLOBAL CUTOVER 25.05, all 1000+ users». Реальность через 4 дня — admin-only canary. Nutritionist 10 в start-of-session потратил час на reality check. Это **прямое следствие** того что 25.05 агент не обновил MEMORY с **реальным** post-merge state.

## Чек-лист (mandatory перед сообщением «готово»)

Перед каждым EOS-сообщением агент **обязан явно self-check**:

### ☐ 1. Daily-журнал (всегда, без исключений)

`claude-memory-compiler/daily/YYYY-MM-DD.md`:
- Что изменено
- Зачем
- **Применено ли LIVE** (mig apply / PR merged / deploy run)
- PR ссылки если open

Несколько сессий за день → append в один файл с маркером времени.

**Без этого следующий агент не узнает что ты сделал.** Это minimum bar — даже если ничего не закончил, daily-запись обязательна.

### ☐ 2. Handover (для крупных изменений)

`claude-memory-compiler/handover/YYYY-MM-DD_<scope>_<role>.md` обязателен если:
- Закрытый cutover (Stage X / Phase Y)
- Архитектурный рефакторинг
- Множественные PR в одной сессии
- Blocker'ы для следующего агента (нужно его решение)
- Состояние «applied LIVE но PR не merged» (важно знать!)

Цель handover — **стартовый брифинг 5-минутный** для следующего агента. Если ты сам не смог бы за 5 минут понять что произошло — handover недостаточен.

### ☐ 3. KB lesson (если был gotcha / новый паттерн)

- Сначала `grep -r` по `concepts/` — не описано ли уже
- Подходящая статья → append section с датой
- Нет статьи → создать новую + **обязательно** добавить в `knowledge/index.md` (иначе lost)
- Не ждать compiler — duplicates сольёт позже

### ☐ 4. MEMORY.md update (если изменилось состояние проекта)

`~/.claude/projects/-Users-vladislav-Documents-NOMS/memory/MEMORY.md`:
- Migration HEAD (обновить с N → M)
- Завершённый cutover (переместить в Recently shipped, вычеркнуть из Open)
- Новый flag / row в app_constants
- Новая RPC / removed RPC
- Changes в активной архитектуре

**MEMORY читают ВСЕ агенты в начале сессии.** Stale MEMORY = массовая дезинформация. См. [[concepts/memory-claim-vs-live-verification]] case study.

### ☐ 5. MEMORY housekeeping

Если размер `MEMORY.md` > 20 KB или > 150 строк → flag owner: «MEMORY раздулась, нужен `/anthropic-skills:consolidate-memory`». **Сам skill не запускать** — требует human review (риск удалить важное).

---

## Self-check pattern — что спросить себя перед «готово»

```
1. Я обновил daily/YYYY-MM-DD.md? Если нет — НЕ говорю готово.
2. Большой scope (cutover / refactor / 3+ PR)? Тогда handover написан?
3. Был ли gotcha / новый pattern? Если да — в KB добавил?
4. State проекта изменился (mig HEAD / cutover / flag)? MEMORY обновлён?
5. Если в KB добавил новую статью — она в index.md тоже?
6. Если в MEMORY дополнения — размер всё ещё OK?
```

Если хотя бы один пункт не выполнен — **продолжаю работу, не выхожу**.

---

## Real failure cases (зачем это правило)

### Case 1: Stage 7 «GLOBAL CUTOVER» phantom (2026-05-25 → 05-29)

**Что произошло:** агент 25.05 закрыл PR #192 (Stage 7 Python AI Engine canary expansion). Написал в MEMORY «GLOBAL CUTOVER complete, all 1000+ users». **На самом деле:** `ai_engine_beta_testers=[417002669]` — только admin. Дальше 4 дня все агенты строили планы Stage 7c на этом ложном baseline.

**Cost:** Nutritionist 10 за 1 час reality check выяснил что 75% recognition еды до сих пор через n8n. Если бы apply Stage 7c (deactivate workflows) на ложном MEMORY — сломал бы recognition для всех не-owner юзеров. Один час чек + один час explanation + переписывание handover'а — всё из-за **2-минутной ошибки** в session close 25.05.

**Lesson:** в session close 25.05 нужно было **verify через psycopg2** что `ai_engine_beta_testers` value = ожидаемое («global»), не просто claim.

### Case 2: Migration collision при parallel subagents (29.05)

**Что произошло:** одна сессия → 3 параллельных потока работы (cycle UX / xp_correction / DIAAS). Каждый subagent проверил `ls migrations/` + `gh pr list` независимо. Race: 2 subagent взяли mig 375 в одну минуту до того как другой push'нул.

**Cost:** orchestrator (главный агент) потратил 15 минут на:
- Diagnostic: «кто когда взял какой номер»
- Force-with-lease rename одного PR (mig 375 → 378)
- Comment в обоих PR explaining

**Lesson:** в session close нужно явно зафиксировать **какие mig номера были взяты в parallel** и предупредить о potential collision. Также — pre-push hook должен ловить, но он смотрит origin/main, не in-flight local commits другого worktree.

### Case 3: BMI/min_kcal warnings phantom debt (2026-05-26 → 05-29)

**Что произошло:** handover 28.05 утверждал «BMI/min_kcal warnings — copywriter pending». На самом деле было сделано mig 270 **ещё 18 мая**. Все 4 дня tech debt list содержал ложную задачу.

**Cost:** Nutritionist 10 spent 10 минут проверяя «реально ли pending». Subagent сначала ошибочно подтвердил (NLM хайтек'ил, или прочитал stale handover). Только live SQL verify закрыл вопрос.

**Lesson:** в session close 18.05 нужно было **вычеркнуть** «BMI warnings» из Open tech debt в MEMORY/handover, а не просто «mig 270 applied». **Чистка done-items так же важна как добавление новых.**

---

## Anti-patterns to avoid

### A1. «Сделаю handover на следующей сессии»
**Никогда.** Следующая сессия может быть через дни. Контекст уже потерян. Handover **сейчас** или никогда.

### A2. «Daily пустой, ничего не делал»
Если ничего не делал — daily entry «session 2026-05-29: explored cycle code, no changes; planning continuation tomorrow». Это всё равно важно — следующий агент не дублирует exploration.

### A3. «MEMORY заполнена, нечего обновлять»
Almost never true. Хотя бы дата сессии + «no state changes verified» — это explicit signal что MEMORY checked, not just neglected.

### A4. «KB lesson не gotcha — обычная работа»
Spectrum subjective. Правило: если в session ты сам потратил >15 минут на «как именно работает X» — это KB candidate. Следующий агент потратит те же 15 минут, и так каждая сессия.

### A5. «PR open, оставлю как есть»
PR open в session close → handover **обязательно**. Без него следующий агент не знает merge order, dependencies, какие mig applied LIVE vs nope.

---

## Enforcement options (для owner consideration)

**1. Settings.json `Stop` hook** — выполняется когда агент завершает turn без явного user prompt. Может выводить reminder:
```json
{
  "hooks": {
    "Stop": [{
      "matcher": "*",
      "hooks": [{
        "type": "command",
        "command": "echo '⚠️ Session close checklist: daily/handover/KB/MEMORY обновлены? См. [[session-close-discipline]]'"
      }]
    }]
  }
}
```
Это **не блокирует** агента, просто напоминает в transcript.

**2. CLAUDE.md augmentation** — добавить **обязательный** «Self-check перед готово» pattern (cribbed из этой статьи).

**3. KB index «Start here»** — добавить row «Закрытие сессии» с pointer на эту статью. Агенты которые читают index в начале (правильное поведение) увидят и будут ждать end-of-session.

**4. Slack/Telegram notification** — если daily file для today не существует к концу сессии, send admin alert. Сложнее implement, но max signal.

Owner на 29.05 явно выбрал **discipline через documentation + KB**. Hook enforcement — open option для будущего.

---

## Related KB

- [[concepts/memory-claim-vs-live-verification]] — почему stale claims дорого стоят (Stage 7 case)
- [[concepts/migration-collision-guard]] — pre-push hook для номеров миграций (parallel subagent gotcha)
- [[concepts/subagent-live-apply-review-rule]] — orchestrator не должен делегировать session close
- [[concepts/agent-collaboration-protocol]] — общие правила multi-agent coordination
- CLAUDE.md §Закрытие сессии — каноничное правило (этот KB amplifies)
