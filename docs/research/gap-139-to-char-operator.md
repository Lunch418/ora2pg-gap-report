# GAP-139: `TO_CHAR(a/b)` becomes `a/b::text`

Oracle feature: `TO_CHAR` without a format, of an expression: `TO_CHAR(a/b)`, `TO_CHAR(-a)`.

## How it was found

While checking the earlier gaps: the same functions were run in Oracle 23ai and, after ora2pg 25.0, in PostgreSQL 16.

## Minimal example

`tests/fixtures/char_to_char_round/oracle_functions.sql`, VALID in a live Oracle 23ai:

```sql
CREATE OR REPLACE FUNCTION gx_r1(a NUMBER, b NUMBER) RETURN VARCHAR2 IS
BEGIN
  RETURN TO_CHAR(a/b) || '|' || TO_CHAR(-a);
END;
/
```

## ora2pg output (v25.0)

```sql
  RETURN a/b::text || '|' || -a::text;
```

A one-argument `TO_CHAR` becomes a cast to text. The argument is put in parentheses only when it has a space in it: `TO_CHAR(a / b)` becomes `(a / b)::text`, `TO_CHAR(a/b)` becomes `a/b::text` - and `::` binds tighter than `/`, so only `b` is cast. The same for `+`, `-`, `*` and a leading minus.

## Observed problem

The function loads; the first call fails (Oracle 23ai: `gx_r1(1, 4)` = `.25|-1`):

```
ERROR:  operator does not exist: bigint / text
```

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16, Oracle 23ai.

## Verdict

**Gap confirmed, severity high, failure_stage runtime.** Put the expression in parentheses: `(a/b)::text`. The detector flags a one-argument `TO_CHAR` whose argument has no space and an operator outside parentheses - exactly the shape ora2pg leaves unparenthesized.

Implemented: `ora2pg_gap_report/detectors/to_char_operator.py`.
