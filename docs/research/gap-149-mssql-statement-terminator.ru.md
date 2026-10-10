# GAP-149: команды T-SQL без `;` - ora2pg теряет всё, что после

Возможность T-SQL: `;` необязательна. SSMS пишет каждый объект как команду, за которой идёт строка `GO`, без `;`.

## Как найдено

Прогон --migrate --load-check на Sakila от jOOQ (версии для MySQL и SQL Server), базе Employees и демо-базах Microsoft (pubs, Northwind) и разбор того, что не объяснял ни один известный пробел.

## Минимальный пример

`tests/fixtures/dialect_corpus_gaps/mssql_source.sql`:

```sql
CREATE TABLE store (
  store_id INT NOT NULL,
  manager_id INT NOT NULL,
  PRIMARY KEY NONCLUSTERED (store_id)
)
GO
 CREATE  INDEX idx_fk_store_id ON store(store_id)
GO

CREATE TABLE staff (
  ...
  PRIMARY KEY NONCLUSTERED (staff_id),
)

CREATE TABLE customer (
  ...
)
GO
```

## Вывод ora2pg (v25.0)

```sql
CREATE TABLE store (
	store_id integer NOT NULL,
	manager_id integer NOT NULL
) ;
ALTER TABLE store ADD PRIMARY KEY (store_id);
```

ora2pg 25.0 (-M) конвертирует первую команду и выбрасывает всё после неё до следующей `;`: здесь `staff` и `customer` с их индексами. Ни в выводе, ни в консоли об этом ни слова.

## Наблюдаемая проблема

То, чего нет в выводе, не падает при загрузке - его просто нет:

| Исходник | Таблиц в выводе ora2pg | После --prepare |
|---|---|---|
| эта фикстура | 1 из 3 | 3 из 3 |
| Sakila (jOOQ) для SQL Server | 1 из 16 | 15 из 16 (ещё одна заканчивалась ничем перед следующим CREATE TABLE - теперь тоже учтено) |
| pubs от Microsoft | 70 команд | 88 команд |

**Воспроизводится: ДА.** Версия Ora2Pg: 25.0, PostgreSQL 16.

## Вердикт

**Пробел подтверждён, severity high, failure_stage conversion.** `--prepare` ставит `;` в конце каждой команды перед её `GO` (и перед `CREATE TABLE` в начале строки) и убирает строки `GO` (`prepare_mssql_go_separator`, который раньше делал это только для подпрограмм, для GAP-126). Сообщается один раз на файл, с числом таких команд: причина одна, исправление одно.

Реализовано: `ora2pg_gap_report/detectors/mssql_statement_terminator.py`.
