# GAP-087: bracketed identifiers break the conversion entirely

The first gap of the MSSQL batch. ora2pg supports SQL Server as a source
directly, via `-M`/`--mssql`, and works file-based (`-i <file>`, no live
connection) the same way the Oracle and MySQL modes do.

MSSQL feature: `[dbo].[Orders]`, `[Id]`, `[int]` — the standard way of
writing names in T-SQL. It is exactly what SSMS and "Generate Scripts"
emit by default, so it is what practically every real script looks like.

## Minimal example

```sql
CREATE TABLE [dbo].[Orders](
    [Id] [int] IDENTITY(1,1) NOT NULL,
    [CustomerName] [nvarchar](100) NOT NULL,
    [Total] [money] NULL,
    [CreatedAt] [datetime2](7) NOT NULL,
 CONSTRAINT [PK_Orders] PRIMARY KEY CLUSTERED ([Id] ASC)
);
```

## ora2pg output (v25.0, `-M -t TABLE`)

```sql
CREATE TABLE "[dbo]"."[orders]" (
	"[id]" [INT] NOT NULL,
	"[customername]" [NVARCHAR] NOT NULL,
	"[total]" [MONEY],
	"[createdat]" [DATETIME2] NOT NULL
) ;
ALTER TABLE "[dbo]"."[orders]" ADD PRIMARY KEY ([id]);
```

The brackets are not stripped: they stayed part of the name and were then
wrapped in double quotes on top. The result is a table named `[orders]`
in a schema `[dbo]`, with columns of types `[INT]`, `[NVARCHAR]`,
`[MONEY]` — types that do not exist.

## Observed problem

Confirmed on a real PostgreSQL 16:

```
ERROR:  syntax error at or near "["
LINE 2:  "[id]" [INT] NOT NULL,
                ^
```

The load fails on the very first column.

## It really is the brackets

Checked separately — the same table written without brackets converts
correctly:

```sql
CREATE TABLE dbo.Orders(
    Id int IDENTITY(1,1) NOT NULL,
    CustomerName nvarchar(100) NOT NULL,
    Total money NULL,
    CreatedAt datetime2(7) NOT NULL,
 CONSTRAINT PK_Orders PRIMARY KEY CLUSTERED (Id ASC)
);
```

```sql
CREATE TABLE dbo.orders (
	id integer NOT NULL,
	customername citext NOT NULL,
	total numeric(15,4),
	createdat timestamp without time zone NOT NULL
) ;
```

## Why this happens

ora2pg's sources do strip brackets — a regex of the form `s/[\[\]]+//g`
appears eight times in `lib/Ora2Pg/MSSQL.pm`. But all eight sit inside
subroutines that work against a live connection, applied to strings read
from the database through DBI:

| line | subroutine |
|---|---|
| 381, 384 | `_column_info` |
| 644 | `_get_views` |
| 832 | `_check_constraint` |
| 900 | `_get_functions` |
| 944 | `_get_procedures` |
| 2331 | `_column_attributes` |
| 2631 | `_get_materialized_views` |

The file-based path through `-i` never reaches them at all — hence the
difference in behaviour between "dump from a live SQL Server" and
"convert a script".

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16. Source
dialect: MSSQL (`ora2pg -M`).

## Verdict

**Gap confirmed, severity high.** By reach this is the largest gap of
the whole MSSQL batch: it catches any script exported by SSMS with
default settings, and it fails on the very first table, before the other
problems get a chance to surface. Two workarounds: strip the brackets in
the script before conversion, or export the schema through a live
connection to SQL Server. Implemented:
`ora2pg_gap_report/detectors/mssql_bracket_identifier.py` — one finding
per object rather than per bracket.
