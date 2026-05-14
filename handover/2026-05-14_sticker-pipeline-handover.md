---
title: "Telegram Sticker Pipeline — Handover для агента-преемника"
date: 2026-05-14
author: claude-agent (context-handover)
status: active
related_kb:
  - "concepts/telegram-sticker-pipeline.md"
  - "daily/2026-05-10.md"
  - "daily/2026-05-11.md"
  - "daily/2026-05-12.md"
  - "daily/2026-05-14.md"
---

# Telegram Sticker Pipeline — Handover

> **Контекстное окно предыдущего агента переполнилось.** Этот документ передаёт всю работу по созданию `.webm`-стикеров Номса для Telegram. Цель — чтобы ты вышел в продакшн с первого запроса пользователя.

## 0. Первое что сделать

1. **Прочитай главный KB-документ:**
   `claude-memory-compiler/knowledge/concepts/telegram-sticker-pipeline.md`
   ~880 строк, 9 секций. Это **источник правды**. Все детали (правила, флаги скрипта, промпт-шаблоны, история, тонкости) — там.

2. **Просмотри список эталонов** в `Дизайн/stickers/noms_*.webm` — 5 одобренных пользователем стикеров.

3. **НЕ запускай ничего вслепую.** Все типовые ошибки уже описаны в KB секциях 7.3–7.6 и 8.4b — читай их, чтобы не повторять чужие потерянные часы.

## 1. Что просит пользователь и как отвечать

Пользователь Владислав. Стиль:
- **Русский язык во всём** (см. user_preferences). Кроме идентификаторов (имена файлов, флаги, RGB-значения).
- **План → ExitPlanMode → реализация.** Если задача неочевидная — описать варианты, дать выбрать.
- **Push back на переусложнение.** Если предложенный путь сложнее чем нужно — скажи.
- **Не молчать о проблемах.** Если что-то нестандартное в source — описать, не пытаться скрыть/обойти.
- **Цикл "проверь → покажи → ожидай feedback"** — после генерации показать sample-кадры, дождаться реакции, не сразу фиксировать в KB.

Типовой запрос: «сделай стикер из `<...>/<сценарий>/<file>.mp4`, окно от A до B».

## 2. Главный workflow (happy path)

```bash
# 1. Изучить sample-кадры исходника
ffmpeg -i <src.mp4> -vf "fps=2,scale=320:-1" /tmp/preview/p_%02d.png
# Посмотри 8-16 кадров → выбери окно с пиком действия

# 2. Запустить pipeline (БЕЗ --strip-* — auto-pillarbox разберётся)
/Users/vladislav/Documents/NOMS/Дизайн/stickers/.venv/bin/python \
  /Users/vladislav/Documents/NOMS/Дизайн/stickers/scripts/make_sticker.py \
  --input "<src.mp4>" \
  --output "/Users/vladislav/Documents/NOMS/Дизайн/stickers/<имя>.webm" \
  --start <N> --duration 3 \
  --mode scene \
  --bg-color 0xFF1493 \
  --scene-fps 24 \
  --scene-tightness tightest \
  --air-percent 2

# 3. Verify
ffprobe -v error -show_entries stream=codec_name,width,height,r_frame_rate:format=duration -of default=noprint_wrappers=1 <out.webm>
# Декодируй 3-5 кадров через format=rgba и посмотри визуально

# 4. Покажи пользователю + дождись feedback
```

**99% случаев** этих параметров достаточно. Параметры — баланс качества и compatibility со всеми lessons learned ниже.

## 3. Артефакты pipeline

