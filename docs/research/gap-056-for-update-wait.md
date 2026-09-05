# GAP-056: `FOR UPDATE ... WAIT n`

Oracle feature: locking rows, waiting no longer than n seconds.

## Minimal example

```sql
SELECT * FROM accounts WHERE id = 1 FOR UPDATE OF bal WAIT 5;
```

## ora2pg output (v25.0, `-t QUERY`)

```sql
SELECT * FROM accounts WHERE id = 1 FOR UPDATE OF bal WAIT 5;
```

Copied as written.

## Observed problem

Confirmed against a real PostgreSQL 16:

```
ERROR:  syntax error at or near "WAIT"
LINE 1: ...ELECT * FROM accounts WHERE id = 1 FOR UPDATE OF bal WAIT 5;
                                                                ^
```

`FOR UPDATE` in PostgreSQL offers only `NOWAIT` and `SKIP LOCKED` — there
is no "wait exactly n seconds" variant. `NOWAIT` is spelled the same in
both databases and is carried over correctly, so the detector flags only
the form with a numeric timeout.

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16.

## Verdict

**Gap confirmed.** Implemented in
`ora2pg_gap_report/detectors/for_update_wait.py`. Manual rework: the
equivalent is set at session level rather than per query — `SET LOCAL
lock_timeout = 'n s'` before `SELECT ... FOR UPDATE`. The difference is
not only syntactic: on timeout Oracle returns ORA-30006 while PostgreSQL
aborts the query on `lock_timeout`, so the error handling in the calling
code needs adjusting too.
