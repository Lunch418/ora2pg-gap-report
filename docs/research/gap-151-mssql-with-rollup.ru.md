# GAP-151: `GROUP BY ... WITH ROLLUP` (SQL Server)

Возможность T-SQL: `GROUP BY a, b WITH ROLLUP` и `WITH CUBE` - старая форма `GROUP BY ROLLUP (a, b)`.

## Как найдено

Прогон --migrate --load-check на Sakila от jOOQ (версии для MySQL и SQL Server), базе Employees и демо-базах Microsoft (pubs, Northwind) и разбор того, что не объяснял ни один известный пробел.

## Минимальный пример

`tests/fixtures/dialect_corpus_gaps/mssql_source.sql`:

```sql
CREATE PROCEDURE staff_totals @store INT AS
BEGIN
  SELECT store_id, SUM(amount) AS total FROM staff GROUP BY store_id WITH ROLLUP;
END;
```

## Вывод ora2pg (v25.0)

```sql
   SELECT  store_id, SUM(amount) AS total FROM staff GROUP BY store_id WITH ROLLUP;
```

Копируется как есть.

## Наблюдаемая проблема

PostgreSQL знает только `GROUP BY ROLLUP (...)`, и подпрограмма не загружается:

```
ERROR:  syntax error at or near "WITH"
```

Найдено в pubs от Microsoft: три процедуры (`group by pub_id with rollup`).

**Воспроизводится: ДА.** Версия Ora2Pg: 25.0, PostgreSQL 16.

## Вердикт

**Пробел подтверждён, severity high, failure_stage deployment.** Механически: `--fix` пишет `GROUP BY ROLLUP (a, b)` (и `CUBE`) - та же группировка (`fix_mssql_with_rollup`).

Реализовано: `ora2pg_gap_report/detectors/mssql_with_rollup.py`.