| Файл | Назначение |
|---|---|
| `Дизайн/STICKER_PIPELINE.md` | Stub-указатель (документ переехал в KB) |
| **`claude-memory-compiler/knowledge/concepts/telegram-sticker-pipeline.md`** | Полный operational guide. 9 секций. **Читать первым.** |
| `Дизайн/stickers/scripts/make_sticker.py` | CLI-скрипт со всеми фиксами. **Не модифицировать без записи lesson в daily log.** |
| `Дизайн/stickers/.venv/` | venv с rembg, scipy, PIL, numpy, onnxruntime. Готов к использованию. |
| `Дизайн/stickers/noms_*.webm` | Эталоны (5 шт.) |
| `Дизайн/NOMS Желе фото/Сценарии:Сцены/<scenario>/*.mp4` | Source-видео от Veo / Nano Banana |
| `Дизайн/NOMS Желе фото/Сценарии:Сцены/<scenario>/Gemini_*.png` | Image-референсы для image-to-video (от Nano Banana) |

## 4. Что нашли и зафиксировали (compressed lessons)

| Lesson | Симптом | Решение | Где детали |
|---|---|---|---|
| **rembg теряет огонь** | Декорация рядом с телом, но не часть тела (огонь в руке) — rembg выкидывает её | `--mode scene` (combined alpha rembg+chromakey). Не `--mode clean`. | KB 7.4 |
| **Magenta просвечивает сквозь jelly** | Розовый ободок halo вокруг Номса | `--bg-color 0xFF1493` обязательно даже в clean mode. Despill в contour band 6px. | KB 7.3, 8.2 |
| **Veo рендерит pillarbox** | Чёрные вертикальные полосы по бокам в финальном webm | auto-pillarbox detect (default ON). НЕ указывать `--strip-*` вручную для Veo-источников | KB 7.5b |
| **Alpha-blended splash unfixable** | Полупрозрачная лужа / тень / отражение → pink residue не убирается chromakey | Невозможно фиксить в post. Перегенерировать source без splash, или ping-pong loop из pre-splash window | KB 7.5, 7.6 |
| **rembg плохо на сложной сцене** | Сложный фон с конфетти → rembg теряет голову Номса | `--mode scene` с closing iter=12 + scene region bounding | KB 7.4 |
| **Direction-specific motion** | Танец / ходьба / поворот → ping-pong reverse выглядит странно | Указать в промпте `periodic motions only` (см. 8.4b checklist). Если уже в source — мерять, действие должно быть periodic | KB 7.6, 8.4b |
| **Floor / reflective surface** | Источник с полом → pink halo внизу | В промпте `no floor, no reflective tiles` (mandatory negative). Если уже в source — перегенерировать | KB 7.5, 8.4b |
| **`floor at non_dom_max` bug** | Despill превращал deep purple в розовый | Удалён из despill. Не возвращать. | KB 8.2 (история фикса) |
| **Закрытие дыр в маске** | Между лапкой и огнём провал alpha | `binary_fill_holes` только для МАЛЫХ дыр (`MAX_HOLE_PX=1500`). Большие — реальный фон, заполнять ≠ ОК | KB 7.5b |
| **Серийная схожесть** | Pipeline ОК, но пользователь говорит «выглядит как соседний стикер серии» | До выбора окна — декодировать t=0 соседних `noms_<series>_*.webm` и убедиться что новый отличается **позой/атрибутом**, не только интенсивностью | KB 7.7 |

## 5. Чеклист «перед сдачей»

```
[ ] ffprobe: codec_name=vp9, width=512, height=512, r_frame_rate ≤30/1, TAG:ALPHA_MODE=1, duration ≤3.0
[ ] ls -la: размер ≤ 256_000 bytes
[ ] Декодирован случайный кадр через format=rgba — Номс в полный рост, ничего не обрезано
[ ] Декодирован t=0 и t=last — loop seam терпимый (визуально близкие кадры)
[ ] Цвет тела Номса в центре кадра ≈ deep purple (R~55, G~25, B~118), НЕ розовый
[ ] Нет чёрных рамок по бокам (auto-pillarbox сработал)
[ ] Нет видимого halo вокруг контура (magenta despill сработал)
[ ] Нет полу-прозрачных артефактов на полу (если в источнике не было пола)
[ ] Огонь / декорации видны на всех кадрах
```

Если хоть один пункт fail — НЕ показывать пользователю как готово. Чинить или спрашивать.

