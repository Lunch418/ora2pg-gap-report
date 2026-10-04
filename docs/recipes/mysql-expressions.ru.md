*[English](mysql-expressions.md) | Русский*

# Выражения MySQL: LIMIT, LAST_INSERT_ID, DATE_FORMAT, ENUM, SET

Покрывает: GAP-075 (`mysql_limit_comma`), GAP-079 (`mysql_last_insert_id`),
GAP-081 (`mysql_date_format`), GAP-069
(`mysql_on_update_current_timestamp`), GAP-068 (`mysql_enum_type`),
GAP-086 (`mysql_set_type`).

## Проблема

Шесть форм MySQL, которые `ora2pg -m` копирует без изменений, коверкает
или конвертирует наполовину. Каждую легко исправить вручную, если знать,
чего ждёт PostgreSQL.

## LIMIT смещение, количество

```sql
CREATE TABLE items (id integer PRIMARY KEY, name text NOT NULL);
INSERT INTO items SELECT g, 'item ' || g FROM generate_series(1, 20) AS g;

DO $$
BEGIN
    -- MySQL: SELECT id FROM items ORDER BY id LIMIT 10, 5
    ASSERT (SELECT array_agg(id) FROM (SELECT id FROM items ORDER BY id LIMIT 5 OFFSET 10) s)
           = ARRAY[11, 12, 13, 14, 15];
END $$;
```

Числа меняются местами: `LIMIT 10, 5` из MySQL - это `LIMIT 5 OFFSET 10`.
Форму `LIMIT 5 OFFSET 10` (MySQL её тоже понимает) менять не нужно.

## LAST_INSERT_ID() -> RETURNING

```sql
CREATE TABLE notes (id serial PRIMARY KEY, body text NOT NULL);

DO $$
DECLARE
    v_id integer;
BEGIN
    -- INSERT INTO notes (body) VALUES ('x'); SET v_id = LAST_INSERT_ID();
    INSERT INTO notes (body) VALUES ('x') RETURNING id INTO v_id;
    ASSERT v_id = 1;
    -- ближайшая замена один к одному, если INSERT менять нельзя:
    ASSERT lastval() = 1;
END $$;
```

`lastval()` возвращает последнее значение любой последовательности в
сессии, включая ту, что использовал триггер, и падает, если ни одной ещё не
пользовались. `RETURNING` точен.

## DATE_FORMAT -> to_char

`ora2pg` превращает `DATE_FORMAT(d, fmt)` в пару в скобках без имени
функции, так что запрос возвращает строку таблицы вместо текста, и часть
спецификаторов оставляет непереведёнными (GAP-081). Пишите `to_char` с
шаблоном PostgreSQL:

```sql
DO $$
DECLARE
    d timestamp := '2026-03-07 14:05:09';
BEGIN
    -- DATE_FORMAT(d, '%Y-%m-%d %H:%i:%s')
    ASSERT to_char(d, 'YYYY-MM-DD HH24:MI:SS') = '2026-03-07 14:05:09';
    -- DATE_FORMAT(d, '%e %M %Y, %W')
    ASSERT to_char(d, 'FMDD FMMonth YYYY, FMDay') = '7 March 2026, Saturday';
    -- DATE_FORMAT(d, '%h:%i %p')
    ASSERT to_char(d, 'HH12:MI AM') = '02:05 PM';
END $$;
```

| MySQL | `to_char` | MySQL | `to_char` |
|---|---|---|---|
| `%Y` | `YYYY` | `%H` | `HH24` |
| `%y` | `YY` | `%h`, `%I` | `HH12` |
| `%m` | `MM` | `%i` | `MI` |
| `%c` | `FMMM` | `%s`, `%S` | `SS` |
| `%d` | `DD` | `%p` | `AM` |
| `%e` | `FMDD` | `%f` | `US` |
| `%M` | `FMMonth` | `%j` | `DDD` |
| `%b` | `Mon` | `%W` | `FMDay` |
| `%a` | `Dy` | `%%` | `%` |

