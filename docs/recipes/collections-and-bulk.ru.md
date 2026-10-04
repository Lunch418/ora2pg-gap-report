*[English](collections-and-bulk.md) | Русский*

# Коллекции и массовые операции: массивы и SQL над множествами

Покрывает: GAP-003 (`bulk_collect`), GAP-021 (`collection_type`), GAP-041
(`multiset_operator`), GAP-054 (`table_collection`).

## Проблема

У коллекций PL/SQL (`TABLE OF`, `VARRAY`, `INDEX BY`) и построенных на них
массовых операций (`BULK COLLECT INTO`, `FORALL`) нет аналога в PL/pgSQL, и
`ora2pg` копирует их как есть: тело не компилируется (GAP-003). Тип уровня
схемы `CREATE TYPE ... AS TABLE OF` исчезает без следа, и каждая таблица,
которая его использовала, не загружается (GAP-021). `TABLE(коллекция)`,
`MULTISET`, `MEMBER OF` и `SUBMULTISET OF` копируются без изменений
(GAP-054, GAP-041).

В PostgreSQL те же задачи решают две вещи: **обычный SQL над всем
множеством**, если коллекция была только способом обработать строки
пачкой, и **массивы**, если коллекция действительно является значением.

## Сначала: обойтись без коллекции

Большая часть кода с `BULK COLLECT` + `FORALL` появилась потому, что
построчный PL/SQL был медленным. Исходник Oracle:

```plsql
DECLARE
    TYPE t_ids IS TABLE OF orders.order_id%TYPE;
    v_ids t_ids;
BEGIN
    SELECT order_id BULK COLLECT INTO v_ids
    FROM orders WHERE status = 'CLOSED';

    FORALL i IN 1 .. v_ids.COUNT
        INSERT INTO orders_archive SELECT * FROM orders WHERE order_id = v_ids(i);
    FORALL i IN 1 .. v_ids.COUNT
        DELETE FROM orders WHERE order_id = v_ids(i);
END;
```

В PostgreSQL обе операции делает одна команда, атомарно и быстрее
любого цикла:

```sql
CREATE TABLE orders (
    order_id integer PRIMARY KEY,
    status   text NOT NULL,
    amount   numeric NOT NULL
);
CREATE TABLE orders_archive (LIKE orders);
INSERT INTO orders VALUES (1, 'OPEN', 10), (2, 'CLOSED', 20), (3, 'CLOSED', 30);

CREATE PROCEDURE archive_closed_orders()
LANGUAGE sql
AS $$
    WITH moved AS (
        DELETE FROM orders WHERE status = 'CLOSED'
        RETURNING *
    )
    INSERT INTO orders_archive SELECT * FROM moved;
$$;

CALL archive_closed_orders();

DO $$
BEGIN
    ASSERT (SELECT count(*) FROM orders) = 1;
    ASSERT (SELECT sum(amount) FROM orders_archive) = 50;
END $$;
```

`DELETE ... RETURNING` внутри `WITH` передаёт удалённые строки в `INSERT`:
ни переменной, ни цикла, ни второго прохода по таблице.

## Когда коллекция - значение: массивы

Если коду действительно нужен список в переменной (его передают дальше,
проверяют, наращивают в цикле), используйте массив:

```sql
CREATE FUNCTION closed_order_ids()
RETURNS integer[]
LANGUAGE plpgsql
AS $$
DECLARE
    v_ids integer[];          -- TYPE t_ids IS TABLE OF ...; v_ids t_ids;
BEGIN
    SELECT array_agg(order_id ORDER BY order_id)   -- BULK COLLECT INTO
    INTO v_ids
    FROM orders_archive;

    IF cardinality(v_ids) > 0 THEN                 -- v_ids.COUNT
        RAISE NOTICE 'первый %, последний %',
            v_ids[1],                              -- v_ids(1), v_ids.FIRST
            v_ids[cardinality(v_ids)];             -- v_ids(v_ids.LAST)
    END IF;

    v_ids := v_ids || 99;                          -- v_ids.EXTEND; v_ids(v_ids.LAST) := 99
    RETURN v_ids;
END;
$$;

CREATE PROCEDURE reopen(p_ids integer[])
LANGUAGE plpgsql
AS $$
BEGIN
    -- FORALL i IN 1 .. p_ids.COUNT UPDATE ... WHERE order_id = p_ids(i)
    UPDATE orders_archive SET status = 'REOPENED' WHERE order_id = ANY (p_ids);
END;
$$;

CALL reopen(closed_order_ids());

DO $$
BEGIN
    ASSERT closed_order_ids() = ARRAY[2, 3, 99];
    ASSERT (SELECT count(*) FROM orders_archive WHERE status = 'REOPENED') = 2;
END $$;
```

