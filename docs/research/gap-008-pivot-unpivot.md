# GAP-008: `PIVOT`/`UNPIVOT`

Oracle feature: `PIVOT (aggregate_function FOR pivot_column IN (values))` /
`UNPIVOT (...)` — поворот строк в столбцы и обратно прямо в SQL, без
условной агрегации вручную. Распространено в отчётности.

## Минимальный пример

```sql
SELECT * FROM (SELECT product_id, quarter, sales FROM sales_history)
PIVOT (
  SUM(sales)
  FOR quarter IN ('Q1' AS q1, 'Q2' AS q2, 'Q3' AS q3, 'Q4' AS q4)
);
```

## Вывод ora2pg (v25.0, `-t PACKAGE`)

Конструкция копируется как есть, без единого изменения (кроме
косметического удаления пробела перед скобкой).

## Наблюдаемая проблема

Подтверждено на реальном PostgreSQL 16: `CREATE PROCEDURE` проходит без
ошибки, падает при первом вызове:

```
ERROR:  syntax error at or near "("
LINE 4:         SUM(sales)
```

В PostgreSQL нет встроенного `PIVOT`/`UNPIVOT` вообще. Обычно
переписывается на условную агрегацию (`FILTER (WHERE ...)`/`CASE WHEN`)
или расширение `tablefunc` (`crosstab()`), архитектурно разные подходы в
зависимости от того, известен ли список значений для поворота заранее.

**Reproducible: YES.** Ora2Pg version: 25.0.

## Вердикт

**Gap подтверждён.** Реализовано:
`ora2pg_gap_report/detectors/pivot_clause.py`.
