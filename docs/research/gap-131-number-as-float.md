# GAP-131: `NUMBER(p,s)` and `FLOAT` become binary floating point

Oracle feature: `NUMBER(p,s)` and `FLOAT` are decimal types. `0.1 + 0.2`
is exactly `0.3`.

## How it was found

Next to GAP-130, in ora2pg's own type mapping (`Ora2Pg/Oracle.pm`,
`_sql_type`), then run on Oracle 23ai and PostgreSQL 16.

## Minimal example

`tests/fixtures/silent_numbers/`, VALID in a live Oracle 23ai:

```sql
CREATE TABLE gx_pay (id NUMBER(10), amount NUMBER(10,2), rate NUMBER(5,4));

CREATE OR REPLACE FUNCTION gx_f1 RETURN VARCHAR2 IS
  a NUMBER(10,2) := 0.1;
  b NUMBER(10,2) := 0.2;
BEGIN
  IF a + b = 0.3 THEN RETURN 'equal'; END IF;
  RETURN 'not equal';
END;
/
CREATE OR REPLACE FUNCTION gx_f2 RETURN VARCHAR2 IS
  t NUMBER(12,2);
BEGIN
  SELECT SUM(amount) INTO t FROM gx_pay;
  RETURN TO_CHAR(t);
END;
/
```

## ora2pg output (v25.0)

```sql
	amount double precision,
	rate decimal(5,4)
...
  a double precision := 0.1;
  b double precision := 0.2;
...
  t double precision;
```

With `PG_NUMERIC_TYPE 1` (the shipped ora2pg.conf), `NUMBER(p,s)` with
`0 < s <= p` becomes `real` for `p <= 6` and `double precision` for
`p <= 15`; a column with `p <= 6` gets `decimal(p,s)` instead (checked:
`NUMBER(5,2)` and `NUMBER(6,2)` columns stay decimal, `NUMBER(7,2)` and
`NUMBER(15,2)` become `double precision`, `NUMBER(16,2)` stays decimal).
`FLOAT` is always `double precision`.

## Observed problem

Everything loads in PostgreSQL 16, and with ten rows of `amount = 0.1`:

| | Oracle 23ai | PostgreSQL 16 |
|---|---|---|
| `gx_f1()` | `equal` | `not equal` |
| `gx_f2()` (`SUM(amount)`) | `1` | `0.9999999999999999` |

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16, Oracle 23ai.

## Verdict

**Gap confirmed, severity high, failure_stage semantic.** Money in
`double precision` is the classic bug, and here nothing in the code asked
for it.

The fix is in ora2pg.conf, checked on the same files:

```
PG_NUMERIC_TYPE 0
DATA_TYPE       FLOAT:numeric
```

`NUMBER(p,s)` then becomes `decimal(p,s)` everywhere, `FLOAT` becomes
`numeric`. The detector reports once per file, at the first such
declaration. `BINARY_FLOAT`/`BINARY_DOUBLE` are IEEE in Oracle too and are
not flagged.

`--migrate` converts with these settings by default (see README, `--migrate`).

Implemented: `ora2pg_gap_report/detectors/number_as_float.py`.
