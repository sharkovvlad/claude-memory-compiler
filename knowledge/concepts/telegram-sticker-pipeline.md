---
title: "Telegram Sticker Pipeline (NOMS)"
aliases: [sticker, webm, video-sticker, make-sticker, nano-banana, veo, chromakey, sticker-pipeline]
tags: [reference, design, tooling, pipeline, operational]
sources:
  - "daily/2026-05-10.md"
  - "daily/2026-05-11.md"
created: 2026-05-10
updated: 2026-05-11
---

# Telegram Sticker Pipeline (NOMS)

> **Источник правды для всего, что связано со стикерами NOMS** — правила,
> CLI-скрипт, промт-шаблоны генерации, история эталонов, промт делегирования.
> Operational guide для агентов, которым ставят задачу «сделай Telegram-стикер
> из видео-заготовки персонажа NOMS».

---

## 1. Что мы делаем

Превращаем `.mp4` (Номс на одноцветном фоне, обычно зелёный chroma) в `.webm`-стикер для Telegram, готовый к загрузке через `@Stickers`.

**Источники:** `/Users/vladislav/Documents/NOMS/Дизайн/NOMS Желе фото/Сценарии:Сцены/<scenario>/*.mp4`
**Выход:** `/Users/vladislav/Documents/NOMS/Дизайн/stickers/<имя>.webm`
**Скрипт:** `/Users/vladislav/Documents/NOMS/Дизайн/stickers/scripts/make_sticker.py`
**venv:** `/Users/vladislav/Documents/NOMS/Дизайн/stickers/.venv/` (rembg[cli], scipy, Pillow, numpy, onnxruntime)
**Эталоны:** `Дизайн/stickers/noms_*.webm` — одобренные стикеры.

---

## 2. Жёсткие правила результата

### 2.1 Лимиты Telegram (нарушать нельзя)

| Параметр | Значение |
|---|---|
| Контейнер / кодек | WebM / VP9 |
| Размер кадра | 512×512 (одна сторона ровно 512) |
| Длительность | ≤ 3 секунды |
| Частота кадров | ≤ 30 fps |
| Размер файла | ≤ 256 KB |
| Аудио | отсутствует |
| Прозрачность | через `alpha_mode=1` (libvpx-vp9 alpha track) |

### 2.2 Композиционные правила (NOMS-специфичные)

1. **Aspect ratio 1:1.** Всегда квадрат.
2. **Персонаж в полный рост.** Силуэт никогда не обрезается границами кадра — ни голова, ни руки в любой позе, ни ножки. Если что-то «висит» близко к краю — это ошибка композиции, нужен air.
3. **Воздух ≥ 6 %** по длинной стороне bbox с каждой стороны. Защищает от обрезки UI плеера/превью в Telegram.
4. **Персонаж занимает максимум canvas** при условиях (1)–(3). Достигается через `max(bbox_width, bbox_height)` square с air, не через crop вплотную.
5. **Резка по горизонтали — да, по вертикали — нет.** Если персонаж шире, чем выше (расставленные руки), у него остаётся воздух сверху и снизу — это нормально. Никогда не обрезаем по верху или низу ради «крупности».
6. **Watermark убираем.** Через `--strip-right/left/top/bottom` (отсечение полосы пикселей перед обработкой). Если есть — обязательно.
7. **Декоративные неоновые элементы** рядом с персонажем (pixel-сердце, иконки, эмодзи в стиле glow) — **сохраняем**, если они являются частью сюжета (приветствие → сердце; идея → лампочка; и т.п.). Исключение: явный мусор / арт-фон / артефакты генератора.
8. **Кадры по сюжету.** Окно 0–3 сек должно содержать пик действия. Если в исходнике есть фазы «после действия» (засыпание, выход из кадра, повтор зацикленный) — обрезаем.

### 2.3 Чего не делать

- Не обрезать ради «крупного плана», если это режет силуэт.
- Не пропускать `--strip-*`, если на видео есть watermark («Veo», «Sora», логотип сервиса).
- Не использовать `pix_fmt=yuv420p` (без alpha) — стикер потеряет прозрачность.
- Не использовать только `chromakey` без `rembg` — на теле персонажа NOMS есть зелёный binary-код, который chromakey съест.
- Не оставлять файл больше 256 KB — Telegram отвергнет.

---

## 3. Pipeline

```
.mp4 (1280×720 или другое) на одноцветном фоне
   ↓
[1] ffmpeg trim 0..3s + crop strip (отрезает watermark)
   ↓
[2] PNG-кадры в hi-res (без раннего downscale)
   ↓
[3] rembg (U^2-Net) → чистая alpha-маска персонажа
   ↓
[4] (опц.) detect_decoration_mask → восстановить неоновую декорацию ВНЕ персонажа,
       только в указанной области (left/right/top/bottom), по hue + brightness
   ↓
[5] composite: персонаж RGBA от rembg + декорация RGB от raw
   ↓
[6] global bbox по всем кадрам (объединение alpha bbox каждого кадра)
   ↓
[7] tight square crop = max(bbox_w, bbox_h) + 6% air, центрирование
   ↓
[8] Lanczos scale → 512×512
   ↓
[9] ffmpeg libvpx-vp9 yuva420p с авто-CRF (30→55), пока размер ≤ 256 KB
   ↓
.webm с alpha_mode=1
```

---

## 4. Запуск

### 4.1 Два режима

| Режим | Когда использовать | Кейс |
|---|---|---|
| `--mode clean` (default) | Простая сцена: персонаж на одноцветном фоне, опционально с одной неоновой декорацией (сердце/иконка одного hue) | «Привет», «Думаю», «Заснул» |
| `--mode scene` | Сложная сцена: динамический многоцветный фон (конфетти, искры, разлетающиеся частицы), несколько декораций разных цветов | «Празднование», «Взрыв», «Магия» |

### 4.2 Clean mode (типичный кейс)

```bash
/Users/vladislav/Documents/NOMS/Дизайн/stickers/.venv/bin/python \
  /Users/vladislav/Documents/NOMS/Дизайн/stickers/scripts/make_sticker.py \
  --input  "/Users/vladislav/Documents/NOMS/Дизайн/NOMS Желе фото/Сценарии:Сцены/<сценарий>/<file>.mp4" \
  --output "/Users/vladislav/Documents/NOMS/Дизайн/stickers/<имя>.webm" \
  --strip-right 140 \
  --keep-decoration left \
  --decoration-hue green
```

### 4.3 Scene mode (для сцен с конфетти / искрами / частицами)

```bash
/Users/vladislav/Documents/NOMS/Дизайн/stickers/.venv/bin/python \
  /Users/vladislav/Documents/NOMS/Дизайн/stickers/scripts/make_sticker.py \
  --input  "<src.mp4>" \
  --output "<dst.webm>" \
  --start 2.5 --duration 3 \
  --strip-right 140 \
  --mode scene \
  --scene-fps 15
```

