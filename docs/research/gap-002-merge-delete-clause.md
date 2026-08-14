# GAP-002: `MERGE ... DELETE WHERE` (Oracle's compound MERGE-DELETE clause)

Oracle feature: `MERGE` statement's optional `DELETE WHERE` clause nested
inside `WHEN MATCHED THEN UPDATE SET ...` — deletes rows that were just
matched and updated, if they also satisfy the delete condition. Documented,
standard Oracle syntax (SQL Language Reference, `MERGE` statement).

## Minimal example

```sql
MERGE INTO customers c
USING staging_customers s
ON (c.customer_id = s.customer_id)
WHEN MATCHED THEN
  UPDATE SET c.name = s.name, c.updated_at = SYSDATE
  WHERE s.name IS NOT NULL
  DELETE WHERE s.is_deleted = 1
WHEN NOT MATCHED THEN
  INSERT (customer_id, name, created_at)
  VALUES (s.customer_id, s.name, SYSDATE);
```

## ora2pg output (v25.0, `-t PACKAGE`, default and `PG_VERSION 16` — identical)

The `MERGE` statement is passed through almost verbatim (only `SYSDATE` →
`clock_timestamp()`, and an Oracle empty-string/NULL equivalence fixup on
the `WHERE`). The `DELETE WHERE s.is_deleted = 1` clause is left exactly as
written.

## Observed problem

PostgreSQL's `MERGE` (15+) has no equivalent of Oracle's compound
`UPDATE SET ... WHERE ... DELETE WHERE ...` clause — each `WHEN` branch is
a single action (`UPDATE`, `DELETE`, `INSERT`, or `DO NOTHING`); the
Oracle-only "delete some of the matched-and-updated rows" behavior has no
direct syntax. The equivalent in PostgreSQL requires splitting into two
`WHEN MATCHED` branches with complementary conditions.

Confirmed against a real PostgreSQL 16 server: `CREATE PROCEDURE` succeeds
silently (ora2pg's output sets `SET check_function_bodies = false`, so the
body isn't parsed at creation time) — the error only surfaces on the first
actual `CALL`:

```
ERROR:  syntax error at or near "WHERE"
LINE 6:       WHERE (s.name IS NOT NULL AND s.name::text <> '')
              ^
```

**Reproducible: YES.** Ora2Pg version: 25.0. PostgreSQL version: 16.

## Scope check: plain `MERGE` (no `DELETE WHERE`)

Tested separately — a `MERGE` with only `WHEN MATCHED THEN UPDATE SET ...`
and `WHEN NOT MATCHED THEN INSERT ...` (no `DELETE WHERE` clause) converts
correctly and loads/runs without error on PostgreSQL 16. **Plain `MERGE` is
not a gap** — detecting it would be exactly the keyword-driven false
positive this project's methodology avoids.

## Verdict

**Gap confirmed, narrowly scoped to `MERGE`'s `DELETE WHERE` sub-clause.**
Dangerous specifically because it fails silently at object-creation time
and only errors at runtime — a migration could pass a "does everything
compile" smoke check and still break in production the first time this
code path executes.

Candidate detector: flag `DELETE\s+WHERE` appearing inside a `MERGE`
statement's `WHEN MATCHED` branch in the Oracle source (cheap, source-level
check — no `ora2pg` invocation needed, same design as `autonomous_tx`/
`compound_triggers`/`dbms_utl_calls`).
