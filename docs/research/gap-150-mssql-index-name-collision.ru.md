# GAP-150: одно имя индекса на нескольких таблицах (SQL Server)

Возможность T-SQL: имя индекса принадлежит своей таблице: `CREATE INDEX idx_fk_store_id ON staff(...)` и `... ON customer(...)`.

## Как найдено

Прогон --migrate --load-check на Sakila от jOOQ (версии для MySQL и SQL Server), базе Employees и демо-базах Microsoft (pubs, Northwind) и разбор того, что не объяснял ни один известный пробел.

## Минимальный пример

`tests/fixtures/dialect_corpus_gaps/mssql_source.sql`:

```sql
 CREATE  INDEX idx_fk_store_id ON staff(store_id)
GO
 CREATE  INDEX idx_fk_store_id ON customer(store_id)
GO
```

## Вывод ora2pg (v25.0)

```sql
CREATE INDEX idx_fk_store_id ON staff (store_id);
CREATE INDEX idx_fk_store_id ON customer (store_id);
```

Имена сохраняются. В PostgreSQL имя индекса принадлежит схеме.

## Наблюдаемая проблема

Второй падает, и у этой таблицы нет индекса:

```
ERROR:  relation "idx_fk_store_id" already exists
```

Найдено в Sakila (jOOQ) для SQL Server (пять имён) и pubs от Microsoft (`titleidind`).

**Воспроизводится: ДА.** Версия Ora2Pg: 25.0, PostgreSQL 16.

## Вердикт

**Пробел подтверждён, severity high, failure_stage deployment.** `--prepare` переименовывает каждое использование после первой таблицы в `<таблица>_<имя>` (`prepare_mssql_index_names`), как для MySQL (GAP-128).

Реализовано: `ora2pg_gap_report/detectors/mssql_index_name_collision.py`.