В scene mode:
- chromakey тонко срезает только тёмный фон (similarity 0.13 — узкая зона) → яркие конфетти/звёзды переживают;
- rembg+closing восстанавливает «дыры» в теле персонажа от green binary-кода;
- **bbox считается по Номсу**, область сцены ограничена `±18 % по x, +35 % сверху, +10 % снизу` — далеко улетевшие частицы отрезаются (иначе персонаж стал бы 30 % canvas);
- noise-фильтр (drop components < 100 px) удаляет мелкие шумы chromakey;
- despill убирает зелёный fringe вокруг конфетти;
- fps снижается до 15 (по умолчанию) — компромисс «качество vs 256 KB лимит» для сложных сцен.

### 4.4 Параметры

| Флаг | Режим | Назначение |
|---|---|---|
| `--input PATH` | оба | исходный mp4 |
| `--output PATH` | оба | целевой webm |
| `--mode clean\|scene` | оба | выбор режима, default `clean` |
| `--start N` | оба | начало окна (сек), default 0 |
| `--duration N` | оба | длина (сек, ≤3), default 3 |
| `--strip-{left,right,top,bottom} N` | оба | отрезать N px с указанной стороны (watermark / UI генератора). Обычно НЕ нужен — pillarbox auto-detect срабатывает первым (см. секцию 7.5b). |
| `--no-auto-pillarbox` | оба | выключить авто-детект чёрных полос (по умолчанию ВКЛЮЧЁН) |
| `--keep-decoration {left\|right\|top\|bottom\|auto\|none}` | clean | где искать неоновую декорацию одного hue |
| `--decoration-hue {green\|cyan\|magenta\|yellow}` | clean | цвет декорации |
| `--bg-color HEX` | scene | hex цвет фона для chromakey (default `0x127B28` — тёмно-зелёный Veo) |
| `--scene-fps N` | scene | output FPS (default 15) |
| `--scene-tightness {tightest\|tight\|medium\|wide}` | scene | сколько окружения сохранять; default `medium`. `tightest` = 96%+ canvas |
| `--scene-ext-horiz N` | scene | оверрайд горизонтального расширения (доля от ширины персонажа) |
| `--scene-ext-top N` | scene | оверрайд верхнего расширения (доля от высоты) |
| `--scene-ext-bottom N` | scene | оверрайд нижнего расширения (доля от высоты) |
| `--air-percent N` | оба | воздух у краёв; default clean=6, scene=4 |
| `--keep-frames` | оба | сохранить временные PNG для дебага |

### 4.5 Зависимости (уже установлены)

- `ffmpeg` — `/opt/homebrew/bin/ffmpeg` (8.x с libvpx-vp9, libvpx)
- venv `Дизайн/stickers/.venv/` с пакетами: `rembg[cli]`, `scipy`, `Pillow`, `numpy`, `onnxruntime`

---

## 5. Верификация результата

Перед сдачей всегда проверить:

```bash
ffprobe -v error -show_streams <output.webm> | grep -iE "codec_name|width|height|r_frame_rate|ALPHA_MODE|duration"
ls -la <output.webm>
```

Чек-лист:
- [ ] `codec_name=vp9`
- [ ] `width=512`, `height=512`
- [ ] `r_frame_rate ≤ 30/1`
- [ ] `TAG:ALPHA_MODE=1`
- [ ] `duration ≤ 3.0`
- [ ] `size ≤ 262144 байт` (256 KB)
- [ ] Визуальный smoke-check: персонаж в полный рост, ничего не обрезано, фон прозрачный

Ещё можно декодировать кадр с alpha и посмотреть глазами:
```bash
ffmpeg -ss 1.0 -i <output.webm> -frames:v 1 -vf "format=rgba" /tmp/check.png
```

---

## 6. Промт-шаблон для делегирования агенту

Копируй блок ниже в первое сообщение агенту, когда юзер просит «сделай стикер из такого-то файла». Заполни плейсхолдеры в `<…>`.

```
Задача: сделать Telegram-стикер из <file.mp4>.

Источник: <абсолютный путь к .mp4>
Выход:    /Users/vladislav/Documents/NOMS/Дизайн/stickers/<имя>.webm

Правила (см. KB [[concepts/telegram-sticker-pipeline]] —
/Users/vladislav/Documents/NOMS/claude-memory-compiler/knowledge/concepts/telegram-sticker-pipeline.md):

1. Telegram: WebM/VP9, 512×512, ≤3 сек, ≤30 fps, ≤256 KB, alpha_mode=1.
2. Персонаж в полный рост, всегда с воздухом ≥6 % у каждой стороны bbox.
3. Crop по бокам — да; обрезать персонажа сверху/снизу — никогда.
4. Watermark убираем через --strip-* до обработки.
5. Декоративные неоновые элементы (сердце, лампочка, иконка) сохраняем,
   если они относятся к сюжету; указываем регион через --keep-decoration.
6. Окно 3 сек выбираем по пику действия; «затухания» отбрасываем.

Алгоритм:

(a) Прежде чем запускать pipeline, изучи исходник:
    - ffprobe размер, fps, длительность;
    - извлеки 8–16 sample-кадров (ffmpeg fps=2, scale=320:-1) и посмотри визуально;
    - определи:
      • есть ли watermark и какая полоса нужна для --strip-*;
      • однотонный фон или динамическая многоцветная сцена (конфетти, искры) —
        от этого зависит выбор --mode clean (default) или --mode scene;
      • в clean mode — есть ли неоновая декорация (сердце/иконка) и в каком углу
        (для --keep-decoration);
      • пик действия — для --start/--duration; видео обычно длиннее 3 сек,
        бери только активную фазу.

(b) Запусти готовый скрипт.

    Clean mode (простая сцена):
    /Users/vladislav/Documents/NOMS/Дизайн/stickers/.venv/bin/python \
      /Users/vladislav/Documents/NOMS/Дизайн/stickers/scripts/make_sticker.py \
      --input "<src>" --output "<dst>" \
      [--start N] [--duration N] \
      [--strip-right N] [--strip-left N] [--strip-top N] [--strip-bottom N] \
      --bg-color 0xFF1493   # обязательно для magenta/cyan! despill halo от просвечивания
      [--keep-decoration left|right|top|bottom|auto|none] \
      [--decoration-hue green|cyan|magenta|yellow]

    Scene mode (динамические частицы / конфетти):
    /Users/vladislav/Documents/NOMS/Дизайн/stickers/.venv/bin/python \
      /Users/vladislav/Documents/NOMS/Дизайн/stickers/scripts/make_sticker.py \
      --input "<src>" --output "<dst>" \
      --start N --duration N \
      [--strip-* N] \
      --mode scene \
      [--scene-fps 15]              # default 15; если не влезает в 256KB — снизить до 12
      [--scene-tightness tight]     # default medium; tight = персонаж крупнее, отрезаем дальние частицы

    После сборки оцени долю персонажа в кадре. Если он мельче 80% — попробуй
    --scene-tightness tight. Если конфетти/частицы важны для сюжета и теряются —
    --scene-tightness wide. По умолчанию medium.

(c) Верифицируй:
    - ffprobe → codec, width/height, fps, ALPHA_MODE, duration;
    - размер файла ≤ 256 KB;
    - декодируй один кадр и убедись, что персонаж полностью в кадре,
      нет halo вокруг декорации, фон прозрачный.

(d) Покажи юзеру: путь файла, итоговые параметры, sample-кадр (декодированный
    с alpha). Если результат не соответствует правилам — объясни что не так
    и переделай (изменив параметры), не сдавай «как есть».

Если что-то нестандартное (другой цвет фона, watermark в нестандартном месте,
несколько декораций, персонаж выходит за края source) — НЕ молчать, описать
проблему и предложить варианты решения.
```

