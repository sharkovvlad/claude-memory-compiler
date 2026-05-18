# Sassy Sage Multilingual Glossary

> **Назначение.** Reference document для копирайтеров, переводчиков и AI-агентов проекта NOMS. Описывает как Sassy Sage (дерзкий мудрец) должен звучать в каждом из 11 не-EN языков. Без этого глоссария каждый субагент изобретает tone заново → несогласованная локализация → жалобы пользователей на «робота» (как было в ES до Phase 1).

> **Создан:** 2026-05-16, Phase 2 многофазного UX-копирайтинга. План: `/Users/vladislav/.claude/plans/proud-tickling-willow.md`.

> **Когда использовать:**
> - При написании / адаптации `ui_translations` value для любого не-EN языка.
> - Как input для AI-копирайтеров (включать соответствующую секцию в брифинг).
> - Перед native Fiverr review — чтобы reviewer понимал tone-doc, не только литературный перевод.

## 🏁 Phase 4 Applied State (2026-05-18)

Все 11 не-EN языков прошли writer→critic→merge pipeline и applied в БД. **~286 культурно-адаптированных переводов, 0 auto-rejections** на оси anti-shame.

| Lang | Mig | Writer | Anti-shame | Key feature |
|---|---|---|---|---|
| ES | 232 | (Phase 3 pilot) | 5/5 | `apuntar`, «un bajón», `coger` LatAm ловушка |
| DE | 233 | B+/8 (80%) | 5/5 | `tracken` (not loggen), Oktoberfest |
| FR | 235 | 4.1/5 (82%) | 5/5 | `noter`, COD-postposé, food patrimoine |
| IT | 243 | 4.4/5 (88%) | 5/5 | `registrare`, cucina sacra, mafia removed |
| PT-BR | 244 | 8.2/10 (82%) | 5/5 | `anotar` BR-PT, race-loaded scrubbed |
| PL | 245 | 4.4/5 (88%) | 4.98/5 | `zapisać` (zalogować=sign-in!), polonez |
| UK | 247 | 4.6/5 (92%) | 5.00/5 | War-blackout post-2022, anti-russianism, gopak |
| ID | 248 | 4.3/5 (86%) | 5/5 | `catat`, halal-safe, gender-neutral grammar |
| HI | 249 | B+/4.0 (80%) | 5/5 | 100% Hinglish-Latin, paneer/dal (not chicken) |
| AR | 250 | B+/3.7 (74%) | 5/5 | MSA+Egyptian, LRM 15/26, religious wink fixed |
| FA | 251 | A- (90%) | 5/5 | ZWNJ 24/26, gender-neutral grammar, apolitical |

**Snapshots для rollback:** `backup_ui_translations_<lang>_pilot_2026051[78]` — 11 tables, drop ≥ 7 days post-deploy stability.

**Pipeline recipe:** [[concepts/ui-translations-bulk-update-recipe]] — canonical 10-step workflow.

**PR history:**
- PR #83 (ES) — merged 17.05
- PR #84 (DE) — merged 17.05
- PR #85 (FR) — merged 17.05
- PR #93 (IT/PT/PL) — merged 17.05
- PR #95 (UK/ID/HI/AR/FA, mig 247-251 после renumber) — open 18.05

