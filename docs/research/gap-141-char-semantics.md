# GAP-141: `CHAR(n)` loses its trailing blanks

Oracle feature: `CHAR(n)` is blank-padded to n characters, and the padding counts: in `LENGTH`, in `||`, and in a comparison with a `VARCHAR2`.

## How it was found

While checking the earlier gaps: the same functions were run in Oracle 23ai and, after ora2pg 25.0, in PostgreSQL 16.

## Minimal example

`tests/fixtures/char_to_char_round/oracle_functions.sql`, VALID in a live Oracle 23ai:

```sql
CREATE TABLE gx_codes (id NUMBER(5), code CHAR(5), flag CHAR(1));

CREATE OR REPLACE FUNCTION gx_r3 RETURN VARCHAR2 IS
  c CHAR(5) := 'AB';
  v VARCHAR2(5) := 'AB';
  l NUMBER(5);
BEGIN
  SELECT LENGTH(code) INTO l FROM gx_codes WHERE id = 1;
  RETURN LENGTH(c) || '|' || (c || 'x') || '|' || CASE WHEN c = v THEN 'equal' ELSE 'not equal' END || '|' || l;
END;
/
```

## ora2pg output (v25.0)

```sql
	code char(5),
...
  c char(5) := 'AB';
  v varchar(5) := 'AB';
```

`CHAR(n)` becomes `char(n)` - the right type, with other rules: PostgreSQL treats a `char(n)`'s trailing blanks as insignificant and drops them when it is used as text.

## Observed problem

Everything loads and runs, with `code = 'AB'` in row 1:

| | Oracle 23ai | PostgreSQL 16 |
|---|---|---|
| `LENGTH(c)` | 5 | 2 |
| `c \|\| 'x'` | `AB   x` | `ABx` |
| `c = v` (`VARCHAR2`) | not equal | equal |
| `LENGTH(code)` of the column | 5 | 2 |

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16, Oracle 23ai.

## Verdict

**Gap confirmed, severity high, failure_stage semantic.** Reported once per file, at the first `CHAR(n)` or `NCHAR(n)` with n > 1: the decision - `varchar(n)` with explicit `rpad`, or `char(n)` with its `LENGTH`, `||` and comparisons checked - is made once for the schema. `CHAR(1)` flags are not reported: a single character has no trailing blanks.

Implemented: `ora2pg_gap_report/detectors/char_semantics.py`.
