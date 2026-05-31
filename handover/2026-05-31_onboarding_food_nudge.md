# Handover — Onboarding food nudge («доделай профиль» после пробного распознавания)

**From:** агент angry-liskov, 2026-05-31. **Status:** копи готов + утверждён owner (вариант 1 «метаболический»). Триггер НЕ реализован (требует food-path работы — отдельный фокус).

## Что это
Незарегистрированный юзер (status `new`/`registration_step_*`) может пробовать распознавание еды (намеренно, owner: вовлечение). После пробы — мягкий НЕблокирующий nudge: «доделай профиль, подгоню калории под метаболизм». БЕЗ слова «стрик/серия» (owner-правило).

## Копи (утверждён owner, вариант 1) — 13 языков, СЫРЫЕ эмодзи
Ключ (предложение): `messages.onboarding_food_nudge` (string, не массив).

- **ru:** 👀 Еду я разложил на атомы, но пока не знаю, кого кормлю! Заверши настройку профиля, и я подгоню математику калорий лично под твой метаболизм.
- **en:** 👀 I broke this food down to atoms, but I still don't know who I'm feeding! Finish your profile so I can tailor the calorie math exactly to your metabolism.
- **ar:** 👀 فكّكتُ هذا الطعام إلى ذرّاته، لكنّي ما زلتُ لا أعرف مَن أُطعِم! أكمِل إعداد ملفك الشخصي كي أضبط حسابات السعرات تماماً وفق أيضك.
- **de:** 👀 Dieses Essen habe ich in seine Atome zerlegt, weiß aber noch nicht, wen ich da füttere! Profil fertig einrichten, dann passe ich die Kalorienmathematik genau an deinen Stoffwechsel an.
- **es:** 👀 Desmenucé esta comida hasta sus átomos, ¡pero aún no sé a quién alimento! Completa tu perfil y ajusto las calorías a tu metabolismo.
- **fa:** 👀 این غذا را تا اتم‌هایش تجزیه کردم، اما هنوز نمی‌دانم چه‌کسی را تغذیه می‌کنم! نمایه را کامل کن تا حساب کالری را دقیقاً با سوخت‌وساز بدنت تنظیم کنم.
- **fr:** 👀 J'ai décomposé ce plat jusqu'aux atomes, mais j'ignore encore qui je nourris ! Complète ton profil et j'ajuste les calories à ton métabolisme.
- **hi:** 👀 इस खाने को मैंने परमाणुओं तक तोड़ डाला, पर अब भी पता नहीं किसे खिला रहा हूँ! प्रोफ़ाइल पूरी करो, फिर कैलोरी का हिसाब ठीक तुम्हारे मेटाबॉलिज़्म के मुताबिक बैठा दूँगा।
- **id:** 👀 Makanan ini sudah kuurai sampai ke atom, tapi aku masih belum tahu siapa yang kuberi makan! Lengkapi profilmu, biar hitungan kalori kupaskan tepat ke metabolismemu.
- **it:** 👀 Ho scomposto questo cibo fino agli atomi, ma non so ancora chi sto nutrendo! Completa il profilo e taro le calorie sul tuo metabolismo.
- **pl:** 👀 Rozłożyłem to jedzenie na atomy, ale wciąż nie wiem, kogo karmię! Dokończ konfigurację profilu, a dopasuję matematykę kalorii dokładnie do twojego metabolizmu.
- **pt:** 👀 Decompus esta comida até aos átomos, mas ainda não sei quem alimento! Conclui o perfil e ajusto as calorias ao teu metabolismo.
- **uk:** 👀 Цю їжу я розклав на атоми, та досі не знаю, кого годую! Заверши налаштування профілю, і я підлаштую математику калорій саме під твій метаболізм.

## Триггер — план реализации (TODO)
1. **Где показывается еда незарегам?** Router: food-текст/фото на `registration_step_*`/`new` → target `ai`. НО `handle_ai_input` (handlers/food_log.py) gated webhook'ом `_try_authoritative_path` для status `registered`+`editing_meal` (см. docstring food_log.py:497). **Сначала проверить:** идёт ли еда незарегов в Python `handle_ai_input` или форвардится в n8n `03_AI_Engine`. От этого зависит точка вставки. (webhook_server.py ~1556-1620, target=='ai' ветка.)
2. **Точка вставки:** после успешного рендера food-карточки, если `ctx.status` ∈ онбординг → добавить вторым сообщением nudge (`messages.onboarding_food_nudge`). Через `resolve_translation_text(ctx, 'messages.onboarding_food_nudge')` + отдельный send (как toast).
3. **Once-логика:** owner просил «после пары распознаваний» / неблокирующе. Показать 1 раз → нужен флаг. Варианты: новая колонка `users.onboarding_nudge_shown` BOOL DEFAULT FALSE (set TRUE после показа; сбрасывать в reset_to_onboarding!), ИЛИ показывать каждое N-е. Рекомендация: once-флаг, проще и не назойливо.
4. **Кнопка?** Вероятно НЕ нужна — юзер продолжает онбординг следующим действием/`/start`. Если нужна CTA — отдельный cmd. Решить с owner.
5. **Деплой:** food handler — код → нужен деплой.
6. **i18n:** добавить ключ × 13 (копи выше) миграцией `migrations/NNN_*.sql` (JSONB string, не массив; jsonb_set per-lang; verify SELECT).
7. **Тесты:** synthetic незарег юзер + food → nudge показан 1 раз; registered юзер → НЕ показан; после reset флаг сброшен.

## Связанное
mig HEAD 401. KB copywriter-playbook. Не путать с food-trial-gate (отменён, open trial). MEMORY current state.