---

## 6.5. Активация стикера в БД (после готового `.webm`)

Стикер-pipeline производит файл `Дизайн/stickers/<name>.webm`. Чтобы он реально начал летать пользователям, нужно **загрузить в Telegram** (получить `file_id`) и **активировать строку** в `bot_stickers`. Большинство placeholder-строк уже засеяны миграциями (например, mig 198 — Channel A onboarding, mig 191 — Channel C freeze, mig 205 — Channel C streak milestones). Активация = одна SQL-команда без деплоя.

### Шаг 1. Загрузить в Telegram, получить file_id

Способы (выбери удобный):
- **@RawDataBot / @JsonDumpBot / @ShowJSONbot:** отправь `.webm` боту, он вернёт JSON с `message.sticker.file_id`. Длинная строка ≈ 100 символов вида `CAACAgIA...`.
- **Через своего бота:** отправь стикер в личку `@nomsaibot`, прочитай file_id из `journalctl -u noms-webhooks` на VPS.

**Важно:** file_id видео-стикеров **глобально валидны** для всех ботов — file_id, полученный через сторонний echo-бот, работает в `@nomsaibot` тоже.

### Шаг 2. Активировать строку в БД

Канонический one-liner (никакого деплоя, эффект через ≤60 секунд из-за TTL кэша `services/stickers_cache`):

```sql
UPDATE public.bot_stickers
   SET file_id   = 'CAACAgIA...<твой file_id>',
       is_active = true
 WHERE sticker_key = '<sticker_key из миграции-плейсхолдера>';
```

**Чтобы мгновенно (не ждать 60 секунд)** — дёрни reload endpoint (требует `STICKERS_RELOAD_TOKEN` в `.env` на VPS):

```bash
curl -X POST -H "X-Stickers-Reload-Token: $STICKERS_RELOAD_TOKEN" \
     https://<vps>/internal/stickers/reload
```

Ответ: `{"ok": true, "loaded": N, "stats": {...}}`.

### Шаг 3. Проверка

```sql
SELECT sticker_key, category, is_active, left(file_id, 25) AS fid, meta
  FROM public.bot_stickers
 WHERE sticker_key = '<sticker_key>';
-- expect: is_active=true, fid начинается с CAACAg…, не TODO_
```

### Когда placeholder-строки нет

Если для новой темы нет существующего placeholder — добавь его отдельной миграцией (минимальная):

```sql
INSERT INTO public.bot_stickers
    (sticker_key, category, file_id, file_type, description,
     sort_order, is_active, meta)
VALUES
    ('<topic>_1', '<topic_category>',
     'CAACAgIA...<file_id>', 'video_sticker',
     '<one-line description>',
     0, true,
     '{"channel": "<A|B|C|D>"}'::jsonb)
ON CONFLICT (sticker_key) DO UPDATE
   SET file_id = EXCLUDED.file_id, is_active = true;
```

`meta.channel` — обязательный самодокументирующий маркер (см. ADR 0001).

---

## 6.6. ОБЯЗАТЕЛЬНЫЙ canonical Negative-блок для всех Veo image-to-video промптов

> ⚠️ Эту секцию читать **каждому агенту**, который пишет промпт для генерации стикерного source. История: 2026-05-12 первая версия `streak_milestone_3` имела розовую splash-лужу под Номсом — alpha-blended pixels, которые **переживают chromakey** (см. секцию 7.5 «alpha-blended translucent jelly»). Перегенерация source — единственный надёжный путь, тюнинг similarity / ping-pong — компромисс.

**Любой промпт image-to-video для NOMS ОБЯЗАН содержать этот блок** (в дополнение к шаблонам секций 8.3 и 8.4):

```
CRITICAL — no translucent environmental effects during animation:
no jelly puddles appearing under the character, no liquid splashes
from jumps, no water reflections, no soft drop shadows, no mist,
no fog, no semi-transparent particle trails, no ripples, no goo
dripping, no body parts shedding translucent droplets. These render
as alpha-blended magenta pixels that survive chromakey and stay
visible as pink artifacts in the final sticker — irreversible in
post. The monster is in a clean isolated airborne pose against the
flat magenta background. NEVER let it interact with any translucent
medium, surface, or environmental element.
```

И обязательно дублировать в **Negative prompt** (отдельное поле в Veo UI):

```
no jelly puddle, no liquid splash, no water reflection, no ground
shadow, no mist, no fog, no semi-transparent particles, no droplets,
no ripples, no goo, no ground surface, no floor, no character landing
on a surface
```

**Правило в промпте:**
- Действия описывай **in place / airborne / floating** — никаких «landing», «splash», «pool», «droplets», «ripples on ground», «reflection of».
- Прыжки/приземления — `keep the character airborne` или `on an implied flat surface`, **никогда не описывать момент столкновения с поверхностью**.
- Predпочитай stationary позы с jelly-bounce in-place вместо z-axis impact.

Подробная математика и измерения — секция 7.5. Правило закреплено в memory агентов (`feedback_veo_sticker_prompt_no_environmental.md`).

---

## 7. Известные кейсы и параметры

### 7.1 NOMS на зелёном фоне (Veo / Gemini генерация, 1280×720)

**Простая сцена (clean mode):**
```bash
--strip-right 140               # убирает watermark "Veo" в правом нижнем
--keep-decoration left          # типичная позиция pixel-сердца (для приветствий)
--decoration-hue green
```

**Сложная сцена с конфетти / искрами (scene mode):**
```bash
--strip-right 140
--mode scene
--scene-fps 15                  # снижаем для влезания в 256 KB
--scene-tightness tight         # tight | medium (default) | wide
```

`--scene-tightness` управляет тем, насколько крупно показан персонаж vs насколько широко видна окружающая сцена:

| Tightness | Расширение зоны (horiz / top / bot) | Доля Номса в canvas | Когда |
|---|---|---|---|
| `tightest` | 0% / +5% / 0% | **~96%** | максимально крупный персонаж, дальние декорации обрезаются (близкие декорации на теле — остаются) |
| `tight` | ±5% / +15% / +5% | ~85–93% | хочется крупного персонажа, дальние частицы не нужны |
| `medium` (default) | ±10% / +25% / +8% | ~80–88% | баланс «персонаж + окружение» |
| `wide` | ±18% / +35% / +10% | ~74–80% | атмосферно, частицы важны для сюжета |

