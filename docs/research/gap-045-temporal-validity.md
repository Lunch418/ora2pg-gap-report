# GAP-045: `PERIOD FOR` — Temporal Validity, truncated in the output

Oracle feature: `PERIOD FOR <name> (<start>, <end>)` (12c Temporal
Validity) — declares a row's validity period, enabling "as it was on a
date" queries through `AS OF PERIOD FOR`.

## Minimal example

```sql
CREATE TABLE emp_hist (
    emp_id     NUMBER,
    valid_from DATE,
    valid_to   DATE,
    PERIOD FOR emp_valid_time (valid_from, valid_to)
);
```

## ora2pg output (v25.0, `-t TABLE`)

```sql
CREATE TABLE emp_hist (
	emp_id bigint,
	valid_from timestamp(0),
	valid_to timestamp(0),
	period FOR
) ;
```

This is neither dropping the clause nor copying it whole — a **stump**,
`period FOR`, is left in the column list, with no period name and no
column list.

## Observed problem

Confirmed against a real PostgreSQL 16 — creating the whole table breaks,
not merely the feature being lost:

```
ERROR:  syntax error at or near "FOR"
LINE 5:  period FOR
                ^
```

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16.

## Verdict

**Gap confirmed.** Implemented in
`ora2pg_gap_report/detectors/temporal_validity.py`. PostgreSQL has no
built-in temporal validity. Manual rework: an ordinary pair of timestamp
columns plus filtering on them in queries, or a `tstzrange` type with an
exclusion constraint if overlapping periods need to be controlled.

## The DBMS_METADATA.GET_DDL spelling (added 2026-09-26)

An export from a live Oracle 23ai does not put the period inside the
`CREATE TABLE`; `GET_DDL` writes it as a separate statement after it:

```sql
  CREATE TABLE "G045"."EMP_HIST"
   (	"EMP_ID" NUMBER,
	"VALID_FROM" DATE,
	"VALID_TO" DATE
   ) ...
  ALTER TABLE "G045"."EMP_HIST" ADD PERIOD FOR "EMP_VALID_TIME"("VALID_FROM","VALID_TO")
```

ora2pg 25.0 (`-t TABLE` on that file) drops the `ALTER TABLE` entirely:

```sql
CREATE TABLE g045.emp_hist (
	emp_id bigint,
	valid_from timestamp(0),
	valid_to timestamp(0)
) ;
```

So in this spelling nothing fails to load — the period is lost silently.
The detector flags both spellings; the `ALTER TABLE` one carries its own
message (`temporal_validity.alter`) saying so.
