# GAP-043: `ACCESSIBLE BY` — a whitelist of callers

Oracle feature: `ACCESSIBLE BY (...)` (12c+) declares a subprogram
accessible only to the listed packages, procedures or functions; anything
else gets a compilation error on trying to call it. A means of
encapsulation within one schema, layered on top of ordinary `GRANT`s.

## Minimal example

```sql
CREATE OR REPLACE PROCEDURE secret_proc (p_id NUMBER)
  ACCESSIBLE BY (PACKAGE hr_admin_pkg)
IS
BEGIN
  UPDATE employees SET salary = salary * 1.1 WHERE employee_id = p_id;
END;
/
```

## ora2pg output (v25.0, `-t PROCEDURE`)

```sql
CREATE OR REPLACE PROCEDURE secret_proc (p_id bigint) ACCESSIBLE BY (PACKAGE hr_admin_pkg) AS $body$
BEGIN
  UPDATE employees SET salary = salary * 1.1 WHERE employee_id = p_id;
END;
$body$
LANGUAGE PLPGSQL
;
```

The clause is carried over verbatim, straight into the function header.

## Observed problem

Confirmed against a real PostgreSQL 16 — it fails at load, so the
procedure is not created at all:

```
ERROR:  syntax error at or near "ACCESSIBLE"
LINE 1: ...TE OR REPLACE PROCEDURE secret_proc (p_id bigint) ACCESSIBLE...
                                                             ^
```

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16.

## Verdict

**Gap confirmed.** Implemented in
`ora2pg_gap_report/detectors/accessible_by.py`. PostgreSQL has no direct
analogue: a restriction on *which code* may call something cannot be
expressed. The nearest equivalent in spirit is moving the subprogram into
a separate schema and managing `GRANT`/`REVOKE`, which gives protection at
the level of roles rather than of specific calling subprograms.