## 6. Промпт для делегирования через Agent tool

Если решаешь делегировать (например в Explore для исследования или general-purpose для обработки) — **обязательно** скопируй блок ниже и заполни `<…>`:

```
Задача: сделать Telegram-стикер из <file.mp4>.

Источник: <абсолютный путь к .mp4>
Выход:    /Users/vladislav/Documents/NOMS/Дизайн/stickers/<имя>.webm

ИСТОЧНИК ПРАВДЫ: KB-концепт
/Users/vladislav/Documents/NOMS/claude-memory-compiler/knowledge/concepts/telegram-sticker-pipeline.md

ПРЕЖДЕ ВСЕГО: прочитай этот KB полностью. Особенно секции 2 (правила), 4 (запуск),
7.3-7.6 (типовые проблемы и решения), 8.4b (если промпт писать для Veo/Nano Banana).
Игнорировать — значит наступать на грабли которых там уже описано 10+ штук.

Алгоритм:
1. Извлеки 8-16 sample-кадров (ffmpeg fps=2 scale=320:-1) и визуально оцени:
   - есть ли пол / отражения / splash → если да и нужно убирать, читай 7.5
   - есть ли direction-specific motion (танец, ходьба) → 7.6
   - где пик действия → определи окно --start/--duration
2. Запусти готовый скрипт (флаги по умолчанию для Veo-source с magenta фоном):
   /Users/vladislav/Documents/NOMS/Дизайн/stickers/.venv/bin/python \
     /Users/vladislav/Documents/NOMS/Дизайн/stickers/scripts/make_sticker.py \
     --input "<src>" --output "<dst>" \
     --start <N> --duration 3 \
     --mode scene --bg-color 0xFF1493 \
     --scene-fps 24 --scene-tightness tightest --air-percent 2
3. Verify по чек-листу секции 5 этого handover.
4. Покажи юзеру: путь + размер + sample-кадр (декодированный с alpha). Если что-то
   не соответствует правилам — переделай, не сдавай «как есть».

Если нестандартное (источник НЕ от Veo, фон НЕ magenta, в кадре splash/floor,
direction-specific motion) — НЕ молчать, описать проблему и предложить варианты
(перегенерация source через Nano Banana, ping-pong loop, переключение режима).
```

## 7. История стикеров (production)

5 одобренных эталонов в `Дизайн/stickers/`:

| Файл | Сценарий | Mode | Урок |
|---|---|---|---|
| `noms_hello_wave.webm` (245 KB) | Привет | clean | Pivotal — pipeline зафиксирован |
| `noms_celebrate_registration.webm` (243 KB) | Поздравление с регистрацией | scene tight | Scene mode для конфетти |
| `noms_frozen.webm` (169 KB) | Замёрзший | clean | Огонь и лёд внутри контура → clean ОК |
| `noms_streak_3days.webm` (195 KB) | Стрик 3 дня | scene + ping-pong | **Ping-pong loop обходит проблемную фазу** |
| `noms_streak_7days.webm` (183 KB) | Стрик 7 дней | scene tightest | **Первый стикер по обновлённым 8.4b-промптам — happy path** |

Детали (точные параметры, причины выбора) — секция 9 KB.

## 8. Что НЕ делать (top-5 типовых ошибок)

1. **НЕ повышать chromakey similarity ради лужи.** Огонь живёт в том же YUV-кластере что splash — увеличишь similarity убьёшь огонь. Если лужа в source — это alpha-blending (unfixable), нужна перегенерация source. KB 7.5.

2. **НЕ заявлять «работает из коробки» после одного прогона** без визуального сравнения с source RGB. Бывшая ложная гипотеза «magenta работает в clean mode без `--bg-color`» — на практике даёт halo на jelly-теле. Всегда sample RGB центра тела через PIL.

3. **НЕ пытаться чинить «обрезанный огонь» через расширение crop / уменьшение strip-right.** Это `rembg-loses-fire` (КБ 7.4) — данных в alpha-маске нет, расширение границ их не вернёт. Решение: `--mode scene`.