**Совет:** для максимально крупного субъекта используй `--scene-tightness tightest --air-percent 2`. Дополнительные `--scene-ext-*` оверрайды обычно не нужны — preset уже даёт минимум.

Дополнительно есть прямые оверрайды: `--scene-ext-horiz`, `--scene-ext-top`, `--scene-ext-bottom` (доли от размера персонажа).

**Эталоны:**
- `Дизайн/stickers/noms_hello_wave.webm` (10.05.26, clean mode, `mp_.mp4`, 245 KB, 24 fps, Номс 89 %, + pixel-сердце слева)
- `Дизайн/stickers/noms_celebrate_registration.webm` (10.05.26, scene mode, `1_2.5-5.5сек.mp4`, 243 KB, 15 fps, Номс 92 %, + шапка + жёлтая звезда + разноцветные конфетти)
- `Дизайн/stickers/noms_frozen.webm` (11.05.26, clean mode, `Заморозка/mp_.mp4`, 169 KB, 24 fps, + лёд + пиксельное пламя + binary-код)

### 7.2 Как выбрать mode по sample-кадрам

Перед запуском извлеки 8-16 sample-кадров (`ffmpeg fps=2 scale=320:-1`) и оцени:

| Признак | Что выбрать |
|---|---|
| Однотонный фон, рядом с персонажем — 0–1 неоновая декорация одного цвета **МЕЛКАЯ и БЛИЗКО к телу** | `--mode clean` |
| Однотонный фон, без декораций | `--mode clean --keep-decoration none` |
| **Пиксельная декорация (огонь, иконка), КРУПНАЯ или иногда оторванная от тела** | `--mode scene` ⚠️ — rembg её теряет |
| Динамические частицы (конфетти, искры, магия) | `--mode scene` |
| Несколько декораций разных цветов, перекрытия | `--mode scene` |
| Сложный фон (узор, не однотонный) | scene mode не подходит — нужна ручная подготовка |

**Sanity check после первой попытки в clean mode:** если стикер визуально потерял декоративный объект (огонь, иконку) на каких-то кадрах, **не пытайся это починить в clean mode** — переключайся на scene. Симптом: запусти с `--keep-frames`, открой `<workdir>/raw/f_NN.png` и `<workdir>/nobg/f_NN.png` — если в raw декорация есть, а в nobg нет, это **rembg-failure**, починить можно только в scene mode через combined alpha.

### 7.3 Тонкости (обновлены 2026-05-12)

**ВАЖНО-1:** Всегда передавай `--bg-color` в clean mode для magenta/cyan фонов — иначе фон просвечивает сквозь полупрозрачное jelly-тело Номса и оставляет halo. См. подробности в секции 8.2. Default `0x127B28` (зелёный) работает только для legacy зелёных исходников.

**ВАЖНО-2 — rembg выкидывает крупные пиксельные декорации (огонь, иконки).** Подробное объяснение и измеренные цифры — см. секцию 7.4 ниже. Если в сцене есть пиксельный огонь / иконка / эмблема, **которая бывает крупной или отделена от тела пробелом** — сразу `--mode scene`, не пытаться чинить в clean.

### 7.4 Феномен «rembg-loses-fire» — детально для агента-преемника

**Симптом:** На исходном `.mp4` Номс держит в руке пиксельный огонь (или иконку, эмблему). После прогона `--mode clean`:
- В финальном `.webm` огонь **частично отсутствует** на некоторых кадрах: вместо целого пламени остаётся либо тонкий контур-ободок, либо вообще ничего, либо «обрубок» между лапкой и тем местом где огонь должен быть.
- Лапка может выглядеть «обрезанной» — на самом деле обрезана не лапка, а огонь, который рядом с ней.
- На других кадрах того же стикера огонь может быть сохранён нормально (рандомность поведения rembg).

**Корень — не chromakey, не магента, не кадрирование, не watermark-strip.** Корень — U²-Net (модель rembg) **сегментирует один главный объект**. Когда декорация маленькая, близко к телу и сливается с ним по контексту, U²-Net считает её частью персонажа. Когда декорация **крупная и отделена пробелом от тела** (как полно-кадровый пиксельный огонь, отстоящий от лапки на 20+ пикселей), U²-Net **считает её фоном** и выкидывает в alpha=0.

**Где это подтверждено экспериментально (2026-05-12):** запущен `make_sticker.py --keep-frames` на сценарии «Стрик 3 дня окно 2.5-5.5с». Декодирован peak-fire-кадр (frame 10 в subsampled 15fps, ~source 3.0с). Выполнен попиксельный анализ:

```
Fire pixels в raw кадре (high-R, mid-G, low-B):       9934
  Сохранено chromakey (alpha=255):  9876 (99.4%)   ✅ chromakey НЕ ест огонь
  Сохранено rembg (alpha>200):        936  (9.4%)  ❌ rembg ест 90%+ огня
  Сохранено в финальном composite:  9934 (100%)    ✅ combined alpha = max(rembg, chromakey)
```

**Почему ложная гипотеза «chromakey ест огонь из-за похожего R-канала» НЕ верна:**
- Magenta `#FF1493` = (255, **20**, **147**) — R-high, G-very-low, B-mid
- Огонь оранжевый ≈ (250, **100**, **15**) — R-high, G-mid, B-very-low
- RGB-distance ≈ 145–190, далеко в любом color-space
- ffmpeg `chromakey` работает в YUV: огонь имеет другую U/V chrominance чем magenta, similarity 0.13 (узкая) их разделяет

**Sanity-check для проверки этого диагноза на любой новой задаче:**

```bash
# Запусти с keep-frames
make_sticker.py ... --mode clean --keep-frames

# В выводе будет "Frames preserved at: <WORK>"
WORK=<workdir>
# Возьми кадр где декорация должна быть крупной (например источник на 3-4с)
open $WORK/raw/f_NN.png     # должна быть видна целиком
open $WORK/nobg/f_NN.png    # если декорация отсутствует/обрезана — диагноз подтверждён
```

Если raw имеет декорацию, а nobg её потерял — **это rembg-failure, фикс только через `--mode scene`**.

**Почему scene mode решает:**

Pipeline scene mode:
1. ffmpeg `chromakey color=<bg>:similarity=0.13` удаляет ТОЛЬКО фоновый цвет → всё остальное (огонь, декорации, тело Номса) сохраняется
2. rembg даёт чистую alpha-маску Номса, но **с дырами** на огне (как описано выше)
3. **Combined alpha = `max(rembg+closing, chromakey)`** — где rembg "молчит" (alpha=0), вступает chromakey. Огонь спасён.
4. bbox считаем по rembg-маске (Номсу), но scene region расширяем через `--scene-tightness` чтобы захватить декорации рядом

