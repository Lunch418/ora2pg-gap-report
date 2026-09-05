# GAP-103: `COLLATE` is dropped and everything becomes `citext`

MSSQL feature: `COLLATE` on a column — the comparison and sorting rule
for strings.

## Minimal example

A `_CS_` collation is used here — case-sensitive:

```sql
CREATE TABLE cs1 (
    id int NOT NULL PRIMARY KEY,
    code varchar(20) COLLATE SQL_Latin1_General_CP1_CS_AS NOT NULL
);
```

## ora2pg output (v25.0, `-M -t TABLE`)

```sql
CREATE TABLE cs1 (
	id integer NOT NULL,
	code citext NOT NULL
) ;
```

The `COLLATE` clause is dropped and the column itself is mapped to
`citext` — a case-insensitive type.

## Observed problem

For source collations with `_CI_` this hits the target. For `_CS_` it is
a silent substitution of the opposite meaning. Verified on live data,
real PostgreSQL 16:

```
=# INSERT INTO cs1 VALUES (1,'ABC');
=# SELECT count(*) FROM cs1 WHERE code = 'abc';
 matches_lowercase_abc
-----------------------
                     1
```

SQL Server with the `..._CS_AS` collation would have found nothing here.

There is no error at any stage — only query results change, and that
shows up in production: uniqueness checks, code lookups and identifier
comparisons all break.

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16. Source
dialect: MSSQL (`ora2pg -M`).

## Verdict

**Gap confirmed, severity high, failure_stage semantic.** Severity is
high rather than medium precisely because query results change, not just
the execution plan (cf. GAP-025/`invisible_index`, where only an
optimizer hint is lost). Fixed by replacing `citext` with `text` plus an
explicit `COLLATE` of the required sensitivity — PostgreSQL offers ICU
collations for exactly this. The related gap on the MySQL side is
GAP-085, but there the substitution runs the other way: case-insensitive
comparison becomes case-sensitive. Implemented:
`ora2pg_gap_report/detectors/mssql_collation.py`.
