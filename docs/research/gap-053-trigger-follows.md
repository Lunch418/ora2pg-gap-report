# GAP-053: `FOLLOWS` / `PRECEDES` — trigger firing order

Oracle feature: a clause specifying the firing order of triggers on the
same event of the same table.

## Minimal example

```sql
CREATE OR REPLACE TRIGGER trg_b
BEFORE INSERT ON employees
FOR EACH ROW
FOLLOWS trg_a
BEGIN
  :NEW.audited := 'Y';
END;
/
```

## ora2pg output (v25.0, `-t TRIGGER`)

```sql
CREATE OR REPLACE FUNCTION trigger_fct_trg_b() RETURNS trigger AS $BODY$
FOLLOWS trg_a
BEGIN
  NEW.audited := 'Y';
RETURN NEW;
END
$BODY$
 LANGUAGE 'plpgsql';
CREATE TRIGGER trg_b
	BEFORE INSERT ON employees FOR EACH ROW
	EXECUTE PROCEDURE trigger_fct_trg_b();
```

The key point: the clause is not dropped — it ends up **inside the
function body**, between `AS $BODY$` and `BEGIN`.

## Observed problem

The load succeeds entirely cleanly (ora2pg sets `check_function_bodies =
false` in its output, so the body is not parsed):

```
DROP TRIGGER
CREATE FUNCTION
CREATE TRIGGER
```

The failure happens on the very first `INSERT` into the table. Confirmed
against a real PostgreSQL 16:

```
ERROR:  syntax error at or near "FOLLOWS"
LINE 2: FOLLOWS trg_a
        ^
QUERY:
FOLLOWS trg_a
BEGIN
```

So what breaks is not the trigger firing order but every insert into the
table — this is `failure_stage = runtime`, not `deployment`, and it was
verified that way rather than inferred by analogy.

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16.

## Verdict

**Gap confirmed.** Implemented in
`ora2pg_gap_report/detectors/trigger_follows.py`. The detector looks for
the clause only in the trigger's header (from `CREATE TRIGGER` to the
first `DECLARE`/`BEGIN`/`CALL`) — where Oracle's grammar allows it:
`FOLLOWS` on its own is a perfectly ordinary identifier (`SELECT follows
FROM t`), and without that restriction the detector would produce false
positives.

Manual rework: PostgreSQL has no "after this named trigger" ordering —
triggers on the same event fire in alphabetical order of their names. The
clause has to go, and the required sequence achieved through naming
(`t10_...`, `t20_...`) or by merging the triggers into one.
