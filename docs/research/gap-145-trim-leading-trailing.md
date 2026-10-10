# GAP-145: `TRIM(LEADING ... FROM ...)` becomes `trim(both leading ...)`

Oracle feature: `TRIM(LEADING x FROM y)`, `TRIM(TRAILING x FROM y)` - the same syntax PostgreSQL has.

## How it was found

Running --migrate --load-check on other people's code (utPLSQL, OraOpenSource Logger, the Alexandria PL/SQL library, Oracle's sample schemas) and reading the errors no known gap explained.

## Minimal example

`tests/fixtures/corpus_gaps/oracle_functions.sql`, VALID in a live Oracle 23ai:

```sql
  RETURN trim(leading a_c from a_item) || '|' || trim(trailing a_c from a_item) || '|' || a_base;
```

## ora2pg output (v25.0)

```sql
  RETURN trim(both leading a_c from a_item) || '|' || trim(both trailing a_c from a_item) || '|' || a_base;
```

ora2pg puts BOTH in front of every TRIM, also in front of a LEADING or TRAILING already there. `TRIM(BOTH ...)` and `TRIM(x)` come out right.

## Observed problem

The routine does not load:

```
ERROR:  syntax error at or near "leading"
```

Found in utPLSQL: `trim(leading a_connector from a_item)` in `ut_utils`.

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16, Oracle 23ai.

## Verdict

**Gap confirmed, severity high, failure_stage deployment.** Mechanical: `--fix` removes the extra BOTH (`fix_trim_both_side`), checked: `gx_c1('..ab..')` returns `ab..|..ab|0`, as in Oracle.

Implemented: `ora2pg_gap_report/detectors/trim_leading_trailing.py`.
