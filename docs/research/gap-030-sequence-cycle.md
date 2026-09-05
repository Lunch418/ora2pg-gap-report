# GAP-030: `CREATE SEQUENCE ... CYCLE` loses the `CYCLE` clause

Oracle feature: `CREATE SEQUENCE ... CYCLE` — once `MAXVALUE` is reached
(or `MINVALUE` for a descending sequence), `NEXTVAL` does not fail but
starts counting again from `MINVALUE`. Common practice for sequences over
a bounded range of values (status codes, slot numbers, cyclic batch
identifiers).

## Minimal example

```sql
CREATE SEQUENCE seq_small
  START WITH 1
  INCREMENT BY 1
  MAXVALUE 3
  CYCLE
  NOCACHE
  ORDER;
```

## ora2pg output (v25.0, `-t SEQUENCE`)

```sql
CREATE SEQUENCE seq_small INCREMENT 1 NO MINVALUE MAXVALUE 3 START 1;
```

The `CYCLE` clause disappears without trace. (`ORDER`/`NOCACHE` are not
carried over either, but those are RAC-specific and performance semantics
with no analogue and no consequence for correctness — not the same thing
as `CYCLE`.)

## Observed problem

Not a syntax error — the `CREATE SEQUENCE` runs without trouble, and the
sequence works normally until its range is exhausted. Confirmed against a
real PostgreSQL 16:

```sql
SELECT nextval('seq_small'), nextval('seq_small'), nextval('seq_small');
--  1 | 2 | 3

SELECT nextval('seq_small');
-- ERROR:  nextval: reached maximum value of sequence "seq_small" (3)
```

On Oracle that same fourth `NEXTVAL` would have returned `1` and carried
on indefinitely. After migration the sequence behaves identically to the
original right up to the moment its range runs out — which may be months
after the migration, in production rather than in testing. The failure
surfaces as an `ERROR` on the next insert (an `INSERT` with `DEFAULT
nextval(...)` or an explicit call), exactly where the application expected
the sequence to behave as it did on Oracle.

**Reproducible: YES.** Ora2Pg version: 25.0.

## Verdict

**Gap confirmed.** Implemented in
`ora2pg_gap_report/detectors/sequence_cycle.py`.