**Когда scene mode НЕ помогает:**
- Если фон не однотонный — chromakey не справится в принципе
- Если декорация имеет цвет близкий к фону (например зелёный огонь на зелёном фоне) — оба теряют. Решение — менять цвет фона в источнике (см. секцию 8.2 про magenta).

**Связь с типовой ошибкой агента:** при первом столкновении с этой проблемой агент склонен искать причину в:
- «обрезано кадрированием» → проверяет crop, расширяет bbox (НЕ помогает, проблема не там)
- «watermark-strip отсёк декорацию» → уменьшает `--strip-right` (НЕ помогает)
- «aggressive despill убил цвет» → крутит параметры despill (НЕ помогает)

**Правильный диагноз делается за 30 секунд через `--keep-frames` + сравнение `raw/` vs `nobg/`.** Это первое что нужно делать когда стикер визуально «теряет» декоративный объект.

### 7.5 Феномен «alpha-blended translucent jelly» — почему не убирается chromakey

**Симптом:** на полупрозрачных элементах сцены (jelly puddle, splash, мыльные пузыри, тонкие тени) виден **остаточный розовый/зелёный оттенок фона**, который НЕ убирается ни увеличением `--chromakey-similarity`, ни zoned chromakey, ни despill.

**Почему:**

Veo рендерит полупрозрачный объект (например jelly puddle, alpha=0.4) на цветном фоне (magenta). Финальный пиксель `.mp4`:

```
finalRGB = alpha * objectRGB + (1 - alpha) * bgRGB
```

То есть прозрачный жёлто-белый jelly (объект, скажем `(220, 220, 200)`) с alpha=0.4 на magenta фоне `(255, 20, 147)` → пиксель `(234, 100, 168)` в mp4. Это **уже смешанный пиксель**, в нём bg и foreground неразделимы.

**chromakey работает только на pure-bg-color пикселях** (alpha≈0, чистый magenta). На alpha-blended пиксели:
- При узкой similarity 0.13 — chromakey их игнорирует (не считает фоном)
- При широкой similarity 0.25+ — chromakey начинает их затрагивать, **но одновременно повреждает огонь / другие color-близкие декорации**

**Это решаемо только через advanced de-matting**, который требует:
- Известного «чистого» цвета объекта (transparent jelly)
- Inverse alpha-compositing уравнения для каждого пикселя
- Это не делается одним ffmpeg-фильтром

**Измеренные цифры (2026-05-12, scene «прыжок в желейную лужу»):**

| Подход | Огонь сохранён | Лужа убрана |
|---|---|---|
| Default similarity 0.13 | 99.5% ✅ | 89% (11% остаётся) |
| Similarity 0.18 | 92.5% | 92% |
| Similarity 0.22 | 64.5% ❌ | 94% |
| Zoned 0.13/0.32 (top/bottom) | 99% сверху ✅ | ~93% (но ободок остаётся) |

Ни один подход не убирает 100% лужи без существенного повреждения огня.

**Практические рекомендации:**

1. **Если splash/puddle небольшой и визуально не мешает** — оставить как есть, не тратить время на pixel-perfect cleanup.
2. **Если splash/puddle большой и портит стикер** — единственное действительно чистое решение: **переделать source без splash**. В Veo prompt'е добавить:
   - `"no liquid splashes, no jelly puddles, no shadows on the ground"`
   - `"clean isolated character pose, no environmental interaction"`
   - Использовать `--mode clean --bg-color 0xFF1493` (с фиксами 2026-05-12)
3. **Гибрид:** оставить текущую версию + рекомендовать `--chromakey-similarity 0.18` для тех сцен где splash есть, но огонь не критичен.
4. **Категорически НЕ делать** — повышать similarity до 0.25+ ради лужи. Это сильно повредит огонь, и пользователь увидит «обрезанный огонь» — куда более явный дефект чем фоновое размытие.

**Эвристика для генерации source (предупреждение в промпт-шаблонах секций 8.3 и 8.4):** Если в сцене персонаж взаимодействует с поверхностью (приземляется, погружается, бросает) — это вызовет полупрозрачные splash-эффекты, которые **навсегда останутся в стикере**. Предпочтительнее «статичные» позы или с твёрдыми (непрозрачными) декорациями.

### 7.5b Чёрные пиллабоксы Veo (auto-detect)

**Симптом:** в финальном стикере по бокам Номса видны **две вертикальные чёрные полосы**, особенно заметные на цветном фоне Telegram-чата.

**Корень:** Veo рендерит 1:1 контент **в контейнере 1280×720** (16:9), добавляя по 280px чёрных пиллабоксов слева и справа. Реальный content zone — только центральные 720×720.

**Как обнаружить вручную (для дебага):**

```python
import numpy as np
from PIL import Image
im = np.array(Image.open("source_frame.png"))  # raw frame from source mp4
col_brightness = im[..., :3].mean(axis=2).mean(axis=0)  # mean brightness per column
bright = np.where(col_brightness > 30)[0]
print(f"Content: x={bright.min()}..{bright.max()}, "
      f"left bar={bright.min()}px, right bar={im.shape[1]-1-bright.max()}px")
```

**Решение (автоматически с 2026-05-12):**

`make_sticker.py` теперь **по умолчанию** запускает `detect_pillarbox()` на первом кадре source — sample brightness per column, find leftmost/rightmost bright columns, и добавляет их ширины к `--strip-left` / `--strip-right`. Логи покажут: `Auto-detected pillarbox: left=280px, right=280px`.

**Когда отключить авто-детект:**

Флаг `--no-auto-pillarbox`. Использовать если:
- В source есть тёмный объект у самого края кадра (детектор сочтёт его за pillarbox).
- Видео уже было обрезано вручную.

**Прежняя ошибка (lesson):** в первой партии стикеров я указывал только `--strip-right 140` (думая, что это убирает watermark «Veo»), но **`140` ≠ 280** — отрезано меньше чем нужно. Левый пиллабокс не трогался вовсе. На финальном стикере были видны чёрные рамки, особенно справа (где осталось 140px чёрного) и слева (полная полоса 280px). **Симптом проявлялся слабо** при тёмном фоне Telegram-чата, но был сразу виден на светлом фоне.

**Правильный workflow:**
- Просто **запускай скрипт без указания `--strip-*` для Veo-сгенерированных видео** — pillarbox auto-detect срабатывает первым.
- Если в Veo source ЕЩЁ И watermark (например «Veo» в правом нижнем углу) — он окажется в нижней половине правого пиллабокса (внутри 280px) и тоже автоматически уйдёт. Никаких дополнительных action не нужно.
- `--strip-*` теперь только для НЕ-Veo источников или когда auto-detect неприменим.

### 7.6 Техника «ping-pong loop» — обойти проблемную фазу source без перегенерации

**Когда применять:** в source есть полезные ≤2.5 сек действия + последующая «грязь» (splash, лужа, нежелательная поза, выход из кадра). Перегенерация source через Veo — дорогая (минуты на промпт + проверку). Если pre-content окно ≥ 1.0 сек, можно собрать seamless 3-секундный loop через ping-pong БЕЗ Veo.

