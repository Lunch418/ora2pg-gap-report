# GAP-117: a package procedure called from a trigger is copied without `CALL`

Oracle feature: a trigger body that calls a package procedure as a
statement - `audit_pkg.log_change(:NEW.id, 'X');`, `audit_pkg.touch;` -
which is how most real triggers delegate their work.

## How it was found

`--load-check` on ora2pg's output for
`docs/research/samples/compound_trigger_dlee.sql`: the trigger functions
calling `equitable_salaries_pkg.make_equitable` did not load.

## Minimal example

```sql
CREATE OR REPLACE TRIGGER t_biu BEFORE INSERT OR UPDATE ON orders FOR EACH ROW
DECLARE
  v NUMBER;
BEGIN
  audit_pkg.log_change(:NEW.id, 'X');
  audit_pkg.touch;
  v := audit_pkg.next_seq(:NEW.id);
  :NEW.total := v;
END;
/
```

Oracle 23ai compiles and fires it (with `audit_pkg` present).

## ora2pg output (v25.0, `-t TRIGGER`)

```sql
CREATE OR REPLACE FUNCTION trigger_fct_t_biu() RETURNS trigger AS $BODY$
DECLARE
  v bigint;
BEGIN
  audit_pkg.log_change(NEW.id, 'X');
  audit_pkg.touch;
  v := audit_pkg.next_seq(NEW.id);
  NEW.total := v;
RETURN NEW;
END
$BODY$
 LANGUAGE 'plpgsql';
```

The two procedure calls are copied as written. The function call inside
an assignment is fine.

Inside a package the same call is converted: in one run with both
packages, `other_pkg.do_it;` becomes `CALL other_pkg.do_it();`, whichever
package comes first in the file. ora2pg knows a name is a procedure only
when the procedure is in the same run, and triggers are always a run of
their own (`-t TRIGGER`).

## Observed problem

PostgreSQL 16 rejects the trigger function, and then the trigger:

```
ERROR:  42601: syntax error at or near "audit_pkg"
ERROR:  42883: function trigger_fct_t_biu() does not exist
```

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16, Oracle 23ai.

## Verdict

**Gap confirmed, severity high, failure_stage deployment.** Add `CALL`
before each package procedure call in the trigger function. Calls into
`DBMS_*`/`UTL_*` are left to `dbms_utl_calls`.

Implemented: `ora2pg_gap_report/detectors/trigger_package_call.py`.
