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

## Not a hardcode: a documented default that ignores the column it is applied to

This is `CASE_INSENSITIVE_SEARCH`, a real, documented ora2pg option
(`doc/Ora2Pg.pod`): "Emulate the same behavior of MSSQL with
case-insensitive search. If the value is citext, it will use the citext
data type instead of char/varchar/text ... To disable case-insensitive
search set it to: none." It defaults to `citext` specifically for MSSQL
sources (`Ora2Pg.pm`'s own MSSQL-block initialization sets
`$self->{case_insensitive_search} = 'citext'`), on the reasoning that
SQL Server installations are commonly case-insensitive by default.

The option exists and can be turned off with one config line. What it
does not do, in any setting other than `none`, is look at the specific
column's own `COLLATE` clause before applying it. Read
`Ora2Pg.pm` (~line 8774): the condition that triggers the substitution is

```perl
if ($self->{case_insensitive_search} =~ /^citext$/i && $type =~ /^(?:char|varchar|text)/)
{
	...
	$type = 'citext';
}
```

only the base type (`char`/`varchar`/`text`) is checked, never the
column's collation string. So with the shipped default, every string
column from an MSSQL source becomes `citext`, whether its own `COLLATE`
was `_CI_` or `_CS_`. The example below is deliberately a `_CS_` source,
to make the mismatch observable; a `_CI_` source would have hit the
right answer by coincidence, the same default applied without checking
either way.

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
optimizer hint is lost). Fixed either by setting `CASE_INSENSITIVE_SEARCH
none` before conversion and adding an explicit per-column `COLLATE` of
the required sensitivity by hand, PostgreSQL offers ICU collations for
exactly this, or by replacing `citext` with `text` plus that `COLLATE`
after the fact. The related gap on the MySQL side is GAP-085: same
category (a `COLLATE` clause not carried into the PostgreSQL output),
but MySQL's `-m` path has no `citext`-by-default behaviour at all, so
there `COLLATE` is dropped outright rather than replaced with a
consistently-wrong guess. Implemented:
`ora2pg_gap_report/detectors/mssql_collation.py`.
