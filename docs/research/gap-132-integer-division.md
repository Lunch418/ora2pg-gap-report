# GAP-132: a division of integers truncates

Oracle feature: `/` always returns a NUMBER. `7 / 2` is `3.5`, whatever
the operands are declared as.

## How it was found

With GAP-130: `NUMBER(10) / NUMBER(10)` and `PLS_INTEGER / 2` gave
different results in Oracle 23ai and PostgreSQL 16.

## Minimal example

`tests/fixtures/silent_numbers/oracle_functions.sql`, VALID in a live
Oracle 23ai:

```sql
CREATE OR REPLACE FUNCTION gx_d1(n NUMBER) RETURN VARCHAR2 IS
  b NUMBER(9,0) := n;
  e BINARY_INTEGER := n;
BEGIN
  RETURN (7 / 2) || '|' || ROUND(b / 2) || '|' || (e / 2);
END;
/
```

## ora2pg output (v25.0)

```sql
  b integer := n;
  e integer := n;
BEGIN
  RETURN(7 / 2) || '|' || ROUND(b / 2) || '|' || (e / 2);
```

`NUMBER(p)` and `NUMBER(p,0)` become `smallint`, `integer` or `bigint`
(p <= 19), `INTEGER`, `PLS_INTEGER`, `BINARY_INTEGER` become `integer`;
the division is copied.

## Observed problem

| | Oracle 23ai | PostgreSQL 16 |
|---|---|---|
| `gx_d1(7)` | `3.5\|4\|3.5` | `3\|3\|3` |
| `-7 / 2` | -3.5 | -3 |

Found in OraOpenSource Logger, `docs/research/samples/logger.pkb`:
`p_date_stop - p_date_start < 1/1440` - a minute as a fraction of a day
in Oracle, 0 in PostgreSQL.

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16, Oracle 23ai.

## Verdict

**Gap confirmed, severity high, failure_stage semantic.** Cast one side:
`i::numeric / 2`.

The detector flags `a / b` where each side is an integer literal or a
variable or parameter declared with one of the types above in the same
routine or its package. Not flagged: `NUMBER` without a precision
(GAP-130, and gone with its fix), `TRUNC(a / b)` (the same either way),
`2.0`, and columns, whose types the routine does not show.

Implemented: `ora2pg_gap_report/detectors/integer_division.py`.