**Алгоритм:**

```bash
SRC="<source.mp4>"
PRE_END=1.5  # верхняя граница безопасной зоны (до начала "грязи"); подбирается визуально

# Step 1: cut forward chunk
ffmpeg -y -ss 0 -t $PRE_END -i "$SRC" -an -c:v libx264 -crf 12 -preset slow /tmp/fwd.mp4

# Step 2: reverse it
ffmpeg -y -i /tmp/fwd.mp4 -vf reverse -an -c:v libx264 -crf 12 -preset slow /tmp/rev.mp4

# Step 3: concat (forward + reverse = 2 × PRE_END seconds)
cat > /tmp/concat.txt <<EOF
file '/tmp/fwd.mp4'
file '/tmp/rev.mp4'
EOF
ffmpeg -y -f concat -safe 0 -i /tmp/concat.txt -an -c copy /tmp/pingpong.mp4

# Step 4: feed into make_sticker.py with --start 0 --duration 3
make_sticker.py --input /tmp/pingpong.mp4 ...
```

**Свойства результата:**

- Длина = `2 × PRE_END` секунд. Для PRE_END=1.5 → 3.0 сек ровно (под Telegram-лимит).
- **Seamless loop по построению:** последний кадр reverse-фазы = первый кадр forward-фазы. Telegram-плеер зацикливает без видимого "прыжка".
- Точка реверса (t = PRE_END) — это последний кадр forward, следующий — первый кадр reverse (тот же). Будет видна **краткая пауза/задержка** на peak позе.

**Когда работает идеально:**
- Действие не имеет явного направления: махание рукой, вибрация, дрожь, дыхание, моргание, мигание огня.
- Reverse выглядит как естественное продолжение forward.

**Когда работает плохо:**
- Direction-specific действия: ходьба, бросок, толчок, поворот головы в одну сторону.
- В reverse они выглядят неестественно (Номс «идёт назад», рука «всасывает» огонь).

**Решение если direction-specific:** взять более короткое pre-окно где Номс делает только периодичное (например первые 0.5 сек), сделать ping-pong = 1 сек, и зациклить Telegram-плеером (укажет 1 сек как `duration`).

**Подтверждено в production:** `noms_streak_3days.webm` v3 (2026-05-12, SHA `1a27ed30...`). Source имел splash после 2.7с. Ping-pong из окна 0-1.5 → 3 сек seamless loop. Splash полностью исключён, огонь сохранён, переход без видимых артефактов.

**Параметры pingpong-source при подаче в make_sticker.py:**

- `--start 0 --duration 3` (полная длина ping-pong файла)
- `--mode scene --bg-color 0xFF1493` (если огонь крупный, иначе clean mode)
- `--scene-fps 24` (можно держать 24, поскольку scene-сложность ниже без splash → CRF не зашкаливает)
- `--scene-tightness tight`


- **rembg vs chromakey.** На теле NOMS есть зелёный binary-код — `chromakey` без rembg съест дыры в персонаже. В `clean` mode всегда `rembg → composite`. В `scene` mode rembg+closing «затыкает» эти дыры внутри Номса, а chromakey — только снаружи (через combined alpha = max).
- **rembg теряет верх Номса в сложной сцене.** Если в сцене активный фон (конфетти), стандартный u2net плохо сегментирует и теряет голову/шапку. **Решение** — scene mode: closing с iter=12 + расширенная bbox-маска по rembg. AI-модели `isnet-general-use` и `birefnet-general` тоже не идеальны на таких сценах.
- **Decoration halo (clean mode).** Скрипт делает opening+dilation. Если halo остался — поднять `brightness_min` в `detect_decoration_mask`.
- **Despill.** Полупрозрачные пиксели у конфетти получают зелёный fringe от фона. Скрипт снижает G-канал до `max(R, B)` на fringe — без этого все конфетти получают зеленоватый ореол.
- **Размер файла.** Clean mode: CRF 30→55 шагом 5. Scene mode: CRF до 60 + fine-tuning ±4 от лимита. Если scene-сцена не влезает на CRF 60 — снизить `--scene-fps` до 12 или сократить `--duration`.
- **Bbox в scene mode.** Считаем по Номсу (rembg), а не по всему alpha — иначе конфетти растягивают bbox на весь кадр и Номс сжимается до 30 %. Расширение `±18 % / +35 % top / +10 % bot` оставляет звезду над головой и близкие конфетти.
- **Слишком широкий персонаж (расставленные руки).** Это не баг — square по `max(w, h)`, и Номс с разведёнными руками займёт 89 % ширины и ~60 % высоты. Так и должно быть.

---

## 8. Генерация исходников через Nano Banana / Veo

### 8.1 Workflow (профессиональная цепочка)

```
[1] Image generation (Nano Banana = Gemini 2.5 Flash Image)
    → 4–8 reference images Номса в нужной позе
    → отбираем 1 лучший (centered, ≥15% air, clean bg, on-canon look)
    → сохраняем в Дизайн/character_bible/ для consistency

[2] Video generation (Veo через Gemini / AI Studio)
    → передаём отобранный референс как seed image (image-to-video)
    → prompt описывает ТОЛЬКО действие + камеру + стиль движения,
      не повторяет внешний вид персонажа (он из image)
    → если модель умеет — задаём end frame = start frame (seamless loop)
    → генерируем 3–5 вариантов, выбираем лучший по плавности и точности

[3] Sticker pipeline
    → make_sticker.py с подходящими флагами (см. секции 4–7)
```

### 8.2 Выбор цвета фона — **magenta как новый стандарт** + `--bg-color` обязателен

Старый стандарт (зелёный `#00B140`) — наследие от первых генераций через Veo. Но для NOMS это **плохой выбор**: тело Номса содержит зелёный binary-код, иногда зелёные декорации (pixel-сердце, конфетти, glow). При зелёном фоне chromakey съедает эти элементы.

**Magenta `#FF1493` — текущий рекомендуемый стандарт**, НО обязательно указывать `--bg-color 0xFF1493` в clean mode тоже (не только в scene mode). Причина:

> **Полупрозрачное jelly-тело Номса** пропускает фоновый цвет насквозь. Magenta «проходит сквозь Номса» во время рендеринга Veo и оседает на контуре в виде розового halo. rembg сохраняет эти полупрозрачные пиксели как часть объекта (правильно — это и есть полупрозрачная оболочка), но фоновый цвет в них остался. Видно как розовое свечение на границе + жёлтые binary-код пиксели вместо зелёных + дыры в alpha-маске между пальцами и пиксельными декорациями (огонь, иконка).

**Решение** (фикс 2026-05-12 в `make_sticker.py` после первой неудачной итерации `noms_streak_3days.webm`):

1. **Closing + selective hole-fill** — `binary_fill_holes` на rembg-маске, но заполняются только **малые** дыры (`≤ 1500 px`, размером с пиксельный огонь). Большие дыры — реальный фон между объектами, заполнять их = разместить magenta-RGB пиксели внутри Номса (это и был bug у первого фикса). Работает в clean mode default (`--clean-closing-iters 3`, выключить `0`).

