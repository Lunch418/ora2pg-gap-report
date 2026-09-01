# GAP-104: вычисляемый столбец получает тип `citext`

MSSQL feature: вычисляемый столбец — `<имя> AS (<выражение>)`, с
`PERSISTED` или без.

## Минимальный пример

```sql
CREATE TABLE items3 (
    id int NOT NULL PRIMARY KEY,
    price decimal(10,2) NOT NULL,
    qty int NOT NULL,
    total AS (price * qty) PERSISTED
);
```

## Вывод ora2pg (v25.0, `-M -t TABLE`)

```sql
CREATE TABLE items3 (
	id integer NOT NULL,
	price numeric(10,2) NOT NULL,
	qty integer NOT NULL,
	total citext
) ;
...
CREATE OR REPLACE FUNCTION fct_virt_col_items3_trigger() RETURNS trigger AS $BODY$
BEGIN
	NEW.total = (NEW.price * NEW.qty) PERSISTED;

RETURN NEW;
end
$BODY$
 LANGUAGE 'plpgsql' SECURITY DEFINER;
```

Подход с триггером сам по себе рабочий, но тип столбца выведен как
`citext` — независимо от того, что считает выражение. Заодно в тело
триггера попало служебное слово `PERSISTED`.

## Наблюдаемая проблема

Ошибки нет ни на загрузке, ни при вставке. Проверено на реальном
PostgreSQL 16:

```
=# \d items3
 Column |     Type      | Nullable
--------+---------------+----------
 id     | integer       | not null
 price  | numeric(10,2) | not null
 qty    | integer       | not null
 total  | citext        |
```

Значение посчитается и запишется, но дальше это уже строка: сортировка
идёт лексикографически (`'100' < '20'`), сравнение с числом и `SUM()` по
столбцу падают или дают не то.

Слово `PERSISTED` в теле триггера, как ни странно, ошибки не вызывает:
PostgreSQL читает его как псевдоним столбца в выражении — ровно та же
безобидная случайность, что и с `STORED` на MySQL-стороне.

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16. Source
dialect: MSSQL (`ora2pg -M`).

## Вердикт

**Gap подтверждён, severity high, failure_stage semantic.** Чинится
заменой типа столбца на тот, что реально считает выражение, а лучше —
переносом на штатный `GENERATED ALWAYS AS (...) STORED`, который в
PostgreSQL есть и делает ровно то же, что `PERSISTED` в SQL Server.
Реализовано: `ora2pg_gap_report/detectors/mssql_computed_column.py`.
