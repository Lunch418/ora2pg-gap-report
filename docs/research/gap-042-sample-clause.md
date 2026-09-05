# GAP-042: `SAMPLE (n)` — sampling a percentage of rows

Oracle feature: sampling a random percentage of a table's rows (`SAMPLE`)
or blocks (`SAMPLE BLOCK`) directly in `FROM`.

## Minimal example

```sql
CREATE OR REPLACE VIEW v_sampled AS
SELECT employee_id, last_name
FROM employees SAMPLE (10);
```

## ora2pg output (v25.0, `-t VIEW`)

```sql
CREATE OR REPLACE VIEW v_sampled AS SELECT employee_id, last_name
FROM employees SAMPLE(10);
```

Copied as written.

## Observed problem

Confirmed against a real PostgreSQL 16:

```
ERROR:  syntax error at or near "10"
LINE 2: FROM employees SAMPLE(10);
                              ^
```

What is distinctive about this gap: PostgreSQL **does** have the
equivalent functionality — `TABLESAMPLE BERNOULLI (n)` / `TABLESAMPLE
SYSTEM (n)` — but the syntax differs, and ora2pg does not make the
substitution. So the problem is not a missing capability but an
unconverted syntax.

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16.

## Verdict

**Gap confirmed.** Implemented in
`ora2pg_gap_report/detectors/sample_clause.py`. Manual rework: `SAMPLE
(n)` → `TABLESAMPLE BERNOULLI (n)` (row-wise sampling, closer to Oracle's
`SAMPLE`), `SAMPLE BLOCK (n)` → `TABLESAMPLE SYSTEM (n)`.
