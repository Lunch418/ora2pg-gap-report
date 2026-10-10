# GAP-152: `GROUP BY ... WITH ROLLUP` (MySQL)

Возможность MySQL: `GROUP BY a, b WITH ROLLUP` - его форма `GROUP BY ROLLUP (a, b)`.

## Как найдено

Прогон --migrate --load-check на Sakila от jOOQ (версии для MySQL и SQL Server), базе Employees и демо-базах Microsoft (pubs, Northwind) и разбор того, что не объяснял ни один известный пробел.

## Минимальный пример

`tests/fixtures/dialect_corpus_gaps/mysql_source.sql`:

```sql
CREATE TABLE payment (store_id INT NOT NULL, amount INT NOT NULL);
CREATE VIEW payment_totals AS SELECT store_id, SUM(amount) AS total FROM payment GROUP BY store_id WITH ROLLUP;
```

## Вывод ora2pg (v25.0)

```sql
CREATE OR REPLACE VIEW payment_totals AS SELECT store_id, SUM(amount) AS total FROM payment GROUP BY store_id WITH ROLLUP;
```

Копируется как есть - и в представлениях, и в подпрограммах.

## Наблюдаемая проблема

Представление не загружается:

```
ERROR:  syntax error at or near "WITH"
```

**Воспроизводится: ДА.** Версия Ora2Pg: 25.0, PostgreSQL 16.

## Вердикт

**Пробел подтверждён, severity high, failure_stage deployment.** Механически: `--fix` пишет `GROUP BY ROLLUP (store_id)` (`fix_mysql_with_rollup`), проверено: на строках (1, 10), (1, 5), (2, 7) представление возвращает 15, 7 и итог 22, как WITH ROLLUP в MySQL.

Реализовано: `ora2pg_gap_report/detectors/mysql_with_rollup.py`.