| PL/SQL | PL/pgSQL |
|---|---|
| `TYPE t IS TABLE OF x` / `VARRAY(n) OF x` | `x[]` |
| `BULK COLLECT INTO v` | `SELECT array_agg(col ORDER BY ...) INTO v` |
| `v.COUNT` | `cardinality(v)` (0 для пустого массива; для `NULL` будет `NULL`) |
| `v(i)` | `v[i]` (с единицы, как в PL/SQL) |
| `v.FIRST` / `v.LAST` | `array_lower(v, 1)` / `array_upper(v, 1)` |
| `v.EXTEND; v(v.LAST) := x` | `v := v \|\| x` |
| `v.DELETE` | `v := '{}'` |
| `FORALL i IN ... DML ... v(i)` | одна DML-команда с `= ANY (v)` или `unnest(v)` |
| `FOR i IN 1 .. v.COUNT LOOP` | `FOREACH x IN ARRAY v LOOP` |
| `TABLE OF orders%ROWTYPE` | `orders[]`, заполняется через `array_agg(o)` из `orders o` |

`array_agg` по пустому набору строк возвращает `NULL`, а не пустой массив.
Пишите `coalesce(array_agg(...), '{}')` там, где дальше код берёт
`cardinality` и сравнивает результат с `0`.

## Типы коллекций уровня схемы

`CREATE TYPE phone_list AS VARRAY(3) OF varchar2(20)` превращается в домен
над массивом, который сохраняет ограничение размера, как в Oracle:

```sql
CREATE DOMAIN phone_list AS varchar(20)[]
    CHECK (cardinality(VALUE) <= 3);

CREATE TABLE customers (
    customer_id integer PRIMARY KEY,
    phones      phone_list
);
INSERT INTO customers VALUES (1, ARRAY['+1 555 0100', '+1 555 0101']);

DO $$
BEGIN
    BEGIN
        INSERT INTO customers VALUES (2, ARRAY['1', '2', '3', '4']);
        RAISE EXCEPTION 'ограничение размера не сработало';
    EXCEPTION WHEN check_violation THEN
        NULL;  -- так и должно быть: VARRAY(3) допускает не больше трёх
    END;
END $$;
```

У вложенной таблицы (`AS TABLE OF`) нет ограничения размера: хватит
обычного типа-массива (`varchar(20)[]`). Если столбец ищут по его
элементам, подумайте о дочерней таблице: её PostgreSQL умеет индексировать
и соединять.

## TABLE(), MULTISET, MEMBER OF

```sql
DO $$
DECLARE
    a integer[] := ARRAY[1, 2, 2, 3];
    b integer[] := ARRAY[3, 4];
BEGIN
    -- SELECT column_value FROM TABLE(a)
    ASSERT (SELECT sum(x) FROM unnest(a) AS t(x)) = 8;
    -- a MULTISET UNION b
    ASSERT a || b = ARRAY[1, 2, 2, 3, 3, 4];
    -- a MULTISET UNION DISTINCT b
    ASSERT (SELECT array_agg(DISTINCT x ORDER BY x) FROM unnest(a || b) AS t(x)) = ARRAY[1, 2, 3, 4];
    -- a MULTISET INTERSECT b
    ASSERT (SELECT array_agg(x) FROM (SELECT unnest(a) INTERSECT ALL SELECT unnest(b)) AS t(x)) = ARRAY[3];
    -- 2 MEMBER OF a
    ASSERT 2 = ANY (a);
    -- b SUBMULTISET OF a  (как множества: число повторов не учитывается)
    ASSERT NOT (b <@ a);
    ASSERT ARRAY[2, 3] <@ a;
    -- CAST(MULTISET(SELECT ...) AS t)
    ASSERT ARRAY(SELECT g FROM generate_series(1, 3) AS g) = ARRAY[1, 2, 3];
END $$;
```

`<@` сравнивает как множества: `ARRAY[2, 2, 2] <@ ARRAY[2]` истинно, а
`SUBMULTISET OF` в Oracle учитывает повторы. Если число повторов важно,
сравнивайте через `EXCEPT ALL`: левая часть является подмультимножеством,
когда `SELECT unnest(левая) EXCEPT ALL SELECT unnest(правая)` не
возвращает строк.

## Ассоциативные массивы (INDEX BY)

- `INDEX BY VARCHAR2`: объект `jsonb` (`v := v || jsonb_build_object(k, x)`,
  `v ->> k`) или `hstore`, если значения только текстовые.
- `INDEX BY PLS_INTEGER` как разреженный массив: объект `jsonb` с числом в
  роли ключа или временная таблица, если строк много.
- `INDEX BY PLS_INTEGER`, заполненный с 1 без пропусков: обычный массив.

## На что обратить внимание

- **Циклы `BULK COLLECT ... LIMIT n` на больших объёмах.** Пачки там нужны
  для экономии памяти. Переписанному на множествах коду пачки не нужны;
  если шаг всё же должен идти пачками (вызывает что-то на каждую строку),
  обходите курсор через `FOR r IN SELECT ...`, а PostgreSQL сам читает его
  порциями.
- **`SAVE EXCEPTIONS`.** `FORALL ... SAVE EXCEPTIONS` продолжает работу
  после упавшей строки. Прямого аналога в PostgreSQL нет: либо сначала
  проверить данные и выполнить DML для корректных строк, либо цикл с
  блоком `EXCEPTION` на каждую строку (медленнее).
