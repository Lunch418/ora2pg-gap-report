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
