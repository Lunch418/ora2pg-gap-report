# GAP-017: `JSON_TABLE(...)` — does not exist in PostgreSQL 16 and earlier

Oracle feature: `JSON_TABLE(json_doc, path COLUMNS (...))` — a tabular
projection of a JSON document into ordinary relational rows and columns,
directly in `FROM`.

## Minimal example

```sql
SELECT COUNT(*) INTO v_count
FROM JSON_TABLE(
    '[{"id":1,"amount":100},{"id":2,"amount":200}]',
    '$[*]'
    COLUMNS (
        id     NUMBER PATH '$.id',
        amount NUMBER PATH '$.amount'
    )
);
```

## ora2pg output (v25.0, `-t PACKAGE`)

The construct is copied as written — `JSON_TABLE`, `COLUMNS` and `PATH`
are not rewritten into anything.

## Observed problem

Confirmed against a real PostgreSQL 16: `CREATE PROCEDURE` succeeds
without error and fails on the first call:

```
ERROR:  syntax error at or near "COLUMNS"
```

PostgreSQL 16 and earlier have no `JSON_TABLE` function at all.
**Important caveat:** PostgreSQL 17 added `JSON_TABLE`, but with its own
`COLUMNS` syntax (notably `NESTED PATH` and the placement of
`ERROR`/`DEFAULT ... ON ERROR`); whether that matches Oracle's syntax was
not verified empirically in this research, since only PostgreSQL 16 was
available in the sandbox. The detector therefore makes no distinction by
target version and always flags the construct — a false positive on PG17,
where some of it may convert nearly as-is, is preferable to missing a real
failure on the still more widespread 16 and earlier.

**Reproducible: YES (PostgreSQL 16).** Ora2Pg version: 25.0.

## Verdict

**Gap confirmed.** Implemented in
`ora2pg_gap_report/detectors/json_table.py`.

## PostgreSQL 17 and 18

Checked later with ora2pg 25.0 and real PostgreSQL 16, 17 and 18
(`tests/test_pg_version.py`, the output recorded in
`tests/fixtures/pg_version/`). ora2pg rewrites the column types (`NUMBER`
-> `bigint`) and keeps the rest; on 17 and 18 the procedure loads and
returns the same count, and a `NESTED PATH ... COLUMNS (...)` works too.
What does not is Oracle's placement of the error handling, before the
column list: `'$[*]' ERROR ON ERROR COLUMNS (...)` fails with `syntax
error at or near "ERROR"` - PostgreSQL takes `ON ERROR`/`ON EMPTY` after
`COLUMNS (...)`.

So with `--pg-version 17` (or 18) a plain JSON_TABLE is no longer
reported; one with `ON ERROR`/`ON EMPTY` before `COLUMNS` is, with its own
message (`json_table.on_error`): move the clause after the column list.
