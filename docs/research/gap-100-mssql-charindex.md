# GAP-100: `CHARINDEX()` becomes `position()` with doubled quotes

MSSQL feature: `CHARINDEX(<needle>, <haystack>)` — substring search.

## Minimal example

```sql
CREATE PROCEDURE dbo.ci @nm varchar(50) AS
BEGIN
    SELECT CHARINDEX('abc', @nm);
END;
```

## ora2pg output (v25.0, `-M -t PROCEDURE`)

```sql
CREATE OR REPLACE PROCEDURE dbo.ci (p_nm varchar(50)) AS $body$
BEGIN
BEGIN 
     SELECT  position(''abc'' in p_nm);
END;
END;
$body$
```

Unlike the other built-in functions in this batch, ora2pg does try to
translate `CHARINDEX` — and picks the right target, `position(... in
...)` — but doubles the quotes around the search string.

## Observed problem

`position(''abc'' in p_nm)` is no longer valid SQL. Confirmed on a real
PostgreSQL 16:

```
ERROR:  syntax error at or near "abc"
LINE 4:      SELECT  position(''abc'' in p_nm);
```

The load goes through cleanly (`check_function_bodies = false` in
ora2pg's output); the error surfaces on the first call.

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16. Source
dialect: MSSQL (`ora2pg -M`).

## Verdict

**Gap confirmed, severity high, failure_stage runtime.** This is not "the
construct is missing from PostgreSQL" but a translation bug proper: the
target is right, the escaping is broken. Fixed by removing the extra
quotes — `position('abc' in p_nm)`. Keep in mind that `CHARINDEX` has a
third argument (the position to start searching from) which has no direct
counterpart in `position()` and is ported via `substring()`. Implemented:
`ora2pg_gap_report/detectors/mssql_charindex.py`.
