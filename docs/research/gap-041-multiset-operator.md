# GAP-041: операторы над коллекциями — `MULTISET`, `MEMBER OF`, `SUBMULTISET`

Oracle feature: работа с вложенными таблицами и `VARRAY` как со
множествами прямо в SQL — объединение/пересечение/разность коллекций,
проверка вхождения элемента, проверка подмножества, а также идиома
`CAST(MULTISET(SELECT ...) AS <collection_type>)` для сбора результата
подзапроса в коллекцию.

## Минимальный пример

```sql
CREATE OR REPLACE VIEW v_multiset AS
SELECT id, col_a MULTISET UNION col_b AS merged
FROM basket_data
WHERE 5 MEMBER OF col_a;
```

## Вывод ora2pg (v25.0, `-t VIEW`)

```sql
CREATE OR REPLACE VIEW v_multiset AS SELECT id, col_a MULTISET
UNION
 col_b AS merged
FROM basket_data
WHERE 5 MEMBER OF col_a;
```

Скопировано как есть (ora2pg лишь переносит `UNION` на отдельную строку,
разрывая конструкцию — но не конвертирует её).

## Наблюдаемая проблема

Подтверждено на реальном PostgreSQL 16:

```
ERROR:  syntax error at or near "col_b"
LINE 3:  col_b AS merged
         ^
```

Отдельно проверено — все конструкции этого семейства ведут себя
одинаково (копируются дословно, падают при загрузке):

- `CAST(MULTISET(SELECT ...) AS num_list_t)` →
  `ERROR: syntax error at or near "SELECT"`
- `col_a SUBMULTISET OF col_b` →
  `ERROR: syntax error at or near "SUBMULTISET"`
- `MULTISET INTERSECT` — переносится дословно так же.

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16.

## Вердикт

**Gap подтверждён.** Реализовано:
`ora2pg_gap_report/detectors/multiset_operator.py`. Ручная переработка
под модель массивов PostgreSQL: `CAST(MULTISET(...))` → `ARRAY(SELECT
...)`, `MULTISET UNION` → `||`, `MEMBER OF` → `= ANY(...)`,
`SUBMULTISET OF` → `<@`.

Отдельно от `collection_type` (GAP-021): тот про объявление типа
коллекции (`CREATE TYPE ... AS TABLE OF`), этот — про операторы над
значениями коллекций в запросах.
