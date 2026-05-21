# visible_condition gotcha — пишет только из public.users

> **Канонический pattern для UI conditional buttons.** Lesson 2026-05-21 (mig 300).

## Симптом

Кнопка в `ui_screen_buttons` с `visible_condition='<some-cond>'` молча скипается для всех юзеров. Никаких ошибок в логах юзера. Если убрать condition — кнопка появляется.

## Корень

`render_screen` SQL для evaluation `visible_condition` собирает:

```sql
EXECUTE 'SELECT (' || cond || ')::boolean FROM public.users u WHERE u.telegram_id = $1'
```

Это означает:

1. **Только колонки `public.users`** доступны как идентификаторы. Любое `bare_word` пытается resolve как `users.bare_word`.
2. Если bare_word не существует — `psycopg2.errors.UndefinedColumn`.
3. `render_screen` ловит этот EXCEPTION и просто **скипает кнопку** (RAISE WARNING).

Никакого пути business_data в visible_condition нет. Даже если экран имеет `business_data_rpc`, его результат **не виден** condition'у.

## Антипример

Mig 219 (my_subscription cancel button):
```sql
INSERT INTO ui_screen_buttons (..., visible_condition, meta)
VALUES (..., 'can_cancel', '{"save_rpc": "cancel_subscription"}'::jsonb);
```

Намерение автора: `can_cancel` это поле в business_data (через `get_subscription_business_data` RPC).
Результат: `SELECT (can_cancel)::boolean FROM users u WHERE telegram_id=$1` → UndefinedColumn → кнопка молча скрыта **полтора месяца**.

Никаких индикаторов кроме того что юзер сообщил «нет кнопки отмены».

## Канонический pattern (mig 300)

Создать SQL function принимающую `p_telegram_id` и делающую SELECT сама:

```sql
CREATE OR REPLACE FUNCTION public.user_has_renewable_sub(p_tid bigint)
RETURNS boolean
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path TO 'public'
AS $$
    SELECT EXISTS (
        SELECT 1 FROM public.user_subscriptions
        WHERE telegram_id = p_tid
          AND status = 'active'
          AND cancelled_at IS NULL
          AND payment_method != 'trial'
    )
$$;
```

Тогда visible_condition:
```sql
visible_condition = 'public.user_has_renewable_sub(u.telegram_id)'
```

EXECUTE генерирует `SELECT (public.user_has_renewable_sub(u.telegram_id))::boolean FROM users u WHERE telegram_id=$1`. Функция вызвана, internal SELECT отрабатывает, condition корректно эвалится.

## Прецеденты

- **Mig 276 (safety pill)** уже использовал этот pattern: `visible_condition='public.has_active_safety_guards(u.telegram_id)'`. Работало.
- **Mig 219 (my_subscription cancel)** ДО mig 300 этого pattern не знал → bug 1.5 месяца до launch test.

## Defensive practice

При написании condition:

1. **Если ссылается на колонку `users`** — write `u.<col>`, не bare word. Пример: `u.subscription_status = 'premium'`.
2. **Если ссылается на business_data / другую таблицу** — обязательно через SQL function `<name>(p_telegram_id bigint) returns boolean STABLE`.
3. **Тест pre-deploy:** `SELECT (<cond>) FROM users u WHERE telegram_id=<known_tid>` через psycopg2. Если падает с UndefinedColumn — fix перед applying.

## See also

- [[concepts/headless-architecture]] — full ui_screens / ui_screen_buttons / render_screen modeling
- daily/2026-05-21.md секция «Payment P0 launch blockers» — incident report