2. **Chroma-aware despill в contour band** — определяем доминантные каналы из `--bg-color HEX` (для magenta `#FF1493` ⇒ только R доминирует, потому что B=147 ниже threshold; non-dom = max(G, B) per pixel). На полосе 6 пикселей от bg-маски (`binary_dilation(bg_mask, 6) & ~bg_mask`) подавляем доминирующие каналы пропорционально spill. **Critical fix:** НЕ применять floor `np.maximum(new_val, non_dom_max)` — он может поднять канал ВЫШЕ исходного значения, превратив deep purple body в розовый. Floor только на 0.

| Цвет | Hex | Когда | Что указывать |
|---|---|---|---|
| **Magenta** (рекомендуется) | `#FF1493` | NOMS с зелёными элементами / конфетти | `--bg-color 0xFF1493` обязательно в clean mode! |
| Cyan / blue | `#00BFFF` | Только если в сцене нет голубых элементов | `--bg-color 0x00BFFF` |
| Зелёный (legacy) | `#00B140` / `#127B28` | Старые видео для совместимости | `--bg-color 0x00B140` (default 0x127B28) |

**Симптомы пропущенного `--bg-color`:**
- Розовое/жёлтое свечение по краям Номса (halo)
- Жёлтые цифры binary-кода вместо зелёных у краёв
- Обрезанные пальцы возле декораций (огонь, иконка) — провалы в alpha
- bbox растягивается на весь кадр из-за фоновых артефактов на краях

**Проверка качества фикса (всегда):**
- Сравнить decoded webm-кадр с source mp4 кадром: deep purple body vs розовое (плохо), green binary-код vs жёлтые цифры (плохо).
- Сэмплировать RGB центра тела через PIL/numpy — должно совпадать с source ±5 каналов.

### 8.3 Промпт-шаблон для **image generation** (референс Номса)

Используется для генерации канонических референсов в `character_bible/` и для seed-image конкретной сцены.

```
A cute, round, 3D monster made of glossy, semi-transparent deep purple
jelly. Big expressive glowing eyes, small cute mouth, two small feet.
Vivid neon green binary code is streaming inside its body like the Matrix
effect, glowing through the translucent purple jelly from within.

[SCENARIO-SPECIFIC TRAITS — fill per scene, e.g.:]
  - "Partially covered in stylized, translucent glowing blue ice crystals
     and frost on its head and shoulders. Holds in both hands a bright,
     glowing 8-bit pixelated orange-and-red flame close to its chest.
     Looking slightly chilly but relieved, giving a small confident wink."

Composition: Subject perfectly centered. Full body visible — head, hands,
and feet entirely within frame. At least 15% empty space on all four
sides between the monster and the frame edges.

Background: Solid uniform pure magenta / hot pink chroma key screen
(approximately #FF1493 or #E91E63), completely flat — NO texture, NO
gradient, NO vignette, NO shadows on the background, NO floor or horizon
line. Single saturated color so it can be removed cleanly with chroma
keying.

Style: 3D render, highly detailed, cyberpunk aesthetic, retro-futurism,
glitch art accents, soft gelatinous jelly texture, clear sub-surface
scattering through the purple body.

Lighting: Volumetric soft front-top key light, gentle rim light, no
strong directional shadows on background.

Format: 1:1 square aspect ratio.

Negative — must NOT appear: no watermark, no logo, no signature, no
text, no UI overlay, no border, no multiple monsters, no human hands or
faces, no realistic photo elements, no green or magenta color on the
monster's body that could be confused with the background.

Avoid environmental interaction that creates translucent effects:
no jelly puddles, no liquid splashes, no water reflections, no soft
shadows on the ground, no mist or fog. These render as semi-transparent
pixels blended with the magenta background, which cannot be cleanly
removed in post-processing (see KB section 7.5 for math). The monster
should be in a clean isolated pose against the flat magenta background.
```

### 8.4 Промпт-шаблон для **video generation** (image-to-video, action only)

Используется на этапе [2]: к этому prompt'у обязательно прикрепляется reference image из этапа [1] (или из `character_bible/`).

```
Animate the monster in the reference image with the following action
over 3 seconds (looping seamlessly — the final frame must match the
first frame so the animation repeats without a visible cut):

[ACTION — fill per scene with explicit timing, e.g. for "frozen":]
  - Continuous gentle full-body shiver / micro-tremble.
  - At ~1.0s the monster exhales a small puff of pale icy vapor from its
    mouth, which dissipates by ~1.6s.
  - At ~1.8s a single confident playful wink (one eye softly closes and
    re-opens over ~0.4s) with a small relieved smile.
  - Throughout, it cradles the pixel-flame protectively; the flame
    flickers with retro 8-bit animation, casting a warm orange glow onto
    the monster's lower face and hands.

Camera: Fixed wide-medium shot, eye-level, locked off. Absolutely no
camera motion, no zoom, no pan, no parallax. Subject stays perfectly
centered for the entire clip. At least 10–15% empty space on all four
sides — the top of the head, the bottom of the feet, and both sides must
never touch or cross the frame edges in any pose, including shiver
extremes and wink moments.

Style: Match the reference image exactly. 3D render, cyberpunk
aesthetic, jelly physics, soft gelatinous texture.

Background: Identical to reference — solid uniform magenta / hot pink
chroma key screen (#FF1493 or #E91E63), completely flat. NO new textures,
gradients, particles, or floor lines may appear during the animation.

CRITICAL — no translucent environmental effects during animation:
no jelly puddles appearing under the character, no liquid splashes from
jumps, no water reflections, no soft drop shadows, no mist, no fog,
no semi-transparent particle trails. These render as alpha-blended
magenta pixels that survive chromakey and stay visible as pink
artifacts in the final sticker (irreversible in post — see KB 7.5).
If the action involves jumping or landing, keep the character airborne
or on an implied flat surface, NEVER let it interact with a translucent
medium.

Negative — must NOT appear: no watermark, no logo, no text overlay, no
camera movement, no zoom-in or zoom-out, no character changes (color,
size, identity), no extra characters appearing, no body parts cut off
by the frame edges in any frame.
```

### 8.5 Тонкости и pro-tips

