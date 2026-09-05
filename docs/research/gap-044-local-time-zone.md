# GAP-044: `TIMESTAMP WITH LOCAL TIME ZONE` — the time zone is lost

Oracle feature: `TIMESTAMP WITH LOCAL TIME ZONE` — the instant is stored
normalized, and on reading it is automatically converted into the current
session's time zone.

## Minimal example

```sql
CREATE TABLE durations (
    id      NUMBER PRIMARY KEY,
    span_ym INTERVAL YEAR(4) TO MONTH,
    span_ds INTERVAL DAY(3) TO SECOND(6),
    ts_ltz  TIMESTAMP WITH LOCAL TIME ZONE
);
```

## ora2pg output (v25.0, `-t TABLE`)

```sql
CREATE TABLE durations (
	id bigint,
	span_ym interval,
	span_ds interval,
	ts_ltz timestamp
) ;
```

`TIMESTAMP WITH LOCAL TIME ZONE` becomes `timestamp` — that is,
**without** a time zone. The correct replacement would be `timestamptz`.

## Observed problem

There is no error at any stage — the table is created, the `INSERT`
succeeds, the `SELECT` returns a value. What exactly is lost was checked
against a real PostgreSQL 16:

```sql
SET TIME ZONE 'UTC';
INSERT INTO durations(id, ts_ltz) VALUES (1, TIMESTAMP '2026-01-15 12:00:00');
SET TIME ZONE 'Asia/Tokyo';
SELECT ts_ltz FROM durations WHERE id = 1;
-- 2026-01-15 12:00:00   (the same value)
```

The column's resulting type is `timestamp without time zone`. On Oracle
that same value would have come back shifted in a Tokyo session. So the
conversion into the session's time zone — the entire point of the original
type — silently disappears.

Noted separately (not raised as its own gap): the `INTERVAL YEAR TO MONTH`
/ `INTERVAL DAY TO SECOND` qualifiers are lost too, becoming an untyped
`interval` — which also removes the constraint on which interval fields
are allowed.

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16.

## Verdict

**Gap confirmed.** Implemented in
`ora2pg_gap_report/detectors/local_time_zone.py`. Manual fix: change the
column's type to `timestamptz`, which does exactly what Oracle's LTZ does.
