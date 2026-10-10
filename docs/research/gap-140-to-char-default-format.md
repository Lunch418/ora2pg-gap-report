# GAP-140: `TO_CHAR` of a date or a fraction without a format

Oracle feature: `TO_CHAR(x)` without a format formats a date by the session's `NLS_DATE_FORMAT` (`17-MAR-26` by default) and a number without a leading zero (`.5`).

## How it was found

While checking the earlier gaps: the same functions were run in Oracle 23ai and, after ora2pg 25.0, in PostgreSQL 16.

## Minimal example

`tests/fixtures/char_to_char_round/oracle_functions.sql`, VALID in a live Oracle 23ai:

```sql
CREATE OR REPLACE FUNCTION gx_r2(n NUMBER) RETURN VARCHAR2 IS
  v NUMBER(5,2) := 0.5;
  d DATE := DATE '2026-03-17';
BEGIN
  RETURN TO_CHAR(v) || '|' || TO_CHAR(d);
END;
/
```

## ora2pg output (v25.0)

```sql
  v real := 0.5;
  d timestamp(0) := timestamp(0) '2026-03-17';
BEGIN
  RETURN v::text || '|' || d::text;
```

`TO_CHAR(x)` becomes `x::text`, and PostgreSQL writes its own text for the value.

## Observed problem

It loads and runs, and returns another text:

| | Oracle 23ai | PostgreSQL 16 |
|---|---|---|
| `gx_r2(1)` | `.5\|17-MAR-26` | `0.5\|2026-03-17 00:00:00` |

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16, Oracle 23ai.

## Verdict

**Gap confirmed, severity high, failure_stage semantic.** Give the format explicitly, in Oracle or after conversion: `to_char(d, 'DD-MON-YY')`. The detector flags a one-argument `TO_CHAR` of a `DATE` or `TIMESTAMP` variable or parameter, of `SYSDATE`/`SYSTIMESTAMP`, of a variable that becomes `real`, `double precision` or `decimal`, and of a fractional literal. An integer is written the same in both and is not flagged; a column's type is not known.

Implemented: `ora2pg_gap_report/detectors/to_char_default_format.py`.
