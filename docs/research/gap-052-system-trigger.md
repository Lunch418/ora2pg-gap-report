# GAP-052: system triggers (`ON DATABASE` / `ON SCHEMA`)

Oracle feature: a trigger on a database or schema event rather than on a
table — `LOGON`, `LOGOFF`, `SERVERERROR`, `DDL`, `STARTUP`, `SHUTDOWN` and
so on.

## Minimal example

```sql
CREATE OR REPLACE TRIGGER trg_logon
AFTER LOGON ON DATABASE
BEGIN
  INSERT INTO login_audit (who, when_) VALUES (USER, SYSDATE);
END;
/
```

## ora2pg output (v25.0, `-t TRIGGER`)

```sql
DROP TRIGGER IF EXISTS trg_logon ON database CASCADE;
CREATE OR REPLACE FUNCTION trigger_fct_trg_logon() RETURNS trigger AS $BODY$
BEGIN
  INSERT INTO login_audit(who, when_) VALUES (USER, statement_timestamp());
RETURN NEW;
END
$BODY$
 LANGUAGE 'plpgsql';
CREATE TRIGGER trg_logon
	AFTER LOGON ON database FOR EACH ROW
	EXECUTE PROCEDURE trigger_fct_trg_logon();
```

The system trigger is carried over as an ordinary table trigger: the word
`database` is substituted where the table name goes, and the `LOGON` event
is left as written.

## Observed problem

Confirmed against a real PostgreSQL 16:

```
ERROR:  syntax error at or near "LOGON"
LINE 2:  AFTER LOGON ON database FOR EACH ROW
               ^
```

The `SCHEMA` scope with a different event was checked too:

```
ERROR:  syntax error at or near "DDL"
LINE 2:  BEFORE DDL ON schema FOR EACH ROW
                ^
```

and `SERVERERROR`:

```
ERROR:  syntax error at or near "SERVERERROR"
LINE 2:  AFTER SERVERERROR ON database FOR EACH ROW
               ^
```

So the detector keys on the scope (`ON DATABASE` / `ON SCHEMA`) rather
than on a list of events: a list of events can go out of date, a scope
cannot.

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16.

## Verdict

**Gap confirmed.** Implemented in
`ora2pg_gap_report/detectors/system_trigger.py`. Manual rework: there is
no direct analogue for any of the events. DDL events are covered by
PostgreSQL's event triggers (`CREATE EVENT TRIGGER ... ON
ddl_command_end`), while `LOGON`/`LOGOFF`/`SERVERERROR` are not triggers
at all there — they become server-side logging or application logic.
