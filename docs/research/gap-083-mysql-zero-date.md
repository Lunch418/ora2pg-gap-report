# GAP-083: `'0000-00-00'` silently becomes `'1970-01-01'`

MySQL/MariaDB feature: the "zero" date — not a real date but a marker
meaning "value not set", which MySQL allows in `DATE`/`DATETIME` for
historical reasons.

## Minimal example

```sql
CREATE TABLE events (
  id INT PRIMARY KEY,
  happened_on DATE NOT NULL DEFAULT '0000-00-00'
);
```

## ora2pg output (v25.0, `-m -t TABLE`)

```sql
CREATE TABLE events (
	id integer,
	happened_on date NOT NULL DEFAULT '1970-01-01'
) ;
ALTER TABLE events ADD PRIMARY KEY (id);
```

The "not set" marker has been replaced with a concrete date — the start
of the Unix epoch.

## Observed problem

No error at load or afterwards. Verified on live data, real PostgreSQL
16:

```
=# INSERT INTO events (id) VALUES (1);
INSERT 0 1
=# SELECT id, happened_on FROM events;
 id | happened_on
----+-------------
  1 | 1970-01-01
```

A row whose date would have been "not set" in MySQL now carries a
perfectly meaningful date of 1 January 1970. The consequences are purely
semantic and therefore hard to notice: queries like `WHERE d =
'0000-00-00'` (looking for unfilled values) stop finding anything, and
date reports start showing 1970 as a real event.

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16. Source
dialect: MySQL (`ora2pg -m`).

## Verdict

**Gap confirmed, severity high, failure_stage semantic.** The correct
port is `NULL` (dropping `NOT NULL` if needed) or a separate "not set"
flag. It is not only the `DEFAULT` that needs checking but the data
itself: zero dates in existing rows are migrated by the same mechanism.
Implemented: `ora2pg_gap_report/detectors/mysql_zero_date.py` — the
detector reads the comments-only view of the source, because the date
literal sits inside a string constant that ordinary masking blanks out.
