# GAP-007: `MODEL` clause

Oracle feature: `SELECT ... MODEL PARTITION BY (...) DIMENSION BY (...)
MEASURES (...) RULES (...)` — spreadsheet-стиль вычислений внутри SQL
(прогнозы, накопительные расчёты). Реже встречается, чем остальные gap'ы
этого проекта — в основном в финансовой отчётности/аналитике, но там, где
встречается, обычно центральный, а не периферийный кусок логики.

## Минимальный пример

```sql
SELECT product_id, quarter, sales
FROM sales_history
MODEL
  PARTITION BY (product_id)
  DIMENSION BY (quarter)
  MEASURES (sales)
  RULES (
    sales[4] = sales[3] * 1.1
  );
```

## Вывод ora2pg (v25.0, `-t PACKAGE`)

Конструкция полностью не тронута — `MODEL`/`PARTITION BY`/`DIMENSION
BY`/`MEASURES`/`RULES` копируются как есть.

## Наблюдаемая проблема

Подтверждено на реальном PostgreSQL 16: `CREATE PROCEDURE` проходит без
ошибки, падает при первом вызове:

```
ERROR:  syntax error at or near "PARTITION"
```

В отличие от большинства других gap'ов проекта, у `MODEL` **нет прямого
архитектурного эквивалента** в PostgreSQL вообще — ни через расширение, ни
через синтаксическую замену. Единственный путь — переписать логику на
оконные функции (`LAG`/`LEAD`/`SUM() OVER (...)`) или рекурсивные CTE, что
требует понимания бизнес-смысла правил `RULES`, а не механической
подстановки.

**Reproducible: YES.** Ora2Pg version: 25.0.

## Вердикт

**Gap подтверждён.** Реже встречается на практике, чем остальные детекторы
проекта, но однозначен и архитектурно самый "тяжёлый" — нет пути
автоматической конвертации даже в принципе, только ручной редизайн
запроса.

Реализовано: `ora2pg_gap_report/detectors/model_clause.py`.
