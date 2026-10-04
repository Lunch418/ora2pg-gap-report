*[English](multi-table-dml.md) | Русский*

# INSERT ALL, MERGE ... DELETE и upsert

Покрывает: GAP-016 (`insert_all`), GAP-002 (`merge_delete_clause`), GAP-070
(`mysql_on_duplicate_key_update`), GAP-076 (`mysql_replace_into`), GAP-077
(`mysql_insert_ignore`).

## Проблема

Многотабличные `INSERT ALL` / `INSERT FIRST` из Oracle, ветка `DELETE
WHERE` в `MERGE` и MySQL-овские `ON DUPLICATE KEY UPDATE`, `REPLACE INTO` и
`INSERT IGNORE` `ora2pg` копирует как есть, и PostgreSQL отвергает каждую
из них. У всех есть форма для PostgreSQL, но у двух поведение отличается
так, что об этом стоит прочитать до переписывания.

```sql
CREATE TABLE new_orders   (id integer PRIMARY KEY, amount numeric NOT NULL);
CREATE TABLE small_orders (id integer PRIMARY KEY, amount numeric NOT NULL);
CREATE TABLE big_orders   (id integer PRIMARY KEY, amount numeric NOT NULL);
CREATE TABLE all_orders   (id integer PRIMARY KEY, amount numeric NOT NULL);
INSERT INTO new_orders VALUES (1, 50), (2, 500), (3, 99), (4, 100);
```

## INSERT ALL -> WITH с изменением данных

```plsql
INSERT ALL
    WHEN amount < 100  THEN INTO small_orders VALUES (id, amount)
    WHEN amount >= 100 THEN INTO big_orders   VALUES (id, amount)
    WHEN 1 = 1         THEN INTO all_orders   VALUES (id, amount)
SELECT id, amount FROM new_orders;
```

Каждое `INTO` становится одним `INSERT` внутри `WITH`, источник читается
один раз:

```sql
WITH src AS (
    SELECT id, amount FROM new_orders
),
ins_small AS (
    INSERT INTO small_orders SELECT id, amount FROM src WHERE amount < 100
),
ins_big AS (
    INSERT INTO big_orders SELECT id, amount FROM src WHERE amount >= 100
)
INSERT INTO all_orders SELECT id, amount FROM src;

DO $$
BEGIN
    ASSERT (SELECT array_agg(id ORDER BY id) FROM small_orders) = ARRAY[1, 3];
    ASSERT (SELECT array_agg(id ORDER BY id) FROM big_orders) = ARRAY[2, 4];
    ASSERT (SELECT count(*) FROM all_orders) = 4;
END $$;
```

Изменяющие данные части `WITH` выполняются всегда, читает их кто-то или
нет, и вся команда - одна атомарная единица, как в Oracle.

## INSERT FIRST -> одна ветка на строку

`INSERT FIRST` останавливается на первом подошедшем `WHEN`. Вычислите
ветку каждой строки один раз и вставляйте по ветке:

```plsql
INSERT FIRST
    WHEN amount < 100  THEN INTO small_orders VALUES (id, amount)
    WHEN amount < 1000 THEN INTO big_orders   VALUES (id, amount)
    ELSE                    INTO all_orders   VALUES (id, amount)
SELECT id, amount FROM new_orders;
```

```sql
TRUNCATE small_orders, big_orders, all_orders;

WITH src AS (
    SELECT id, amount,
           CASE WHEN amount < 100  THEN 1   -- те же WHEN, в том же порядке
                WHEN amount < 1000 THEN 2
                ELSE 3 END AS branch
    FROM new_orders
),
b1 AS (INSERT INTO small_orders SELECT id, amount FROM src WHERE branch = 1),
b2 AS (INSERT INTO big_orders   SELECT id, amount FROM src WHERE branch = 2)
INSERT INTO all_orders SELECT id, amount FROM src WHERE branch = 3;

DO $$
BEGIN
    ASSERT (SELECT count(*) FROM small_orders) = 2;
    ASSERT (SELECT count(*) FROM big_orders) = 2;
    ASSERT (SELECT count(*) FROM all_orders) = 0;
END $$;
```

`CASE` проверяет ветки по порядку и останавливается на первой истинной -
ровно как `INSERT FIRST`.

## MERGE ... DELETE WHERE -> второй WHEN MATCHED

В PostgreSQL 15 есть `MERGE`, но без хвоста `DELETE WHERE` у ветки
обновления, как в Oracle. Зато есть более общее: несколько веток
`WHEN MATCHED` со своими условиями.

