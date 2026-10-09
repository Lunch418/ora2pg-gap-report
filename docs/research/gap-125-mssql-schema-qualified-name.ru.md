# GAP-125: `[dbo].[Orders]` - схема остаётся, но не создаётся

Возможность MSSQL: имена из двух частей - `CREATE TABLE [dbo].[Orders]`,
`CREATE PROCEDURE [dbo].[CountOrders]`. SSMS и "Generate Scripts"
уточняют схемой каждое имя, так что так выглядит практически любой
реальный скрипт.

## Как найден

`--migrate --dialect mssql --load-check docker` на скрипте в стиле SSMS:
на чистом PostgreSQL не загрузилось ничего, все ошибки - `schema "dbo"
does not exist`.

## Минимальный пример

`tests/fixtures/gaps_124_125/mssql_source.sql`:

```sql
CREATE TABLE [dbo].[Orders](
    [Id] [int] NOT NULL,
    [Total] [int] NULL,
 CONSTRAINT [PK_Orders] PRIMARY KEY CLUSTERED ([Id] ASC)
);
GO
CREATE VIEW [dbo].[BigOrders] AS SELECT [Id] FROM [dbo].[Orders] WHERE [Total] > 100;
GO
CREATE PROCEDURE [dbo].[CountOrders]
AS
BEGIN
    SELECT COUNT(*) FROM [dbo].[Orders];
END
GO
```

## Вывод ora2pg (v25.0, `-M`, после того как `--prepare` снял скобки)

```sql
CREATE TABLE dbo.orders (...);
CREATE OR REPLACE VIEW dbo.bigorders AS SELECT Id FROM dbo.Orders WHERE Total > 100;
CREATE OR REPLACE PROCEDURE dbo.countorders () AS $body$
...
SELECT  COUNT(*) FROM dbo.Orders;
```

В отличие от пути Oracle (GAP-124), схема остаётся везде, в телах тоже.
`CREATE SCHEMA dbo` нет.

## Наблюдаемая проблема

На чистом PostgreSQL 16 таблица, представление и процедура падают:

```
ERROR:  3F000: schema "dbo" does not exist
```

Если сначала выполнить `CREATE SCHEMA dbo`, они загружаются; остаются
другие, уже зарегистрированные пробелы скрипта.

**Воспроизводится: ДА.** Версия Ora2Pg: 25.0, PostgreSQL 16.

## Вердикт

**Gap подтверждён, severity high, failure_stage deployment.** Создайте
схему. Это механически, поэтому делает `--fix`: `CREATE SCHEMA IF NOT
EXISTS dbo;` после заголовка ora2pg для каждой схемы, которой файл
уточняет имя и которую не создаёт (`fix_mssql_missing_schema`).
`--load-check` сообщает такую ошибку как исправимую, `--migrate`
применяет исправление. Отобразить `dbo` на `public` вместо этого - выбор,
и он остаётся за пользователем.

Реализовано: `ora2pg_gap_report/detectors/mssql_schema_qualified_name.py`.
