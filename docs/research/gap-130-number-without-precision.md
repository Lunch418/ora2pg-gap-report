# GAP-130: `NUMBER` without a precision becomes `bigint`

Oracle feature: `NUMBER` with no precision holds any decimal value, in a
column, a variable, a parameter or a return type.

## How it was found

Looking for what loads and then computes something else (after GAP-129):
the same functions were run in Oracle 23ai and, after ora2pg, in
PostgreSQL 16, and the results compared.

## Minimal example

`tests/fixtures/silent_numbers/oracle_tables.sql` and
`oracle_functions.sql`, VALID in a live Oracle 23ai:

```sql
CREATE TABLE gx_prices (id NUMBER, price NUMBER, qty NUMBER(5));

CREATE OR REPLACE FUNCTION gx_n1 RETURN NUMBER IS
  v NUMBER := 2.5;
BEGIN
  RETURN v * 2;
END;
/
CREATE OR REPLACE FUNCTION gx_n2(p NUMBER) RETURN NUMBER IS
BEGIN
  RETURN p / 4;
END;
/
```

## ora2pg output (v25.0, `-t TABLE`, `-t FUNCTION`)

```sql
CREATE TABLE gx_prices (
	id bigint,
	price bigint,
	qty integer
) ;
CREATE OR REPLACE FUNCTION gx_n1 () RETURNS bigint AS $body$
DECLARE
  v bigint := 2.5;
...
CREATE OR REPLACE FUNCTION gx_n2 (p bigint) RETURNS bigint AS $body$
```

The ora2pg.conf ora2pg ships has `PG_INTEGER_TYPE 1` and `DEFAULT_NUMERIC
bigint`: `NUMBER` without a precision becomes `DEFAULT_NUMERIC`
(`Ora2Pg/Oracle.pm`, `_sql_type`).

## Observed problem

All of it loads in PostgreSQL 16 with no error, and then:

| | Oracle 23ai | PostgreSQL 16 |
|---|---|---|
| `price` 9.99 and 0.25 stored, `SUM(price)` | 10.24 | 10 (stored as 10 and 0) |
| `gx_n1()` (`v := 2.5; RETURN v * 2`) | 5 | 6 |
| `gx_n2(10)` (`p / 4`) | 2.5 | 2 |

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16, Oracle 23ai.

## Verdict

**Gap confirmed, severity high, failure_stage semantic.**

The fix is one line in ora2pg.conf, checked on the same files:

```
DEFAULT_NUMERIC numeric
```

and every `NUMBER` above becomes `numeric`. So the detector reports once
per file, at the first `NUMBER` without a precision, not once per column:
the work is the setting, not each declaration. `NUMBER(p)`, `NUMBER(p,s)`,
`TO_NUMBER`, `%TYPE` and `CAST(x AS NUMBER)` are not flagged.

`--migrate` converts with these settings by default (see README, `--migrate`).

Implemented: `ora2pg_gap_report/detectors/number_without_precision.py`
(the declarations are read by `ora2pg_gap_report/number_types.py`).
