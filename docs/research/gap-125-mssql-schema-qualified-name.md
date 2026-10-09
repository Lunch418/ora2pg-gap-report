# GAP-125: `[dbo].[Orders]` - the schema is kept but never created

MSSQL feature: two-part names - `CREATE TABLE [dbo].[Orders]`,
`CREATE PROCEDURE [dbo].[CountOrders]`. SSMS and "Generate Scripts"
qualify every name with its schema, so practically every real script
looks like this.

## How it was found

`--migrate --dialect mssql --load-check docker` on an SSMS-style script:
nothing loaded on a fresh PostgreSQL, every error `schema "dbo" does not
exist`.

## Minimal example

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

## ora2pg output (v25.0, `-M`, after `--prepare` unwraps the brackets)

```sql
CREATE TABLE dbo.orders (...);
CREATE OR REPLACE VIEW dbo.bigorders AS SELECT Id FROM dbo.Orders WHERE Total > 100;
CREATE OR REPLACE PROCEDURE dbo.countorders () AS $body$
...
SELECT  COUNT(*) FROM dbo.Orders;
```

Unlike the Oracle path (GAP-124), the schema stays everywhere, bodies
included. There is no `CREATE SCHEMA dbo`.

## Observed problem

On a fresh PostgreSQL 16 the table, the view and the procedure fail:

```
ERROR:  3F000: schema "dbo" does not exist
```

With `CREATE SCHEMA dbo` first, these load; what is left are the script's
other, already registered gaps.

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16.

## Verdict

**Gap confirmed, severity high, failure_stage deployment.** Create the
schema. Mechanical, so `--fix` does it: `CREATE SCHEMA IF NOT EXISTS dbo;`
after ora2pg's header, for each schema the file qualifies a name with and
does not create (`fix_mssql_missing_schema`). `--load-check` reports the
error as fixable; `--migrate` applies the fix. Mapping `dbo` onto `public`
instead is a choice, and stays the user's.

Implemented: `ora2pg_gap_report/detectors/mssql_schema_qualified_name.py`.
