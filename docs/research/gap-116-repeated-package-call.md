# GAP-116: a repeated `pkg.proc;` without parentheses loses `CALL`

Oracle feature: calling a parameterless procedure without parentheses,
qualified with its own package's name (`job_pkg.refresh;`), from another
routine of the same package.

## How it was found

While reducing GAP-117 to a minimal case: a package body calling its own
procedure several times came out with one call converted and the next one
not.

## Minimal example

```sql
CREATE OR REPLACE PACKAGE BODY job_pkg AS
  PROCEDURE refresh IS
  BEGIN
    NULL;
  END;
  PROCEDURE run_all IS
  BEGIN
    job_pkg.refresh;
    job_pkg.refresh;
  END;
END job_pkg;
/
```

Oracle 23ai compiles and runs it.

## ora2pg output (v25.0, `-t PACKAGE`)

```sql
CREATE OR REPLACE PROCEDURE job_pkg.run_all () AS $body$
BEGIN
    CALL job_pkg.refresh();
    job_pkg.refresh();
  END;
$body$
LANGUAGE PLPGSQL
;
```

The first call gets `CALL`, the second only gets parentheses.

## Observed problem

PL/pgSQL does not accept a bare procedure call, so the routine does not
load into PostgreSQL 16:

```
ERROR:  42601: syntax error at or near "job_pkg"
```

What breaks it, from separate runs of the same package:

| In one routine | Result |
|---|---|
| `job_pkg.refresh;` once | converted |
| `refresh; job_pkg.refresh;` | the second is not |
| `job_pkg.refresh; job_pkg.refresh;` | the second is not |
| `refresh; refresh;` | converted |
| `job_pkg.refresh(); job_pkg.refresh();` | converted |
| `job_pkg.log_it('a'); job_pkg.log_it('b');` | converted |
| the same call once each in two routines | converted |

So: a qualified, parenthesis-free call to a procedure the same routine
has already called.

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16, Oracle 23ai.

## Verdict

**Gap confirmed, severity high, failure_stage deployment.** Add `CALL`
before the repeated call in the generated code, or write such calls with
parentheses in the source before converting.

Implemented: `ora2pg_gap_report/detectors/repeated_package_call.py`.
