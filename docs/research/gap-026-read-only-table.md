# GAP-026: `CREATE TABLE ... READ ONLY` loses its immutability guarantee

Oracle feature: `CREATE TABLE ... READ ONLY` — the server blocks any
`INSERT`/`UPDATE`/`DELETE` against such a table (`ORA-12081`), regardless
of the connected user's privileges, including the schema owner's.

## Minimal example

```sql
CREATE TABLE audit_log (
    log_id  NUMBER,
    message VARCHAR2(200)
) READ ONLY;
```

## ora2pg output (v25.0, `-t TABLE`)

```sql
CREATE TABLE audit_log (
	log_id bigint,
	message varchar(200)
) ;
```

The `READ ONLY` clause disappears without trace.

## Observed problem

Not a syntax error — the `CREATE TABLE` runs without trouble. Confirmed
against a real PostgreSQL 16 directly:

```sql
INSERT INTO audit_log VALUES (1, 'should have been blocked in Oracle');
-- INSERT 0 1  -- succeeded
```

On Oracle that same `INSERT` would have failed with `ORA-12081: update
operation not allowed on table`, guaranteed. What is lost is not a
syntactic detail but a server-enforced data-integrity guarantee — for a
snapshot table or a historical archive that may be the only protection
against an accidental write.

PostgreSQL has no direct analogue of `READ ONLY` for an ordinary table.
The usual rewrite is `REVOKE INSERT, UPDATE, DELETE` from every role —
though in PostgreSQL the owner still bypasses `REVOKE` by default, so a
more explicit mechanism is needed — or a `BEFORE` trigger that rejects DML
outright.

**Reproducible: YES.** Ora2Pg version: 25.0.

## Verdict

**Gap confirmed.** Implemented in
`ora2pg_gap_report/detectors/read_only_table.py`.
