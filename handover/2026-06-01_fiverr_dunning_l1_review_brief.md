---
title: "Fiverr L1 native-review brief — Dunning d7/d3/d1 + buttons + plan_name (7 langs)"
aliases: [fiverr-dunning-review-brief, dunning-l1-handover-2026-06-01]
tags: [translations, copywriter, handover, fiverr, payment, dunning]
created: 2026-06-01
owner: sharkovvlad
status: open
---

# Fiverr L1 Native-Review Brief — Dunning Translations

**Scope.** 7 languages × 10 translation keys = **70 strings** to be reviewed by native-speaker copywriters on Fiverr. Current values in production are Opus-4.7-generated L1 (mig 402 + mig 409); they pass the algorithmic Sage-tone checks but have NOT had native-speaker sign-off.

**Why a handover rather than another LLM pass.** Adding a second Opus iteration on top of an Opus translation is illusion-of-progress — the same model with the same priors. Native sign-off on Fiverr (~$15-30 per language) gives independent linguistic judgement: idiomaticity, regional register, grammatical-gender bypass naturalness, anti-shame tone in-context — all of which an LLM can fake convincingly but cannot self-verify.

**Two priority tiers:**
1. **L1 native review (priority — likely largest quality lift):** AR, FA, HI, PL.
2. **Sign-off only (already passed prior copywriter pipeline):** ID, PT, UK.

**Total estimated spend:** ~$120-180 across 7 sellers if ordered separately, or ~$80-120 if you find a multilingual translator covering 2-3 of the related langs (rare). Recommend hiring 7 distinct native sellers — each is the only person you trust for that language.

---

## 0. What you (owner) need to do

For each of the 7 languages:

1. **Find a Fiverr seller** filtered by: "Translation", "<Language> Native", "Marketing copywriting" or "App localization". Avoid generic translators — you want copywriters, not literal translators.
2. **Send them the per-language packet** from §3 below (English context block + table of 10 current values). The packet is self-contained — paste it as the order brief.
3. **Deliverable format** (see §4): they return a JSON or markdown table with `proposed_value` and `reasoning` per row.
4. **Quality check:** open the deliverable, sanity-check that placeholders `{expires_date_localized}` and `{streak_days}` are preserved verbatim. Spot-check 2-3 strings against the brief criteria.
5. **Apply** via mig 416 (template in §5). Test with `pytest tests/crons/test_subscription_dunning_pl_plural.py` (PL only — others have no plural runtime).

Estimated turnaround per language: 24-72h depending on seller.

---

## 1. Universal brief — paste into every Fiverr order (English)

> The buyer (you) shows this block to every seller — it sets the context and tone bar identically across languages. Below is the **exact text to copy/paste**, between the fenced lines.

````
Hi! I need a NATIVE-SPEAKER QUALITY REVIEW of 10 short marketing-UX strings translated into <YOUR LANGUAGE> by an AI model. Your job is to verify that each string sounds like a real native speaker wrote it — natural, idiomatic, in the right register, with no grammatical errors and no awkward calques.

