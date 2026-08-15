# GAP-012: `CREATE GLOBAL TEMPORARY TABLE` — потерянный `ON COMMIT`

Oracle feature: `CREATE GLOBAL TEMPORARY TABLE ... ON COMMIT DELETE ROWS`
(или та же семантика по умолчанию, если `ON COMMIT` вообще не указан) —
строки временной таблицы очищаются после каждого `COMMIT`.

## Минимальный пример

```sql
CREATE GLOBAL TEMPORARY TABLE staging_orders (
    order_id NUMBER
) ON COMMIT DELETE ROWS;
```

(тот же результат и без `ON COMMIT` вообще — это поведение по умолчанию
в Oracle).

## Вывод ora2pg (v25.0, `-t TABLE`)

```sql
CREATE TEMPORARY TABLE staging_orders (
    order_id numeric
);
```

Секция `ON COMMIT` полностью пропадает — ни `DELETE ROWS`, ни какой-либо
другой её эквивалент не попадают в вывод. Ни ошибки, ни предупреждения.

## Наблюдаемая проблема

Это не синтаксическая ошибка — сгенерированный SQL валиден и выполняется
без проблем. Проблема в том, что у обычной `CREATE TEMPORARY TABLE` в
PostgreSQL поведение по умолчанию — `ON COMMIT PRESERVE ROWS`, то есть
прямо противоположное умолчанию Oracle (`DELETE ROWS`).

Подтверждено на реальном PostgreSQL 16 одной сессией `psql`:

```sql
CREATE TEMPORARY TABLE staging_orders (order_id numeric);
BEGIN;
INSERT INTO staging_orders VALUES (1);
COMMIT;
SELECT * FROM staging_orders;  -- строка (1) НЕ удалена, хотя в Oracle
                                -- к этому моменту таблица уже пуста
```

Строка `order_id = 1` пережила `COMMIT`, хотя в Oracle-семантике (и в
исходном намерении разработчика, раз он вообще использовал GTT без явного
`PRESERVE ROWS`) она должна была исчезнуть. Это тихая смена поведения —
код компилируется и выполняется без единой ошибки, но начинает вести себя
иначе, чем в Oracle.

Отдельно проверено: если в Oracle-коде `ON COMMIT PRESERVE ROWS` указан
явно, конвертация корректна — это совпадает с собственным умолчанием
PostgreSQL, поведение не меняется.

**Reproducible: YES.** Ora2Pg version: 25.0.

## Вердикт

**Gap подтверждён.** Реализовано:
`ora2pg_gap_report/detectors/global_temp_table.py`. Флагуется и явный
`ON COMMIT DELETE ROWS`, и полное отсутствие секции `ON COMMIT`
(поскольку оба случая означают одну и ту же Oracle-семантику, которую
ora2pg теряет). `ON COMMIT PRESERVE ROWS` не флагуется — этот случай
конвертируется верно.