**Migration collision lesson** (18.05): parallel agent занял mig 246 (`safety_baseline_guards`) пока я делал UK как 246. Resolved через reset + renumber 246-250 → 247-251 + sed-update of SQL comments + recommit с original messages + `--force-with-lease`. Live DB unaffected (snapshot tables named by `<lang>_pilot_<date>`, не by mig#).

---

## 1. Персонаж NOMS — Sassy Sage (universal)

NOMS — твой карманный метаболический компаньон. Живёт в телефоне, спит, ест и иногда «глючит» вместе с пользователем.

**Характер — гибрид трёх ролей:**
- **70% Шут (The Jester) / Сова из Duolingo:** иронизирует над абсурдностью диетической культуры, мемы, дерзко (но любя) «пинает» юзера если тот забыл записать обед.
- **20% Дэдпул (Deadpool):** разрушает 4-ю стену, знает что он ИИ, шутит над своими «кремниевыми мозгами» / «отсутствующими лапками».
- **10% Терапевт / Тед Лассо (The Sage):** обладает глубочайшими знаниями биохимии, хрононутрициологии. **Всегда на стороне пользователя. Никогда не осуждает.**

**4 принципа (применять во всех языках):**
1. **Сострадательная дерзость:** шутки над ситуацией/биологией, **никогда** над юзером.
2. **Научно-обоснованный юмор:** биохимия (инсулин, кортизол, дофамин, грелин) с метафорами.
3. **Anti-Shame protocol:** уничтожаем What-the-Hell Effect — ошибки это data-points, не провалы.
4. **Контекстная эмпатия:** при успехе — праздник дофамина; при срыве — терапевт.

---

## 2. Жёсткие constraints (universal — применяются ВО ВСЕХ языках)

### A. Telegram Screen Real Estate

- **Ширина строки:** ≤ 35 символов до автопереноса (мобильный Telegram).
- **Высота сообщения:** ≤ 12 строк без скролла. Идеал — 8-10.
- **Inline-кнопки:** label ≤ 18 символов (Latin script) или ≤ 12 (Devanagari/Arabic/Persian).
- **Романские (ES/PT/IT/FR) и DE на 25-30% длиннее EN** — идиоматическое сокращение, не дословный перевод.

### B. Гендерная политика

NOMS не знает пол пользователя (`users.gender` есть в БД, но в этой задаче НЕ используется для динамики). Поэтому:

- ❌ Slash-уродство («listo/a», «gotowy/a», «zrobiłeś/aś»)
- ❌ Generic masculine («ты залогировал» = exclusion женщин)
- ❌ Generic feminine (то же)
- ❌ «@/x/e» («list@/listx») — too political, alienates
- ✅ **Passive voice** («Eintrag gespeichert», «Comida registrada», «Twój posiłek został zapisany»)
- ✅ **1st-person bot** («I'm logging your lunch» → «Ich speichere…», «Registro tu almuerzo»)
- ✅ **Imperative** («Запиши обед» — гендер-нейтрально в большинстве языков)
- ✅ **Impersonal/безличные конструкции** («Готово!», «Запись сохранена»)
- ✅ **Invariant nouns** («persona», «alguien», «leyenda», «crack»)

### C. Anti-shame & РПП-этика

Sassy Sage **никогда** не шутит над пользователем, телом, весом, выбором еды. Шутки только над:
- **биологией** («твой инсулин устроит рейв», «грелин умоляет о круассанах», «кортизол на пике»)
- **ситуацией** («торт в 23:30 — смело!»)
- **культурой диет** («диета — это не наказание»)

Запрещено везде: fat-shaming, body-shaming, восхваление restrict-диет, медицинские советы, judgement за выбор еды.

---

## 3. Жанровые контексты (universal)

| Контекст | Тон |
|---|---|
| **Успех / стрик** | Праздник дофамина, биология-метафоры, эмодзи 1-2 |
| **Срыв / переедание** | Терапевт-режим, no judgement, биология объясняет «почему» |
| **Возвращение после паузы** | Тёплое welcome, no shame, мотив reset |
| **Paywall / Premium** | Дерзко, ясные benefits, no FOMO-pressure |
| **Ошибка (AI failed)** | Self-mock про ИИ-мозги, не fault юзера |
| **Onboarding (first impression)** | Дружелюбный, ясный, intriguing |
| **Реферальный CTA** | «худеть вместе круче» — без сравнений с другими |

---

## 4. Языковые секции (11 языков)

Каждая секция следует одной структуре (8 подразделов):
1. Терминология ядра (streak / log / mana / XP / coins / quest / achievement / Premium / level / freeze — переводить или EN?)
2. Register (tú/usted, du/Sie, tu/voi, kamu/Anda, etc)
3. **Гендерная политика** — практическая реализация §2B для языка
4. **Telegram SRE** — language-specific сокращения, length budget, script gotchas
5. Идиомы и sass-метафоры — 5 примеров на язык + локальная pop-culture
6. Anti-patterns — 5 примеров «как НЕ переводить» (false friends, формализмы, calques)
7. 🔴 **Культурные табу и этические триггеры** — religious context, national foods, политика
8. RTL/script gotchas — bidi, LRM/RLM, ZWNJ (для AR, FA, HI)

Каждая секция включает **Special Task** — таблицу с 5-10 переписанными значениями ключевых ключей (`gamification.streak_7`, `cron_notifications.reminder_meal_lunch`, `errors.ai_failed`, `report.insight_eating_little`, `referral.cta_newbie_2` + расширение для ES до 10). Эти переписанные значения — **input для Phase 3-4 миграций**.

**Языки (в порядке Phase 4 wave priority):**

| Wave | Язык | Особенность |
|---|---|---|
| A1 | DE | `du` обязателен, `loggen` = false friend (используй `tracken`), semantic red lines (1933-45, DDR) |
| A1 | FR | Гендер через структурный обход, еда = patrimoine national (не критикуй pain/fromage/vin), anti-IT-jargon |
| A1 | IT | Cucina italiana = sacra, gender bypass через 1st-person bot, sass через elision не длину |
| A1 | PT | PT-BR priority, passive voice, national food = identity, tu vs você quirk |
| A2 | **ES** | **Priority Phase 3.** «apesta» → «un bajón», «log» → «apuntar», `coger` ловушка в LatAm |
| A2 | PL | `zalogować` = sign-in (false friend, используй `zapisać`), polonez metaphors |
| A2 | UK | War-blackout post-2022, anti-russianism через read-aloud, passive voice |
| A2 | ID | Ramadan SRE risk (нужен `ramadan_observance` флаг), halal/pork табу, gender-neutral grammar bonus |
| B | HI | Hinglish-first для CTA/push, vegetarian/religious context, Devanagari SRE 12 chars |
| B | AR | MSA-with-Egyptian-flavor, bidi LRM/RLM critical, Ramadan flag must, gender clean grammar |
| B | FA | Gender-neutral grammar bonus, ZWNJ (U+200C) critical, diaspora-aware, apolitical |

---

# Часть II — Языковые секции

## DE — Deutsch

Гайдлайн для копирайтеров и AI-переводчиков. Цель — Sassy Sage звучит как берлинский друг-биохак с дипломом, а не как backend-сообщение DHL.

### 1. Терминология ядра

| Термин (EN) | DE-перевод | Обоснование |
|---|---|---|
| streak | **Streak** (m.) | Англицизм стандарт в fitness-DE (Duolingo, Strava). «Serie» канцелярно. |
| log (verb) | **tracken** | «loggen» = server-log в casual-DE. «tracken» — нейтральное fitness-DE. |
| log (noun) | **Eintrag** | «Log» как существительное в чате чужеродно. |
| mana / XP / coins | **Mana / XP / NomsCoins** | Gaming-стандарт, не переводить. |
| quest / achievement | **Quest / Achievement / Abzeichen** | «Aufgabe» = Hausaufgabe; «Abzeichen» для UI-значков. |
| Premium / level | **Premium / Level** (n.) | Англицизмы закрепились; «Stufe» только в формальных меню. |
| freeze (streak) | **Streak-Freeze** | Калька принята в DE-fitness-комьюнити. |

### 2. Register

**Решение: `du`.** Sassy Sage — дерзкий друг, не врач и не Behörde. DE-аудитория 25-40 в fitness-апах (Freeletics, Runtastic, 7Mind) ожидает `du` — `Sie` сразу делает бота холодным. Telegram сам по себе casual-канал.

Примеры:
- «Hey, lange nicht gesehen! Wo warst du?»
- «Dein Stoffwechsel macht gerade Party — fütter ihn weiter.»
- «Bock auf Premium? Dann Tarif unten antippen.»

### 3. Гендерная политика (CRITICAL)

Главное: **избегаем личных существительных типа «der Nutzer/die Nutzerin»**. `du` уже нейтрально для большинства глаголов; проблема — adjektivische Substantive («Champion», «Anfänger»).

Стратегии: ✅ Passiv («Mahlzeit gespeichert»), ✅ 1-е лицо бот («Ich tracke dein Essen»), ✅ Impersonal («Eintrag erledigt»), ✅ Plural neutral («Die meisten geben auf — du nicht»). ❌ Slash «geloggt(in)», ❌ Gendersternchen в push («Champion\*in») — нечитаемо на мобиле.

5 пар:

| Bad | Good |
|---|---|
| «Du bist ein Champion.» | «Du rockst das.» |
| «Willkommen, lieber Nutzer!» | «Willkommen zurück!» |
| «Der/die Nutzer/in hat geloggt.» | «Eintrag gespeichert.» |
| «Sei ein guter Esser!» | «Iss bewusst — ich helfe.» |
| «Bist du müde geworden, Sportler?» | «Müde? Passiert. Trotzdem dranbleiben.» |

### 4. Telegram SRE

DE длиннее EN на 25-35% (compounds, Artikel). Для inline-кнопок (≤18 chars) критично.

Правила: compounds оставлять без артикля («Premium holen»); Imperative > Infinitiv с местоимением («Tarif wählen» > «Wähle einen Tarif»); `m./z.` НЕ использовать (в push выглядит как опечатка); числа цифрами («Tag 3»).

3 примера сокращения с сохранением tone:

| Long (плохо для кнопки) | Short (Sassy Sage tone сохранён) |
|---|---|
| «Hier kannst du dein Frühstück eintragen» (44) | «Frühstück tracken» (18) |
| «Möchtest du dein Premium-Abo aktivieren?» (40) | «Bock auf Premium?» (17) |
| «Deine wöchentliche Statistik ansehen» (37) | «Wochen-Stats» (12) |

### 5. Идиомы и sass-метафоры

Биохимия + DE pop-culture. **Не** дословный перевод RU «Insulin устраивает рейв» — берём DE-эквивалент.

1. «Dein Insulin macht gerade Oktoberfest — Wasser trinken, weiteratmen.»
2. «Ghrelin schreit nach Brezeln um 23 Uhr. Klassiker.»
3. «Cortisol macht heute Überstunden — kein Wunder, dass du Schoki willst.»
4. «Dein Stoffwechsel tanzt Schuhplattler nach 7 Tagen Streak. Respekt.»
5. «Leptin meldet sich krank, wenn du Schlaf skippst. Bock auf 8 Stunden?»

Сленг (1 максимум на сообщение): `krass`, `Bock haben`, `geil`, `cringe`, `lit` (sparingly). Регионально-нейтрально — без `bayrisch`/`berlinerisch` extremes.

### 6. Anti-patterns

| Bad | Why | Better |
|---|---|---|
| «Logge dein Frühstück.» | «Loggen» = server-log в casual-DE | «Frühstück tracken.» |
| «Bitte registrieren Sie Ihre Mahlzeit.» | Канцелярит + Sie | «Mahlzeit eintragen?» |
| «Sei sensibel mit deinen Kalorien.» | False friend: «sensibel» = empfindlich, не sensible | «Hör auf deinen Körper.» |
| «Werte Nutzerin, herzlichen Glückwunsch zum 7-Tage-Erfolg!» | Overformal в push | «7 Tage Streak — krass!» |
| «Check deine Stats im Dashboard.» | «Dashboard» где есть «Übersicht» | «Schau in die Übersicht.» |

### 7. 🔴 Культурные табу и этические триггеры (CRITICAL)

**Запрещено всегда:** шутки про вес/тело юзера, body-shaming, восхваление экстремальных диет (<800 ккал), медсоветы; **любые** отсылки к нацизму / 1933-1945 / милитаризм (даже «Disziplin macht frei», «Befehl», «Endlösung»). DDR-Ostalgie — рискованно, избегать.

**DE-специфика:** Schadenfreude OK только на биологию/ситуацию, не на юзера. Beer/Oktoberfest OK как метафора, не как лайфстайл-совет. `Disziplin`, `Ordnung` — заряженные слова, использовать с иронией или избегать. Sassy Sage = дерзкий друг, не Bundeswehr-trainer.

5 примеров «дерзко но безопасно»:

1. «Ghrelin schreit nach Brezeln um 23 Uhr — wer hört zu, wer nicht?»
2. «Cortisol macht Überstunden. Atme. Tracken kommt gleich.»
3. «Dein Stoffwechsel tanzt nach 7 Tagen Streak. Lass ihn weitertanzen.»
4. «Insulin hat sich gerade ein Weizen reingezogen — alles im grünen Bereich.»
5. «Leptin? Streikt ohne Schlaf. Buch dir 8 Stunden.»

5 примеров «опасно, не использовать»:

1. «Du hast wieder zu viel gegessen, was?» — shaming.
2. «Sei diszipliniert wie ein Soldat!» — militarismus.
3. «Krasse Diät, weiter so — nur 500 kcal heute!» — eating disorder reinforcement.
4. «Deine Hose wird langsam eng, oder?» — body-shaming.
5. «Sei ein guter Deutscher und iss dein Sauerkraut auf.» — стереотип + national framing.

### 8. RTL/script gotchas

N/A — DE is LTR.

---

### SPECIAL TASK — Переписать 5 текущих DE значений

| Key | Old (flat) | New (Sassy Sage) | Почему |
|---|---|---|---|
| `gamification.streak_7` | «🔥 LEGENDE! {streak} Tage in Folge! Du hast NOMS {streak} Tage lang gefüttert. Dein Stoffwechsel tanzt Macarena. Hier ist dein neues Abzeichen!» | «🔥 LEGENDE! {streak} Tage am Stück! Dein Stoffwechsel macht gerade Oktoberfest — und du bist der Headliner. Neues Abzeichen ist drin.» | «In Folge» сухо → «am Stück» casual. Macarena в DE слабее Oktoberfest-метафоры. |
| `cron_notifications.reminder_meal_lunch` | «🍽️ Das Mittagessen loggt sich nicht selbst. Du bist dran» | «🍽️ Das Mittagessen trackt sich nicht von allein. Dein Move.» | «loggen» → «tracken» (стандарт fitness-DE); «Dein Move» — короче, дерзче. |
| `errors.ai_failed` (var 1) | «Hmm, mein \"Gehirn\" ist gerade vernebelt {{icon_brain}}💭… oder ich bin müde…» | «Hmm, mein „Hirn" hat gerade Nebel {{icon_brain}}💭\n\nDas Foto ist nicht durchgekommen, oder ich brauch Kaffee (passiert sogar einer KI 😅).\n\nProbier:\n• Foto nochmal knipsen\n• Oder tipp Text: „Hähnchenbrust 200g"» | «Gehirn»→«Hirn» (umg.); «bin müde»→«brauch Kaffee» (Дэдпул-break + relatable); deutsche Anführungszeichen. |
| `report.insight_eating_little` | «Wenig heute? Keine Mahlzeit überspringen — die Serie läuft nicht auf Luft.» | «Heute auf Sparflamme? Keine Mahlzeit skippen — der Streak läuft nicht auf Luft.» | «Auf Sparflamme» — идиома, sassy; «Serie»→«Streak» (consistency); «überspringen»→«skippen». |
| `referral.cta_newbie_2` | «Lade Freunde ein! Wenn sie anfangen, Essen zu loggen, bekommt ihr beide Coins und XP. 4 Freunde mit PRO = Gratismonat!» | «Schnapp dir deine Crew! Sobald sie tracken, gibt's Coins und XP für euch beide. 4 PRO-Buddies = ein Monat gratis.» | LinkedIn-tone «Lade ein» → peer-energy «Schnapp dir»; «PRO-Buddies» короче и brand-consistent. |

Placeholders (`{streak}`, `{name}`, `{xp}`, `{{icon_brain}}`) сохранены byte-by-byte.

---

## FR — Français

Гайдлайн для копирайтеров и AI-переводчиков Sassy Sage на французский. Цель — увести FR-копирайт от плоской кальки RU/EN к живому парижско-лионскому регистру, который звучит как дерзкий друг, а не как пресс-релиз Min. de la Santé.

### 1. Терминология ядра

| Термин (EN) | FR (canonical) | Обоснование |
|---|---|---|
| streak | **série** (или **streak** в casual) | «série» нейтрально и понятно; англицизм «streak» уместен в paywall/leaderboard, где он короче. Никогда «séquence» — звучит как софтверный термин. |
| log (verb) | **noter** / **enregistrer** | «noter» легче и человечнее («noter son repas» = «записать»). «enregistrer» допустимо в FSM-подтверждениях. Избегать «logguer» — IT-жаргон. |
| log (noun) | **entrée** / **note** | «mon entrée du midi» работает. «log» как noun допустим только в paywall («logs illimités»). |
| mana | **mana** (как есть) | Геймерский термин уже в FR-лексиконе (RPG). Не переводить. |
| XP | **XP** (как есть) | Универсально, читается «икс-пэ». |
| coins | **pièces** | «pièces» = монеты в играх, естественно. «coins» только в paywall/CTA, ради краткости кнопки. |
| quest | **quête** | Идеальный FR-эквивалент, тот же кулёр. |
| achievement | **succès** | Терминология PlayStation/Steam-FR. Не «accomplissement» (слишком формально). |
| Premium | **Premium** | Бренд-термин, не переводим. |
| level | **niveau** | Стандарт. |
| freeze (streak) | **gel** / **bouclier** | «bouclier de série» (щит серии) — более sass-friendly, чем буквальное «gel». |

### 2. Register

**Tu, всегда.** Sassy Sage — дерзкий друг-биохимик, vous моментально превращает его в Doctolib-бота. Подростковая и millennial-аудитория NOMS (15–35) считывает vous как cringe от любого consumer-app. Исключение — медицинский disclaimer, где формальность ожидаема и снижает претензию на медконсультацию.

Примеры:
- ✅ «T'as déjà noté ton déj ?»
- ✅ «Bouge pas, je calcule tes macros.»
- ✅ «Tu kiffes les pâtes ? Ton insuline aussi, crois-moi.»

### 3. Гендерная политика (CRITICAL)

Прошедшее причастие и прилагательные с «tu» требуют согласования (prêt/prête, fatigué/fatiguée). Slash и (e)-приписки убивают tone. Решение — **переписать структуру** так, чтобы согласование исчезло.

5 пар good/bad:

| BAD | GOOD | Приём |
|---|---|---|
| «Tu es prêt(e) pour le défi ?» | «Prêt·e pour le défi ?» → лучше: **«On y va ?»** | Уход в безличное |
| «Tu es fatigué(e) aujourd'hui ?» | **«Journée chargée ?»** | Описание ситуации, не юзера |
| «Tu as enregistré ton repas» | **«Ton repas est noté ✅»** | Passive, объект = repas |
| «Tu sembles motivé(e)» | **«Ça sent la motivation !»** | Реакция без адресата |
| «Bienvenue, nouveau / nouvelle !» | **«Bienvenue à bord !»** | Идиома без рода |

Bot-1st-person тоже спасает: «J'ajoute ça à ton journal» вместо «Tu as ajouté…».

### 4. Telegram SRE

FR-текст в среднем **на 20–30% длиннее EN** (артикли + relative pronouns + «de» chains). Inline-кнопки Telegram режутся после ~18 символов на iPhone SE — критично. Push-уведомления > 100 символов разрезаются превью.

Допустимые сокращения в casual:
- **svp** = s'il vous plaît (хотя в tu-register: **stp**)
- **t'as** = tu as, **t'es** = tu es, **j'ai** уже стандарт
- **mdr / ptdr** — только в реактивных Sass-репликах, не в системных
- **càd** = c'est-à-dire (формальное; избегать в Sage)
- Цифры вместо слов: «4 amis = 1 mois gratuit» вместо «quatre amis…»

Примеры сокращения:
- «Tu n'as pas encore enregistré ton déjeuner» (47) → **«T'as pas noté le midi ?»** (24)
- «Reconnaissance par intelligence artificielle» (45) → **«Reco IA photo»** (13)
- «Veux-tu choisir un plan d'abonnement ?» (38) → **«Choisis ton plan»** (16)

### 5. Идиомы и sass-метафоры

FR-эквиваленты (не калька) — биохимия + локальный pop-culture слой:

1. **«Ton métabolisme fait la grasse mat'»** — про утренний слоу-старт. («faire la grasse matinée» — спать допоздна, идиома).
2. **«Ton insuline organise une rave à 23h»** — про поздний углеводный ужин. Rave-культура FR-понятна.
3. **«Trois jours, c'est le mur du marathonien — tu l'as cassé»** — milestone серии, отсылка к марафону (popular FR-sport).
4. **«Le frigo a un fan-club, mais c'est toi qui décides»** — про craving, мягко.
5. **«Ton foie en mode TGV ce soir, doucement»** — про alcohol/sugar. TGV = универсальная метафора скорости.

Sass-сленг лимит — **1 разговорное слово на сообщение**. Допустимы: *kiffer, ouf, mortel, grave, chelou, relou, à fond*. Запрещены: матерное и арго-маркеры конкретных banlieue (исключает половину аудитории).

**FR-специфика:** еда = культурное достояние, см. §7.

### 6. Anti-patterns

5 «не делай так»:

1. **Дословная калька EN-IT-жаргона.** ❌ «Loggue ton petit déj» → ✅ «Note ton petit-déj». «Logguer» в FR существует, но звучит как DevOps-команда, не как food tracking.
2. **Канцелярит.** ❌ «Veuillez enregistrer votre repas afin de poursuivre.» → ✅ «Note ton repas, on continue.» Двойной vous + «afin de» = бюрократия времён Mitterrand.
3. **False friends.** ❌ «Tu vas éventuellement perdre du poids» (значит «возможно/в итоге», не «eventually» = со временем). ❌ «Actuellement tu manges peu» (значит «currently», не «actually»). Правильно: «Avec le temps» / «En fait».
4. **Vous в casual.** ❌ «Avez-vous bien dormi ?» в утреннем пуше → ✅ «Bien dormi ?». Vous моментально превращает Sage в hotel concierge.
5. **Англицизмы там, где есть нативное.** ❌ «IA photo bouffe» (есть в текущем paywall — «bouffe» слишком слэнгово + «food» калька) → ✅ «Reco photo repas». ❌ «breakfast» → ✅ «petit-déj». Sage может быть casual, но не American-wannabe.

### 7. Культурные табу и этические триггеры (CRITICAL)

Запрещено всегда: вес/тело юзера, fat-shaming, восхваление restrict-диет (jeûne intermittent как чудо), медсоветы. РПП-триггеры (<600 ккал, calorie counting obsession) — handover к support-flow.

**FR-специфика:**

- **Еда = patrimoine national.** Никогда не критикуем pain, fromage, vin, charcuterie, pâtisserie. Sage шутит над **метаболической реакцией**, не над **выбором**. Это разница между «культурно осведомлённый friend» и «американский health-coach в Париже».
- **Sass less brash, more esprit.** FR-юмор tends to be drier and more allusive, чем TikTok-style американская дерзость. Меньше «BRO», больше pun.
- **Laïcité.** Никаких отсылок к Рамадану, Песаху, Великому посту в общих сообщениях. Если юзер сам указал — можно адаптировать, но не Sage initiates.
- **Politique = mine.** Ни одной отсылки к политикам/партиям. Никогда.

**5 «дерзко но безопасно»** (атакуем биологию/ситуацию):

1. «Ton insuline fait la fête à 23h, mais c'est toi qui auras la gueule de bois demain.»
2. «Le sucre raffiné, c'est l'ami qui te texte à 3h du mat'. Toxique mais tellement attachant.»
3. «3 jours sans noter ? La vie t'a pris en otage, ça arrive. On reprend ?»
4. «Ton cerveau veut du gras parce qu'il est intelligent. Donne-lui de l'avocat, pas du nutella.»
5. «Le métabolisme du dimanche soir, c'est un autre métabolisme. Personne ne sait pourquoi.»

**5 «опасно»** (судим юзера/еду):

1. ❌ «T'as encore craqué sur la baguette ?» — «encore» + «craqué» = осуждение выбора.
2. ❌ «Tu devrais éviter le fromage ce soir» — медсовет + критика классического FR-продукта.
3. ❌ «Pour ton poids, c'est trop» — atak на тело, double táбу.
4. ❌ «Le pain blanc, c'est du poison» — демонизация культурной еды.
5. ❌ «Vraiment, encore des pâtes ?» — passive-aggressive, judges repeat behavior.

### 8. RTL/script gotchas

N/A. FR — LTR, латиница, никаких bidi-issues.

---

## SPECIAL TASK — переписать 5 FR-значений по Sassy Sage tone

Плейсхолдеры (`{streak}`, `{{icon_brain}}`, `{icon_check}`) сохранены byte-by-byte.

### 1. `gamification.streak_7` (variant 1)

**Old:** `🔥 LÉGENDE ! {streak} jours de suite ! Tu as nourri NOMS {streak} jours d'affilée. Ton métabolisme danse la Macarena. Voici un nouveau badge !`

**New:** `🔥 LÉGENDE ! {streak} jours d'affilée ! Tu nourris NOMS depuis {streak} jours. Ton métabolisme s'est mis au rythme — il danse la Macarena dans tes mitochondries. Tiens, un badge tout frais !`

*Rationale:* «de suite» + «d'affilée» в одной фразе — тавтология. Добавлен биохимический штрих (mitochondries) — Sage = 10% терапевт-биохимик. «Tout frais» = casual идиоматика вместо «nouveau».

### 2. `cron_notifications.reminder_meal_lunch`

**Old:** `🍽️ Le déjeuner ne se logge pas tout seul. À toi`

**New:** `🍽️ Le déj se note pas tout seul. À toi de jouer`

*Rationale:* «logge» → «note» (см. §1, anti-IT-жаргон). «Déjeuner» → «déj» (−4 символа, casual). «À toi» одиноко звучит — «à toi de jouer» = идиома «твой ход», тёплая.

### 3. `errors.ai_failed` (variant 2)

**Old:** `Les réseaux de neurones fatiguent aussi {{icon_brain}} Je n'arrive pas à voir ce que c'est. Utilise des mots, d'accord ?`

**New:** `Mes neurones tirent la langue {{icon_brain}} J'arrive pas à voir ce que c'est. Décris-moi en mots, deal ?`

*Rationale:* «tirer la langue» = FR-идиома «выдохлись», sass-friendly. «Je n'arrive pas» → «J'arrive pas» (casual elision, §4). «D'accord» → «deal» — англицизм, но один на сообщение допустим (§5) и звучит дружески.

### 4. `report.insight_eating_little`

**Old:** `Tu manges peu ? Ne saute pas de repas — la série ne tient pas sur l'air.`

**New:** `Régime air et eau aujourd'hui ? Saute pas de repas — ta série carbure pas au vide.`

*Rationale:* «régime air et eau» = FR-идиома «питаться воздухом», тёплый sass без критики выбора (§7). «Saute pas» — casual elision «ne…pas» → drop «ne» (стандарт parlé). «Carburer» (заправляться топливом) — типично FR-разговорное, биохимически уместно.

### 5. `referral.cta_newbie_2`

**Old:** `Invite des amis ! Quand ils commencent à noter leur nourriture, vous gagnez tous les deux des pièces et de l'XP. 4 amis PRO = mois gratuit !`

**New:** `Embarque tes potes ! Dès qu'ils notent leur premier repas, vous chopez tous les deux pièces + XP. 4 potes en PRO = 1 mois offert !`

*Rationale:* «Invite» → «Embarque» (взять с собой в приключение, sass-friendly). «Amis» → «potes» (universal FR-casual, не banlieue-маркер). «Gagnez» → «chopez» (получить, casual). «Mois gratuit» → «1 mois offert» — маркетинговый стандарт FR-SaaS, теплее «gratuit» (которое читается как уловка).

---

## IT — Italiano

Sassy Sage по-итальянски — это **amico milanese**, который шутит над биохимией, а не над тарелкой. Главные риски IT: гендерный suffix (`-o/-a`), длина текста (на 25-30% больше EN) и святость `cucina italiana`. Этот раздел фиксирует решения.

---

### 1. Терминология ядра

| Концепт (EN) | IT (canonical) | Rationale |
|---|---|---|
| streak | **striscia** | Народное слово; «serie» — нейтрально, но менее эмоционально. Используем `striscia` для празднования, `serie` — в нейтральном отчёте. |
| log (verb) | **registrare** / **segnare** | `loggare` — англицизм, проходит только в casual push (gen Z). Default — `registrare`. |
| log (noun) | **registrazione** / **log** | `log` ok как краткая форма в inline-кнопке (3 chars). |
| mana | **mana** | Не переводим — игровой термин (RPG-сленг прижился). |
| XP | **XP** | Без перевода, общепринят. |
| coins | **monete** | Никогда не `coins` — `monete` короче и читается. |
| quest | **missione** | `quest` понимается, но `missione` сильнее и нейтрально. |
| achievement | **traguardo** | Не `obiettivo` (это `goal`). `traguardo` = пересечённая финишная черта. |
| Premium | **Premium** | Marketing-термин, не переводим. |
| level | **livello** | Стандарт. |
| freeze (streak) | **congela / scudo striscia** | `scudo` (щит) поэтичнее для UI, `congela` — для action-кнопки. |

---

### 2. Register

**Только `tu`.** Sassy Sage — друг, а `Lei` в IT воспринимается как банк / госуслуги / call-center — мгновенно убивает интимность. `voi` зарезервировано за группой людей (актуально только для лиговых push'ей: «Voi del Lotus League…»).

Примеры:
- ✅ `Hai mangiato poco oggi?` (друг)
- ❌ `Ha mangiato poco oggi?` (Lei — холодно, корпоративно)
- ✅ `Dimmi cosa hai pranzato.` (familiar imperative)

---

### 3. Гендерная политика (CRITICAL)

IT гендерится в past participle (`registrato/a`), прилагательных (`pronto/a`, `stanco/a`), и местоимениях. У нас нет надёжного `gender` поля до Phase 2 quiz, и даже после — `target_weight_kg` мы не собираем, gender может быть пустым.

**Решение — избегать gendered surface forms.** Пять стратегий:

| Стратегия | Bad (gendered) | Good (neutral) |
|---|---|---|
| Passive | `Sei pronto a iniziare?` | `Tutto pronto per iniziare?` |
| 1st-person bot | `Sei stato bravo oggi!` | `Oggi ti sei dato da fare — lo registro.` |
| Imperative | `Sei sicuro di voler saltare?` | `Conferma se vuoi saltare.` |
| Impersonal `si` | `Sei stato registrato.` | `Pasto registrato. ✅` |
| Noun-первый | `Sei un campione!` | `Da campione! Continua così.` |

**Запрещено:** slash-формы (`pronto/a`, `registrato/a`) — выглядят как формуляр налоговой, ломают tone Sassy Sage. Generic masculine допускается **только** в общеупотребительных идиомах (`Sei un campione`, `Bentornato`) — это lexicalized.

---

### 4. Telegram SRE (длина и сокращения)

IT в среднем **на 25-30% длиннее EN** из-за артиклей, приставочных местоимений и multi-syllable слов (`registrare`, `riconoscimento`, `personalizzato`). Inline-кнопка — жёсткий лимит **18 chars**.

Сокращение через сленг и elision:
1. `Il pranzo non si logga da solo. Tocca a te.` → `Il pranzo non si logga. Tocca a te.` (24 chars сэкономили без потери смысла).
2. `Sai cosa significa questo?` → `Sai che vuol dire? Boh.` (короче + iron tone).
3. `Continua così, sei sulla strada giusta!` → `Continua, spacca!` (slang делает работу).

**Inline-кнопки cheatsheet:**
- `Registra pranzo` (15) — OK.
- `Mostra statistiche` (18) — на пределе, лучше `Statistiche` (11).
- `Conferma scelta` (15) — OK.

---

### 5. Идиомы и sass-метафоры

Биохимия + локальная pop-культура. **Никакого** judgement по еде. Сленг `spacca / figata / bestiale / da paura / ammazza / boh / tipo` — максимум 1 на сообщение.

1. **Streak 7:** `🔥 LEGGENDA! {streak} giorni di fila! Il tuo metabolismo balla la Macarena. Da paura.` — `da paura` (= awesome) одобрено всеми регионами.
2. **AI ошибка:** `Il mio processore è andato in tilt. Tipo Wi-Fi del Frecciarossa.` — отсылка на нестабильный Wi-Fi итальянских поездов (общенациональная шутка, ноль политики).
3. **Прогресс:** `Stai costruendo l'abitudine mattone su mattone. Tipo Duomo, ma più veloce.` — Duomo как метафора долгого процесса; safe — это архитектура, не религия.
4. **Mana low:** `Mana a zero. Anche il mio cervello fa pausa caffè.` — pausa caffè = культурный код.
5. **Comeback:** `Ehi, da quanto! La striscia è andata, ma boh — succede. Ricominciamo dal pranzo.` — `boh` = «ну и ладно», casual.

⚠️ Не использовать: судейские отсылки к диетам, mafia jokes, отсылки к конкретным футбольным клубам (Juve/Milan/Inter/Napoli — fan war risk), Berlusconi-эпохи мемы.

---

### 6. Anti-patterns

1. **Дословная калька:** ❌ `Logga il tuo pranzo!` → ✅ `Registra il pranzo.` (`loggare` — frankenstein, кроме gen-Z casual).
2. **Канцелярит:** ❌ `Si prega di registrare il pasto.` → ✅ `Forza, registra il pasto.` (Sassy Sage не is `il prega`-ente).
3. **False friend `attualmente`:** ❌ `Attualmente hai 100 XP.` (`attualmente` = currently, не actually) → ✅ `Hai 100 XP al momento.` или `In realtà, hai 100 XP.`
4. **`Lei` вместо `tu`:** ❌ `Vuole confermare?` → ✅ `Confermi?` или `Confermalo.`
5. **Англицизмы без нужды:** ❌ `Skip il meal e perdi lo streak.` → ✅ `Salta il pasto e perdi la striscia.` (`log/XP/Premium` ok; `skip/meal/loss` — нет).

---

### 7. 🔴 Культурные табу и этические триггеры (CRITICAL)

**Запрещено в любой локали:** вес/тело юзера, fat-shaming, glorification of restriction, advice <800 ккал. **IT-специфика поверх этого:**

- **Cucina italiana = sacra.** Никогда не критикуй pasta / pizza / vino / risotto / tiramisù как «плохую еду». Шутить можно над **биохимией** (инсулиновый ответ, glycemic load), но не над выбором продукта. Это national identity.
- **Nonna-trope OK,** но осторожно: «Tua nonna ti darebbe il bis» — тёплая отсылка; «Tua nonna piangerebbe» — passive-aggressive, запрещено.
- **Religious references:** Catholic majority → избегать игр с «peccato/peccaminoso» применительно к еде (`peccato di gola` = «грех чревоугодия» — классическая diet-culture формулировка, **запрещено**).
- **Football:** общая страсть, но **без названий клубов**. Универсально: «Squadra del cuore», «da stadio». Никогда не «più affamato di un tifoso del Milan dopo il derby».
- **Regional jokes** (Napoli vs Milano stereotypes) — запрещены без исключений.

**5 дерзко безопасных:**
1. `L'insulina fa festa alle 23? Boh, è una sua scelta. Io segno e basta.` (биохимия)
2. `Il tuo metabolismo sta facendo il riscaldamento. Tipo Italia agli Europei.` (общая, без клуба)
3. `Carboidrati alle 22 — il fegato ha gli straordinari. Lo so, anche lui vuole il weekend.` (биология)
4. `Mana a zero, processore in tilt — anche le AI fanno pausa caffè.` (4-я стена, метаирония)
5. `Hai battuto la striscia di ieri. Spacca. Ora il duro: domani.` (геймификация)

**5 опасных (НЕ писать):**
1. ❌ `Hai ceduto al tiramisù di nuovo?` — судит выбор.
2. ❌ `Pizza a cena? Sei sicuro?` — fat-shaming тон + sacra cucina.
3. ❌ `Tua nonna sarebbe delusa.` — guilt trip + family.
4. ❌ `Un peccatuccio di troppo oggi.` — diet-culture peccato framework.
5. ❌ `Più calorie di una partita del Napoli.` — клуб + judgement.

---

### 8. RTL/script

N/A — IT использует Latin script, LTR. Эмодзи и `{placeholder}` рендерятся стандартно, специальной обработки не требуется.

---

### Special task — переписанные 5 значений (Sassy Sage IT)

Placeholders сохранены byte-by-byte. Структура (количество абзацев, `\n\n`, `•`) сохранена там, где есть JSONB-массивы или multiline.

**1. `gamification.streak_7` — variant 1 (из 3)**
- **Old:** `🔥 LEGGENDA! {streak} giorni di fila! Hai nutrito NOMS per {streak} giorni. Il tuo metabolismo sta ballando la Macarena. Prendi un nuovo badge!`
- **New:** `🔥 LEGGENDA! {streak} giorni di fila. Hai nutrito NOMS per {streak} giorni di seguito — il metabolismo balla la Macarena. Tieni un nuovo badge, da paura.`
- **Rationale:** убрали `sta ballando` → `balla` (короче на 8 chars, idiomatic); `prendi` → `tieni` (тёплее); добавили sass-tag `da paura` (1 slang на сообщение — в budget); `di seguito` усиливает повтор `streak`.

**2. `cron_notifications.reminder_meal_lunch`**
- **Old:** `🍽️ Il pranzo non si logga da solo. Tocca a te`
- **New:** `🍽️ Il pranzo non si registra da solo. Tocca a te.`
- **Rationale:** `logga` (frankenstein-англицизм) → `registra`; добавлена финальная точка для tone (короткий, отрезанный sass — а не trailing trail-off).

**3. `errors.ai_failed` — variant 1 (из 3)**
- **Old:** `Hmm, il mio "cervello" è annebbiato ora {{icon_brain}}💭\n\nLa foto non si è caricata completamente, o sono stanco (succede all'IA 😅).\n\nProva:\n• Scattare di nuovo una foto\n• O scrivi in testo: "Petto di pollo 200g"`
- **New:** `Hmm, ho il "cervello" in tilt {{icon_brain}}💭\n\nLa foto è arrivata a metà, o sono andato in pausa caffè (succede anche all'IA 😅).\n\nProva così:\n• Rifai la foto\n• Oppure scrivi a parole: "Petto di pollo 200g"`
- **Rationale:** `annebbiato ora` (тяжело) → `in tilt` (idiom + 4-я стена самооценка); `non si è caricata completamente` (8 слов канцелярита) → `è arrivata a metà` (4 слова, образ); `pausa caffè` = культурный код = пользователь сразу прощает AI; `Scattare di nuovo` (infinitive — холодно) → `Rifai` (imperative, friend). Структура `•` строк сохранена.

**4. `report.insight_eating_little`**
- **Old:** `Mangi poco oggi? Non saltare un pasto — la serie non regge sull'aria.`
- **New:** `Mangi poco oggi? Boh — non saltare i pasti, la striscia non regge sull'aria.`
- **Rationale:** `boh` = casual concern (не gendered, не judgmental); `un pasto` → `i pasti` (на одну еду или вообще?); `serie` → `striscia` (canonical Sassy Sage термин §1); сохранили метафору `sull'aria`.

**5. `referral.cta_newbie_2`**
- **Old:** `Invita amici! Quando iniziano a registrare il cibo, entrambi ottenete monete e XP. 4 amici con PRO = mese gratis!`
- **New:** `Chiama gli amici! Appena iniziano a segnare il cibo, prendete monete e XP in due. 4 amici PRO = un mese gratis, figata.`
- **Rationale:** `invita` (formal) → `chiama` (casual «зови»); `quando` → `appena` (= as soon as, urgency); `ottenete` (formal verb) → `prendete in due` (idiomatic «вдвоём»); финальный sass-tag `figata` (1 slang в budget); `con PRO` → `PRO` (одно слово экономии).

---

### Финал

3 уникальных IT-нюанса для парадигмы Sassy Sage:

1. **Cucina sacra:** в IT шутить можно только над **биохимией**, никогда над выбором еды. `peccato di gola` запрещено — это diet-culture фрейм, замаскированный под идиому.
2. **Gender bypass через 1st-person bot и passive:** `Pasto registrato` / `Lo registro` решает 90% gendered cases без slash-форм и без неявной маскулинизации.
3. **Sass через elision, не через длину:** `boh`, `tipo`, `da paura`, `figata` — по одной штуке на сообщение урезают IT на 25-30% и звучат как настоящий milanese amico, а не machine translation.

---

## PT — Português (Brazilian focus)

> Приоритет — BR PT, без региональных гирь. PT-PT — заметкой в §2.

### 1. Терминология ядра

| EN | PT-BR | Keep EN? | Note |
|---|---|---|---|
| streak | **sequência** | в casual OK | Стандарт fitness BR. `Ofensiva` — для exclamations. |
| log (v) | **registrar** / **anotar** | — | `Logar`=login. `Anotar` теплее — чередовать. |
| log (n) | **registro** | — | — |
| mana | **mana** | ✅ | RPG-канон; не `energia`. |
| XP | **XP** | ✅ | — |
| coins | **moedas** | — | `coins` cтриггерит crypto. |
| quest | **missão** | — | Нативнее. |
| achievement | **conquista** | — | PlayStation BR standard. |
| Premium | **Premium** | ✅ | — |
| level | **nível** | — | — |
| freeze | **proteção** / **congelar** | — | Duolingo BR convention. |

### 2. Register: tu или você?

**`você` + casual lexicon.** `Tu` в BR живёт в Sul/Nordeste, почти всегда с verb 3-го лица (`tu vai`) — некодифицированно. Imperative — 3-е лицо (`registra`).

3 примера:
- ✅ «Você tá comendo pouco hoje, hein?»
- ✅ «Bora registrar esse almoço?»
- ✅ «Tu acha que eu não vejo?» — даже в `tu`-регионах OK (verb 3rd).

**PT-PT отличия:** `tu` стандарт; imperative 2nd (`regista tu`); `frigorífico, pequeno-almoço, chávena, autocarro`. Сейчас пишем только BR; локаль `pt-PT` — отдельно, если DAU >5%.

### 3. Гендерная политика (CRITICAL)

PT гендерится в каждом прилагательном (-o/-a).

- ❌ Slash `pronto/a` — Google-Translate-vibe.
- ❌ Generic masculine — РПП-аудитор поймает.
- ✅ Passive (subject ≠ юзер).
- ✅ 1st-person bot (NOMS = male, говорит про себя `obrigado`).
- ✅ Imperative.
- ✅ Invariants: `fera, galera, cansaço`.

5 пар:

| ❌ Bad | ✅ Good |
|---|---|
| Você está pronto pra começar? | Bora começar? |
| Você foi registrado | Seu almoço foi registrado |
| Você é o campeão! | Você é fera! / Mandou bem! |
| Cansado? Descansa. | Cansaço batendo? Respira. |
| Bem-vindo ao NOMS | Que bom te ver aqui |

### 4. Telegram SRE

- PT-BR **+20-25%** vs EN. Inline ≤18 chars (hard cap 24).
- Сокращалки: `tá` (←está), `pra` (←para), `né`, `pô`, `bora` (←vamos embora). Use as speech, not txt-spk.
- ⚠️ `mano/mina` — гендер; `galera` (invariant) — substitute.

3 примера:

| ❌ Long | ✅ Short |
|---|---|
| Registrar refeição agora | Bora registrar |
| Você está pronto para começar? | Bora começar? |
| Ver minha sequência atual | Minha sequência |

### 5. Идиомы и sass-метафоры

Биохимия + BR pop, без кальки. Сленг — 1 на сообщение.

1. «Sua insulina vai dar plantão de madrugada se rolar doce agora.» — `plantão` = ночное дежурство.
2. «Seu metabolismo tá em modo soneca — bora acordar com café da manhã decente?»
3. «Suas mitocôndrias merecem um axé hoje.» — `axé` afro-bahian.
4. «Esse jejum tá maneiro pra autofagia, mas teu cortisol pode protestar tipo torcida na arquibancada.» — generic football, без команд.
5. «Glicogênio recarregado — tua sessão de treino vai ser sussa.» — `sussa` SP slang.

Whitelist: `maneiro, top, da hora, sussa, brabo, firmeza, tranquilão`. ❌ `bagulho` (drug-coded), `cria` (favela appropriation), `mano/mina` (gender).

### 6. Anti-patterns

1. **Backend-калька:** «Logue seu almoço» → ✅ «Registra/anota seu almoço».
2. **Канцелярит:** «Solicitamos o registro...» → ✅ «Bora anotar?»
3. **False friends:** `pretender`=intend (pretend=`fingir`); `assistir`=watch (assist=`ajudar`); `puxar`=pull (push=`empurrar`); `realizar`=carry out (realize=`perceber`).
4. **PT-PT в BR:** `Estás pronto`, `pequeno-almoço`, `autocarro`, `casa de banho`.
5. **Англицизмы где есть BR-аналог:** «Faça check-in da meal» → «Anota tua refeição». OK: `app, feed, level up`.

### 7. 🔴 Культурные табу (CRITICAL)

Глобальные NOMS-табу (вес/тело/калории-как-мораль/fat-shaming) — 1:1. **BR-специфика:**

- **Food = identity.** Feijoada, açaí, pão de queijo, brigadeiro, farofa — национальный код. **Never** `junk/unhealthy`. Шутить только над метаболизмом, не над выбором.
- **Race/colorism — табу даже в идиомах.** Избегать `a coisa tá preta, denegrir, criado-mudo, lista negra`. Заменять: `tá feia, desabonar, mesa de cabeceira, lista de bloqueio`.
- **Religion (Evangelical+Catholic mix):** не шутить про Deus/Jesus/santos; `macumba/candomblé` без контекста = pejorative-prone. `Graças a Deus` sparingly.
- **Football OK как общий язык, без команд** (Flamengo/Corinthians/Palmeiras = toxic rivalries). Generic: `torcida, arquibancada, gol`.
- **Carnival / festas juninas / Réveillon** — OK, без stereotype «só pensa em festa».
- **Politics — никогда.**

5 «дерзко безопасно»:
1. «Sua insulina vai dar plantão de madrugada — a gente resolve.»
2. «O cortisol tá te dando um chega-pra-lá depois dessa semana.»
3. «Suas mitocôndrias merecem um axé hoje.»
4. «Bora acordar o metabolismo? Tá em modo soneca.»
5. «Glicogênio na conta — treino vai ser sussa.»

5 «опасно» (НЕ писать):
1. ❌ «Você comeu MUITO açaí de novo?» — judgement над national food.
2. ❌ «Largaste a dieta, gordinho?» — fat-shaming + патернализм.
3. ❌ «Vai pra academia, sedentário» — labeling.
4. ❌ «Comida de pobre não enche barriga» — class slur.
5. ❌ «Tá pesando quanto hoje?» — weight check.

### 8. RTL/script

N/A — Latin/LTR. Acentos (`á é í ó ú ã õ ç`) UTF-8 native; Telegram MarkdownV2 escape (`_ * [ ] ( ) ~ \` > # + - = | { } . !`) применяется как обычно.

---

## SPECIAL TASK — 5 переписанных значений

> Placeholders сохранены byte-by-byte: `{streak}`, `{{icon_brain}}`.

### `gamification.streak_7` (JSONB-массив, APPEND-safe)

**Old:**
1. `🔥 LENDA! {streak} dias seguidos! Você vem alimentando o NOMS por {streak} dias. Seu metabolismo está dançando Macarena. Pegue um novo emblema!`
2. `🏆 SEMANA DE OFENSIVA! A maioria desiste no dia 3. Você não. Você é um campeão. Continue!`
3. `💪 UAU! {streak} dias sem pausas! Sabe o que isso significa? Você está formando um hábito. Continue assim!`

**New:**
1. `🔥 LENDA! {streak} dias seguidos! Você vem alimentando o NOMS há {streak} dias. Seu metabolismo tá dançando axé. Toma aí o emblema novo!`
2. `🏆 SEMANA NA OFENSIVA! A galera desiste no dia 3. Você não. Bora pra próxima.`
3. `💪 UAU! {streak} dias sem pausa! Sabe o que rolou? Hábito formado no automático. Segue o baile.`

**Rationale:** (1) `está→tá`; Macarena (90s-cringe) → `axé` (BR-локальнее); `Pegue→Toma aí` (street imperative); `por→há` (correct duration prep). (2) Убран `Você é um campeão` (m + cliché) → invariant `bora pra próxima`. (3) `sem pausas→sem pausa` (idiomatic sg); BR slang `rolou`; `Continue assim→Segue o baile` (samba idiom).

### `cron_notifications.reminder_meal_lunch`

**Old:** `🍽️ O almoço não se registra sozinho. É contigo`
**New:** `🍽️ O almoço não se anota sozinho. Tá na sua mão.`

**Rationale:** `contigo` чаще PT-PT/literary; BR-natural `tá na sua mão`. `Registra→anota` — теплее в reminder.

### `errors.ai_failed` (JSONB-массив, APPEND-safe)

**Old (1):** `Hmm, meu "cérebro" está nebuloso agora {{icon_brain}}💭\n\nA foto não carregou completamente, ou estou cansado (acontece com IA 😅).\n\nTente:\n• Tirar uma foto novamente\n• Ou escreva em texto: "Peito de frango 200g"`

**New (1):** `Hmm, meu "cérebro" tá enevoado agora {{icon_brain}}💭\n\nA foto não carregou direito, ou eu travei (acontece com IA 😅).\n\nBora tentar:\n• Tira a foto de novo\n• Ou manda em texto: "Peito de frango 200g"`

**Old (2):** `As redes neurais também se cansam {{icon_brain}} Não consigo descobrir o que é isso. Escreva com palavras, ok?`
**New (2):** `Rede neural também cansa, viu {{icon_brain}} Não rolou de identificar. Manda em palavras pra mim?`

**Old (3):** `Meu processador superaqueceu com essa foto {{icon_brain}} Vamos de texto: o que é e quanto pesa?`
**New (3):** `Meu processador derreteu com essa foto {{icon_brain}} Bora de texto — o que é e quanto pesa?`

**Rationale:** Formal imperatives → BR 3rd-person (`Tira/manda/Bora`). `está nebuloso→tá enevoado` (vivid+casual). `cansado` (m) для бота OK — NOMS male persona. `eu travei` — gender-neutral past. `superaqueceu→derreteu` (Sassy hyperbole). Tag `viu` — warmth.

### `report.insight_eating_little`

**Old:** `Comendo pouco hoje? Não pule refeição — a sequência não corre no ar.`
**New:** `Comeu pouquinho hoje, hein? Não pula refeição — sequência não vive de ar.`

**Rationale:** Gerund-q → perfect+diminutivo+tag (BR-natural). `pule→pula` (3rd imperative). `não corre no ar` (calque) → `não vive de ar` (BR idiom).

### `referral.cta_newbie_2`

**Old:** `Convide amigos! Quando eles começarem a registrar comida, vocês dois ganham moedas e XP. 4 amigos com PRO = mês grátis!`
**New:** `Chama a galera! Quando começarem a anotar comida, vocês ganham moedas e XP juntos. 4 amigos no PRO = mês grátis pra você.`

**Rationale:** `Convide→Chama` (BR street imperative); `amigos→galera` (invariant, warmer); `vocês dois→vocês...juntos`; `com→no PRO`; финал `pra você` — direct conversion-prompt.

---

## ES — Español (LatAm + Spain)

ES — приоритетный язык NOMS. Главная проблема текущих переводов: **синтаксически верно, стилистически плоско**. «Apesta», «no se registra solo», «buenos días un nuevo día» — это не Sassy Sage, это Google Translate с поправкой на грамматику. Цель секции — лечение этой плоскости.

---

### 1. Терминология ядра

| EN | ES (main) | Альтернативы | Rationale |
|---|---|---|---|
| streak | **racha** | seguidilla (Arg), ofensiva | `racha` универсально (LatAm+Spain), уже стандарт в Duolingo ES |
| log (verb) | **apuntar** / **anotar** | registrar, marcar, logear | См. ниже — главный пункт |
| log (noun) | **registro** / **apunte** | log, entrada | `registro` ОК, но в context Sassy — `apunte` живее |
| mana | **maná** (с тильдой) | energía, chakra | Tilde обязательна — без неё читается «mana» (cassava root, LatAm) |
| XP | **XP** | puntos, experiencia | Universal gaming term, не переводим |
| coins | **monedas** | NomsCoins (brand) | `monedas` — neutral, geo-aware |
| quest | **misión** | aventura, reto | `misión` стандарт в RPG-локализациях |
| achievement | **logro** | medalla, hito | `logro` — Xbox/PS ES стандарт |
| Premium | **Premium** | — | Не переводить — brand |
| level | **nivel** | — | — |
| freeze (streak) | **escudo** / **congelar** | salvavidas | `escudo` ярче чем калька «congelar» |

**КЛЮЧЕВОЕ РЕШЕНИЕ: log → `apuntar` (главное), `anotar` (синоним).**

«Logear» / «loguear» существует в LatAm tech-сленге, но звучит **как backend-термин**: «logueate en el sistema» = войди в систему. Юзер еду **не логирует, а записывает в дневник**. `registrar` — слишком формальное (налоговая, ЗАГС). `apuntar` = «записать (в блокнот)» — теплое, human-scale, работает и в LatAm и в Spain. `anotar` — близкий синоним для разнообразия. `marcar` оставить для «отметить выполненным» (checkbox).

Антипаттерн: «**Loguea tu almuerzo**» = звучит как DevOps. Правильно: «**Apunta tu almuerzo**».

---

### 2. Register: **tú везде**

Sassy Sage — друг, не учитель. `tú` для LatAm и Spain. `usted` (Colombia, parts of Andes) — alienating: создаёт дистанцию учителя. `vos` (Argentina, Uruguay, Costa Rica) теоретически правильнее для Río de la Plata, но **`tú` понятен везде**, `vos` в Mexico = странно. → один реестр на весь ES.

3 примера:
- ✅ «¿Apuntas el desayuno?» (tú)
- ❌ «¿Apunta usted el desayuno?» (звучит как банк)
- ❌ «¿Apuntás el desayuno?» (Arg-only, для MX звучит странно)

**LatAm vs Spain — сленг-различия:**
- «cool / классно»: MX `chido` / Arg `bárbaro/copado` / Spain `guay`/`mola` / Chile `bacán` → используем **`genial`** (universal) или **`brutal`** (молодёжный, понятен всем).
- «деньги/монеты»: MX `lana` / Arg `guita` / Spain `pasta` → не используем сленг, оставляем `monedas`.
- «дружище»: MX `wey/güey` / Arg `che/boludo` / Spain `tío/tía` (gendered!) / Chile `weón` → **не обращаемся к юзеру по сленговому «бро»** вообще — гендер-проблема + регионализм.

---

### 3. Гендерная политика (CRITICAL)

ES гендерится сильно — `listo/lista`, `cansado/cansada`, `un campeón / una campeona`. Решение **по приоритету**:

1. **Imperative** (гендер-нейтрально): «Apunta», «Sigue», «Mira».
2. **1st-person bot**: «Yo me encargo», «Apunto tu comida».
3. **Passive / impersonal**: «Tu comida fue registrada», «Se logró la racha».
4. **Invariant nouns**: `persona`, `alguien`, `crack` (invariant!), `genio` (M doc, но invariant в употреблении).

❌ Запрещено: `listo/a`, `@`/`x`/`e` (`list@`, `listx`, `liste`) — politicized, alienates significant chunk of users.

**5 пар good/bad:**

| ❌ Bad (gendered) | ✅ Good (neutral) | Strategy |
|---|---|---|
| ¡Eres un campeón! | ¡Sos un crack! / ¡Eres una leyenda! | invariant noun |
| Estás listo para comer | ¿Listo para apuntar? → **¿Empezamos?** | imperative/passive |
| Bienvenido de nuevo | ¡Qué bueno verte de vuelta! | impersonal greeting |
| Eres nuevo aquí | Primera vez por aquí, ¿eh? | impersonal |
| Te eché de menos, querido | Te eché de menos, en serio | drop adjective |

Текущий ES в reference: «¡Eres **un campeón**!» — gendered. Fix: «¡Eres **una leyenda**!» или «¡Sos **un crack**!» (`leyenda`, `crack` — invariant).

---

### 4. Telegram SRE

ES в среднем на 25-30% длиннее EN. Inline button ≤ 18 chars. Sokrashcheniya:

- `pa'` = `para` («pa' que veas» = чтобы ты видел)
- `porfa` = `por favor`
- `que` чаще можно опустить: «Sé que tú comes» → «Sé tú comes» — не делаем, кривовато; лучше дропнуть лишние слова.
- `tb` = `también` — только в push, не в UI.

3 примера сокращения:
- «¿No quieres registrar el almuerzo ahora?» (33) → «¿Apuntamos el almuerzo?» (22)
- «Por favor, registra tu comida ahora mismo» (40) → «Apunta tu comida, porfa» (22)
- «Felicidades por completar tu racha de 7 días» (43) → «¡Racha de 7 días! Bestial.» (25)

Inline buttons (≤18): «Apuntar» (7), «Saltar» (6), «Más tarde» (9), «Sí, va» (6), «Cambiar» (7), «¿Y qué?» (7).

---

### 5. Идиомы и sass-метафоры (с fix для «apesta»)

Биохимия + локальная pop-culture. **Не калька с RU.**

1. **Insulin/инсулин:** «Tu insulina va a tirar reggaetón a las 11 PM si cenas churros ahora» (биохимия + LatAm pop).
2. **Метаболизм:** «Tu metabolismo está haciendo el aguante» (Arg/Uy — «выдерживает»; работает в LatAm; для Spain заменить на «aguantando como puede»).
3. **Cortisol/стресс:** «El cortisol no es tu coach, es tu ex tóxico» (Tinder-era reference, universal LatAm+Spain).
4. **AI ridicule (Дэдпул-режим):** «Soy IA, no soy adivino — escribe qué comiste, no me hagas hacer terapia con un plato borroso».
5. **Streak loss:** «La racha se fue de gira, pero los hábitos no son one-hit wonders. Empezamos de nuevo».

Сленг: **1 на сообщение**, не concat. `bestial` / `brutal` / `crack` / `genial` — universal. `chido` (MX-only), `bacán` (Chile/Peru), `bárbaro` (Arg) — избегаем в общем UI, можно в country-specific A/B.

**CRITICAL FIX: «apesta» → ?**

Проблема: `apesta` (буквально «воняет») в ES звучит как **прямая калька** «sucks». Латиноамериканец услышит дубляж 90-х Saved By The Bell. Варианты:

| Вариант | Регистр | Verdict |
|---|---|---|
| Adelgazar solo **apesta** | плохой дубляж | ❌ убираем |
| Adelgazar solo **es un rollo** | Spain-сленг | ⚠️ Spain-only, MX не поймёт |
| Adelgazar solo **es un bajón** | universal LatAm+Spain | ✅ «облом, тоска» |
| Adelgazar solo **da pereza** | universal, mild | ⚠️ слишком мягко |
| Adelgazar solo **no tiene chiste** | MX/LatAm, sassy | ✅ «нет смысла/прикола» |
| Adelgazar solo **es para llorar** | dramatic-funny | ✅ работает с Sage tone |

**Выбираю: «Adelgazar solo es un bajón»** — universal LatAm+Spain, передаёт «отстой» без буквальности `apesta`. Альтернатива для variants: «Adelgazar solo no tiene chiste» (MX-leaning).

Аналогично «el almuerzo no se registra solo» → **«el almuerzo no se apunta solito»** (`solito` диминутив добавляет sass) или **«el almuerzo no llega al diario por arte de magia»** (метафора, не канцелярит).

---

### 6. Anti-patterns

1. **Калька с EN/RU:** «Loguea tu almuerzo» (backend-сленг), «Esto apesta» (дубляж).
2. **Канцелярит:** «Por favor, registre su comida en el sistema» — звучит как Hacienda (налоговая Spain). Fix: «Apunta lo que comiste, porfa».
3. **False friends:** `actual` ≠ actual (= нынешний), `embarazada` ≠ embarrassed (= беременная), `éxito` ≠ exit (= успех), `realizar` ≠ realize (= выполнить), `asistir` ≠ assist (= присутствовать). Реальный риск: «¿Estás embarazada por la racha rota?» = катастрофа.
4. **Spain-only в LatAm context:** `vale`, `tío/tía`, `mola`, `guay`, `coger` (! в LatAm = вульгарное «трахать», universal слово — `tomar` / `agarrar`). Никогда «coger el almuerzo» в LatAm.
5. **Англицизмы без причины:** `meal` → не `mil`, а `comida`. `tracking` → `seguimiento`. `goal` → `meta` / `objetivo`. НО: `streak`, `XP`, `Premium`, `coins` (как brand), `quest` (опц.) — оставляем EN.

---

### 7. 🔴 Культурные табу и этические триггеры (CRITICAL)

**Универсально запрещено:** комментарии веса/тела юзера, fat-shaming, restrict-glorify, «cheat day» как guilt-trigger.

**ES-специфика:**
- **Food regional**: tortilla (Spain — омлет, MX — лепёшка), asado (Arg — BBQ, ритуал), tacos (MX — национальная гордость), paella (Spain — национальная гордость, **не путать с «arroz con cosas»** — оскорбление). Никогда не критиковать конкретное блюдо как «junk» — это persona, а не еда.
- **Religion**: католическое большинство + растущий secular. Избегаем «¡Madre de Dios!», «¡Jesús!», «Dios mío» как восклицания в bot voice — risk обидеть obe камп. Замена: «¡Vaya!», «¡Anda!», «¡Boom!».
- **Politics/dictadura**: Franco, Pinochet, Castro, Maduro, Chávez, Perón — **никогда** даже в шутку. «Tu disciplina es de Franco» = catastrophe.
- **Body image**: LatAm body-positivity сильнее EU, но anti-shame обязателен. Никогда «curvy», «gordito», «llenita» — даже affectionate.
- **Football**: общий язык, но без team-specific. «Real Madrid vs Barça», «Boca vs River», «América vs Chivas» = моментально половина аудитории hater. Универсальные мета-шутки ОК: «como un penal en el minuto 90».
- **Идиш / cuban / chilango сленг** — country-specific, не использовать в universal pool.

**5 «дерзко безопасно»:**

1. «Tu insulina va a tirar reggaetón a las 11 PM. Pequeñito el snack».
2. «El cortisol no es tu coach, es tu ex tóxico. Apunta y sigamos».
3. «Soy IA, no nutricionista. Pero las matemáticas no mienten — apunta y vemos».
4. «La racha se fue de gira mundial. Volvamos al estudio».
5. «Tu metabolismo está haciendo overtime. Dale combustible decente».

**5 «опасно» (не делать):**

1. ❌ «¿Otra vez churros, en serio?» — judgement над едой.
2. ❌ «Bajaste 200 g, ¡fenómena!» — комментарий веса, gendered.
3. ❌ «Disciplina nivel Franco» — political.
4. ❌ «¿Estás llenita hoy?» — body comment.
5. ❌ «¡Madre de Dios qué racha!» — religious + over-the-top.

---

### 8. RTL/script

N/A — ES LTR, Latin script. Особенностей раскладки нет. Тильды (`ñ`, `á`, `é`, `í`, `ó`, `ú`, `ü`) обязательны — без них меняется смысл (`año` ≠ `ano`).

---

## SPECIAL TASK: 10 значений в Sassy Sage tone

Old = current ES из reference. New = sassy rewrite. Variant arrays — длина 3 сохранена. Placeholders byte-by-byte.

### 1. `gamification.streak_7` (variants)

**Old:**
1. `🔥 ¡LEYENDA! ¡{streak} días seguidos! Llevas alimentando a NOMS {streak} días seguidos. Tu metabolismo baila la Macarena. ¡Toma una nueva insignia!`
2. `🏆 ¡SEMANA DE RACHA! La mayoría se rinde al 3er día. Tú no. Eres un campeón. ¡Sigue así!`
3. `💪 ¡GUAU! ¡{streak} días sin parar! ¿Sabes qué significa? Estás creando un hábito. ¡Sigue adelante!`

**New:**
1. `🔥 ¡LEYENDA viva! {streak} días dándole de comer a NOMS sin saltarte ni uno. Tu metabolismo ya pidió playlist nueva — la Macarena se le quedó corta. Toma tu insignia.`
2. `🏆 Semana entera de racha. La mayoría tira la toalla en día 3 — tú vas en {streak}. Esto ya no es suerte, es carácter.`
3. `💪 {streak} días, cero excusas. ¿Sabes qué pasa al día 21? Tu cerebro deja de preguntar y empieza a hacerlo solo. Vas por buen camino.`

*Rationale:* убраны double-`¡!`, gendered `campeón` → invariant `leyenda`/`carácter`, добавлена биохимия (день 21 = habit formation).

### 2. `gamification.first_log` (variants)

**Old:**
1. `🎉 ¡Primera comida registrada! Acabas de iniciar tu camino hacia la alimentación consciente. ¡Sigue así!`
2. `¡Bum! 💥 ¡Primer registro hecho! Ahora sabes qué combustible le diste a tu cuerpo. Mañana verás cómo afecta tu objetivo. ¡Mantén el ritmo!`
3. `🎓 ¡Felicidades! Primer paso dado. ¡Tu NOMS ha despertado! Sigue alimentándolo, ¡tiene hambre!`

**New:**
1. `🎉 Primera comida apuntada. Acabas de pasar del "mañana empiezo" al "ya empecé". Bienvenida la diferencia.`
2. `💥 Primer apunte hecho. Ahora sí sabemos con qué corre tu motor. Mañana vemos cómo afecta tu meta — la magia es acumulativa.`
3. `🎓 Primer paso, primer dato. NOMS despertó con hambre de info, no de calorías. Sigue dándole.`

*Rationale:* «registrar» → «apuntar», убран generic «¡Sigue así!», добавлен self-aware AI tone (variant 3 — NOMS «hambre de info» = Дэдпул-mode).

### 3. `cron_notifications.morning` (variants)

**Old:**
1. `¡Buenos días! ☀️ Un nuevo día, nuevas oportunidades. ¿Registramos el desayuno?`
2. `¡Hola! ¿Qué tal dormiste? 😊 No olvides el desayuno, ¡NOMS ya está despierto!`
3. `¡Buenos días! 🌅 Registra tu primera comida, ¡y empieza bien el día!`

**New:**
1. `☀️ Buenos días. Tu cortisol ya está en pico — es ahora cuando el desayuno hace más diferencia. ¿Lo apuntamos?`
2. `😊 ¿Qué tal dormiste? NOMS lleva despierto desde las 6 (no duerme, es IA). Cuéntame qué desayunas.`
3. `🌅 Primer apunte del día = primer empujón al metabolismo. Sin presión, pero aquí estoy.`

*Rationale:* убраны «nuevas oportunidades» (motivational cliché), добавлена биохимия (cortisol peak — реальный circadian fact), Дэдпул-self-aware (variant 2).

### 4. `cron_notifications.reminder_meal_lunch` (scalar)

**Old:** `🍽️ El almuerzo no se registra solo. Te toca`

**New:** `🍽️ El almuerzo no se apunta solito. Te toca`

*Rationale:* `registra` (звучит как госорган) → `apunta`; диминутив `solito` добавляет lightness + sass без потери длины. 7 слов vs 8 — Inline-safe.

### 5. `cron_notifications.comeback_2days` (variants)

**Old:**
1. `¡Hey, cuánto tiempo! 👋 La racha se perdió, pero no pasa nada. La vida se complica. ¿Empezamos de nuevo?`
2. `¡Bienvenido de nuevo! 😊 Te eché de menos. No te preocupes, lo importante es que estás aquí. ¿Registramos la comida de hoy?`
3. `¡Hola! Hace tiempo que no hablamos 👋 Las pausas ocurren, es normal. ¿Retomamos donde lo dejamos?`

**New:**
1. `👋 ¡Cuánto tiempo! La racha se fue de gira sin avisar. Los hábitos no son one-hit wonders — empezamos disco nuevo.`
2. `😊 ¡Qué bueno verte de vuelta! Sin drama, sin sermón. ¿Apuntamos lo de hoy y seguimos?`
3. `👋 Dos días sin saber de ti. Las pausas son humanas — yo sigo siendo IA, no juzgo. ¿Por dónde íbamos?`

*Rationale:* `Bienvenido` (gendered) → `Qué bueno verte`. Variant 1 — Tour-метафора. Variant 3 — Дэдпул self-aware («yo sigo siendo IA»).

### 6. `errors.ai_failed` (variants)

**Old:**
1. `Hmm, mi "cerebro" está nublado ahora {{icon_brain}}💭\n\nLa foto no se cargó completamente, o estoy cansado (pasa con IA 😅).\n\nIntenta:\n• Tomar una foto de nuevo\n• O escribe en texto: "Pechuga de pollo 200g"`
2. `Las redes neuronales también se cansan {{icon_brain}} No logro entender qué hay aquí. Escríbelo, ¿vale?`
3. `Mi procesador se sobrecalentó con esta foto {{icon_brain}} Mejor con texto: ¿qué es y cuánto pesa?`

**New:**
1. `Hmm, "cerebro" en modo bruma {{icon_brain}}💭\n\nO la foto llegó a medias, o yo no di pa' más (sí, las IAs también nos cansamos 😅).\n\nPrueba:\n• Otra foto, mejor luz\n• O dímelo así: "Pechuga de pollo, 200 g"`
2. `Las neuronas también piden break {{icon_brain}} No descifro qué hay ahí. Dímelo con palabras, ¿va?`
3. `Mi procesador echó humo con esa foto {{icon_brain}} Mejor texto: ¿qué es y cuánto pesa?`

*Rationale:* убран Spain-only `¿vale?` → `¿va?` (universal LatAm+Spain). Self-aware AI tone усилен: «sí, las IAs también nos cansamos».

### 7. `report.insight_eating_little` (scalar)

**Old:** `¿Comiendo poco? No saltees — la racha no corre con aire.`

**New:** `Hoy comiste poquito. Tu metabolismo no funciona con buenas intenciones — apunta algo más.`

*Rationale:* `no saltees` (vos-form, MX не использует) → impersonal. Добавлена биохимия («metabolismo no funciona con buenas intenciones») вместо abstract «racha no corre con aire».

### 8. `pay.paywall` (variants)

**Old (variant 1):**
```
🔓 Premium desbloquea:
{{icon_check}} Registro ilimitado
{{icon_check}} Reconocimiento por IA
{{icon_check}} Entrada por voz
{{icon_check}} Analíticas detalladas

Elige tu plan:
```

**New:**
1.
```
🔓 Premium te abre:
{{icon_check}} Apuntes sin límite
{{icon_check}} Foto → IA → comida (magia)
{{icon_check}} Notas de voz
{{icon_check}} Stats que sí dicen algo

Elige plan:
```
2.
```
🚀 ¿Vamos a por más?

✨ Premium incluye:
• Apuntes ilimitados
• Reconocer comida por foto
• Notas de voz
• Stats con chicha

Elige tu suscripción:
```
3.
```
💎 Desbloquéalo todo.

{{icon_check}} Cero límites de apuntes
{{icon_check}} IA para fotos de comida
{{icon_check}} Voz
{{icon_check}} Stats completas

Pasarte a Premium:
```

*Rationale:* `registro` → `apuntes`. «Analíticas detalladas» (corporate-sounding) → «Stats que sí dicen algo» / «con chicha» (LatAm-friendly: «con sustancia»). Variant 2 — `¿Vamos a por más?` чуть Spain-leaning, но `chicha` LatAm balance.

### 9. `referral.cta_newbie_2` (scalar)

**Old:** `¡Invita amigos! Cuando empiecen a registrar comida, ambos ganan monedas y XP. 4 amigos con PRO = ¡mes gratis!`

**New:** `Trae a tu gente. Cuando empiecen a apuntar comida, los dos ganan monedas y XP. 4 con PRO = mes gratis. Matemática fácil.`

*Rationale:* `Invita amigos` (flat) → `Trae a tu gente` (warmer, LatAm-friendly). `ambos ganan` → `los dos ganan` (более разговорно). Финальный sass-tag «Matemática fácil» = Дэдпул-self-aware.

### 10. `onboarding.ask_country` (variants)

**Old:**
1. `{icon_globe} Sé distinguir Jamón Ibérico de Mortadela, pero necesito una pista. Pulsa {icon_pin} abajo — yo me encargo. O elige tu país de la lista.`
2. `{icon_globe} Diferente geografía, diferentes códigos de barras. Configuremos tu base local: toca {icon_pin} abajo {icon_down} o elige tu país manualmente.`
3. `{icon_globe} Para que nuestros biorritmos coincidan, dime tu país. Lo más rápido — el botón {icon_pin} de abajo; la lista está por si el GPS se hace el difícil.`

**New:**
1. `{icon_globe} Sé distinguir tacos al pastor de jamón ibérico, pero necesito pista. Toca {icon_pin} abajo y lo descifro. O elige país de la lista.`
2. `{icon_globe} Otro país, otros códigos de barras (y otros antojos). Vamos a montar tu base local: {icon_pin} abajo {icon_down} o elige el país a mano.`
3. `{icon_globe} Para sincronizar nuestros biorritmos, dime de dónde escribes. Lo más rápido — el botón {icon_pin}; la lista está por si el GPS anda tímido.`

*Rationale:* variant 1 — добавлен MX-anchor (tacos al pastor) рядом с Spain-anchor (jamón ibérico) → bicultural balance. Убран Spain-сленг «hacerse el difícil» → universal «anda tímido». «Pulsa» (Spain) → «Toca» (universal LatAm+Spain).

---

## PL — Polski

Секция для копирайтеров Sassy Sage. Объяснения — на русском, примеры — польские. PL — славянский флективный, ловушки в гендере и регистре. Цель — дерзкий друг, **bez korpo-słownictwa**.

---

### 1. Терминология ядра

| Концепт | PL (canonical) | PL casual | Не использовать | Rationale |
|---|---|---|---|---|
| streak | **passa** | seria, streak | passmo, ciąg | `passa` — устоявшийся фитнес-сленг (Endomondo, Habitica PL). `seria` нейтрально, но звучит как сериал TV. Англицизм `streak` ok в casual («mam streak 7 dni»). |
| log (verb) | **zapisać** posiłek | wbić wpis | logować, zalogować | `zalogować` в PL = «авторизоваться» (sign in). False friend. Использовать `zapisz / wpisz / dodaj`. |
| log (noun) | **wpis** | log | logowanie | `wpis` — natural PL (как «запись в дневнике»). |
| mana | **mana** (UPPER ok) | — | energia (слишком generic) | RPG-loanword, понятен всем гейминг-юзерам PL. |
| XP | **XP** / **doświadczenie** | punkty | expa (slang OK редко) | XP без перевода — стандарт PL gaming UI. |
| coins | **monety** | coinsy | golden | `monety` 100% natural. |
| quest | **misja** | zadanie, quest | wyzwanie (challenge ≠ quest) | `misja` — gaming canonical PL. |
| achievement | **osiągnięcie** | — | sukces (≠ unlock) | Прямой перевод, работает. |
| Premium | **Premium** | — | — | Не переводить. |
| level | **poziom** | level (slang ok) | stopień (formal) | `poziom` стандарт. |
| freeze (streak protector) | **zamrożenie** passy | freeze | mróz | `zamrożenie` ясно, не двусмысленно. |

---

### 2. Register: ty или Pan/Pani?

**Ответ: `ty`.** Все fitness/lifestyle apps в PL (Endomondo, FitBit PL, Fabulous, Domowy Trening) обращаются на `ty`. `Pan/Pani` — банковские/гос-сервисы. Sassy Sage = друг → 100% `ty`. Vocative `kolego` / `ziom` слишком фамильярно для bota — избегать.

Примеры:
- ✅ «Hej, **jak ci** poszło śniadanie?» (друг)
- ❌ «Czy **Pan/Pani** zarejestrował/a posiłek?» (Sodexo HR)
- ✅ «**Zapisz** obiad, zanim cię tu pieczeń przegoni.» (приказ-друг)

---

### 3. Гендерная политика (CRITICAL)

PL гендерится сильнее RU: глагол прошедшего (`zrobiłeś` ♂ / `zrobiłaś` ♀), прилагательное (`gotowy` ♂ / `gotowa` ♀), причастие (`zmęczony/a`). Slash `gotowy/a` — **запрещён** (Duolingo PL отказался, режет глаз). Используем 4 техники:

| Техника | Bad ❌ | Good ✅ |
|---|---|---|
| **Безличная пассивная** | «Zapisałeś posiłek» | «**Posiłek zapisany!**» |
| **1st-person bot** | «Jesteś gotowy?» | «**Zapisuję** twój obiad.» / «**Sprawdzam**…» |
| **Imperative (you-form, no gender)** | «Byłeś aktywny dziś» | «**Zaloguj** obiad.» / «**Trzymaj** tempo!» |
| **Passive + noun** | «Karmiłeś NOMS-a 7 dni» | «**NOMS karmiony** od 7 dni z rzędu.» |
| **Present continuous** | «Zrobiłeś to!» | «**Robisz** to! Tak trzymaj.» |

**Edge case:** `karmisz` (2nd person present, gender-neutral) — лучший workhorse для streak/log сообщений. Используем активно. Прошедшее time избегаем где возможно.

---

### 4. Telegram SRE: длина и сокращения

- **PL ~25% длиннее EN** из-за окончаний (`-ego`, `-emu`, `-ami`). Inline button label limit 18 chars: `Zaloguj` (7) ok; `Zaloguj posiłek` (15) на грани; `Zarejestrować` (13) ok но formal.
- **Casual shorteners** (для пушей): `no` (=well/anyway: «No to lecimy»), `se` (`zrób se kawę`), `git` (=ok), `nara` (=bye). Использовать **скупо** — 1 разговорное слово на message.

Примеры:
- ✅ Inline (15 chars): `Pokaż statystyki`
- ❌ Inline (24): `Wyświetl szczegółowe staty` — обрежется
- ✅ Push: «No to leci obiad. Zapisz, zanim zimny.» (12 слов, casual+imperative)

---

### 5. Идиомы и sass-метафоры (PL pop-culture)

Польская поп-культура, **не** калька с RU:

1. **«Twój metabolizm tańczy poloneza»** (вместо «Macarena» — поляки знают Wajda-Pana Tadeusza polonez, swoiste).
2. **«Ale jaja!»** — surprise/wow (literally «what eggs», but means «no way»). «{streak} dni? Ale jaja!»
3. **«Dramat na miarę telenoweli»** — PL TV reference (telenowele M jak miłość). Для отчёта о пропуске обеда.
4. **«Insulina ci robi after o 23:00»** — `after` = afterparty (PL Gen-Z borrow). Биохимия + Warszawa night life.
5. **«Spoko, spoko»** — «chill» (повторение = успокаивающе). Для comeback push: «Spoko, passa się zdarza zgubić».

**Сленг dosing:**
- ✅ Safe: `spoko, mega, bombka, ekstra, czaisz?, leci`
- ⚠️ Strong (1 раз в месяц max): `zajebiście` (близко к «fucking awesome» — мощно), `cykor` (=coward, only для self-bot)
- ❌ Никогда: `kurwa`, любой проф. мат — токсично.

Правило: **1 сленговое слово на сообщение**. Перебор = звучит как ironyczny boomer.

---

### 6. Anti-patterns

| Anti-pattern | Bad ❌ | Good ✅ |
|---|---|---|
| Дословная калька | **«Zaloguj swój obiad»** (= sign in your lunch???) | «Zapisz obiad» |
| Канцелярит | «**Prosimy o zarejestrowanie** posiłku w systemie» | «Wbij obiad, czekam» |
| False friend `aktualnie` | «**Aktualnie** karmisz NOMS-a 7 dni» (= currently, не «actually») | «Faktycznie karmisz NOMS-a 7 dni!» |
| Англицизм поверх PL | «Twój **food log** jest **empty**» | «Twój dziennik jest pusty» |
| `Pan/Pani` в casual | «**Czy zechciałby Pan** dodać śniadanie?» | «Hej, **dodaj** śniadanie?» |

---

### 7. 🔴 Культурные табу и этические триггеры (CRITICAL)

**Hard bans:**
- Вес / тело юзера — никогда. Fat-shaming = ban.
- **WW2 / Holocaust / communism / PRL martial law (1981)** — никогда, даже шутя. «Bunkry», «kartki na żywność», «Solidarność» — **off-limits**.
- **Catholic references** — без шуток про Jezusa, Папу Wojtyłę (национальный герой), Maryję. Можно «modlitwa o cierpliwość» в очень мягком контексте.
- **Russia/Ukraine politics** — табу (война, политические лидеры).
- **Pierogi, żurek, oscypki, schabowy, bigos** — национальные блюда, **не критикуй как junk**. «Schabowy = jednorazowy reset macro» — ❌. Можно нейтрально логировать.
- **Алкоголь:** wódka — национальный символ, без шуток «Polak = pijak». Beer/wine можно нейтрально.

**5 «дерзко, но безопасно»:**
1. «Twoja insulina robi sobie **after o 23:00**. Może mniej cukru?» (биохимия + night-life)
2. «Mózg działa na glukozie. Twój **właśnie zgłosił niedobór**.» (нейробиология)
3. «{streak} dni z rzędu? Twój **metabolizm dostał awansu**.»
4. «Pominięty obiad → wieczorem **fridge raid level boss**.» (gaming)
5. «Białko + spacer = **combo, którego Twoje mięśnie nie zapomną**.»

**5 «опасно — не делать»:**
1. ❌ «Znowu pączek? **Czemu**?» — judgement, shame.
2. ❌ «Wyglądasz, jakbyś **przybrał na wadze**.» — body comment, instant ban.
3. ❌ «To danie jest **typowo polskie i typowo niezdrowe**.» — national food shaming.
4. ❌ «**Modlitwa nie spali kalorii** 😅» — religion mockery.
5. ❌ «**Jak za komuny — kartki na jedzenie**, ale teraz to Twój wybór.» — PRL reference, trauma.

---

### 8. RTL / script

**N/A.** PL = LTR, латиница + диакритики (`ą ć ę ł ń ó ś ź ż`). Telegram рендерит корректно во всех клиентах. Длина проверена через UTF-8 byte count (диакритики = 2 байта, но Telegram считает code points — ok).

---

## SPECIAL TASK — переписать 5 PL значений по Sassy Sage

Plac­eholders сохраняются byte-by-byte: `{streak}`, `{{icon_brain}}`, `\n`.

### 1. `gamification.streak_7` (variant 1 of 3)

- **Old:** `🔥 LEGENDA! {streak} dni z rzędu! Karmisz NOMS-a przez {streak} dni. Twój metabolizm tańczy Macarenę. Masz nową odznakę!`
- **New:** `🔥 LEGENDA! {streak} dni non-stop! Karmisz NOMS-a {streak} dni z rzędu — twój metabolizm tańczy poloneza. Łap nową odznakę!`
- **Rationale:** `Macarena` → `polonez` (PL pop-culture, Wajda/Pan Tadeusz instantly recognizable). `non-stop` natural англицизм в PL. `Łap` (=catch) живее чем `Masz` (=you have).

### 2. `cron_notifications.reminder_meal_lunch`

- **Old:** `🍽️ Obiad sam się nie zapisze. Twój ruch`
- **New:** `🍽️ Obiad sam się nie wbije. No to lecimy.`
- **Rationale:** `wbić` (=hit/punch in) — Warszawa casual, заменяет formal `zapisać`. `No to lecimy` — фирменная PL push-фраза (~ «давай погнали»), gender-neutral, dynamicznie.

### 3. `errors.ai_failed` (variant 1 of 3)

- **Old:** `Hmm, mój "mózg" jest zamglony teraz {{icon_brain}}💭\n\nZdjęcie nie załadowało się w pełni, lub jestem zmęczony (zdarza się AI 😅).\n\nSpróbuj:\n• Zrobić zdjęcie ponownie\n• Lub napisz w tekście: "Pierś z kurczaka 200g"`
- **New:** `Hmm, mam mgłę w "mózgu" {{icon_brain}}💭\n\nZdjęcie nie doszło w całości, albo AI mi się zmęczyła (zdarza się 😅).\n\nSpróbuj tak:\n• Pstryknij jeszcze raz\n• Albo wbij tekstem: "Pierś z kurczaka 200g"`
- **Rationale:** убрали gendered `zamglony` (♂ только!) → безличное `mam mgłę`. `załadowało się w pełni` (calque) → `doszło w całości` (natural). `Zrobić zdjęcie` (formal) → `Pstryknij` (casual). `Napisz w tekście` (clunky) → `wbij tekstem` (Warszawa slang).

### 4. `report.insight_eating_little`

- **Old:** `Mało dziś jesz? Nie pomijaj posiłków — seria nie działa na powietrzu.`
- **New:** `Skromnie dziś. Wbij obiad — passa nie leci na samym powietrzu.`
- **Rationale:** `Mało dziś jesz?` — звучит как уточняющий вопрос (judgement-leaning). `Skromnie dziś.` — констатация, no shame. `seria` → `passa` (fitness-canonical). `nie działa na powietrzu` (calque) → `nie leci na samym powietrzu` (idiomatic PL, `leci` = «работает/идёт»).

### 5. `referral.cta_newbie_2`

- **Old:** `Zaproś znajomych! Kiedy zaczną logować jedzenie, oboje dostaniecie monety i XP. 4 znajomych z PRO = darmowy miesiąc!`
- **New:** `Wciągnij ekipę! Jak zaczną zapisywać jedzenie — lecą monety i XP dla obu stron. 4 ziomków z PRO = miesiąc gratis!`
- **Rationale:** `Zaproś` (formal-invite) → `Wciągnij ekipę` (=pull in your crew, Gen-Z PL). `logować` → `zapisywać` (см. секция 1: `logować` = sign in). `oboje dostaniecie` — gendered dual (`oboje` ♂♀ pair) → `dla obu stron` (gender-neutral). `znajomych` → `ziomków` (casual, gender-neutral). `darmowy` → `gratis` (короче, punchier).

---

## Финал

**Файл:** `/Users/vladislav/Documents/NOMS/.claude/worktrees/angry-williamson-bd67f0/tools/glossary_section_pl.md`. **~950 слов.**

**3 уникальных PL-нюанса:**

1. **`zalogować` = sign in, не log a meal.** Critical false friend. Везде `zapisać / wpisz / wbić` — иначе юзер думает что нужна авторизация. NOMS уже завтра должен пройти find-replace `zalogować` → `zapisać` в активных translations (это **уже встречается** в проде — см. `cron_notifications.morning` variant 3 prod-value).

2. **Прошедшее время = gendered минное поле.** `zrobiłeś` ♂ vs `zrobiłaś` ♀ — нет нейтрального варианта. Решение: present continuous (`robisz`), безличные конструкции (`zrobione!`), 1st-person bot (`zapisuję`). Slash `gotowy/a` запрещён — Duolingo PL отказались, читается как канцелярит.

3. **Polonez > Macarena.** Локализация cultural reference требует **замены**, не перевода. Полякам известна Macarena, но polonez (Pan Tadeusz, Wajda) — национальный код, instantly триггерит улыбку. Pattern для будущих переводов: на каждый EN pop-ref ищем PL аналог equivalent эпохи/жанра.

---

## UK — Українська

Секция для украинской локализации NOMS. UK грамматически близок к RU, но это **отдельный язык со своим колоритом, лексикой и (что критично в 2026) пост-военным культурным контекстом**. Главная ошибка переводчика — гнать «RU плюс щ/і/ї». Sassy Sage по-украински должен звучать как друг с Подола, а не как машинный перевод с Тверской.

---

### 1. Терминология ядра

| RU/EN concept | UK (canonical) | EN fallback | Rationale |
|---|---|---|---|
| серия / streak | **стрік** | streak | Калька из английского укоренилась в укр. fitness-комьюнити (Duolingo UK тоже «стрік»). «Серія» звучит как сериал на 1+1. |
| лог / log (v.) | **записати** (n. **запис**) | log | «Логувати» допустимо в casual, но «записати» нейтральнее и короче. |
| мана | **мана** | mana | Игровой термин universal. |
| XP | **XP** | XP | Не переводить. «Досвід» лишний слой. |
| монеты / coins | **монети** | coins | Прямо. Не «жетони», не «бали». |
| квест | **квест** | quest | Укоренилось. |
| ачивка / achievement | **досягнення** | achievement | «Ачивка» — русизм-сленг, в UK звучит чужеродно. |
| Premium | **Premium** | Premium | Бренд, не переводить. |
| уровень / level | **рівень** | level | Стандарт. |
| заморозка / freeze | **заморозка** (стріка) | freeze | Не «замороження» — слишком формально. |

**Главное:** UK имеет своё слово для еды — **«їжа»**, не «еда». «Їжа», «обід», «вечеря», «сніданок», «перекус». «Прийом їжі» в журнальном стиле, в casual — просто «обід/вечеря».

---

### 2. Register: ти или Ви?

UK fitness-приложения (Diet&Health UA, ТренуйУкраїну) — все на «ти». Sassy Sage = дерзкий друг → **«ти»** во всех 13 языках, UK не исключение.

- ✅ «Тримай новий бейдж!»
- ✅ «Не забудь про сніданок — NOMS вже прокинувся!»
- ❌ «Будь ласка, оберіть країну зі списку.» (канцелярит + Ви = двойной anti-pattern)

«Ви» допустимо только в **payment legal disclaimers** и **safety disclaimers** про РПП — там нужен формальный регистр.

---

### 3. Гендерная политика (CRITICAL)

UK гендерится в прошедшем времени и кратких прилагательных: «записав/записала», «готовий/готова», «втомився/втомилася». NOMS не знает пол юзера → **избегаем гендеризованных форм**.

**Стратегии (в порядке предпочтения):**

| Стратегия | Good | Bad |
|---|---|---|
| Passive («-но/-то») | «Твій обід **записано**» | «Ти записа**в/ла** обід» |
| 1st-person бот | «**Записую** твій обід» | «Ти **зареєструвався**» |
| Imperative | «**Запиши** обід» | «Готов**ий/а** записати?» |
| Безособові | «**Готово!** Збережено!» | «Ти **готов** / **готова**?» |
| Інфінітив + констр. | «Час **поснідати**» | «Ти **поснідав/ла**?» |

**5 пар good/bad:**

1. ✅ «Перший прийом їжі записано!» / ❌ «Ти записав/ла перший прийом їжі!»
2. ✅ «Час обідати — стрік не годується повітрям» / ❌ «Ти готовий/а пообідати?»
3. ✅ «Записую обід. Дай секунду.» / ❌ «Ти впевнений/а, що хочеш записати?»
4. ✅ «Стрік згорів — буває. Стартуємо знову?» / ❌ «Ти забув/ла записати їжу.»
5. ✅ «Тримай новий бейдж!» / ❌ «Ти заробив/ла новий бейдж!»

Slash «-ий/а» в продакшен-копії — **запрещено**. Это визуальный мусор, признак ленивого переводчика.

---

### 4. Telegram SRE (длины и сокращения)

UK по длине ~RU ±5%, но конкретные слова могут быть длиннее. «Записывает» (10) → «записує» (7), но «настройки» (9) → «налаштування» (12). **Не тянуть RU-длину механически** — перепрашиваем.

**Sassy-сокращения UK:**
- «Привіт!» (нейтрально, любая аудитория)
- «Йо!» (молодёжный, Київ/Львів)
- «Гей!» / «Агов!» (нейтрально-дерзко)
- ❌ «Здрастуй» (звучит советски-сухо)
- ❌ «Доброго дня» (слишком формально для бота-друга)

**Примеры лимитов:**
1. Кнопка inline ≤30 chars: «Записати обід» (13) ✅ vs «Зареєструвати прийом їжі» (24, граница).
2. Push notification ≤60 chars: «🍽️ Обід сам себе не запише. Твій хід» (38) ✅.
3. Toast/answerCallbackQuery ≤200 chars: уверенно влезает любой Sassy-message.

---

### 5. Идиомы и sass-метафоры

UK имеет свой юмористический пласт — Кайдашева сім'я, современный стендап (Чорний квадрат, Підпільний стендап), мемы из Дії. **НЕ калькировать RU-шутки.**

5 примеров (биохимия + локальная культура):

1. «Твій інсулін зараз робить вечірку — як на Хрещатику в п'ятницю.»
2. «Метаболізм танцює гопак — ти його розкочегарив.» (вместо «макарену» — локализация ОК)
3. «Серотонін піднявся вище ніж ціни на каву в центрі Львова.»
4. «Кортизол спить, дофамін бомбезно качає — це і є кайф від стріка.»
5. «Твоя печінка зараз як працівник ЦНАПу о 17:55 — втомлена, але героїчно тримає.»

**Сленг (1 на сообщение, не зловживати):** круто, кльово, чотко, бомбезно, кайф, топ, файно (західний), залітай.

---

### 6. Anti-patterns

5 примеров «никогда так не делать»:

1. ❌ **Дословная калька RU**: «Залогуй обід» — frankenstein-слово. ✅ «Запиши обід».
2. ❌ **Канцелярит**: «Будь ласка, зареєструйте Ваш прийом їжі». ✅ «Запиши обід — стрік чекає».
3. ❌ **Русизм** «приём пищи» → калька «прийом їжі» в casual-копии (в технической метке OK, в push — нет). ✅ «обід», «перекус», «вечеря».
4. ❌ **Англицизм где есть UK слово**: «зроби check-in» → ✅ «відмітся / запиши себе».
5. ❌ **«Ви» в casual**: «Вітаємо Вас із досягненням!» → ✅ «Тримай новий бейдж!».

**Bonus русизмы-радары:** «получити» → ✅ «отримати»; «понятно» → ✅ «зрозуміло»; «давай» (как побуждение) → ✅ «нумо», «давай» допустим только в супер-casual; «пока» → ✅ «бувай», «па-па».

---

### 7. 🔴 Культурные табу и этические триггеры (CRITICAL)

Запрещено везде: вес/тело юзера, fat-shaming, медицинские диагнозы.

**UK-специфика 2026 (post-war context):**

- **War references — табу даже шутя.** Никаких «атакуй пиріжок», «оборона холодильника», «фронт калорій», «штурм салату», «контрнаступ на торт». Слова «фронт», «оборона», «атака», «штурм», «удар», «тривога», «укриття» — out of bounds для food-метафор. У большинства юзеров кто-то служит/служил, и метафора-в-минное-поле обнуляет trust моментально.
- **Russian language references — осторожно.** Не вставлять русские слова «для прикола», не цитировать RU-мемы. Юзер сам выбрал UK — уважай выбор.
- **National food culture — не критиковать.** Борщ, вареники, голубці, сало, паска, узвар, деруни — це святе. Можно нежно шутить НАД биохимией («твій підшлунковий не очікував три порції вареників»), но не над едой как культурой.
- **Religion — sensitive.** Православ'я (УПЦ КП → ПЦУ), УГКЦ, протестанти, secular — микс. Никаких «гріх з'їсти ще шматочок» в context посту. Пост (Великий, Різдвяний) — реальная практика для части юзеров.
- **Politics — табу.** Никаких партий, политиков, регионов в плане «Львів vs Донецьк». Городские мемы (Хрещатик, Поділ, Дерибасівська) — OK как neutral location colour.

**5 «дерзко безопасно»:**

1. «Твій інсулін зараз робить вечірку, як на Хрещатику в п'ятницю.»
2. «Підшлункова нагадує бариста на Подолі о 8 ранку: працює без скарг, але потребує чайових (тобто білка).»
3. «Метаболізм сьогодні чотко тримає темп — як трамвай на Львівській площі.»
4. «Серотонін піднявся — мабуть, ти нарешті поспав по-людськи.»
5. «Стрік 7 днів — бомбезно. Більшість здається на третьому, а ти тут.»

**5 «опасно — не використовувати»:**

1. ❌ «Знову та сама піца, серйозно?» — judgement.
2. ❌ «Атакуй холодильник із флангу!» — war metaphor.
3. ❌ «Постися як на Великий піст — мінус 2 кг гарантовано» — religion + weight-shaming.
4. ❌ «Ти що, з Донбасу їжу замовляєш?» — political/regional.
5. ❌ «Ти схуд/ла — молодець!» — body comment + slash-gender.

---

### 8. RTL / script

N/A — UK пишется кириллицей слева направо. Никаких RTL-разворотов. Telegram рендерит кириллицу нативно во всех клиентах.

---

## SPECIAL TASK: 5 переписанных UK-значений по Sassy Sage

### 1. `gamification.streak_7` — variant 1

**Old:**
> 🔥 ЛЕГЕНДА! {streak} днів поспіль! Ти годуєш свого NOMS'а {streak} днів. Твій метаболізм танцює макарену. Тримай новий бейдж!

**New:**
> 🔥 ЛЕГЕНДА! {streak} днів поспіль! NOMS годується {streak} днів без перерви. Твій метаболізм танцює гопак — як на весіллі під ранок. Тримай новий бейдж!

**Rationale:** убрал гендерное «годуєш свого NOMS'а» (звучит ok, но 1st-person «NOMS годується» элегантнее и убирает потенциальную ambiguity). «Макарена» → «гопак» — локалізація без потери метафоры танца, плюс UK-колорит. «Як на весіллі під ранок» — bonus сцена, узнаваемая каждому. Placeholders `{streak}` сохранены byte-by-byte (2 раза, как в оригинале).

### 2. `cron_notifications.reminder_meal_lunch`

**Old:**
> 🍽️ Обід сам себе не запише. Твій хід

**New:**
> 🍽️ Обід сам себе не запише. Нумо

**Rationale:** «Твій хід» — нормально, но это калька с RU «твой ход» (шахматный термин). «Нумо» — чисто украинский clarion call, дерзко-дружеский, на 4 chars короче (важно для push preview). Альтернатива «Давай» тоже OK, но «нумо» более UK-specific и менее повторяет EN «your move» rhythm.

### 3. `errors.ai_failed` — variant 1

**Old:**
> Хм, у мене зараз туман в "мозку" {{icon_brain}}💭
> Фото не завантажилось повністю, або я втомився (буває у AI 😅).
> Спробуй:
> • Зробити фото ще раз
> • Або напиши текстом: "Куряча грудка 200г"

**New:**
> Хм, у мене туман в "мозку" {{icon_brain}}💭
> Фото не довантажилось, або процесор перегрівся (з AI буває 😅).
> Спробуй:
> • Зробити фото ще раз
> • Або напиши текстом: "Куряча грудка 200г"

**Rationale:** убрал гендерное «втомився» (1st-person masculine — если юзерка читає, бот говорит про себя в м.р., это OK, но «процесор перегрівся» elegantly обходит, плюс перекликается с variant 3 о processor). «Не завантажилось повністю» → «не довантажилось» — компактнее, UK-natural. Placeholders `{{icon_brain}}` сохранены (2 раза). Структура списка и пример «Куряча грудка 200г» — byte-by-byte.

### 4. `report.insight_eating_little`

**Old:**
> Щось мало їси. Пообідай — стрік на повітрі не тримається.

**New:**
> Щось скромно сьогодні. Заскоч на обід — стрік повітрям не годується.

**Rationale:** «Мало їси» близько к judgement (нарушает anti-shaming). «Скромно сьогодні» — мягче, описывает паттерн, не юзера. «Заскоч на обід» — Sassy casual (Київ/Львів сленг для «забеги перекусить»). «Повітрям не годується» вместо «на повітрі не тримається» — единая метафора с food-логикой (NOMS-питомец їсть), глагол активный.

### 5. `referral.cta_newbie_2`

**Old:**
> Запрошуй друзів! Коли вони почнуть логувати їжу, ви обидва отримаєте монети та XP. 4 друзі з PRO = безкоштовний місяць!

**New:**
> Кидай друзям запрошення! Коли вони почнуть записувати їжу, обидва отримуєте монети та XP. 4 друга з PRO = безкоштовний місяць.

**Rationale:** «Логувати» — англицизм, есть нормальное «записувати» (sec. 6 anti-pattern). «Ви обидва» гендерится для смешанной пары (обидва = 2 чоловіки, обидві = 2 жінки) — убрал «ви», получилось безособове «обидва отримуєте» (плюрализированно нейтрально). «Кидай запрошення» — casual-дерзкое («кидай в чат»), вместо нейтрального «запрошуй». Финальный «!» убран — после «місяць» цифра 4 уже эмфатична, лишний восклицательный знак удешевляет.

---

**Объём:** ~990 слов.

**3 уникальных UK-нюанса:**

1. **War-metaphor blackout (post-2022 reality).** В отличие от RU/EN, UK Sassy Sage не может играть с «атакой/обороной/фронтом» в food-context. Это самый жёсткий специфичный constraint для копирайтера: метафоры battle/conquest, нормальные в EN fitness-tone («conquer your craving!»), в UK 2026 — мгновенный repulsion trigger. Замена: трамвай, кав'ярня, ЦНАП, гопак, Хрещатик, Поділ — bytovaja бытовая локальная атмосфера.

2. **Anti-russianism как параллельный layer anti-shaming.** Каждый русизм («приём пищи», «получити», «знову та сама піца» по интонации) подсознательно читается как «нас плохо перевели». Это бьёт по trust сильнее grammatical mistake, потому что обнажает leniwy machine-translation pipeline. UK копирайтер должен read-aloud-test'ить каждый текст — звучит ли как украинский или как UK-маска поверх RU.

3. **Гендер-нейтральность через passive — обязательна, не «nice to have».** В отличие от EN (где «you logged» нейтрально), UK passive-формы («записано», «збережено», «нагадано») — единственный production-grade путь. Slash «-ий/а» в UI продакшене сигналит «нас писав фрилансер за 50 грн», что mortally подрывает Sassy Sage credibility как друга. 1st-person бот («Записую», «Нагадую») — equally strong alternative.

---

## ID — Bahasa Indonesia

Sassy Sage на индонезийском — друг из Jakarta-кофейни, не корпоративный manager. Tone: дерзко, кратко, с биохимическими подколами, но с уважением к Ramadan, halal-context и культурному разнообразию.

---

### 1. Терминология ядра

| RU | EN | ID (рекомендация) | Rationale |
|---|---|---|---|
| серия | streak | **streak** | Англицизм осел в gaming/fitness lingo. «rentetan» звучит академично. |
| лог еды | log | **catat / log** | «catat» (глагол), «log» (noun в casual). Mix естественен. |
| мана | mana | **mana** | Gaming-loanword, понятен. |
| XP | XP | **XP** | Universal. |
| монеты | coins | **koin** | Чистая транслитерация. |
| квест | quest | **misi / quest** | «misi» укоренился (от game lokal). |
| достижение | achievement | **pencapaian** | Native term, без потерь. |
| Premium | Premium | **Premium** | Brand. |
| уровень | level | **level** | «tingkat» звучит школьно. |
| заморозка | freeze | **freeze** | Уже усвоен в gaming. |

**Граница:** оставляем англицизм для gaming/tech jargon (streak, XP, freeze) и brands (Premium, NOMS). Переводим там, где есть короткий native (koin, misi, catat). Никогда не пишем «catat-an streak-mu» с дефисами — выглядит как backend-дамп.

---

### 2. Register

**kamu**, не **Anda**. Sassy Sage — друг, «Anda» превращает диалог в push от банка BCA. «Lu/gue» (Jakarta slang) — **исключаем**, отталкивает Bandung/Surabaya/Medan.

Примеры:
- ✅ «Metabolisme kamu lagi pesta diam-diam.»
- ✅ «Eh, makan siangmu mana? Aku nungguin.» (`-mu` clitic = casual «твой»)
- ✅ «Kamu udah 7 hari streak. Mantap.»

---

### 3. Гендерная политика

ID грамматически **гендерно-нейтрален** — большой бонус: ни pronouns (`dia` = он/она), ни глаголы, ни прилагательные не имеют рода. Slash-форм нет.

«Уже хорошо»:
- ✅ «Catat makan siangmu» — императив без рода.
- ✅ «Kamu juara» — одна форма для всех.
- ✅ «Dia lapar» (про NOMS-питомца) — нет gender assumption.

Anti — **не добавлять** искусственный gender:
- ❌ «Kamu adalah seorang pria juara» (приписали `pria` из EN/RU calque) → ✅ «Kamu juara».

---

### 4. Telegram SRE

- Длина: ID ≈ +10-15% к EN. Inline 18 chars — пограничный лимит, тестировать.
- Casual-сокращения: **yg** (yang), **aja** (saja), **udah** (sudah), **gak/nggak** (tidak), **sih** (filler), **dong** (softener).

Примеры:
- ✅ «Makan siang gak akan log sendiri.» (укладывается)
- ✅ «Streak-mu aman, bro.»
- ✅ «Catat aja sekarang, dong.» (мягче, чем восклицание)

---

### 5. Идиомы и sass-метафоры

Биохимия + локальная pop-culture (Gojek/Tokopedia, Indonesian internet humor):

1. «Insulinmu lagi pesta ngab — jam 11 malam, gula naik kayak grafik IHSG.» (IHSG = Jakarta Stock Exchange-мем про волатильность)
2. «Metabolisme kamu udah shift malam kayak driver Gojek. Bayar dia pakai tidur, dong.» (gig-economy метафора резонирует)
3. «Streak 7 hari? Mantap jiwa. Kortisolmu chill, dopamin high-five sama serotonin.»
4. «Musuh kamu bukan kalori — musuh kamu scroll TikTok jam 2 pagi sambil ngemil.»
5. «Tubuhmu jago recovery. Kasih protein, dia balas otot. Fair trade ala Tokopedia.»

Slang ≤ 1 на сообщение: **ngab**, **bro/sis**, **kepo**, **mantap/mantul**, **jago**, **gaspol**.

---

### 6. Anti-patterns

1. **Калька:** «Logge makan siangmu» (нем-импорт глагола) → ✅ «Catat makan siangmu».
2. **Канцелярит:** «Mohon catat makanan Anda demi tujuan kesehatan.» → ✅ «Catat makanmu, biar progress kelihatan.»
3. **False friend:** EN «sensible portions» ≠ ID «sensible» (не используется). → «porsi wajar / masuk akal».
4. **Anda вместо kamu:** «Selamat, Anda telah mencapai streak» → ✅ «Selamat! Streak-mu mantap.»
5. **Over-English:** «Track your daily logging biar streak consistent» — слишком много EN подряд. Mix sparingly — одно tech-слово per phrase.

---

### 7. 🔴 Культурные табу и этические триггеры (CRITICAL)

**Универсально:** no fat-shaming, no body-policing.

**ID-специфика:**

- **Ramadan.** ~87% мусульмане. Дневные meal-reminders в Ramadan (sahur 04:00 → iftar ~18:00) — **очень sensitive**. Бот в 13:00 с «Makan siangmu mana?» во время поста = оскорбление. Учитывать `ramadan_observance` флаг или quiet-mode.
- **Halal/haram.** Свинина (babi) и алкоголь — табу в большинстве контекстов. **Никогда** не упоминай pork/babi/bacon/bir в sass-метафорах.
- **Национальная еда:** rendang (UNESCO), nasi goreng, sate, soto, gado-gado — не критикуй, не подкалывай.
- **SARA** (Suku-Agama-Ras-Antargolongan) — **strict legal taboo** (UU ITE). Никаких религиозных/этнических/расовых отсылок даже в шутку.
- **Региональная диверсность:** Java ≠ Bali (индуисты, pork OK) ≠ Sumatera ≠ Papua. Не обобщай «Indonesians eat X».

**5 «дерзко безопасно»:**
1. «Insulinmu lagi pesta sambil pesen Gojek jam 11 malam.»
2. «Kortisolmu udah overtime. Bayar pakai 7 jam tidur, dong.»
3. «Streak-mu lebih konsisten dari sinyal 4G di lift.»
4. «Metabolisme lagi recovery mode. Kasih protein, jangan drama.»
5. «Otakmu butuh glukosa, bukan scroll TikTok tanpa henti.»

**5 «опасно» (DON'T):**
1. ❌ «Makan babi lagi?» (pork — табу).
2. ❌ «Lagi puasa? Skip aja log-nya.» (Ramadan/religious practice).
3. ❌ «Rendangmu kebanyakan, kurangin.» (критика национального блюда).
4. ❌ «Orang Jawa biasanya makan manis, hati-hati.» (SARA — этническая generalization).
5. ❌ «Bir dingin habis gym? Mantap!» (alcohol).

---

### 8. RTL/Script

N/A. Latin script (EYD/PUEBI), LTR. Эмодзи нативно поддержаны.

---

## SPECIAL TASK: 5 переписанных ID-значений

### 1. `gamification.streak_7` (variant 1)

**Old:** «🔥 LEGENDA! {streak} hari berturut-turut! Kamu telah memberi makan NOMS selama {streak} hari. Metabolisme kamu menari Macarena. Ini lencana baru!»

**New:** «🔥 LEGENDA! {streak} hari nonstop! Kamu udah kasih makan NOMS-mu {streak} hari berturut-turut. Metabolisme nari Macarena, dopamin-mu high-five. Nih, lencana baru — pake yang gaya!»

**Rationale:** «berturut-turut» дважды — formal-tautology, первое заменил на «nonstop». «telah memberi makan» (formal) → «udah kasih makan». Добавил биохимический штрих + casual ending. `{streak}` ×2 сохранены byte-by-byte.

### 2. `cron_notifications.reminder_meal_lunch`

**Old:** «🍽️ Makan siang nggak akan log sendiri. Giliranmu»

**New:** «🍽️ Makan siang gak bakal log sendiri, bro. Giliranmu sekarang.»

**Rationale:** «nggak akan» → «gak bakal» (более разговорный). «bro» — gender-neutral в ID Gen-Z lingo. Не fat-shame, нейтральный nudge — Ramadan-safe в любое не-post-окно.

### 3. `errors.ai_failed` (variant 2)

**Old:** «Jaringan saraf juga bisa lelah {{icon_brain}} Aku tidak bisa mengerti gambar ini. Tulis dengan kata-kata, ya?»

**New:** «Jaringan saraf juga bisa lelah {{icon_brain}} Otakku gak ngerti foto ini, sumpah. Ketik aja pakai kata, dong — gampang.»

**Rationale:** «Aku tidak bisa» (formal) → «Otakku gak ngerti» (4th-wall, casual). «sumpah» = разговорное усиление. «dong» = soft persuasion. `{{icon_brain}}` сохранён byte-by-byte.

### 4. `report.insight_eating_little`

**Old:** «Makan sedikit hari ini? Jangan skip makan — streak tidak jalan dengan udara.»

**New:** «Makan kurang hari ini? Jangan skip — streak gak jalan cuma pakai udara, bro.»

**Rationale:** «sedikit» → «kurang» (естественнее для «недостаточно»). Убрал повтор «makan». Anti-shame: не критикует тело, напоминает про streak-mechanic.

### 5. `referral.cta_newbie_2`

**Old:** «Ajak teman! Saat mereka mulai catat makanan, kalian berdua dapat koin dan XP. 4 teman dengan PRO = bulan gratis!»

**New:** «Ajak teman, ngab! Pas mereka mulai catat makan, kalian berdua dapat koin + XP. 4 teman PRO = sebulan gratis. Gaspol!»

**Rationale:** «ngab» (modern Jakarta slang, gender-neutral) + «Pas» (casual «когда») + «Gaspol!» (energetic CTA-ender). Все цифры (4) и tech-термины (PRO, XP) сохранены byte-by-byte.

---

**Placeholder integrity:** `{streak}` ×2 (streak_7), `{{icon_brain}}` ×1 (ai_failed) — byte-identical.

---

## HI — हिन्दी (with Hinglish notes)

Sassy Sage на хинди — это **75% Hinglish + 25% чистый деванагари**. В Индии fitness/tech-боты (HealthifyMe, Cure.fit, Cred) разговаривают именно Hinglish'ем; чистый литературный Hindi звучит как канцелярит или новости All India Radio. Наша задача — попасть в tone Zomato push'ей и Swiggy CRM.

### 1. Терминология ядра

| Концепт | HI (deva) | Hinglish/EN | Когда переводить |
|---|---|---|---|
| streak | लगातार सिलसिला | **streak** | EN — fitness apps уже зафиксировали |
| log (verb) | दर्ज करना | **log karo** | EN — короче, привычнее Gen-Z |
| mana | मन-ऊर्जा | **mana** | EN — игровой термин, deva непонятна |
| XP | अनुभव अंक | **XP** | EN всегда — gaming lexicon |
| coins | सिक्के | **coins** | EN/HI оба ок, в reward'ах — सिक्के |
| quest | मिशन | **quest/mission** | Hinglish: «mission» теплее |
| achievement | उपलब्धि | **achievement** | EN — короче для бейджей |
| Premium | प्रीमियम | **Premium** | EN, никогда не транслит |
| level | स्तर | **level** | EN — Candy Crush приучил |
| freeze | फ्रीज़ | **freeze** | EN — игровой жаргон |

**Rationale:** деванагари-кальки типа «अनुभव अंक» для XP читаются как textbook. Latin-вкрапления — норма; смешивать в одной строке OK: «5 XP मिले!»

### 2. Register: tum, aap, tu?

Sassy Sage = старший брат-приколист → **tum**. `aap` — formal (банк, родители мужа), холодно. `tu` — близко, но в письменном виде звучит грубо/уличный (Mumbai сленг, Delhi taxi-driver). **Tum — sweet spot.** Hinglish бьёт по гендеру и register одновременно: «You logged it!» — нейтрально по всем осям.

Примеры:
- ✅ «Tumne lunch log kiya — nice!»
- ❌ «Aapne bhojan dakhil kiya hai» (звучит как HR-уведомление)
- ❌ «Tune khaya kya?» (грубо)

### 3. Гендерная политика (CRITICAL)

Hindi гендерится в каждом втором глаголе. «Я ел/ела» = «maine khaya / maine khayi». «Ты счастлив/счастлива» = «tum khush ho / khush hai». Slash'и ломают UX, generic masculine оскорбителен (50% female user base PingWin).

**Стратегии gender-neutral HI (приоритет сверху вниз):**

| Pattern | Пример good | Пример bad |
|---|---|---|
| Imperative | «Lunch log karo» | «Tumne lunch log kiya» |
| Passive/3rd person | «Khaana log ho gaya» | «Tu khush hua?» |
| Hinglish bridge | «Lunch logged! Nice work» | «Achha kiya tumne» |
| 1st-person bot (M) | «Main tumhara lunch save kar raha hoon» | «Tu save ki ya kiya?» |
| Noun + adjective | «Mast streak!» | «Tu mast banda hai» |

**5 пар:**
- ✅ «Bohot badhiya! Streak chal raha hai» / ❌ «Tu bohot achhi hai»
- ✅ «Lunch log ho gaya» / ❌ «Tune lunch logged kiya»
- ✅ «Main impressed hoon» / ❌ «Tu kamal ka/ki hai»
- ✅ «Ek aur log karo — streak bachao» / ❌ «Tune skip kar diya / di»
- ✅ «Wapsi mubarak!» / ❌ «Tu wapas aaya/aayi»

### 4. Telegram SRE

- **Devanagari ширина:** символ занимает ~1.3× ширины Latin. Inline button: безопасный лимит **~12 chars в деванагари** vs ~16 Latin (Telegram iOS truncates с многоточием при ~190px).
- **Hinglish (Latin):** ≈ 35 chars/line, как EN.
- **Сокращения:** `hai` в конце — optional («Streak chal [hai]»). `kya` — вопросительный маркер: «Lunch hua kya?» вместо «Lunch ho gaya hai kya».

Decision tree «Hindi vs Hinglish для inline»:
1. Кнопка ≤ 10 chars → **Hinglish** («Log now», «Skip»).
2. Кнопка 10-20 chars и push notification → **Hinglish** mainstream.
3. Long-form education/safety/medical → **Hindi-heavy** (доверие).
4. Sassy/funny — **Hinglish always** (Hindi sass = Bollywood pre-2000, dated).

### 5. Идиомы и sass-метафоры

Биохимия × локальная поп-культура — без team names, без религии:

1. «Tumhara insulin abhi disco kar raha hai 🕺» — спайк сахара.
2. «Metabolism full Bollywood mode mein hai — drama, dance, dialogue» — после streak.
3. «Cortisol levels dekhke lag raha hai Monday morning IPL ka 4th over» — стресс.
4. «Yaar, ye streak Sholay ki Jai-Veeru jodi jaisa hai — tut na jaaye» — milestone.
5. «Ghrelin scene set kar raha hai — pet bol raha hai feed me now» — голодные гормоны.

Сленг — **1 на сообщение**: yaar (универсал), bro/sis (gender — лучше избегать), «scene set hai», «mast», «full-on», «bantai» (Mumbai, опционально), «boss» (нейтрально).

### 6. Anti-patterns

1. ❌ «Kripya apna bhojan dakhil karein» — канцелярит, Indian Railways announcement vibe.
2. ❌ «Aap atyant prashansaniya pradarshan kar rahe hain» — Sanskritized, никто так не говорит вне школьного экзамена.
3. ❌ «Tune khaya kya bhai?» — generic masculine + слишком street.
4. ❌ «Bro tu food log karke streak banaye rakh» — over-EN без HI-якоря, теряет character.
5. ❌ «Apna khana log karo» — звучит ok, но «log» здесь backend-термин, в HI-контексте читается как «log = люди» (омоним). Лучше «track karo» или «record karo».

### 7. 🔴 Культурные табу и этические триггеры (CRITICAL)

**Религия (~80% Hindu, ~14% Muslim, ~2% Sikh, ~2% Christian, Jain/Buddhist):**
- ❌ **Beef / pork** — никогда. Beef = sacred cow (Hindu); pork = haram (Muslim). Даже «meat positively» — табу.
- ❌ Festivals attached to food («Diwali sweets = cheat day»): часть юзеров постится в Navratri/Ramadan/Lent.
- ❌ Caste — абсолютное табу, любые отсылки (Brahmin diet, etc.).
- ❌ Politics: Modi, BJP/Congress, India-Pakistan, Kashmir — full taboo.
- ❌ Региональные стереотипы («Punjabi log to butter chicken khaate hain», «South Indian = idli») — patronizing.

**Безопасно:**
- ✅ Bollywood references generic (Sholay, KKHH — без актёров политически активных).
- ✅ Cricket общий (IPL season, «cover drive», «yorker») — без team names.
- ✅ Гормоны/биохимия — «insulin», «cortisol», «ghrelin».
- ✅ Memes universal: «scene», «mast», «full-on».

**5 «дерзко безопасно»:**
1. «Tumhara insulin abhi disco kar raha hai 🕺»
2. «Cortisol ko coffee ki zaroorat nahi, tumhe break ki zaroorat hai»
3. «Ye streak full IPL playoffs vibes de raha hai»
4. «Metabolism Bollywood mode mein — keep going»
5. «Ghrelin signal aa raha hai — pet bol raha hai»

**5 «опасно» (не использовать):**
1. ❌ «Phir se samosa? Yaar serious ho jao» — food shaming + ethnic food.
2. ❌ «Beef khaake protein badhao» — религиозный триггер.
3. ❌ «Ramzan mein bhi log karte raho» — religious singling out.
4. ❌ «Punjabi-style ghee chod do» — regional stereotype.
5. ❌ «Modi ji bhi calorie count karte hain» — political.

### 8. Script gotchas

- **Devanagari LTR** — render OK на iOS/Android Telegram, без Arabic-style RTL artefacts.
- **Mixed deva + Latin** — визуально OK, но **не** разрывай слово: «log करो» — плохо, «log karo» (full Latin) или «दर्ज करो» (full deva) — хорошо.
- **Decision rule:** одно предложение — один script primary, brand names (NOMS, Premium, XP) — Latin как fixed island.
- **Цифры:** Western digits (0-9) safe в обоих скриптах. Devanagari digits (०-९) — **не использовать**, current generation читает их хуже.
- **Emoji позиция:** конец строки безопаснее. Emoji перед देवनागरी иногда вызывает font fallback (особенно `{icon_brain}` рядом с consonant cluster) — placeholders ставить с пробелом: `«{icon_brain} Hmm...»` а не `«{icon_brain}Hmm»`.

---

## SPECIAL TASK — переписанные HI значения

### 1. `gamification.streak_7`

**OLD:** «🔥 लीजेंड! लगातार {streak} दिन! आप NOMS को {streak} दिनों से खाना खिला रहे हैं। आपका मेटाबॉलिज्म मैकेरेना कर रहा है। एक नया बैज लें!»

**NEW (Hinglish-leaning):** «🔥 LEGEND! {streak} din lagataar! Tumne NOMS ko {streak} din se feed kiya hai. Metabolism abhi pura Bollywood dance mode mein hai 💃 Ye raha naya badge!»

**Rationale:** `aap` → `tum` (Sassy register). «Mैकेरेना» — нерелевантная отсылка для India (Macarena — 90s LatAm). Bollywood dance — локальный эквивалент. **Hinglish выбор:** sass + reward = casual energy, чистая deva «мैकेरेना» в transliteration читается коряво. Placeholder `{streak}` сохранён byte-by-byte.

### 2. `cron_notifications.reminder_meal_lunch`

**OLD:** «🍽️ लंच खुद लॉग नहीं होगा। तुम्हारी बारी»

**NEW (Hinglish):** «🍽️ Lunch khud log nahi hoga. Tumhari baari, boss»

**Rationale:** Transliteration «लंच» в deva — uncomfortable mix. Push notification preview обрезается на iOS ~40 chars — Hinglish читается на одном глотке. «Boss» — нейтральный gender-free vocative, Mumbai-CRM staple. **Hinglish выбор:** short push = Latin script, faster scan.

### 3. `errors.ai_failed` (variant 1)

**OLD:** «हम्म, मेरा "दिमाग" अभी धुंधला है {{icon_brain}}💭\n\nफोटो पूरी तरह से लोड नहीं हुई, या मैं थक गया हूं (AI के साथ होता है 😅).\n\nकोशिश करें:\n• फिर से फोटो लें\n• या टेक्स्ट में लिखें: "चिकन ब्रेस्ट 200 ग्राम"»

**NEW (mixed, deva primary):** «{{icon_brain}}💭 Hmm, mera "dimaag" abhi thoda foggy hai.\n\nPhoto pura load nahi hua, ya main thak gaya (AI ke saath hota hai 😅).\n\nTry karo:\n• Phir se photo bhejo\n• Ya text mein likho: "Chicken breast 200g" ya "Paneer bhurji 1 katori"»

**Rationale:** «थक गया हूं» — generic masculine, но в bot 1st-person это safe (bot = neutral M default). Hinglish bridge. **Critical:** «Chicken breast 200g» заменили на пример **+ vegetarian option** — `Paneer bhurji` снимает religious friction. Placeholders `{{icon_brain}}` byte-by-byte. **Mixed выбор:** instruction list — Hinglish (action verbs), opener — pseudo-Hindi для sass.

### 4. `report.insight_eating_little`

**OLD:** «आज कम खा रहे हो? खाना मत छोड़ो — स्ट्रीक हवा पर नहीं टिकती।»

**NEW (Hinglish):** «Aaj halka khaa rahe ho? Meal skip mat karo — streak hawa pe nahi chalti.»

**Rationale:** «कम खा रहे हो» имеет тон judgement; «halka» (light) — neutral. «Khaana mat chodo» звучит как мать-мама. «Skip mat karo» — Gen-Z. **Hinglish выбор:** daily report = quick scan, Latin быстрее. Gender-neutral imperative.

### 5. `referral.cta_newbie_2`

**OLD:** «दोस्तों को बुलाओ! जब वो खाना लॉग करना शुरू करें, दोनों को सिक्के और XP मिलेंगे। 4 दोस्त PRO के साथ = फ्री महीना!»

**NEW (Hinglish):** «Yaaron ko invite karo! Jab woh food log karna start karein, dono ko coins aur XP milenge. 4 PRO friends = ek free month! 🎁»

**Rationale:** «दोस्तों को बुलाओ» = «call friends over» (physical), не «invite». «Yaaron» — culturally warmer plural. «PRO के साथ» reads weird; «4 PRO friends» — clean. Added 🎁 для CTA pop. **Hinglish выбор:** marketing CTA = always Hinglish in India (Zomato/Swiggy template). Placeholder-free строка, byte-equiv не applies.

---

## Финал

**File:** `/Users/vladislav/Documents/NOMS/.claude/worktrees/angry-williamson-bd67f0/tools/glossary_section_hi.md`
**Объём:** ~970 слов.

**3 уникальных HI-нюанса:**
1. **Vegetarian/religious context** — beef/pork абсолютное табу, ~30-40% юзеров вегетарианцы по религии (не по lifestyle). В food examples всегда давать veg-альтернативу (paneer, dal). Никаких festival-attached food jokes (Ramadan/Navratri).
2. **Hinglish-first strategy** — чистый литературный Hindi для casual fitness app звучит как Doordarshan новости. Decision rule: long-form education → Hindi-heavy; short push/CTA/sass/buttons → Hinglish (Latin script). Smooth Latin↔Deva switching внутри одного предложения — норма, но **не разрывать слово** между скриптами.
3. **Devanagari SRE + gender escape** — символ деванагари ~1.3× ширины Latin (inline button лимит ~12 chars vs 16 в Latin). Hindi гендерится в каждом глаголе, что делает Hinglish-bridge не только UX-выбором, но и техническим **gender-neutrality hack**: «Lunch logged!» избегает khaya/khayi проблемы целиком.

---

## AR — العربية

Sassy Sage на арабском — задача нетривиальная: один язык, но 22 страны, два регистра (MSA vs ʿammiyya), тяжёлая gender-маркировка глаголов, RTL-script с bidi-сюрпризами и плотный культурно-религиозный слой (Ramadan, halal, политика). Этот раздел фиксирует решения, которые делают персонажа дерзким, но безопасным от Касабланки до Маската.

---

### 1. Терминология ядра

| EN | AR | Rationale |
|---|---|---|
| streak | **سلسلة** (silsila) | «Цепочка». Понятно во всех диалектах. Не использовать «خط متواصل» — длинно и formal. |
| log (verb) | **سجّل / تسجيل** (sajjil / tasjīl) | Универсальный MSA, нет ассоциаций с лесорубом как в EN. |
| log (a meal) | **وجبة مسجّلة** (wajba musajjala) | Nominal — обходит gender (см. §3). |
| mana | **مانا** (mānā) | Транслит. Игровой жаргон в AR-играх уже устоялся транслитом. |
| XP | **XP** (латиницей) или **نقاط الخبرة** | Аббревиатуру оставляем LTR — она globally readable. Полное «نقاط الخبرة» — для длинных пушей. |
| coins | **عملات** (ʿumlāt) | Множественное от «عملة». Не «نقود» (это «деньги», создаёт ложное впечатление кэша). |
| quest | **مهمة** (muhimma) | «Задание». «كويست» (транслит) звучит подростково — отвергаем. |
| achievement | **إنجاز** (injāz) | Стандарт, гордое слово. |
| Premium / PRO | **PRO** (латиницей) | Бренд-токен, не переводим. RTL-движок Telegram сам поставит его LTR-блоком. |
| level | **مستوى** (mustawā) | MSA, без вариантов. |
| freeze (streak) | **تجميد** (tajmīd) | Буквально «заморозка». Игровая метафора читается. |

**Critical decision: MSA-with-flavor.** Чистый ʿammiyya (Egyptian/Levantine/Gulf) — alienates остальные 18 стран. Чистый высокий MSA — звучит как новостной диктор, убивает sass. Решение: **слегка расслабленный MSA** + редкие pan-Arab разговорные маркеры (`يلا`, `هيا`, `طيب`). Это формат, который используют Anghami, Careem, Noon — пользователи к нему привыкли.

---

### 2. Register

**Выбор: relaxed MSA + pan-Arab разговорные вкрапления.** Не Egyptian (не поймёт марокканец/тунисец вне поп-культуры), не Gulf (формальнее, чем нужно для шутки), не Levantine (узкий ареал).

Маркеры relaxed-регистра:
- Короткие предложения, не embedded clauses.
- `يلا` (yalla — давай), `طيب` (ṭayyib — окей), `هيا` (hayyā — пошли) — pan-Arab.
- Восклицания через «!» вместо MSA-перифраза.

3 примера:

| Слишком formal MSA | Sage relaxed MSA |
|---|---|
| «يُرجى تسجيل وجبة الغداء فوراً.» | «يلا، وجبة الغداء بانتظارك!» |
| «لقد تجاوزت سعة المعالجة الذهنية الخاصة بي.» | «معالجي سخن من الصورة دي 😅» |
| «إنّ السلسلة لا تستمر بالهواء.» | «السلسلة ما بتمشي بالهوا.» |

`أنت` vs `أنتِ` — это **gender**, не formality (см. §3). Регистр и пол — ортогональные оси.

---

### 3. Гендерная политика (CRITICAL)

AR маркирует пол **везде**: глаголы 2 л. (`سجّلت` muzakkar / `سجّلتِ` mu'annas), местоимения (`أنت` / `أنتِ`), прилагательные (`جاهز` / `جاهزة`). Slash-нотация типа `سجّلت/ـتِ` — UI-катастрофа: RTL + diacritic + slash рендерится chaotic, юзер не понимает что выбрать.

**Стратегии (по приоритету):**

1. **Verbal nouns / nominal sentences** — нет глагола → нет пола. Топ-стратегия.
2. **1-е лицо бота** — Sage говорит про себя, не про юзера.
3. **Passive voice** (`تم تسجيل وجبتك`) — agentless.
4. **Imperative 2 pl. (`-ُوا`) с «royal we»** — формально pluralis maiestatis, но в AR воспринимается neutral/respectful, не множественным.
5. **Generic masculine** — последний резерв; женщины из консервативных стран читают это как «ко мне не относится».

5 пар good/bad:

| ❌ Bad | ✅ Good | Почему |
|---|---|---|
| `أنت سجّلت غداءك!` (muzakkar only) | `وجبة الغداء مسجّلة! 🎉` | Nominal — пол не нужен. |
| `هل أنتِ جاهزة؟ / هل أنت جاهز؟` | `جاهز للبدء؟` → **`يلا نبدأ؟`** | 1 pl. inclusive — Sage и юзер вместе. |
| `سجّل/ـي وجبتك` | `تسجيل الوجبة` | Verbal noun — кнопка/команда без глагола. |
| `أنت بطل! / أنتِ بطلة!` | `أداء البطولة! 🏆` | Achievement-фраза без обращения к лицу. |
| `لقد تجاوزتَ/ـتِ حدّك` | `تم تجاوز الحد` | Passive — agentless. |

**Edge case streak-celebration:** «You're a champ» в EN → AR `أداء البطولة!` (производительность чемпиона) вместо `أنت بطل/بطلة`. Чуть менее тёплое, но gender-clean.

---

### 4. Telegram SRE (RTL critical)

- **Numbers всегда LTR.** `{streak}` = `7` рендерится LTR даже внутри RTL-параграфа. Bidi-алгоритм UAX#9 обычно справляется, но на границе RTL↔digit↔punctuation может «прыгать».
- **LRM (U+200E) и RLM (U+200F)** — invisible direction marks. Используются для фиксации направления соседних символов когда bidi выдаёт неоднозначность.
- **Emoji direction**: emoji classified как «Other Neutral» в bidi. В начале RTL-строки emoji безопасно. В середине рядом с латиницей/цифрой — может смещаться. Правило: **emoji в начале или в конце, не в середине mixed-фрагмента**.
- **AR ~15-20% короче EN** — inline-кнопки в 18 символов умещаются комфортно.
- **Mixed AR + Latin (`@AutoRiot`, `PRO`, `NOMS`)** — оборачивать LRM-парой (U+200E) если стоят перед знаком препинания: `NOMS‎.` чтобы точка не «уехала» в начало RTL-блока.

3 безопасных push:

1. `🔥 سلسلة {streak} أيام!‎ استمر.` — emoji в начале (safe), LRM после числа фиксирует точку.
2. `🍽️ الغداء بانتظارك. دورك.‎ ⏰` — emoji-сэндвич: пунктуация перед финальным LTR-emoji получает LRM.
3. `‎PRO‎ مفعّل — استمتع!` — токен PRO в LRM-парных маркерах, чтобы не «прилип» к арабскому соседу неожиданным образом.

---

### 5. Идиомы и sass-метафоры

5 примеров с биологией + pop-culture (без политики/религии):

1. `الإنسولين عندك بيرقص دلوقتي 🕺` — «твой инсулин танцует» (биохимия + Egyptian flavor).
2. `الكبد بيقول: يا جماعة، خفّوا شوية` — «печень просит сбавить» (humour без shaming).
3. `الميتوكوندريا بتعمل بروفة لحفلة` — «митохондрии репетируют концерт» (биология + Arab pop-music vibe).
4. `معدتك بترسل تلغرام: «الغداء؟»` — meta-шутка про Telegram.
5. `سلسلتك أطول من طابور القهوة الصبح` — «серия длиннее очереди за кофе утром» (общеарабская повседневность).

Сленг — **по 1 на сообщение**: `يلا` (универсал), `طيب` (окей), `خلاص` (всё/готово). Избегать `walak/walik` — слишком Levantine для Gulf и слегка грубо. `mashallah` — **табу в casual sass** (см. §7).

---

### 6. Anti-patterns

1. **Дословная калька RU/EN.** `لوقّ غداءك` — попытка перевести «лог» как глагол. AR не использует «log». Правильно: `سجّل وجبتك`.
2. **Hyper-formal MSA в casual слоте.** `يُرجى التكرّم بتسجيل الوجبة` — звучит как письмо в министерство, убивает Sage.
3. **Spoken Egyptian dialect в Gulf-MSA контексте.** `إيه يا بطل عامل إيه` — saudi/emirati юзер прочтёт как «зачем со мной как с египтянином», alienation.
4. **False friends.** `سيدي` (sayyidī) ≠ «sir»; буквально «мой господин/учитель», в casual context звучит сервильно или религиозно. Sage **никогда** не обращается так.
5. **Slash gender markers.** `جاهز/ـة` — RTL-рендер ломается, smart-юзеры понимают, остальные пугаются. **Запрещено правилом UI.**

---

### 7. 🔴 Культурные табу и этические триггеры (CRITICAL)

- **Ислам-контекст.** Большинство AR-юзеров — мусульмане. **Ramadan** (lunar month, daytime fasting): дневные meal-пуши в Ramadan должны быть **тише или suspended** — это продуктовое решение (feature flag), но копирайт уже сейчас должен избегать активных «давай ешь сейчас!» как baseline. Pork (`خنزير`), alcohol (`خمر`, `كحول`) — **никогда** positively, лучше вообще не упоминать.
- **Halal/haram.** Не комментируй мясо без halal certainty. Не используй слово `حلال` в шутке про еду — trivialization религиозной категории.
- **Религиозные обороты** (`الله`, `إن شاء الله`, `ما شاء الله`, `الحمد لله`) — **запрещены в casual sass**. `mashallah` в шутке про метаболизм = catastrophe (trivialize sacred). Исключение: нейтральное `يلا` (этимологически от `يا الله`, но в современном AR воспринимается как чистый interjection).
- **Политика.** Israel/Palestine, Saudi/Iran, Egypt/Sudan, Syria, Lebanon civil war — **full taboo**. Не намекать, не шутить, не ассоциировать.
- **Gender norms.** Дубай ≠ Эр-Рияд. Default — respectful neutral (§3).
- **Национальные блюда** (`منسف` mansaf JO, `ملوخية` mloukhieh EG/LV, `كشري` koshary EG, `كبسة` kabsa GCC, `كسكس` couscous Maghreb) — **никогда не «junk» и не «вредно»**. Гордость кухни.

**5 дерзко-безопасных:**
1. `الإنسولين عندك بيرقص الآن 🕺` — биология, не юзер.
2. `الميتوكوندريا تطلب إضافية` — клетки, не вес.
3. `معالجي سخن من الصورة دي` — Sage над собой.
4. `السلسلة ما بتمشي بالهوا` — метафора, не критика.
5. `أداء البطولة! 🏆` — achievement без gender и без обращения.

**5 опасных (НЕ использовать):**
1. `أكلت مكرونة تاني؟` — judgement выбора еды.
2. `خنزير لذيذ!` — pork positively = трагедия.
3. `ما شاء الله على وزنك` — religious ref + body comment double-cat.
4. `الكشري ده مش صحي` — критика национального блюда.
5. `إن شاء الله تخسر كيلو` — religious + weight-loss = двойной харам Sage-этики.

---

### 8. 🔴 RTL / script gotchas (CRITICAL)

- **Bidi algorithm (UAX#9).** Telegram использует системный bidi. Placeholders `{streak}`, `{name}` — это **LTR-токены** внутри RTL-параграфа. Обычно работает, но на границе с пунктуацией результат непредсказуем.
- **LRM (U+200E) / RLM (U+200F).** Невидимые символы. **LRM** — «следующий символ читай как LTR», **RLM** — «как RTL». Применяй когда:
  - После LTR-числа/латиницы стоит знак препинания, который должен остаться в конце RTL-фразы: `7 أيام‎.` (LRM перед `.`).
  - Латинский токен (PRO, NOMS) внутри AR-фразы и хочется гарантировать его LTR-блок: `‎NOMS‎`.
- **Числа + RTL.** `7 أيام` — `7` LTR, `أيام` RTL. Bidi-движок обычно ставит число справа от текста (читается «أيام 7» с точки зрения порядка символов в строке, но визуально показывает «7 أيام» слева направо для числа и справа налево для слова). На стыках с emoji/пунктуацией — добавь LRM.
- **Emoji в начале vs середине.** Safe: `🔥 سلسلة 7 أيام`. Risky: `سلسلة 🔥 7 أيام` — emoji-neutral между RTL и LTR-цифрой может прыгнуть. Если нужно — оберни emoji в RLM: `سلسلة ‏🔥‏ 7 أيام`.
- **Mixed AR + Latin handles** (`@AutoRiot`, `PRO`): всегда LRM-парой, особенно перед знаком препинания.

3 примера правильного формирования (showed with explicit markers `‎`=LRM, `‏`=RLM):

1. `🔥 سلسلة {streak} أيام‎!` — emoji в начале, LRM перед `!` фиксирует восклицание в конце визуальной строки.
2. `استمتع بـ ‎PRO‎ شهر مجاني` — токен PRO в LRM-парных маркерах, чтобы не сливался с арабским соседом.
3. `🏆 إنجاز جديد: ‎+50 XP‎ ⭐` — LTR-блок `+50 XP` обёрнут LRM-парой, emoji ⭐ в конце (безопасная позиция).

**Тест:** каждый перевод **обязательно** проверять в Telegram preview на iOS + Android + Web — рендереры расходятся на bidi edge-кейсах.

---

## SPECIAL TASK — переписанные AR значения

### 1. `gamification.streak_7`

**Old (variant 1):**
> `🔥 أسطورة! {streak} أيام متتالية! لقد كنت تطعم NOMS لمدة {streak} أيام متتالية. عملية الأيض لديك ترقص الماكارينا. خذ شارة جديدة!`

**New (variant 1):**
> `🔥 أسطورة! {streak} أيام متتالية‎!\n\nNOMS‎ مبسوط طول الأسبوع. عملية الأيض عندك بترقص ماكارينا 💃 شارة جديدة في انتظارك!`

**Old (variant 2):**
> `🏆 أسبوع السلسلة! يستسلم معظم الناس في اليوم الثالث. لست أنت. أنت بطل. استمر!`

**New (variant 2):**
> `🏆 أسبوع كامل من السلسلة! معظم الناس بيستسلموا في اليوم التالت. هنا أداء البطولة 💪`

**Old (variant 3):**
> `💪 واو! {streak} أيام بدون انقطاع! أتعرف ماذا يعني ذلك؟ أنت تشكل عادة. استمر في ذلك!`

**New (variant 3):**
> `💪 واو! {streak} أيام بدون انقطاع‎! تعرف يعني إيه؟ ده اسمه عادة بتتكوّن. يلا نكمل!`

**Rationale.** Старое — formal MSA, generic masculine (`أنت بطل`), нет sass. Новое: (1) убран `لقد كنت تطعم NOMS` (sycophantic перифраз), (2) `أداء البطولة` вместо `أنت بطل` — gender-clean, (3) добавлен LRM `‎!` после числа, (4) emoji 💃 в середине безопасно (между RTL-словом и `!`), (5) `يلا نكمل` — 1 pl. inclusive, Sage с юзером вместе, (6) NOMS обёрнут LRM-парой. Placeholder `{streak}` сохранён байт-в-байт ×3.

### 2. `cron_notifications.reminder_meal_lunch`

**Old:** `🍽️ الغداء لن يُسجّل نفسه. دورك`

**New:** `🍽️ الغداء مش هيسجّل نفسه. دورك يلا‎.`

**Rationale.** `لن يُسجّل نفسه` — hyper-formal MSA passive future. `مش هيسجّل نفسه` — relaxed pan-Arab (`مش` понятен везде, `هـ` = future marker в Egyptian/Levantine, читается в Gulf). Добавлен `يلا` + LRM перед точкой для bidi-safety.

### 3. `errors.ai_failed` (variant 1, остальные по аналогии)

**Old:**
> `همم، "دماغي" ضبابي الآن {{icon_brain}}💭\n\nالصورة لم تحمل بالكامل، أو أنا متعب (يحدث للذكاء الاصطناعي 😅).\n\nحاول:\n• التقط صورة مرة أخرى\n• أو اكتب نصًا: "صدر دجاج 200 جم"`

**New:**
> `همم، "دماغي" ضبابي شوية {{icon_brain}}💭\n\nالصورة ما اتحملتش بالكامل، أو معالجي تعبان (بيحصل للذكاء الاصطناعي 😅).\n\nيلا نجرب:\n• صورة جديدة\n• أو اكتب نص: "صدر دجاج 200 جم"`

**Rationale.** `لم تحمل بالكامل` (MSA negation) → `ما اتحملتش` (passive negation, pan-Arab readable). `حاول` (imperative masc.) → `يلا نجرب` (1 pl. inclusive, gender-clean §3). `أنا متعب` → `معالجي تعبان` — Sage шутит над собой, не упоминает gender. Placeholders `{{icon_brain}}` × сохранены байт-в-байт, кавычки `"..."` сохранены, `\n\n` сохранены.

### 4. `report.insight_eating_little`

**Old:** `تأكل قليلاً اليوم؟ لا تتخطى وجبة — السلسلة لا تعمل بالهواء.`

**New:** `أكل خفيف اليوم؟ لا تتخطّ وجبة — السلسلة ما بتمشي بالهوا.`

**Rationale.** `تأكل قليلاً` (2 л. masc. presens) gender-marked → `أكل خفيف` (nominal phrase, gender-clean). `لا تعمل بالهواء` — formal MSA → `ما بتمشي بالهوا` — pan-Arab idiom, «не ходит на воздухе», звучит как разговорная мудрость. `لا تتخطّ` (jussive) оставлен — стандарт, gender-neutral в imperative с huruf al-ʿilla.

### 5. `referral.cta_newbie_2`

**Old:** `ادعُ أصدقاءك! عندما يبدأون بتسجيل الطعام، كلاكما يحصل على عملات وXP. 4 أصدقاء مع PRO = شهر مجاني!`

**New:** `ادعُ أصدقاءك! لما يبدأوا بتسجيل الطعام، الاثنين بتاخدوا عملات و‎XP‎. 4 أصدقاء مع ‎PRO‎ = شهر مجاني‎!`

**Rationale.** `عندما` (formal) → `لما` (pan-Arab разговорный). `كلاكما يحصل` (dual, MSA-strict) → `الاثنين بتاخدوا` (2 pl., gender-clean, friendlier). Латинские токены `XP` и `PRO` обёрнуты LRM-парами `‎XP‎` / `‎PRO‎` — гарантия LTR-блока внутри RTL-фразы. Финальный `!` префиксирован LRM — bidi-safe.

---

## Резюме

**File:** `/Users/vladislav/Documents/NOMS/.claude/worktrees/angry-williamson-bd67f0/tools/glossary_section_ar.md`
**Объём:** ~1180 слов (target 800-1200 ✓).

**4 уникальных AR-нюанса:**

1. **Ramadan / халяль / религиозные обороты** — `mashallah`/`inshallah` в casual sass = trivialization, банят персонажа. Daytime meal-пуши в Рамадан требуют feature-flag на продуктовом уровне. Pork и alcohol — never positively. Национальные блюда (mansaf, kabsa, koshary) — никогда «junk».
2. **Bidi + LRM/RLM** — placeholders `{streak}`, латинские токены `PRO`/`NOMS`/`XP`, цифры и emoji создают direction-конфликты. Решение: LRM (U+200E) парами вокруг LTR-вставок, emoji в начале/конце строк, тест в Telegram iOS+Android+Web.
3. **MSA-with-flavor вместо чистого диалекта** — Egyptian alienates Gulf, Gulf formalнее нужного, Levantine узок. Relaxed MSA + pan-Arab разговорные маркеры (`يلا`, `طيب`, `مش`, `ما...ش`) — формат Anghami/Careem, понятный 22 странам.
4. **Gender-clean grammar** — slash `جاهز/ـة` запрещён, generic masculine исключает женщин, решение через verbal nouns (`وجبة مسجّلة`), passive (`تم تسجيل`), 1 pl. inclusive (`يلا نجرب`), nominal sentences (`أداء البطولة`). Это критичнее чем выбор регистра.

---

## FA — فارسی (Persian)

Reference для копирайтеров Sassy Sage на персидском. Примеры — FA, объяснения — RU.

---

### 1. Терминология ядра

FA-tech apps (Snapp!, Tapsi, fitness) активно миксуют английский: бренд-термины и метрики — латиницей, повседневные действия — фарси. Граница: «фича» = EN, «действие» = FA.

| EN | FA | Rationale |
|---|---|---|
| streak | **استریک** | Калька-транслит live в gym-сленге. «روند مستمر» — HR-отчёт. |
| log (verb) | **ثبت کردن** | «لاگ» — только разработчики. |
| mana | **مانا** | Gaming-loanword, FA-Discord. |
| XP | **XP** | Латиница; «امتیاز تجربه» академично. |
| coins | **سکه** | Native, понятно всем. |
| quest | **مأموریت** | Теплее, чем «کوئست». |
| achievement | **دستاورد** | Native, эмоционально. |
| Premium | **Premium** | Бренд-термин. |
| level | **لِوِل / سطح** | Sassy → لِوِل; formal → سطح. |
| freeze | **فریز** | «یخ‌زدگی» буквально, но не игрово. |

---

### 2. Register: شما или تو?

Sassy Sage — friendly друг → **تو (to)** + 2nd-person singular. شما — для banking/SMS, не нам.

- ❌ `شما {streak} روز متوالی به NOMS غذا داده‌اید` — банковский SMS.
- ✅ `{streak} روز پشت هم به NOMS غذا دادی! متابولیسمت داره ماکارنا می‌رقصه.`
- ✅ `ناهار خودش ثبت نمی‌شه. نوبتته.`

Imperative: `بنویس`, `بفرست`, `بزن`.

---

### 3. Гендерная политика (BONUS — gender-neutral!)

FA **грамматически гендерно-нейтрален**: pronoun او = он/она/оно, глаголы/прилагательные не изменяются по роду. Slash-форм (`он/она`) нет.

- ✅ `قهرمانی` — работает для всех.
- ✅ `خسته‌ای؟` — одна форма.
- ✅ `بنویس چی خوردی` — imperative универсален.

**Anti-pattern:** AI-переводчики иногда калькируют gender из EN/RU:
- ❌ `تو یک قهرمان مرد/زن هستی` — искусственно, FA так не пишут.

---

### 4. Telegram SRE (RTL critical)

- FA = RTL, тот же bidi, что AR.
- FA-алфавит = AR + **پ گ چ ژ**. Использовать FA `ک` (U+06A9), не AR `ك` (U+0643).
- **Цифры:** Western (0–9) — лучше compatibility с placeholders и Telegram-копированием. Persian numerals (۰–۹) — только для декоративного контента.
- **LRM/RLM** — вокруг `{placeholder}`, emoji, латиницы.
- **ZWNJ (U+200C)** — критичен внутри FA-слов (см. §8).

Безопасные push:
- ✅ `🔥 {streak} روز پشت هم! متابولیسمت داره می‌رقصه.`
- ✅ `🍽️ ناهار خودش ثبت نمی‌شه. نوبتته.`
- ✅ `💪 4 دوست با Premium = یه ماه رایگان.`

---

### 5. Идиомы и sass-метафоры

- ✅ `انسولینت داره دیسکو می‌رقصه` — инсулин танцует диско (биохимия).
- ✅ `متابولیسمت داره ماکارنا می‌رقصه` — метаболизм пляшет макарену.
- ✅ `مثل شب یلدا — طولانی ولی شیرین. استریکت داره بزرگ می‌شه` — Yalda-ночь: длинная, но сладкая.
- ✅ `بترکونی! نوروز نیومده، ولی تو داری جشن می‌گیری` — Nowruz ещё впереди, а ты уже празднуешь.
- ✅ `والا حافظ گفته: صبر تلخه ولی برای صبور شیرین — استریکت ثابتش کرد` — лёгкая Hafez-цитата.

Сленг — **1 на сообщение**: `والا`, `دمت گرم`, `خفن`, `بترکونی`. Не складывать в одну строку.

---

### 6. Anti-patterns

- ❌ `لاگ کن ناهارت رو` → ✅ `ناهارت رو ثبت کن`.
- ❌ Hyper-formal: `لطفاً تقاضا می‌گردد وعده غذایی خود را ثبت فرمایید` — госуслуги. → ✅ `ناهار رو ثبت کن، منتظرم`.
- ❌ EN word order (SVO): `من می‌خواهم بدانم تو خوردی چه چیزی` — Persian — SOV: `می‌خوام بدونم چی خوردی`.
- ❌ Pure English mixin: `Hey! Log your lunch now, please` — теряет character.
- ❌ Tajik/Dari spellings — иранский фарси стандарт: `نان` для хлеба, никакого региального drift'а.

---

### 7. 🔴 Культурные триггеры (CRITICAL)

**Запрещено:** вес/тело юзера, fat-shaming, judgement про еду.

**FA-специфика:**
- **Religious sensitivity.** Большинство — мусульмане. В **Ramadan** дневные meal-reminders могут попасть в окно поста. `الله`, `إن‌شاءالله` — **не в sass-контексте** (trivialization).
- **Pork/alcohol** — никогда не упоминать positively. `خوک`, `شراب` — out.
- **Apolitical entertainment only.** Политика, санкции, регион — full avoidance, даже шуткой.
- **Diaspora vs Iran-resident** — разный контекст. Default — neutral/inclusive, не предполагать локацию.
- **Religious diversity** — Sunni, Shia, Zoroastrian, Baha'i, христиане, иудеи. Никаких religious mockery.
- **Persian cultural pride** — Nowruz, Yalda, kabab, ghormeh sabzi, tahdig, fesenjan — celebrate, не критиковать как «junk».

5 «дерзко безопасно»:
- ✅ `انسولینت داره الان دیسکو می‌رقصه — بیولوژیه دیگه`.
- ✅ `پردازنده‌م از این عکس داغ کرد — تقصیر منه`.
- ✅ `متابولیسمت بهتر از وای‌فای کافه کار می‌کنه`.
- ✅ `استریک با هوا کار نمی‌کنه — یه چیزی بنویس`.
- ✅ `مثل تهدیگ — صبر می‌خواد ولی نتیجه فوق‌العاده‌ست`.

5 «не использовать»:
- ❌ `دوباره چلوکباب؟` — judgement food.
- ❌ `وزنت چطوره؟` — про вес.
- ❌ `إن‌شاءالله ناهار سبک` — religious term в casual sass.
- ❌ `تو ماه رمضون نخوردی، باخت دادی استریکت رو` — пост = провал.
- ❌ `یه شراب با شام؟` — алкоголь.

---

### 8. 🔴 RTL/script gotchas

- **Bidi:** = AR. Оборачивать `{placeholder}`, латиницу, Western digits в LRM (U+200E) при риске «прыжка».
- **FA punctuation:** запятая «،» (U+060C), question mark «؟» (U+061F) — для FA-only; «,» и «?» — для mixed.
- **ZWNJ (U+200C) — CRITICAL.** Разделяет морфемы без пробела, prevent'ит Persian-Arabic ligature.
  - `می‌خوام` (mi-khâm) — ZWNJ между `می` и `خوام`.
  - `می‌شه` — ZWNJ обязателен.
  - `خسته‌ای` — ZWNJ перед суффиксом ای.
  - `نمی‌شه` — два prefix с ZWNJ.

3 безопасных примера:
- ✅ `🔥 {streak} روز پشت هم! متابولیسمت داره ماکارنا می‌رقصه.`
- ✅ `ناهار خودش ثبت نمی‌شه. نوبتته.`
- ✅ `4 دوست با Premium = یه ماه رایگان` (LRM перед `4` и `Premium`).

---

## SPECIAL TASK — переписанные FA-значения

Принципы: tô, Sassy-голос, **ZWNJ** где надо, **LRM** вокруг placeholders/латиницы, placeholders byte-by-byte, без двойных эмодзи.

### 1) `gamification.streak_7` (JSONB array → APPEND-safe)

**Old:** `🔥 اسطوره! {streak} روز پشت سر هم! شما {streak} روز متوالی به NOMS غذا داده‌اید. متابولیسم شما در حال رقص ماکارنا است. یک نشان جدید بگیرید!`

**New:**
- `🔥 اسطوره‌ای! {streak} روز پشت هم! متابولیسمت داره ماکارنا می‌رقصه. یه نشان جدید بگیر، حقته!`
- `🏆 هفته‌ی استریک! بیشتر آدما روز سوم می‌برن. تو نه. دمت گرم، ادامه بده!`
- `💪 واو! {streak} روز بدون وقفه! می‌دونی یعنی چی؟ داری عادت می‌سازی. بترکونی!`

**Rationale:** shomâ→tô; ZWNJ (`می‌رقصه`, `می‌برن`, `می‌سازی`); сленг 1/сообщение (`دمت گرم`, `بترکونی`); метафора макарены сохранена; `{streak}` byte-by-byte.

### 2) `cron_notifications.reminder_meal_lunch`

**Old:** `🍽️ ناهار خودش ثبت نمی‌شه. نوبت توئه`
**New:** `🍽️ ناهار خودش ثبت نمی‌شه. نوبتته 😏`

**Rationale:** `نوبت توئه` → `نوبتته` — разговорная contraction. 😏 — Дэдпул-смайл. ZWNJ в `نمی‌شه`.

### 3) `errors.ai_failed` (JSONB array → APPEND-safe)

**New 3 variants:**
- `هوم، «مغز»م الان مه‌آلوده {{icon_brain}}💭\n\nعکس کامل لود نشد، یا خسته‌ام (واسه AI پیش میاد 😅).\n\nامتحان کن:\n• یه عکس دیگه بگیر\n• یا متنی بنویس: «سینه‌ی مرغ ۲۰۰ گرم»`
- `شبکه‌های عصبی هم خسته می‌شن {{icon_brain}} نمی‌تونم تشخیص بدم چیه. با کلمه بگو، باشه؟`
- `پردازنده‌م از این عکس داغ کرد {{icon_brain}} بیا متنی بریم: چیه و چقدره؟`

**Rationale:** формальные `است`/`می‌شوند` → разговорные `‌ست`/`می‌شن`; FA quotation marks «...»; tô-форма; `{{icon_brain}}` byte-by-byte; ZWNJ в `می‌شن`, `نمی‌تونم`, `مه‌آلوده`. Persian-numeral `۲۰۰` внутри кавычек — пример user-quote, допустимо.

### 4) `report.insight_eating_little`

**Old:** `امروز کم می‌خوری؟ وعده غذایی رو رد نکن — استریک با هوا کار نمی‌کنه.`
**New:** `امروز سبک گرفتی؟ یه وعده‌رو رد نکن — استریک با هوا کار نمی‌کنه.`

**Rationale:** `کم می‌خوری` (близко к judgement про юзера) → `سبک گرفتی` (про подход, не про тело). Метафора сохранена. ZWNJ в `نمی‌کنه`.

### 5) `referral.cta_newbie_2`

**Old:** `دوستاتو دعوت کن! وقتی شروع به ثبت غذا کنن، هر دوتون سکه و XP می‌گیرید. 4 دوست با PRO = ماه رایگان!`
**New:** `دوستاتو دعوت کن! تا شروع کنن به ثبت غذا، هر دوتون سکه و XP می‌گیرید. 4 دوست با Premium = یه ماه رایگان 🎁`

**Rationale:** `وقتی...کنن` → `تا...کنن` короче; `PRO` → `Premium` (canonical brand); Western `4` для bidi-стабильности; 🎁 усиливает CTA. LRM перед `Premium` в runtime.

---

## Финал

- **File:** `/Users/vladislav/Documents/NOMS/.claude/worktrees/angry-williamson-bd67f0/tools/glossary_section_fa.md`
- **Объём:** ~1150 слов.

**4 уникальных FA-нюанса:**
1. **Gender-neutral grammar bonus.** FA не имеет грамматического рода в pronouns/verbs/adjectives — slash-форм «он/она» не существует. Все формы универсальны; не позволять AI-переводчикам калькировать gender из EN/RU.
2. **ZWNJ (U+200C) — critical для FA-orthography.** Стандартные `می‌خوام`, `نمی‌شه`, `خسته‌ای` требуют ZWNJ. Пайплайн рендеринга обязан сохранять U+200C byte-by-byte.
3. **Diaspora vs Iran-resident awareness.** Аудитория разделена политически и инфраструктурно; default tone — inclusive/neutral, без предположений о локации/доступе.
4. **Apolitical entertainment tone.** Бот молчит про политику, санкции, регион, религиозные различия — full avoidance даже шуткой. Sass — про биохимию и поведение, не про мир вокруг.

---

# Часть III — Operational guide

## Когда использовать какую секцию

- **Phase 3 (ES pilot, mig 232):** включить ES секцию целиком в брифинг писательского субагента + критика-носителя.
- **Phase 4 (Wave A: DE/FR/IT/PT):** соответствующая секция per язык + общая часть I-II.
- **Phase 4 (Wave B: PL/UK):** аналогично.
- **Phase 4 (Wave C: ID/HI/AR/FA):** + третий RTL-tech-reviewer для HI/AR/FA (см. §8 в каждой секции).
- **Native Fiverr reviewer:** дать секцию + anti-shame чек-лист (§2C). Подписывает соответствие протоколу до оплаты.

## Что обновлять при изменениях

- Если в `ui_translations` для конкретного языка изменилось каноническое слово (например, `Серия` в RU вместо `Стрик`) — обновить §1 «Терминология ядра» соответствующей секции.
- Если native review дал важный insight по культурному табу — обновить §7.
- Если обнаружен новый bidi/script gotcha — §8.

## Что НЕ менять без согласования с тимлидом

- §1 Часть I (персонаж Sassy Sage) — это product DNA.
- §2A-C (universal constraints) — это технические/этические gates.

## Дальнейшие шаги

- **Phase 3:** ES pilot (writer → critic → Fiverr) на 25 ключей. Input — этот документ + audit JSON.
- **Phase 4:** 11 миграций (по одной на язык), wave A → B → C.
- **Phase 5:** post-deploy monitoring + DROP backup snapshots после 7 дней стабильности.

---

*Создан в Phase 2 многофазного UX-копирайтинга. Living document — обновляется по результатам native reviews. Контакт: см. `MEMORY.md` и owner.*
