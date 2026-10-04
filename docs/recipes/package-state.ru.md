*[English](package-state.md) | Русский*

# Переменные пакета и контексты приложения

Покрывает: GAP-036 (`package_state`), GAP-015 (`context_object`).

## Проблема

Переменная или константа, объявленная в начале пакета, живёт всю сессию и
общая для всех подпрограмм пакета. В PostgreSQL пакетов нет; `ora2pg`
эмулирует переменную пользовательской настройкой
(`set_config('pkg.var', ...)` / `current_setting('pkg.var')`). Идея
верная, но сгенерированные вызовы падают: значение передаётся без
приведения к `text`, а чтение переменной, которую ещё никто не задал,
вызывает ошибку вместо `NULL` (GAP-036). Контекст приложения
(`CREATE CONTEXT`, `SYS_CONTEXT`, `DBMS_SESSION.SET_CONTEXT`) пропадает
молча (GAP-015), а вместе с ним и защита на уровне строк, которая на нём
держалась.

## Переменные сессии, которые ведут себя как переменные пакета

По одной функции чтения и одной функции записи на переменную, названных по
пакету: они прячут от вызывающего кода и имя настройки, и её текстовый тип.

```sql
CREATE FUNCTION pkg_ctx_set_user(p_id bigint)
RETURNS void
LANGUAGE sql
AS $$
    -- false: значение живёт всю сессию, как переменная пакета.
    SELECT set_config('pkg_ctx.g_user_id', p_id::text, false);
$$;

CREATE FUNCTION pkg_ctx_get_user()
RETURNS bigint
LANGUAGE sql
STABLE
AS $$
    -- true: missing_ok, незаданная переменная читается как NULL, как в Oracle.
    -- NULLIF: заданная и потом сброшенная настройка читается как '', а не NULL.
    SELECT NULLIF(current_setting('pkg_ctx.g_user_id', true), '')::bigint;
$$;

DO $$
BEGIN
    ASSERT pkg_ctx_get_user() IS NULL;      -- в этой сессии ещё не задавали
    PERFORM pkg_ctx_set_user(42);
    ASSERT pkg_ctx_get_user() = 42;
END $$;
```

Два исправления относительно вывода `ora2pg`: `::text` в функции записи и
`current_setting(..., true)` с `NULLIF` в функции чтения. В имени
настройки нужна точка (`pkg_ctx.g_user_id`); часть до неё можно выбрать
любую, а имя пакета не даёт разным пакетам пересечься.

### Константы

Константа пакета - это не состояние. Функция, возвращающая значение, так
и говорит, и PostgreSQL может её встроить:

```sql
CREATE FUNCTION pkg_ctx_c_max_retries()
RETURNS integer
LANGUAGE sql
IMMUTABLE
AS $$ SELECT 3 $$;

DO $$
BEGIN
    ASSERT pkg_ctx_c_max_retries() = 3;
END $$;
```

### Коллекции и записи

Настройка хранит только текст. Коллекцию или запись уровня пакета либо
сериализуйте (`jsonb` в настройку и обратно, годится для нескольких
значений), либо держите во временной таблице, которая так же принадлежит
сессии, как переменная пакета. См. [временные таблицы](temporary-tables.ru.md).

### Пулы соединений

Переменная пакета принадлежит сессии Oracle. С пулом соединений одну сессию
PostgreSQL по очереди используют многие клиенты, и значение, заданное
через `set_config(..., false)`, достаётся следующему. Два безопасных
способа:

- задавать значение в начале каждой транзакции с `is_local = true`
  (`set_config('pkg_ctx.g_user_id', '42', true)` или `SET LOCAL`), чтобы
  оно исчезало при коммите; это работает и с PgBouncer в режиме транзакций;
- или сбрасывать его, когда соединение возвращается в пул (`RESET ALL`
  или `DISCARD ALL`, большинство пулов умеют делать это сами).

## Контексты приложения и защита на уровне строк

`SYS_CONTEXT('hr_ctx', 'tenant_id')` читает такое же значение: сопоставьте
его настройке, названной по контексту.

```pgsql
-- Oracle: SYS_CONTEXT('hr_ctx', 'tenant_id')
NULLIF(current_setting('hr_ctx.tenant_id', true), '')
```

**Разница, которая важна для безопасности:** контекст Oracle может менять
только пакет, указанный в `CREATE CONTEXT ... USING`. Настройку PostgreSQL
любая сессия меняет командой `SET`. Если на контексте держалась политика
VPD, одной настройки мало: пользователь сам выберет себе арендатора.
Привяжите политику к тому, что пользователь изменить не может, например к
его роли:

```sql
CREATE TABLE tenants_by_role (role_name name PRIMARY KEY, tenant_id integer NOT NULL);
CREATE TABLE documents (doc_id integer PRIMARY KEY, tenant_id integer NOT NULL, body text);
INSERT INTO documents VALUES (1, 10, 'ours'), (2, 20, 'theirs');

-- DBMS_RLS.ADD_POLICY -> политика защиты на уровне строк
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON documents
    USING (tenant_id = (SELECT t.tenant_id FROM tenants_by_role t WHERE t.role_name = current_user));

CREATE ROLE recipe_app_user;
GRANT SELECT ON documents, tenants_by_role TO recipe_app_user;
INSERT INTO tenants_by_role VALUES ('recipe_app_user', 10);

SET ROLE recipe_app_user;
DO $$
BEGIN
    -- политика показывает только своего арендатора, что бы пользователь ни задал через SET
    PERFORM set_config('hr_ctx.tenant_id', '20', true);
    ASSERT (SELECT array_agg(doc_id) FROM documents) = ARRAY[1];
END $$;
RESET ROLE;
```

Если арендатора действительно нужно выбирать на сессию (одна роль базы на
всё приложение), задавайте его из функции `SECURITY DEFINER`, которая
проверяет, что вызывающему это разрешено, а политика пусть читает
настройку. Пользователь, который может выполнять произвольный SQL, всё
равно сделает `SET`, так что это подходит только приложениям, которые
никогда не отдают соединение с базой конечному пользователю.

Суперпользователи и владелец таблицы обходят защиту на уровне строк, если у
таблицы нет `ALTER TABLE ... FORCE ROW LEVEL SECURITY`; проверяйте политики
под ролью самого приложения, как выше.
