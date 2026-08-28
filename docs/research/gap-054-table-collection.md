# GAP-054: оператор `TABLE(...)` во `FROM`

Oracle feature: `TABLE(...)` разворачивает коллекцию (nested table,
`VARRAY` или результат pipelined-функции) в набор строк прямо во `FROM`.

## Минимальный пример

```sql
SELECT t.column_value
  FROM TABLE(get_ids(42)) t;
```

## Вывод ora2pg (v25.0, `-t QUERY`)

```sql
SELECT t.column_value
  FROM TABLE(get_ids(42)) t;
```

Скопировано как есть.

## Наблюдаемая проблема

Подтверждено на реальном PostgreSQL 16:

```
ERROR:  syntax error at or near "TABLE"
LINE 2:   FROM TABLE(get_ids(42)) t;
               ^
```

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16.

## Вердикт

**Gap подтверждён.** Реализовано:
`ora2pg_gap_report/detectors/table_collection.py`. Детектор требует
перед `TABLE(` ключевого слова `FROM`/`JOIN`/`APPLY`: слово `TABLE`
слишком частое в SQL (`CREATE TABLE`, `ALTER TABLE`, `TRUNCATE TABLE`,
`TYPE t IS TABLE OF`), и без этой привязки ложных срабатываний было бы
больше, чем настоящих находок.

Ручная переработка: ближайший аналог — `unnest(...)` для массива или
обычный вызов set-returning функции во `FROM` (`FROM get_ids(42)`). Но
подстановка не механическая: она зависит от того, чем в PostgreSQL стала
сама коллекция — массивом, отдельной таблицей или функцией,
возвращающей `SETOF`. Про сами объявления таких типов — см.
GAP-021/`collection_type.py`.
