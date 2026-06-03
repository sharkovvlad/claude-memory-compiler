# Handover: онбординг копирайт + прогресс-бар → перевод на 11 языков

**Дата:** 2026-06-03. **Контекст:** RU+EN копирайт онбординга + прогресс-бар по фазам
УЖЕ в проде (mig 444 headless + mig 454 location.py PR #317 merged). Остался **перевод на
остальные 11 языков** — owner тестировал в ES, увидел старый голый текст без бара (ожидаемо:
staged RU+EN-only rollout, НЕ баг).

## Цель
Довести онбординг-копирайт + прогресс-бар до **11 языков**: `ar, de, es, fa, fr, hi, id, it, pl, pt, uk`.
(ru, en — готовы, НЕ трогать. 13 всего.)

## КАК это устроено (обязательно понять перед работой)
- **Прогресс-бар** = template_var `{onb_progress}`, который `render_screen` (RPC) подставляет
  ТОЛЬКО в онбординг-статусах (gated на `registration_step_%`/`onboarding:*`); вне — `''`.
  Поэтому headless-экраны (пол/возраст/вес/рост/активность/тренировки/цель/темп + maternal/
  cycle/diet/phenotype/waist) должны иметь `{onb_progress}` В НАЧАЛЕ тела (плейсхолдер).
  Экраны общие с профилем → бар нельзя зашивать литералом (полез бы в профиль).
- **Страна/таймзона** (`onboarding.ask_country/ask_timezone`) — рендерит `handlers/location.py`
  (МИНУЯ render_screen) → template_vars там НЕ работают. Тип — **JSONB-array**. Бар для
  онбординга добавляет САМ location.py (`_onb_progress_finish` читает `onboarding.progress.finish`).
  Поэтому в текст country/timezone **НЕ** добавлять `{onb_progress}` — только перевести копирайт.
- **Прогресс-строки фаз** (`onboarding.progress.{basics,lifestyle,goal,precision,finish}`) —
  переводится только СЛОВО-метка («Базовое»/«Basics»), блоки `[⬛⬜⬜⬜⬜]` и эмодзи 📋🏃🎯🔬🏁 —
  без изменений. precision — текст без блоков (у квиза свой бар). Хвост `\n\n` сохранять.
- **copywriter-playbook** (`knowledge/concepts/copywriter-playbook.md`): тон Sassy Sage (наука
  без пафоса, anti-shame, «зачем вопрос»), ≤35 симв/строка, gender-neutral, ar/fa RTL.
  Переводить ИДИОМАТИЧНО (не дословно), сохраняя длину строк и эмодзи.

## ЧАСТЬ A — перевести 15 ключей на 11 языков (канон ru/en ниже)

### A1. Headless-экраны (8) — формат: `{onb_progress}` + копирайт (плейсхолдер В НАЧАЛЕ, сохранить!)


**`questions.gender`**
- RU: `{onb_progress}👤 Биологический пол
У мужского и женского метаболизма разная математика — без этого расчёт базового обмена улетит мимо.`
- EN: `{onb_progress}👤 Biological Sex
Male and female metabolisms run on different math — without this, our calculations will drift.`

**`questions.age`**
- RU: `{onb_progress}🎂 Возраст
С годами скорость обмена веществ плавно меняется — я учту эту хронобиологию в твоём плане.
Напиши число 👇`
- EN: `{onb_progress}🎂 Age
Metabolism shifts gears over the years — I’ll factor this chronobiology into your personal plan.
Type a number 👇`

**`questions.weight`**
- RU: `{onb_progress}⚖️ Вес
Наша отправная точка для эмпирической термодинамики. Никаких оценок, чистая математика.
Напиши в кг 👇`
- EN: `{onb_progress}⚖️ Weight
Our starting point for empirical thermodynamics. Zero judgment, just numbers.
Type it in kg 👇`

**`questions.height`**
- RU: `{onb_progress}📐 Рост
В связке с весом определяет твой базовый метаболизм (BMR) — главный фундамент архитектуры БЖУ.
Напиши в см 👇`
- EN: `{onb_progress}📐 Height
Combined with weight, it unlocks your basal metabolic rate (BMR) — the foundation of your macros.
Type it in cm 👇`

**`questions.activity`**
- RU: `{onb_progress}🔥 Активность
Твой ежедневный термогенез вне тренировок. Чем больше движения, тем больше топлива в плане. Пиши как есть.`
- EN: `{onb_progress}🔥 Activity
Your daily non-exercise thermogenesis. More movement means more fuel allowed. Be honest — desk days are totally fine.`

**`questions.training_type`**
- RU: `{onb_progress}🏋️ Тренировки
Железо и кардио расходуют гликоген и калории по-разному — адаптирую пропорции БЖУ под твой тип нагрузок.`
- EN: `{onb_progress}🏋️ Training
Lifting and cardio burn glycogen and fuel differently — I’ll fine-tune your macro ratios accordingly.`

**`questions.goal`**
- RU: `{onb_progress}🎯 Твоя цель
Главный вектор для баланса энергии: определит, пойдём мы в дефицит или в профицит дневного калоража.`
- EN: `{onb_progress}🎯 Your Goal
The main vector for energy balance: it decides whether we aim for a caloric deficit or a surplus.`

**`questions.goal_speed`**
- RU: `{onb_progress}⏱️ Темп
Высокий темп — резче дефицит, умеренный — комфортнее для нервной системы и устойчивее в долгую. Без гонки.`
- EN: `{onb_progress}⏱️ Pace
Fast means a sharper deficit; steady is comfier for your nervous system and sustainable. No rush.`


### A2. Страна/таймзона (2) — JSONB-array[1], БЕЗ {onb_progress} (бар добавит location.py)

**`onboarding.ask_country`** (хранить как `["..."]`)
- RU: `🌍 Где ты находишься?
Чтобы точнее распознавать местную кухню: тортилья в Мексике и Испании — это принципиально разный состав.`
- EN: `🌍 Where are you?
To accurately decode local cuisine: a tortilla in Mexico vs Spain means entirely different macros.`

**`onboarding.ask_timezone`** (хранить как `["..."]`)
- RU: `🕐 Часовой пояс
Синхронизация с твоими биоритмами. Чтобы нуджи прилетали в твоё утро и вечер, а не будили среди ночи.`
- EN: `🕐 Time Zone
Biorhythm synchronization. So prompts land during your actual morning and evening, not in the dead of night.`


### A3. Прогресс-строки фаз (5) — перевести ТОЛЬКО метку, блоки/эмодзи/`\n\n` не трогать

**`onboarding.progress.basics`**
- RU: `'📋 Базовое  [⬛⬜⬜⬜⬜]\n\n'`
- EN: `'📋 Basics  [⬛⬜⬜⬜⬜]\n\n'`

**`onboarding.progress.lifestyle`**
- RU: `'🏃 Образ жизни  [⬛⬛⬜⬜⬜]\n\n'`
- EN: `'🏃 Lifestyle  [⬛⬛⬜⬜⬜]\n\n'`

**`onboarding.progress.goal`**
- RU: `'🎯 Цель  [⬛⬛⬛⬜⬜]\n\n'`
- EN: `'🎯 Goal  [⬛⬛⬛⬜⬜]\n\n'`

**`onboarding.progress.precision`**
- RU: `'🔬 Микро-тест на фенотип\n\n'`
- EN: `'🔬 Phenotype micro-test\n\n'`

**`onboarding.progress.finish`**
- RU: `'🏁 Финал  [⬛⬛⬛⬛⬛]\n\n'`
- EN: `'🏁 Finish  [⬛⬛⬛⬛⬛]\n\n'`


## ЧАСТЬ B — prepend `{onb_progress}` к «хорошим» экранам в 11 языках (механически)
Эти экраны уже имеют хороший копирайт ×13, но `{onb_progress}` добавлен ТОЛЬКО в ru/en (mig 444).
Для 11 языков нужно ДОБАВИТЬ префикс `{onb_progress}` в НАЧАЛО тела (копирайт НЕ трогать).
Идемпотентный паттерн (как mig 444 §3):
```sql
UPDATE public.ui_translations
   SET content = jsonb_set(content, '{PATH}', to_jsonb('{onb_progress}' || (content #>> '{PATH}')), true)
 WHERE lang_code = ANY(ARRAY['ar','de','es','fa','fr','hi','id','it','pl','pt','uk'])
   AND jsonb_typeof(content #> '{PATH}') = 'string'
   AND (content #>> '{PATH}') NOT LIKE '{onb_progress}%';
```
Ключи (PATH через запятую):
- `{questions,waist_onboarding}`  (questions.waist_onboarding)
- `{questions,diet_question}`  (questions.diet_question)
- `{onboarding,maternal_status_question}`  (onboarding.maternal_status_question)
- `{onboarding,maternal_trimester_question}`  (onboarding.maternal_trimester_question)
- `{onboarding,maternal_lactation_type_question}`  (onboarding.maternal_lactation_type_question)
- `{onboarding,cycle_question_title}`  (onboarding.cycle_question_title)
- `{cycle_setup,title}`  (cycle_setup.title)
- `{cycle_setup,length_prompt}`  (cycle_setup.length_prompt)
- `{cycle_setup,date_prompt}`  (cycle_setup.date_prompt)
- `{phenotype,q1_prompt}`  (phenotype.q1_prompt)
- `{phenotype,q2_prompt}`  (phenotype.q2_prompt)
- `{phenotype,q3_prompt}`  (phenotype.q3_prompt)
- `{phenotype,q4_prompt}`  (phenotype.q4_prompt)


## ПРИМЕНЕНИЕ
1. **NLM-first** (блокнот NOMS Supabase Data) + KB `copywriter-playbook`, `onboarding-v3-map`.
2. Перевод — через **субагента-переводчика** (как делали waist ×13): сначала читает copywriter-playbook,
   возвращает JSON {lang:текст} для каждого ключа; ты проверяешь (плейсхолдеры целы, тон, длина, эмодзи).
3. **Миграция** `migrations/NNN_*.sql` (next free: `git fetch origin main` → max + проверь открытые PR;
   collision guard CI активен). `jsonb_set` per (key,lang). Часть A — overwrite строки/массива;
   часть B — idempotent prepend (guard выше). Apply через psycopg2 (`~/Documents/NOMS/.env` DATABASE_URL)
   + SELECT-верификация.
4. **E2E:** render_screen для тест-юзера в registration_step_1/2/... на КАЖДОМ из 11 языков →
   убедиться: бар «📋/🏃/🎯/🔬/🏁» + переведённый копирайт. Страна/таймзона — через location.py
   (`_render_country_picker` mock или dispatch) + бар «🏁 Финал» только в онбординге.
5. **Деплой НЕ нужен** (чистые данные ui_translations; render_screen/location.py уже в проде).

## ПРАВИЛА (NOMS §12 — критично, я наступал 3×)
- ВСЕ git/python/файловые операции — ТОЛЬКО в worktree, НИКОГДА `cd` в основной клон `~/Documents/NOMS`
  (он на устаревшей ветке). `python3`/`route()`/import — cwd=worktree.
- НЕ `git add -A` (затягивает чужие файлы) — только явные пути. sanity-diff `git diff origin/main..HEAD --stat`
  ПЕРЕД push. rebase origin/main ПЕРЕД commit. force только `--force-with-lease`.
- Закрытие: daily + KB (onboarding-v3-map §перевод) + MEMORY (снять Open-пункт перевода).

## Референс-миграции
- mig 444: headless копирайт 10 экранов + прогресс-бар (ru/en) + {onb_progress} в render_screen.
- mig 454: убрал литеральный бар из country/timezone текста (location.py добавляет условно).
- location.py `_render_country_picker`/`_render_timezone_picker` + `_onb_progress_finish` (PR #317).
- KB: [[onboarding-v3-map]] §Progress bar, [[ux-crosscutting-principles]] §4 shared-screens, [[reply-keyboard-lifecycle]].
