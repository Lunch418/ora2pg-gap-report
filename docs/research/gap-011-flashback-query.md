# GAP-011: `AS OF TIMESTAMP`/`AS OF SCN` — flashback query

Oracle feature: `SELECT ... FROM table AS OF TIMESTAMP (...)` / `AS OF SCN
...` — reading a table as it was in the past (using Oracle's undo data),
with no separate history table.

## Minimal example

```sql
SELECT COUNT(*) INTO v_count
FROM orders AS OF TIMESTAMP (SYSTIMESTAMP - INTERVAL '1' DAY)
WHERE status = 'OPEN';
```

## ora2pg output (v25.0, `-t PACKAGE`)

The construct is copied as written, but with the text incidentally
corrupted while substituting `SYSTIMESTAMP` → `statement_timestamp()`: the
output came out as `AS OF timestamp(tatement_timestamp() - INTERVAL '1'
DAY)` — the leading `s` of `statement_timestamp` is missing. This looks
like an artefact of a collision between the `SYSTIMESTAMP` replacement and
the lowercasing of the `TIMESTAMP` in `AS OF TIMESTAMP`. Not tested with
other time expressions — it may be specific to this particular case.

## Observed problem

Confirmed against a real PostgreSQL 16: `CREATE PROCEDURE` succeeds
without error and fails on the first call:

```
ERROR:  syntax error at or near "timestamp"
```

But even without the corrupted text the result would be invalid —
PostgreSQL has no built-in equivalent of a flashback query at all. It
needs a separate architectural mechanism: temporal tables through an
extension, or purpose-built history/audit tables, rather than a syntactic
substitution.

**Reproducible: YES.** Ora2Pg version: 25.0.

## Verdict

**Gap confirmed.** Implemented in
`ora2pg_gap_report/detectors/flashback_query.py`.
