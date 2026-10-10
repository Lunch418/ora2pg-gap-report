# GAP-146: a parameter without a default after one with a default

Oracle feature: any parameter may have a default, wherever it is; callers name the arguments they skip around.

## How it was found

Running --migrate --load-check on other people's code (utPLSQL, OraOpenSource Logger, the Alexandria PL/SQL library, Oracle's sample schemas) and reading the errors no known gap explained.

## Minimal example

`tests/fixtures/corpus_gaps/oracle_functions.sql`, VALID in a live Oracle 23ai:

```sql
CREATE OR REPLACE PROCEDURE gx_c2(p_text VARCHAR2 DEFAULT NULL, p_id OUT NUMBER) IS
BEGIN
  p_id := NVL(LENGTH(p_text), 0);
END;
/
```

## ora2pg output (v25.0)

```sql
CREATE OR REPLACE PROCEDURE gx_c2 (p_text text DEFAULT NULL, p_id OUT bigint) AS $body$
```

The order is kept.

## Observed problem

PostgreSQL 16 rejects it - checked for every shape: an input parameter (IN or IN OUT) without a default after one with a default fails in a function and a procedure alike; an OUT parameter fails in a procedure and is allowed in a function.

```
ERROR:  procedure OUT parameters cannot appear after one with a default value
ERROR:  input parameters after one with a default value must also have defaults
```

Found in OraOpenSource Logger: `ins_logger_logs` and `ins_logger_logs_atx`.

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16, Oracle 23ai.

## Verdict

**Gap confirmed, severity high, failure_stage deployment.** No mechanical fix: moving the defaulted parameters to the end changes every call that passes arguments by position. Give the later parameters defaults, or reorder and check the calls.

Implemented: `ora2pg_gap_report/detectors/param_after_default.py`.