- **Image stage variants:** Nano Banana / Imagen генерят 1–4 image per request. Запроси 4, отбери 1. Если все четыре «не те» — меняй промпт, а не выбирай «лучший из плохих».
- **Character bible:** заведи папку `Дизайн/character_bible/`, положи туда 1–3 канон-референса (нейтральная поза + типичная улыбка/жест). Используй ОДИН и тот же reference между сценариями — это даёт consistency и Номс не «дрейфует» от сцены к сцене.
- **Video seed:** ВСЕГДА передавай image как seed (image-to-video), не генерь видео text-only. Это критично для consistency.
- **Don't repeat appearance in video prompt:** если уже есть seed image, повторное описание внешнего вида в text prompt часто заставляет модель его «переделывать» по-своему. Описывай ТОЛЬКО действие.
- **Camera lock:** модели любят добавлять микро-zoom или drift. Прямой запрет («locked off, no parallax») реально работает в Veo. Дублируй в Negative.
- **Seamless loop:** если модель умеет принимать `end_image_frame` (Veo 2/3 умеет в некоторых режимах) — поставь его равным start image. Иначе генерь 5 вариантов, выбирай где конечная поза визуально ≈ начальной.
- **3 секунды:** всегда указывай в промпте «3 seconds duration» — модели по умолчанию могут отдать 5–10 сек, что потом всё равно обрежется и потеряет нужные фазы.
- **Negative prompts реально работают** в Veo / Imagen. Используй явные запреты: «no watermark, no text, no camera movement, no body parts cut off».
- **Watermark Veo:** включается, если в промпте есть слова, которые модель ассоциирует с «professional» / «cinematic». Помогает добавить «no watermark, no logo» в Negative и `--strip-right 140` в нашем pipeline (страховка).
- **«Nano Banana» = Gemini 2.5 Flash Image** (image-only). Видео генерируется через Veo (тоже через Gemini AI Studio). Если пользователь говорит «делаю видео в Nano Banana» — уточни, скорее всего под капотом Veo.

---

## 9. История

| Дата | Файл | Mode | Параметры | Заметки |
|---|---|---|---|---|
| 2026-05-10 | `noms_hello_wave.webm` (245 KB, 24 fps, 3 сек) | clean | `--strip-right 140 --keep-decoration left` | Эталон clean mode; pipeline зафиксирован (rembg + decoration recovery + bbox square crop) |
| 2026-05-10 | `noms_celebrate_registration.webm` (243 KB, 15 fps, 3 сек) | scene | `--start 2.5 --duration 3 --strip-right 140 --mode scene --scene-fps 15 --scene-tightness tight` | Эталон scene mode; hybrid alpha для сцен с конфетти. `tight` даёт Номса 92% canvas, дальние частицы отрезаны (изначально была wide, переделано по фидбеку) |
| 2026-05-11 | `noms_frozen.webm` (169 KB, 24 fps, 3 сек) | clean | `--start 3.5 --duration 3 --strip-right 140 --mode clean` | «Замёрзший Номс» — дрожь, подмигивание, пиксельное пламя в руках, ледяные кристаллы. Огонь и лёд внутри контура Номса → rembg сохраняет автоматически, decoration recovery не нужен. Пар изо рта (~4с в source) rembg отбросил как отдельный объект |
| 2026-05-12 | `noms_streak_3days.webm` v1 (216 KB, 24 fps, окно 0–3с) | clean | `--start 0 --duration 3 --strip-right 140 --mode clean --bg-color 0xFF1493` | «Стрик 3 дня» окно 1 — приветствие с огнём. **Первое видео на magenta-фоне.** Первая итерация (без `--bg-color`) дала розовое halo + дыру между лапкой и огнём. Фикс: добавлены в `make_sticker.py` (1) `binary_fill_holes` на маленьких дырах (`MAX_HOLE_PX=1500`), (2) chroma-aware despill в contour band 6px, (3) убран ошибочный `floor at non_dom_max`. Опровергает предыдущее ложное правило «magenta работает из коробки» |
| 2026-05-12 | `noms_streak_3days.webm` v2 (192 KB, 15 fps, окно 2.5–5.5с) | scene | `--start 2.5 --duration 3 --strip-right 140 --mode scene --bg-color 0xFF1493 --scene-fps 15 --scene-tightness tight` | «Стрик 3 дня» окно 2 — Номс прыгает в желейную лужу с огнём в руке. Clean mode **не сработал**: на крупных кадрах огня rembg **полностью теряет пиксельный огонь** (рендерит его как отдельный объект и считает фоном). Решение — scene mode с magenta chromakey: combined alpha `max(rembg, chromakey)` сохраняет огонь. **Lesson:** пиксельные декорации, которые иногда крупные и далеко от тела (огонь, иконки), требуют scene mode даже на простом одноцветном фоне. Симптом: kadr-by-kadr scan через `make_sticker --keep-frames` показывает `nobg/f_NN.png` где огня нет, хотя в `raw/f_NN.png` он есть. Розовые желейные брызги под ножками — часть сюжета прыжка, остаются в финале (alpha-blended, не убираются chromakey — см. секцию 7.5). v2 отвергнута пользователем из-за этих брызг |
| 2026-05-12 | `noms_streak_3days.webm` v3 (210 KB, 24 fps, ping-pong 0-1.5 / 1.5-0) | scene | `--start 0 --duration 3 --strip-right 140 --mode scene --bg-color 0xFF1493 --scene-fps 24 --scene-tightness tight` (на pre-built ping-pong mp4) | «Стрик 3 дня» промежуточная версия (заменена v4 из-за чёрных рамок). **Техника ping-pong loop:** обойти splash-проблему. Source pre-puddle окно 0-1.5с. Forward 1.5 + reverse 1.5 = 3 сек seamless loop. **Lesson — секция 7.6.** ⚠️ Имела чёрные пиллабоксы по бокам — `--strip-right 140` отрезал лишь половину правого пиллабокса (280px), левый не трогался вовсе |
| 2026-05-12 | `noms_streak_3days.webm` v4 (183 KB, 24 fps, ping-pong) | scene | Без `--strip-*` — auto-pillarbox detect | Промежуточная: добавлен `detect_pillarbox()` в `make_sticker.py`: автоматически детектит чёрные полосы Veo (280px слева + 280px справа в стандартном 1280×720 source) и применяет к strip. Чёрные рамки убраны. **Lesson — секция 7.5b:** Veo рендерит 1:1 контент в 16:9 контейнере с pillarbox; для прежних стикеров `--strip-right 140` был неполным — реально нужно было 280. Auto-detect избавляет агентов от ручного подсчёта. Subject 93% canvas — недостаточно, пользователь попросил максимально крупного |
| 2026-05-12 | `noms_streak_3days.webm` v5 (195 KB, 24 fps, ping-pong) | scene | `--scene-tightness tightest --air-percent 2` | **Финал.** Добавлен preset `tightest` (0%/+5%/0% — minimum scene region around Noms). Subject **96% of canvas**, минимальный air 2%. Огонь сохранён на всех кадрах (с лёгким clip на point reverse t=1.5 где у Номса две руки с огнями). Это технический максимум — больше нельзя сжать без обрезки самого силуэта. SHA `c7467568...` |

Чтобы добавить новый сценарий: запустить скрипт, проверить по чек-листу, дописать строку в эту таблицу.

---

## Related Concepts

- [[concepts/ux-crosscutting-principles]] — стикеры как часть UX-системы NOMS
- [[concepts/ui-stickers-headless]] — headless-стикеры в UI бота (как используются те, что мы здесь делаем)
- [[concepts/user-preferences]] — стиль работы пользователя (план → одобрение → реализация)
