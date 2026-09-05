# GAP-022: `CROSS APPLY` / `OUTER APPLY` — синтаксиса APPLY нет в PostgreSQL

Oracle feature (12c+): `CROSS APPLY`/`OUTER APPLY` — вызов табличного
подвыражения для каждой строки внешнего запроса с возможностью
ссылаться на её столбцы (аналог `LATERAL JOIN` в других СУБД).

## Минимальный пример

```sql
SELECT COUNT(*) INTO v_count
FROM customers c
CROSS APPLY (
    SELECT o.order_id, o.amount
    FROM orders o
    WHERE o.customer_id = c.customer_id
    ORDER BY o.order_date DESC
    FETCH FIRST 1 ROWS ONLY
) latest;
```

## Вывод ora2pg (v25.0, `-t PACKAGE`)

`CROSS APPLY(...)` копируется как есть (пробел перед скобкой убран, но
это косметика — суть конструкции не тронута).

## Наблюдаемая проблема

Подтверждено на реальном PostgreSQL 16: `CREATE PROCEDURE` проходит без
ошибки, падает при первом вызове:

```
ERROR:  syntax error at or near "APPLY"
LINE 2:         CROSS APPLY(
```

В PostgreSQL нет синтаксиса `APPLY` вообще. Ближайший архитектурный
эквивалент — `JOIN LATERAL (...) ON true` (для `CROSS APPLY`) или
`LEFT JOIN LATERAL (...) ON true` (для `OUTER APPLY`) — синтаксически
похоже, но требует ручной правки каждого случая.

**Reproducible: YES.** Ora2Pg version: 25.0.

## Вердикт

**Gap подтверждён.** Реализовано:
`ora2pg_gap_report/detectors/cross_apply.py`.