`FM` убирает выравнивание: без него `Month` дополняется пробелами до
девяти символов, как в Oracle. `STR_TO_DATE(s, fmt)` - это
`to_timestamp(s, шаблон)` с той же таблицей.

## ON UPDATE CURRENT_TIMESTAMP -> триггер

```sql
CREATE TABLE profiles (
    id         integer PRIMARY KEY,
    name       text NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now()   -- часть DEFAULT остаётся
);

CREATE FUNCTION touch_updated_at()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    -- MySQL сдвигает столбец, только если строка действительно изменилась
    IF NEW IS DISTINCT FROM OLD THEN
        NEW.updated_at := clock_timestamp();
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER profiles_touch
    BEFORE UPDATE ON profiles
    FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

INSERT INTO profiles VALUES (1, 'old', '2000-01-01');
UPDATE profiles SET name = 'old';   -- без изменений: отметка остаётся
DO $$
BEGIN
    ASSERT (SELECT updated_at FROM profiles) = '2000-01-01';
END $$;
UPDATE profiles SET name = 'new';
DO $$
BEGIN
    ASSERT (SELECT updated_at FROM profiles) > '2000-01-01';
END $$;
```

Функция универсальная: одна на базу и по триггеру на каждую таблицу, где
был `ON UPDATE CURRENT_TIMESTAMP`. Берите `clock_timestamp()`, если каждая
строка должна получить время своей записи, и `now()`, если все строки
транзакции должны получить время её начала (MySQL берёт время команды -
посередине между ними).

## ENUM: создать тип, про который забыл ora2pg

Для каждого столбца `ENUM` `ora2pg` придумывает тип `<таблица>_<столбец>_t`
и использует его в таблице, но `CREATE TYPE` так и не пишет (GAP-068).
Самое маленькое исправление - добавить ровно эту команду перед таблицей:

```sql
-- MySQL: status ENUM('new', 'paid', 'shipped') NOT NULL DEFAULT 'new'
CREATE TYPE orders_status_t AS ENUM ('new', 'paid', 'shipped');

CREATE TABLE orders (
    id     serial PRIMARY KEY,
    status orders_status_t NOT NULL DEFAULT 'new'
);
INSERT INTO orders (status) VALUES ('shipped'), ('new');

DO $$
BEGIN
    -- сортировка в порядке объявления, как в MySQL
    ASSERT (SELECT array_agg(status::text ORDER BY status) FROM orders) = ARRAY['new', 'shipped'];
END $$;
```

Значения берите из `CREATE TABLE` в MySQL: в сгенерированном файле их уже
нет. Два отличия от MySQL: недопустимое значение - ошибка (MySQL в
нестрогом режиме сохраняет `''`), а добавить значение позже можно через
`ALTER TYPE ... ADD VALUE`, удалить же - только создав новый тип. Если
список часто меняется, `text` с `CHECK (status IN (...))` развивать проще.

## SET -> массив с проверкой

Столбец `SET('a','b',...)` `ora2pg` делает обычным `text`, и принимается
любая строка (GAP-086). Массив сохраняет и несколько значений, и проверку:

```sql
CREATE TABLE posts (
    id   integer PRIMARY KEY,
    tags text[] NOT NULL DEFAULT '{}'
         CHECK (tags <@ ARRAY['news', 'tech', 'sport'])   -- SET('news','tech','sport')
);
INSERT INTO posts VALUES (1, ARRAY['news', 'tech']);

DO $$
BEGIN
    -- FIND_IN_SET('tech', tags) > 0
    ASSERT (SELECT 'tech' = ANY (tags) FROM posts WHERE id = 1);
    BEGIN
        INSERT INTO posts VALUES (2, ARRAY['gossip']);
        RAISE EXCEPTION 'неизвестное значение принято';
    EXCEPTION WHEN check_violation THEN
        NULL;  -- так и должно быть
    END;
END $$;
```

Существующие данные приходят текстом вида `'news,tech'`; при загрузке
преобразуйте их через `string_to_array(value, ',')`.
