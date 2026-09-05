# GAP-062: alternative quoting `q'[...]'`

Oracle feature: a way to write a string containing apostrophes without
doubling them.

## Minimal example

```sql
CREATE OR REPLACE PROCEDURE say IS
  msg VARCHAR2(100) := q'[it's a test]';
BEGIN
  DBMS_OUTPUT.PUT_LINE(msg);
END;
/
```

## ora2pg output (v25.0, `-t PROCEDURE`)

```sql
CREATE OR REPLACE PROCEDURE say () AS $body$
DECLARE
  msg varchar(100) := q'[it's a test]';
BEGIN
  RAISE NOTICE '%', msg;
END;
$body$
LANGUAGE PLPGSQL
;
```

The literal is copied as written.

## Observed problem

The load succeeds cleanly (`check_function_bodies = false` in ora2pg's
output):

```
CREATE PROCEDURE
```

The failure comes on the first call. Confirmed against a real PostgreSQL
16:

```
ERROR:  mismatched parentheses at or near "]"
LINE 4:   msg varchar(100) := q'[it's a test]';
                                            ^
```

PostgreSQL reads `q` as a separate identifier, an ordinary string literal
`'[it'` starts after it, and the parse goes off the rails.

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16.

## Verdict

**Gap confirmed.** Implemented in
`ora2pg_gap_report/detectors/alt_quote_literal.py`. This is one of the two
detectors working over `mask_comments_only()`: `plsql_lex` understands
q-quotes and duly blanks them along with the other literals, so ordinary
masking would erase exactly the text being searched for here. Scanning the
raw source is not an option either — the detector would then catch
commented-out code.

Manual rework: replace it with an ordinary literal using doubled
apostrophes, or — closer in spirit — with PostgreSQL's dollar quoting:
`$q$it's a test$q$`, inside which nothing needs escaping at all.
