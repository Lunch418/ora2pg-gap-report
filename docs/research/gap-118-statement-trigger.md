# GAP-118: a statement-level trigger becomes `FOR EACH ROW`

Oracle feature: a DML trigger without `FOR EACH ROW` - a statement-level
trigger, which fires once per triggering statement however many rows it
touches. Used for refreshing summaries, logging a batch, enforcing a rule
across the whole table after a change.

## How it was found

While checking GAP-117's trigger output: the minimal statement-level
trigger came out with `FOR EACH ROW`.

## Minimal example

```sql
CREATE OR REPLACE TRIGGER gx_t_ai AFTER INSERT ON gx_orders
BEGIN
  UPDATE gx_fired SET n = n + 1;
END;
/
```

In a live Oracle 23ai, `INSERT INTO gx_orders SELECT level FROM dual
CONNECT BY level <= 5` inserts five rows and the trigger runs once:
`gx_fired.n` is 1.

## ora2pg output (v25.0, `-t TRIGGER`)

The same for the hand-written source and for `DBMS_METADATA.GET_DDL`
(`CREATE OR REPLACE EDITIONABLE TRIGGER "HR"."GX_T_AI" AFTER INSERT ON
gx_orders ...`):

```sql
CREATE OR REPLACE FUNCTION trigger_fct_gx_t_ai() RETURNS trigger AS $BODY$
BEGIN
  UPDATE gx_fired SET n = n + 1;
RETURN NEW;
END
$BODY$
 LANGUAGE 'plpgsql';
CREATE TRIGGER gx_t_ai
	AFTER INSERT ON gx_orders FOR EACH ROW
	EXECUTE PROCEDURE trigger_fct_gx_t_ai();
```

## Observed problem

Everything loads into PostgreSQL 16. The same five-row insert then runs
the trigger five times: `gx_fired.n` is 5. Checked with
`--load-check`, where an `ASSERT (SELECT n FROM gx_fired) = 1` after the
insert fails. Nothing reports an error; whatever the trigger counts,
logs or recomputes is multiplied by the number of rows, and a trigger
that recomputes a whole table now does it once per row.

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16, Oracle 23ai.

## Verdict

**Gap confirmed, severity high, failure_stage semantic.** In the
generated trigger, change `FOR EACH ROW` to `FOR EACH STATEMENT`, and in
its function `RETURN NEW` to `RETURN NULL` (a statement trigger has no
row). Not flagged: `INSTEAD OF` triggers (row-level by definition),
compound triggers (GAP-004), triggers on `SCHEMA`/`DATABASE` (GAP-052).

Implemented: `ora2pg_gap_report/detectors/statement_trigger.py`.