PROJECT: NOMS is a Telegram bot for food tracking with AI photo recognition and gamification (XP / streaks / coins). The bot character is called "Sage" — a witty mentor who teases users about their biology (insulin, cortisol, microbiome) but NEVER about their body or their food choices. Tone: 70% playful Jester (like Duolingo's owl), 20% Deadpool 4th-wall breaks ("yes, I'm an AI"), 10% wise therapist. ANTI-SHAME is non-negotiable: errors are data, not failures; the user is always on the bot's side.

THESE 10 STRINGS are subscription-renewal reminders ("Dunning" reminders sent 7 days, 3 days, and 1 day before Premium expires) plus 3 short button labels and 4 short plan-name labels. They appear in Telegram chat (mobile-first).

STRICT RULES — please check ALL of these:

1. ANTI-SHAME: no fat-shaming, no body-shaming, no "you should have done X". The user MAY lose access to features or break their logging streak — describe the LOSS neutrally, never as the user's fault.
2. PLACEHOLDERS: any text in curly braces like `{expires_date_localized}` or `{streak_days}` MUST stay exactly as-is, in Latin braces. Do not translate the braces or the word inside.
3. NO TRANSLITERATION of the English word "streak". Use the natural <YOUR LANGUAGE> equivalent (e.g. "series", "chain of days").
4. GENDER-NEUTRAL: the bot does not know the user's gender. Avoid 2nd-person past tense or adjectives that require masculine / feminine agreement. Prefer impersonal / passive / 1st-person-bot constructions.
5. TELEGRAM SIZE LIMITS:
   - Inline buttons: max 18 visual characters in Latin scripts / max 12 in Devanagari or Arabic.
   - Reminder messages: max ~12 lines on a mobile screen, ~35 chars per line before line break.
6. KEEP THE BRAND WORDS in English: "Premium", "NomsCoins", "AI", "Telegram". Do not translate them.
7. EMOJI at the start of each reminder (💎 🕯 ⏳ 🔄 🚀) stays as-is.

DELIVERABLE: return a markdown table or JSON with 4 columns per row: `key`, `current_value` (what I gave you), `proposed_value` (your improved version, or leave equal to current if you'd ship it as-is), `reasoning` (1–2 sentences: what you changed and why, OR why you'd ship as-is).

If you would ship a string AS-IS with no change, please still write a 1-sentence reasoning confirming that — that is also valuable feedback.
````

---

## 2. Reference — English & Russian canonical versions (for tone calibration)

Sellers reviewing the target language should NOT translate from English — they should review the existing target-language draft against the EN / RU canonical tone. Provide EN + RU as tone anchors only.

### English (canonical L1, written by NOMS team)

| key | value |
|---|---|
| `dunning_d7` | 💎 7 days until your Premium turns into a pumpkin.<br>On {expires_date_localized}, access expires. Your personalized metabolic plan will lose unlimited food logs and AI photo recognition. Don't leave your microbiome guessing. Renew in one tap? ↓ |
| `dunning_d3` | ⏳ 3 days until Premium features shut down.<br>Want to know what hurts? Breaking your {streak_days}-day streak and losing accumulated NomsCoins. Tracking macros without AI context gets twice as hard. Let's save your progress, shall we? |
| `dunning_d1` | 🕯 Tomorrow is your last Premium day.<br>Your history is perfectly safe, but your AI nutrition sage goes into energy-saving mode. No deep insights into insulin or cortisol, just dry numbers. Don't drop out of the zone! |
| `dunning_btn_renew` | 🔄 Renew Premium |
| `dunning_btn_activate` | 🚀 Activate Premium |
| `dunning_btn_decline` | I'll pass, thanks |
| `plan_name_monthly` | Monthly |
| `plan_name_quarterly` | 3 Months |
| `plan_name_yearly` | Year |
| `plan_name_trial` | Trial |

### Russian (canonical L1, written by NOMS team)

| key | value |
|---|---|
| `dunning_d7` | 💎 Через 7 дней твой Premium превратится в тыкву.<br>{expires_date_localized} доступ закроется, и твой персональный метаболический план лишится безлимита логов и ИИ-анализа по фото. Твоему микробиому и нервам будет не хватать моих подсказок. Продлим по красоте в один тап? ↓ |
| `dunning_d3` | ⏳ Осталось 3 дня до отключения Premium-функций.<br>Знаешь, что самое обидное? Прерывать свою серию из {streak_days} дней в ударе и терять накопленные NomsCoins. Без ИИ-анализа удерживать фокус на макросах станет в два раза сложнее. Сохраним твой прогресс? |
| `dunning_d1` | 🕯 Завтра последний день Premium.<br>Подписка закроется. Твой дневник питания останется в целости, но ИИ-нутрициолог уйдёт в спячку. Никаких глубоких инсайтов про инсулин и кортизол, только сухие цифры. Возвращайся в строй! |
| `dunning_btn_renew` | 🔄 Продлить Premium |
| `dunning_btn_activate` | 🚀 Активировать Premium |
| `dunning_btn_decline` | Я уйду, спасибо за всё |
| `plan_name_monthly` | Месяц |
| `plan_name_quarterly` | 3 месяца |
| `plan_name_yearly` | Год |
| `plan_name_trial` | Триал |

---

## 3. Per-language review packets

Each subsection below is a self-contained packet to paste into the Fiverr order for that language. The seller does NOT need the rest of this document — only their own packet + the §1 universal brief.

### 3.1 AR — Arabic (MSA with light Egyptian colour)

- **Tier:** L1 native review (priority)
- **Suggested Fiverr fee:** ~$20-30
- **Script & technical notes:** RTL. Inside templates, the placeholder `{expires_date_localized}` and `{streak_days}` MUST stay in Latin braces — do NOT translate them. Verify LRM (U+200E) / RLM (U+200F) markers if any Latin number appears mid-sentence so digits do not flip orientation.
- **Tone anchor:** Sage-like wisdom, light irony. Do NOT use Quran/Hadith references in marketing copy (religious offence risk). Avoid Egyptian-only slang that Maghreb readers will not catch.
- **Gender bypass:** Arabic has grammatical gender. Prefer impersonal / 1st-person bot constructions over 2nd-person past-tense that requires masculine vs. feminine endings (the user gender is unknown).

**Strings under review (current production values, Opus-generated L1):**

| key | current value | seller notes (length budget) |
|---|---|---|
| `dunning_d7` | 💎 بعد ٧ أيام، Premium الخاص بك سيتحول إلى يقطينة.<br>في {expires_date_localized} سيُغلق الوصول. خطتك الأيضية الشخصية ستفقد التسجيل غير المحدود وتحليل الصور بالذكاء الاصطناعي. لا تترك ميكروبيومك يخمّن في الفراغ. نجدّد بضغطة واحدة؟ ↓ | d7 reminder — 7 days before expiry. Length budget ≤ 350 chars; will be sent as standalone Telegram message. Contains `{expires_date_localized}` (e.g. «25 июня 2026») which IS pre-rendered by code before send; DO NOT translate the braces. |
| `dunning_d3` | ⏳ ٣ أيام تفصلك عن إيقاف ميزات Premium.<br>أتعرف ما الأقسى؟ كسر سلسلتك المتواصلة منذ {streak_days} يومًا وخسارة NomsCoins المتراكمة. تتبّع الماكروز بدون سياق الذكاء الاصطناعي يصبح أصعب بالضعف. نحفظ تقدّمك؟ | d3 reminder — 3 days before expiry. ≤ 350 chars. Contains `{streak_days}` placeholder (integer count of consecutive logging days). For PL, code wraps this with babel plural; for other langs, the «day» word follows the placeholder directly — make sure grammatical agreement with the user-streak number works for typical values (1, 5, 22). |
| `dunning_d1` | 🕯 غدًا آخر يوم لك مع Premium.<br>يومياتك الغذائية في أمان، لكن حكيم التغذية بالذكاء الاصطناعي سيدخل في وضع السكون. لا رؤى عميقة عن الإنسولين أو الكورتيزول، أرقام جافة فقط. عُد إلى الإيقاع! | d1 reminder — last day. ≤ 280 chars. No dynamic placeholders. |
| `dunning_btn_renew` | 🔄 تجديد Premium | Inline button: "Renew Premium" (active sub about to expire). MAX 18 visual chars (Latin) / 12 visual chars (Arabic / Devanagari). Emoji 🔄 leads. |
| `dunning_btn_activate` | 🚀 تفعيل Premium | Inline button: "Activate Premium" (trial about to end). Same length budget as above. Emoji 🚀 leads. |
| `dunning_btn_decline` | لا، شكرًا على كل شيء | Inline button: "I'll pass, thanks" — graceful opt-out, no shame. No emoji. ≤ 24 chars. |
| `plan_name_monthly` | شهر واحد | Short plan label: "1 month". Appears as plan title in payment screens. ≤ 15 chars. |
| `plan_name_quarterly` | ٣ أشهر | Short plan label: "3 months". ≤ 15 chars. |
| `plan_name_yearly` | سنة واحدة | Short plan label: "1 year". ≤ 15 chars. |
| `plan_name_trial` | تجريبي | Short plan label: "Trial". ≤ 15 chars. |

---

### 3.2 FA — Persian / Farsi

- **Tier:** L1 native review (priority)
- **Suggested Fiverr fee:** ~$20-30
- **Script & technical notes:** RTL. Use ZWNJ (U+200C) for prefixes like «می‌خواهم», «می‌شه», «نمی‌توانم». Without ZWNJ the text renders broken on iOS Telegram. Keep `{expires_date_localized}` / `{streak_days}` placeholders in Latin braces (do NOT translate).
- **Tone anchor:** Sage tone works well in Persian — natural fit. AVOID political / Iranian regime references. Apolitical and diaspora-friendly.
- **Gender bypass:** Persian has NO grammatical gender in verbs — natural advantage. Use this freely; no special bypass needed.

**Strings under review (current production values, Opus-generated L1):**

| key | current value | seller notes (length budget) |
|---|---|---|
| `dunning_d7` | 💎 ۷ روز دیگر Premium شما به کدو تنبل تبدیل می‌شود.<br>در تاریخ {expires_date_localized} دسترسی بسته می‌شود. برنامه متابولیک شخصی‌تان ثبت نامحدود و تحلیل عکس با هوش مصنوعی را از دست می‌دهد. میکروبیومتان را در حدس و گمان رها نکنید. با یک تپ تمدید کنیم؟ ↓ | d7 reminder — 7 days before expiry. Length budget ≤ 350 chars; will be sent as standalone Telegram message. Contains `{expires_date_localized}` (e.g. «25 июня 2026») which IS pre-rendered by code before send; DO NOT translate the braces. |
| `dunning_d3` | ⏳ ۳ روز تا خاموش شدن قابلیت‌های Premium باقی مانده.<br>می‌دانید چه چیزی واقعاً سخت است؟ شکستن زنجیره {streak_days} روزه و از دست دادن NomsCoins انباشته. ردیابی ماکروها بدون هوش مصنوعی دو برابر دشوارتر می‌شود. پیشرفت‌تان را ذخیره کنیم؟ | d3 reminder — 3 days before expiry. ≤ 350 chars. Contains `{streak_days}` placeholder (integer count of consecutive logging days). For PL, code wraps this with babel plural; for other langs, the «day» word follows the placeholder directly — make sure grammatical agreement with the user-streak number works for typical values (1, 5, 22). |
| `dunning_d1` | 🕯 فردا آخرین روز Premium شماست.<br>دفتر غذایی‌تان دست‌نخورده می‌ماند، اما حکیم تغذیه هوش مصنوعی به حالت کم‌مصرف می‌رود. دیگر بینش عمیق درباره انسولین یا کورتیزول نیست، فقط اعداد خشک. به ریتم برگردید! | d1 reminder — last day. ≤ 280 chars. No dynamic placeholders. |
| `dunning_btn_renew` | 🔄 تمدید Premium | Inline button: "Renew Premium" (active sub about to expire). MAX 18 visual chars (Latin) / 12 visual chars (Arabic / Devanagari). Emoji 🔄 leads. |
| `dunning_btn_activate` | 🚀 فعال‌سازی Premium | Inline button: "Activate Premium" (trial about to end). Same length budget as above. Emoji 🚀 leads. |
| `dunning_btn_decline` | نه، ممنون از همه چیز | Inline button: "I'll pass, thanks" — graceful opt-out, no shame. No emoji. ≤ 24 chars. |
| `plan_name_monthly` | ۱ ماه | Short plan label: "1 month". Appears as plan title in payment screens. ≤ 15 chars. |
| `plan_name_quarterly` | ۳ ماه | Short plan label: "3 months". ≤ 15 chars. |
| `plan_name_yearly` | ۱ سال | Short plan label: "1 year". ≤ 15 chars. |
| `plan_name_trial` | آزمایشی | Short plan label: "Trial". ≤ 15 chars. |

---

### 3.3 HI — Hindi (Devanagari)

- **Tier:** L1 native review (priority)
- **Suggested Fiverr fee:** ~$15-25
- **Script & technical notes:** Devanagari counts as ~1.3 char in Telegram button width — keep inline buttons short (≤12 visual chars). Mixed Devanagari + Latin (Hinglish) is OK and common. Telegram brand name «Telegram» stays Latin.
- **Tone anchor:** Vegetarian-friendly default. NEVER reference chicken/mutton/pork as a default food image — use paneer, dal, samosa, kheer instead. Avoid religious caste markers entirely.
- **Gender bypass:** Hindi has grammatical gender. The current value «आपका {streak_days} दिन का सिलसिला» treats «सिलसिला» as masculine — VERIFY this is the correct grammatical gender (m. — सिलसिला is masculine, OK). For verbs, prefer impersonal forms over 2nd-person past tense.

**Strings under review (current production values, Opus-generated L1):**

| key | current value | seller notes (length budget) |
|---|---|---|
| `dunning_d7` | 💎 ७ दिनों में आपका Premium कद्दू में बदल जाएगा।<br>{expires_date_localized} को एक्सेस बंद हो जाएगा। आपका पर्सनलाइज़्ड मेटाबॉलिक प्लान अनलिमिटेड लॉग्स और AI फोटो रिकग्निशन खो देगा। अपने माइक्रोबायोम को अंधेरे में मत छोड़िए। एक टैप में रिन्यू करें? ↓ | d7 reminder — 7 days before expiry. Length budget ≤ 350 chars; will be sent as standalone Telegram message. Contains `{expires_date_localized}` (e.g. «25 июня 2026») which IS pre-rendered by code before send; DO NOT translate the braces. |
| `dunning_d3` | ⏳ Premium फीचर्स बंद होने में सिर्फ ३ दिन बचे हैं।<br>सबसे बुरा क्या है पता है? आपका {streak_days} दिन का सिलसिला टूटना और जमा NomsCoins खोना। AI के बिना मैक्रोज़ ट्रैक करना दोगुना मुश्किल हो जाएगा। प्रोग्रेस सेव कर लें? | d3 reminder — 3 days before expiry. ≤ 350 chars. Contains `{streak_days}` placeholder (integer count of consecutive logging days). For PL, code wraps this with babel plural; for other langs, the «day» word follows the placeholder directly — make sure grammatical agreement with the user-streak number works for typical values (1, 5, 22). |
| `dunning_d1` | 🕯 कल आपका आखिरी Premium दिन है।<br>आपकी फूड डायरी सुरक्षित रहेगी, लेकिन आपका AI न्यूट्रिशन सेज एनर्जी-सेविंग मोड में चला जाएगा। इंसुलिन और कॉर्टिसोल पर कोई गहरी इनसाइट नहीं, बस सूखे आँकड़े। फिर से लय में आइए! | d1 reminder — last day. ≤ 280 chars. No dynamic placeholders. |
| `dunning_btn_renew` | 🔄 Premium रिन्यू करें | Inline button: "Renew Premium" (active sub about to expire). MAX 18 visual chars (Latin) / 12 visual chars (Arabic / Devanagari). Emoji 🔄 leads. |
| `dunning_btn_activate` | 🚀 Premium एक्टिवेट करें | Inline button: "Activate Premium" (trial about to end). Same length budget as above. Emoji 🚀 leads. |
| `dunning_btn_decline` | नहीं, सब के लिए धन्यवाद | Inline button: "I'll pass, thanks" — graceful opt-out, no shame. No emoji. ≤ 24 chars. |
| `plan_name_monthly` | १ महीना | Short plan label: "1 month". Appears as plan title in payment screens. ≤ 15 chars. |
| `plan_name_quarterly` | ३ महीने | Short plan label: "3 months". ≤ 15 chars. |
| `plan_name_yearly` | १ साल | Short plan label: "1 year". ≤ 15 chars. |
| `plan_name_trial` | ट्रायल | Short plan label: "Trial". ≤ 15 chars. |

---

### 3.4 PL — Polish

- **Tier:** L1 native review (priority)
- **Suggested Fiverr fee:** ~$20-30
- **Script & technical notes:** Latin script, LTR, no special markers. PLURAL FOR {streak_days} IS HANDLED IN CODE — Python helper (`babel.plural`) picks «1 dzień» vs «5 dni» at runtime. Reviewer should LEAVE the template literal as `{streak_days} dni` (the «dni» is the trigger fragment for runtime replacement). If you change «dni» to e.g. «dnia», the runtime code will no-op and fall back to bare digit substitution.
- **Tone anchor:** Sage-tone works in Polish; informal «ty» (tu-form), NOT «pan/pani». Use «logować» = sign-in only (NOT for food log) — for food tracking use «zapisać» / «notować».
- **Gender bypass:** Polish has grammatical gender. AVOID slash forms like «zrobiłeś/aś» — they look like government forms. Prefer impersonal: «zostało zapisane», «kolacja zapisana». 1st-person bot is also fine.

**Strings under review (current production values, Opus-generated L1):**

| key | current value | seller notes (length budget) |
|---|---|---|
| `dunning_d7` | 💎 Za 7 dni Twój Premium zamieni się w dynię.<br>{expires_date_localized} dostęp wygaśnie. Twój spersonalizowany plan metaboliczny straci nielimitowane logi i analizę zdjęć AI. Nie zostawiaj mikrobiomu w niepewności. Przedłużymy jednym dotknięciem? ↓ | d7 reminder — 7 days before expiry. Length budget ≤ 350 chars; will be sent as standalone Telegram message. Contains `{expires_date_localized}` (e.g. «25 июня 2026») which IS pre-rendered by code before send; DO NOT translate the braces. |
| `dunning_d3` | ⏳ Zostały 3 dni do wyłączenia funkcji Premium.<br>Wiesz, co boli najbardziej? Przerwanie serii {streak_days} dni i utrata zebranych NomsCoins. Śledzenie makro bez AI staje się dwa razy trudniejsze. Zapiszemy Twój postęp? | d3 reminder — 3 days before expiry. ≤ 350 chars. Contains `{streak_days}` placeholder (integer count of consecutive logging days). For PL, code wraps this with babel plural; for other langs, the «day» word follows the placeholder directly — make sure grammatical agreement with the user-streak number works for typical values (1, 5, 22). |
| `dunning_d1` | 🕯 Jutro ostatni dzień Premium.<br>Twój dziennik żywieniowy pozostaje nietknięty, ale Twój mędrzec AI przechodzi w tryb oszczędzania. Żadnych głębokich wglądów w insulinę czy kortyzol, tylko suche liczby. Wracaj do rytmu! | d1 reminder — last day. ≤ 280 chars. No dynamic placeholders. |
| `dunning_btn_renew` | 🔄 Przedłuż Premium | Inline button: "Renew Premium" (active sub about to expire). MAX 18 visual chars (Latin) / 12 visual chars (Arabic / Devanagari). Emoji 🔄 leads. |
| `dunning_btn_activate` | 🚀 Aktywuj Premium | Inline button: "Activate Premium" (trial about to end). Same length budget as above. Emoji 🚀 leads. |
| `dunning_btn_decline` | Rezygnuję, dzięki | Inline button: "I'll pass, thanks" — graceful opt-out, no shame. No emoji. ≤ 24 chars. |
| `plan_name_monthly` | 1 miesiąc | Short plan label: "1 month". Appears as plan title in payment screens. ≤ 15 chars. |
| `plan_name_quarterly` | 3 miesiące | Short plan label: "3 months". ≤ 15 chars. |
| `plan_name_yearly` | 1 rok | Short plan label: "1 year". ≤ 15 chars. |
| `plan_name_trial` | Próbny | Short plan label: "Trial". ≤ 15 chars. |

---

### 3.5 ID — Indonesian (Bahasa Indonesia)

- **Tier:** Sign-off only (L1 already done)
- **Suggested Fiverr fee:** ~$10-15
- **Script & technical notes:** Latin script. Mixed Indonesian + English OK in casual register. «Premium», «AI», «NomsCoins» stay English (brand / technical).
- **Tone anchor:** Casual «kamu» register. Halal-safe defaults (avoid pork as food image). The current «runtun» is the verified streak-equivalent (from «beruntun» pattern).
- **Gender bypass:** Indonesian has NO grammatical gender — natural advantage. No bypass needed.

**Strings under review (current production values, Opus-generated L1):**

| key | current value | seller notes (length budget) |
|---|---|---|
| `dunning_d7` | 💎 7 hari lagi Premium-mu berubah jadi labu.<br>Pada {expires_date_localized} akses ditutup. Rencana metabolik personalmu kehilangan log tanpa batas dan analisis foto AI. Jangan biarkan mikrobiom-mu menebak-nebak. Perpanjang sekali tap? ↓ | d7 reminder — 7 days before expiry. Length budget ≤ 350 chars; will be sent as standalone Telegram message. Contains `{expires_date_localized}` (e.g. «25 июня 2026») which IS pre-rendered by code before send; DO NOT translate the braces. |
| `dunning_d3` | ⏳ Tinggal 3 hari sebelum fitur Premium dimatikan.<br>Tahu apa yang paling menyakitkan? Memutus runtun {streak_days} hari-mu dan kehilangan NomsCoins yang sudah terkumpul. Tracking makro tanpa AI jadi dua kali lebih sulit. Kita simpan progresmu? | d3 reminder — 3 days before expiry. ≤ 350 chars. Contains `{streak_days}` placeholder (integer count of consecutive logging days). For PL, code wraps this with babel plural; for other langs, the «day» word follows the placeholder directly — make sure grammatical agreement with the user-streak number works for typical values (1, 5, 22). |
| `dunning_d1` | 🕯 Besok hari terakhir Premium-mu.<br>Diari makanmu tetap aman, tapi sage nutrisi AI-mu masuk mode hemat energi. Tidak ada insight mendalam soal insulin atau kortisol, hanya angka kering. Kembali ke ritme! | d1 reminder — last day. ≤ 280 chars. No dynamic placeholders. |
| `dunning_btn_renew` | 🔄 Perpanjang Premium | Inline button: "Renew Premium" (active sub about to expire). MAX 18 visual chars (Latin) / 12 visual chars (Arabic / Devanagari). Emoji 🔄 leads. |
| `dunning_btn_activate` | 🚀 Aktifkan Premium | Inline button: "Activate Premium" (trial about to end). Same length budget as above. Emoji 🚀 leads. |
| `dunning_btn_decline` | Lewati, terima kasih | Inline button: "I'll pass, thanks" — graceful opt-out, no shame. No emoji. ≤ 24 chars. |
| `plan_name_monthly` | 1 Bulan | Short plan label: "1 month". Appears as plan title in payment screens. ≤ 15 chars. |
| `plan_name_quarterly` | 3 Bulan | Short plan label: "3 months". ≤ 15 chars. |
| `plan_name_yearly` | 1 Tahun | Short plan label: "1 year". ≤ 15 chars. |
| `plan_name_trial` | Trial | Short plan label: "Trial". ≤ 15 chars. |

---

### 3.6 PT — Portuguese (Brazilian focus — pt-BR primary)

- **Tier:** Sign-off only (L1 already done)
- **Suggested Fiverr fee:** ~$15-25
- **Script & technical notes:** Latin script. Brazilian PT is the primary target (DAU concentrated there). Avoid PT-PT-specific lexemes («frigorífico» → use «geladeira»; «pequeno-almoço» → «café da manhã»; «autocarro» → «ônibus»).
- **Tone anchor:** Casual «você». NEVER critique national foods (feijoada, açaí, brigadeiro, pão de queijo). Avoid race-loaded idioms («a coisa tá preta», «criado-mudo», «lista negra»). No football-club references (Flamengo vs Corinthians = toxic rivalry zone).
- **Gender bypass:** PT-BR has grammatical gender. AVOID slash forms. Prefer passive («pasto registrado»), 1st-person bot, or invariants («fera», «galera»).

**Strings under review (current production values, Opus-generated L1):**

| key | current value | seller notes (length budget) |
|---|---|---|
| `dunning_d7` | 💎 Em 7 dias seu Premium vira abóbora.<br>No dia {expires_date_localized} o acesso encerra. Seu plano metabólico personalizado perde os registros ilimitados e o reconhecimento por foto via IA. Não deixe seu microbioma no escuro. Renovamos num toque? ↓ | d7 reminder — 7 days before expiry. Length budget ≤ 350 chars; will be sent as standalone Telegram message. Contains `{expires_date_localized}` (e.g. «25 июня 2026») which IS pre-rendered by code before send; DO NOT translate the braces. |
| `dunning_d3` | ⏳ Faltam 3 dias para as funções Premium desligarem.<br>Sabe o que dói de verdade? Quebrar sua sequência de {streak_days} dias e perder os NomsCoins acumulados. Rastrear macros sem IA fica duas vezes mais difícil. Salvamos seu progresso? | d3 reminder — 3 days before expiry. ≤ 350 chars. Contains `{streak_days}` placeholder (integer count of consecutive logging days). For PL, code wraps this with babel plural; for other langs, the «day» word follows the placeholder directly — make sure grammatical agreement with the user-streak number works for typical values (1, 5, 22). |
| `dunning_d1` | 🕯 Amanhã é seu último dia Premium.<br>Seu diário alimentar fica intacto, mas seu sábio nutricionista IA entra em modo de economia. Sem insights profundos sobre insulina ou cortisol, só números secos. Volte ao ritmo! | d1 reminder — last day. ≤ 280 chars. No dynamic placeholders. |
| `dunning_btn_renew` | 🔄 Renovar Premium | Inline button: "Renew Premium" (active sub about to expire). MAX 18 visual chars (Latin) / 12 visual chars (Arabic / Devanagari). Emoji 🔄 leads. |
| `dunning_btn_activate` | 🚀 Ativar Premium | Inline button: "Activate Premium" (trial about to end). Same length budget as above. Emoji 🚀 leads. |
| `dunning_btn_decline` | Vou passar, obrigado | Inline button: "I'll pass, thanks" — graceful opt-out, no shame. No emoji. ≤ 24 chars. |
| `plan_name_monthly` | 1 mês | Short plan label: "1 month". Appears as plan title in payment screens. ≤ 15 chars. |
| `plan_name_quarterly` | 3 meses | Short plan label: "3 months". ≤ 15 chars. |
| `plan_name_yearly` | 1 ano | Short plan label: "1 year". ≤ 15 chars. |
| `plan_name_trial` | Trial | Short plan label: "Trial". ≤ 15 chars. |

---

### 3.7 UK — Ukrainian

- **Tier:** Sign-off only (L1 already done)
- **Suggested Fiverr fee:** ~$15-25
- **Script & technical notes:** Cyrillic, LTR. NO transliteration of «streak» → «стрік» (use «серія» / «днів в ударі» instead). The current value uses «серія … днів в ударі» — verified compliant.
- **Tone anchor:** War-blackout post-2022: AVOID metaphors with «фронт», «атака», «оборона», «штурм». Anti-russianism: read aloud and flag any phrasing that sounds like a Russian loanword (e.g. «чуть» → «трохи», «получити» → «отримати»).
- **Gender bypass:** Ukrainian has grammatical gender. AVOID gendered past-tense for the user. Prefer passive («підписку оновлено»), 1st-person bot, or imperative.

**Strings under review (current production values, Opus-generated L1):**

| key | current value | seller notes (length budget) |
|---|---|---|
| `dunning_d7` | 💎 Через 7 днів твій Premium перетвориться на гарбуз.<br>{expires_date_localized} доступ закриється, і твій персональний метаболічний план втратить безліміт логів та ШІ-аналіз по фото. Твоєму мікробіому й нервам бракуватиме моїх підказок. Продовжимо в один тап? ↓ | d7 reminder — 7 days before expiry. Length budget ≤ 350 chars; will be sent as standalone Telegram message. Contains `{expires_date_localized}` (e.g. «25 июня 2026») which IS pre-rendered by code before send; DO NOT translate the braces. |
| `dunning_d3` | ⏳ Залишилось 3 дні до відключення Premium-функцій.<br>Знаєш, що найприкріше? Перервати свою серію з {streak_days} днів в ударі й втратити накопичені NomsCoins. Без ШІ-аналізу тримати фокус на макросах стане вдвічі складніше. Збережемо твій прогрес? | d3 reminder — 3 days before expiry. ≤ 350 chars. Contains `{streak_days}` placeholder (integer count of consecutive logging days). For PL, code wraps this with babel plural; for other langs, the «day» word follows the placeholder directly — make sure grammatical agreement with the user-streak number works for typical values (1, 5, 22). |
| `dunning_d1` | 🕯 Завтра останній день Premium.<br>Підписка закриється. Твій щоденник харчування залишиться в цілості, але ШІ-нутриціолог піде у сплячку. Жодних глибоких інсайтів про інсулін і кортизол, лише сухі цифри. Повертайся у стрій! | d1 reminder — last day. ≤ 280 chars. No dynamic placeholders. |
| `dunning_btn_renew` | 🔄 Продовжити Premium | Inline button: "Renew Premium" (active sub about to expire). MAX 18 visual chars (Latin) / 12 visual chars (Arabic / Devanagari). Emoji 🔄 leads. |
| `dunning_btn_activate` | 🚀 Активувати Premium | Inline button: "Activate Premium" (trial about to end). Same length budget as above. Emoji 🚀 leads. |
| `dunning_btn_decline` | Я піду, дякую за все | Inline button: "I'll pass, thanks" — graceful opt-out, no shame. No emoji. ≤ 24 chars. |
| `plan_name_monthly` | 1 місяць | Short plan label: "1 month". Appears as plan title in payment screens. ≤ 15 chars. |
| `plan_name_quarterly` | 3 місяці | Short plan label: "3 months". ≤ 15 chars. |
| `plan_name_yearly` | 1 рік | Short plan label: "1 year". ≤ 15 chars. |
| `plan_name_trial` | Тріал | Short plan label: "Trial". ≤ 15 chars. |

---

## 4. Deliverable JSON spec (alternative to markdown table)

If the seller prefers JSON, they should return ONE file per language with this shape:

```json
{
  "lang": "ar",
  "reviewer_native_speaker": true,
  "reviewer_country": "EG",
  "reviewed_at": "2026-06-15",
  "strings": [
    {
      "key": "dunning_d7",
      "current_value": "💎 بعد ٧ أيام، Premium الخاص بك سيتحول إلى يقطينة. …",
      "proposed_value": "💎 خلال ٧ أيام، اشتراك Premium الخاص بك سينتهي. …",
      "reasoning": "Replaced «سيتحول إلى يقطينة» (literal pumpkin reference confuses non-Cinderella-familiar readers) with the neutral «سينتهي». Kept emoji and placeholders intact."
    }
  ]
}
```

Placeholders MUST be byte-identical in `current_value` and `proposed_value` — owner will diff to catch accidental drift.

---

## 5. Apply template — mig 416 (one migration covers all 7 langs)

When you have all 7 review packets back, draft `migrations/416_dunning_native_l1_polish_7_langs.sql` modelled on `migrations/409_dunning_l1_copyrighting_7_langs.sql`. Same structure, same POST-VERIFY DO-block (no EN-literal collisions). Apply via psycopg2; auto-deploy after merge.

Skeleton:

```sql
-- 416_dunning_native_l1_polish_7_langs.sql
-- Native-speaker polish of dunning + plan_name × 7 langs (AR/FA/HI/PL priority,
-- ID/PT/UK sign-off). Replaces Opus-generated mig 409 L1 with reviewer-signed-off
-- versions. POST-VERIFY identical to mig 409.
BEGIN;
-- ... 7 sections × 10 UPDATEs each = 70 statements (paste reviewer values)
-- POST-VERIFY: no EN-literal collisions + NULL check (copy from mig 409)
COMMIT;
```

Reviewer values that match the existing prod value verbatim → ship-as-is, no UPDATE needed for that key. Track those in PR description.

---

## 6. Acceptance criteria for the handover closure

- [ ] All 7 review packets returned by Fiverr sellers.
- [ ] Owner sanity-check: each packet preserves `{expires_date_localized}` and `{streak_days}` placeholders byte-identical to current.
- [ ] Owner sanity-check: no slash-gendered forms (`zrobiłeś/aś`, `pronto/a`) introduced.
- [ ] Owner sanity-check: no Russian-sounding constructions in UK (read aloud, listen for «чуть», «получити», «понять» calques).
- [ ] Mig 416 applied LIVE, POST-VERIFY passes.
- [ ] PR description lists ship-as-is keys per language (signal of how confident reviewer was).
- [ ] `daily/YYYY-MM-DD.md` records: how many keys changed per language, what archetype of changes (regional register, idiom, gender bypass).
- [ ] MEMORY.md «Open / для следующего агента» watchlist item «🟡 Fiverr native L1 review» REMOVED.
- [ ] This handover archived: move to `claude-memory-compiler/handover/_archive/` after closure.

---

## Related KB

- [[concepts/copywriter-playbook]] — canonical entry point for any translation session.
- [[concepts/sassy-sage-multilingual-glossary]] — per-language tone, register, anti-pattern reference (11 langs, including all 7 here).
- [[concepts/l1-cultural-sanity-brief]] — review checklist used by previous L1 rounds (Phase 4 cultural localization, mig 232-251).
- [[concepts/agent-collaboration-protocol]] — Rule 9: when L1 vs L2 vs no-review per severity tier.
- `migrations/402_sage_dunning_d7_d3_d1_trial_merge.sql` — original RU/EN/DE/ES/FR/IT L1 (canonical tone baseline).
- `migrations/409_dunning_l1_copyrighting_7_langs.sql` — current Opus-L1 for the 7 langs in this handover (the values being reviewed).
- `crons/subscription_lifecycle.py:_send_renewal_reminders` — runtime render code (PL plural uses babel; other langs do plain replace).