```plsql
MERGE INTO stock t
USING deliveries s ON (t.item_id = s.item_id)
WHEN MATCHED THEN
    UPDATE SET t.qty = t.qty + s.qty_change
    DELETE WHERE t.qty <= 0
WHEN NOT MATCHED THEN
    INSERT (item_id, qty) VALUES (s.item_id, s.qty_change);
```

```sql
CREATE TABLE stock      (item_id integer PRIMARY KEY, qty integer NOT NULL);
CREATE TABLE deliveries (item_id integer PRIMARY KEY, qty_change integer NOT NULL);
INSERT INTO stock VALUES (1, 10), (2, 3);
INSERT INTO deliveries VALUES (1, 5), (2, -3), (3, 7);

MERGE INTO stock t
USING deliveries s ON t.item_id = s.item_id
WHEN MATCHED AND t.qty + s.qty_change <= 0 THEN
    DELETE
WHEN MATCHED THEN
    UPDATE SET qty = t.qty + s.qty_change
WHEN NOT MATCHED THEN
    INSERT (item_id, qty) VALUES (s.item_id, s.qty_change);

DO $$
BEGIN
    ASSERT (SELECT array_agg(item_id || ':' || qty ORDER BY item_id) FROM stock) = ARRAY['1:15', '3:7'];
END $$;
```

Главное, что нужно не упустить: Oracle проверяет `DELETE WHERE` по строке
**после** обновления. Пишите условие через новые значения
(`t.qty + s.qty_change <= 0`, а не `t.qty <= 0`) и ставьте ветку `DELETE`
первой: срабатывает первая подошедшая ветка.

## MySQL: ON DUPLICATE KEY UPDATE -> ON CONFLICT DO UPDATE

```sql
CREATE TABLE counters (name text PRIMARY KEY, hits integer NOT NULL);
INSERT INTO counters VALUES ('home', 1);

-- MySQL: INSERT INTO counters VALUES ('home', 1)
--        ON DUPLICATE KEY UPDATE hits = hits + VALUES(hits);
INSERT INTO counters VALUES ('home', 1)
ON CONFLICT (name) DO UPDATE SET hits = counters.hits + EXCLUDED.hits;

DO $$
BEGIN
    ASSERT (SELECT hits FROM counters WHERE name = 'home') = 2;
END $$;
```

`VALUES(col)` становится `EXCLUDED.col`, а голый столбец в обновлении -
`таблица.col`. PostgreSQL требует явно указать цель конфликта: MySQL
реагирует на совпадение по *любому* уникальному ключу, PostgreSQL - только
по названному. Для таблицы с несколькими уникальными ключами нужно решить,
о каком из них на самом деле команда.

## MySQL: INSERT IGNORE -> ON CONFLICT DO NOTHING

```sql
-- MySQL: INSERT IGNORE INTO counters VALUES ('home', 100);
INSERT INTO counters VALUES ('home', 100) ON CONFLICT DO NOTHING;

DO $$
BEGIN
    ASSERT (SELECT hits FROM counters WHERE name = 'home') = 2;
END $$;
```

Это покрывает только повторяющиеся ключи. `IGNORE` в MySQL превращает в
предупреждения и другие ошибки: слишком длинная строка обрезается, `NULL`
в столбец `NOT NULL` становится нулевым значением типа. PostgreSQL выдаёт
на это ошибки. Прежде чем выбрать такое переписывание, выясните, не
полагался ли код на это.

## MySQL: REPLACE INTO

`REPLACE` удаляет старую строку и вставляет новую. Неперечисленные столбцы
получают значения по умолчанию, срабатывают триггеры удаления. Ближайшая
одиночная команда вместо этого обновляет строку на месте:

```sql
CREATE TABLE settings (
    name       text PRIMARY KEY,
    value      text NOT NULL,
    changed_by text DEFAULT 'system'
);
INSERT INTO settings VALUES ('theme', 'dark', 'alice');

-- MySQL: REPLACE INTO settings (name, value) VALUES ('theme', 'light');
INSERT INTO settings (name, value) VALUES ('theme', 'light')
ON CONFLICT (name) DO UPDATE SET value = EXCLUDED.value,
                                 changed_by = EXCLUDED.changed_by;

DO $$
BEGIN
    -- в EXCLUDED.changed_by значение по умолчанию, как оставил бы REPLACE
    ASSERT (SELECT value || '/' || changed_by FROM settings) = 'light/system';
END $$;
```

Если брать из `EXCLUDED` все столбцы, включая те, что команда не
перечислила, получается поведение `REPLACE` "неперечисленные столбцы
получают умолчания". Чего так не получить, так это удаления: триггеры
`ON DELETE` и дочерние строки с `ON DELETE CASCADE` не затрагиваются. Если
это важно, пишите `DELETE` и `INSERT` двумя командами в одной транзакции.