4. **НЕ копировать `--strip-right 140` из старых эталонов** (legacy hack). Veo pillarboxes 280px с каждой стороны. Auto-detect разберётся, не указывай `--strip-*` вручную.

5. **НЕ генерировать промпт для Nano Banana без чтения 8.4b чеклиста.** Хороший image-промпт ≠ хороший video-промпт. Video требует periodic motions + locked camera + no floor + no perspective. KB 8.4b.

## 9. Дополнительные команды для дебага

```bash
# Sanity-check почему стикер «теряет декорацию»
make_sticker.py ... --keep-frames     # сохранит промежуточные PNG
# Затем open <workdir>/raw/f_NN.png  ← есть ли декорация в исходнике
#       open <workdir>/nobg/f_NN.png ← сохранил ли rembg
# Если raw имеет, nobg потерял → rembg-failure → нужен scene mode

# Sample RGB центра тела (deep purple должен быть R~55, G~25, B~118)
python3 -c "
import numpy as np
from PIL import Image
im = np.array(Image.open('/tmp/check.png'))
print(im[256-16:256+16, 256-16:256+16, :3].mean(axis=(0,1)).astype(int))
"

# Hash check (если пользователь говорит «всё то же» — проверить какой файл смотрит)
shasum -a 256 "/Users/vladislav/Documents/NOMS/Дизайн/stickers/noms_<name>.webm"

# Build ping-pong source (когда есть проблемная фаза после safe pre-content)
ffmpeg -y -ss 0 -t 1.5 -i "$SRC" -an -c:v libx264 -crf 12 /tmp/fwd.mp4
ffmpeg -y -i /tmp/fwd.mp4 -vf reverse -an -c:v libx264 -crf 12 /tmp/rev.mp4
echo -e "file '/tmp/fwd.mp4'\nfile '/tmp/rev.mp4'" > /tmp/concat.txt
ffmpeg -y -f concat -safe 0 -i /tmp/concat.txt -an -c copy /tmp/pingpong.mp4
```

## 10. Известные открытые вопросы

- **Loop seam в `noms_streak_7days.webm`**: пламя на t=0 меньше, на t=2.95 крупное. Не идеальный seamless. Если пользователь увидит flicker — пересобрать ping-pong'ом из 6.5–8с (стабильно пиковое пламя).
- **Старые стикеры hello_wave / celebrate / frozen** делались с `--strip-right 140`, до auto-pillarbox. **Могут иметь скрытые pillarboxes** в финальном webm. Если будут перезаливаться в Telegram — стоит пересобрать через `make_sticker.py` без `--strip-*`.
- **«Nano Banana» = Gemini 2.5 Flash Image** (image-only). Видео через Veo (под капотом). Если пользователь говорит «Nano Banana видео» — уточни UI, скорее всего Veo.

## 11. Кэш-вопросы (если пользователь говорит «не вижу изменений»)

Файл на диске правильный, но плеер/Telegram показывает старую версию. Бывает часто:

1. `shasum -a 256 <file>` — сравни с тем что в логе предыдущего билда
2. Если хэш новый, но визуально старое — это кеш:
   - Browser file:// — `Cmd+Shift+R` hard refresh
   - macOS QuickLook — `qlmanage -r cache && killall Finder`
   - **Telegram кэширует по sticker_id** — после `/addsticker` повторная загрузка с тем же путём НЕ обновит. Удалить через `/delsticker` и залить заново.

## 12. Финальный совет

**Pipeline зрелый.** 99% задач решаются командой из секции 2 с дефолтными параметрами + auto-pillarbox + правильным окном. Если задача выходит за рамки — читай соответствующую секцию KB **до** того как пробовать чинить руками. Каждая секция 7.x и 8.4b — это **history of failed approaches**, обозначенных как «что не делать».

Удачи. Если что-то непонятно — пиши в daily/ и обновляй этот handover.
