# GAP-049: `NLSSORT` — language-aware sorting

Oracle feature: `NLSSORT(col, 'NLS_SORT=<language>')` — a sort key
following a particular language's rules.

## Minimal example

```sql
SELECT name FROM employees
 ORDER BY NLSSORT(name, 'NLS_SORT=GERMAN');
```

## ora2pg output (v25.0, `-t QUERY`)

```sql
SELECT name FROM employees
 ORDER BY name COLLATE "GERMAN";
```

The substitution to `COLLATE` is right in form, but Oracle's language name
is passed through as a PostgreSQL collation name one to one.

## Observed problem

Confirmed against a real PostgreSQL 16 (against a real `employees` table):

```
ERROR:  collation "GERMAN" for encoding "UTF8" does not exist
LINE 2:  ORDER BY name COLLATE "GERMAN";
                       ^
```

Oracle's and PostgreSQL's collation names do not match: `GERMAN`,
`FRENCH`, `RUSSIAN` and the other Oracle names do not exist in PostgreSQL.
The error appears when the query runs, not when the schema loads.

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16.

## Verdict

**Gap confirmed.** Implemented in
`ora2pg_gap_report/detectors/nlssort.py`. Manual rework: map each Oracle
name onto a real PostgreSQL locale (for German, `"de-DE-x-icu"` on an
ICU-enabled build, or `"de_DE.utf8"` otherwise) and create it with `CREATE
COLLATION` where needed.
