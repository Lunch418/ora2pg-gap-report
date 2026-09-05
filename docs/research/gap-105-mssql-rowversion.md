# GAP-105: `ROWVERSION` becomes `bytea` and stops updating

MSSQL feature: `ROWVERSION` — a column whose value the server changes by
itself on every modification of the row. Optimistic locking is usually
built on it.

## Minimal example

```sql
CREATE TABLE versioned (
    id int NOT NULL PRIMARY KEY,
    rv rowversion NOT NULL
);
```

## ora2pg output (v25.0, `-M -t TABLE`)

```sql
CREATE TABLE versioned (
	id integer NOT NULL,
	rv bytea NOT NULL
) ;
ALTER TABLE versioned ADD PRIMARY KEY (id);
```

The type is the right size, but `bytea` lacks the essential part —
self-updating.

## Observed problem

There will be no error at any stage, and that is the dangerous part.
After the migration the value of `rv` never changes, which means a check
of the form

```sql
UPDATE versioned SET ... WHERE id = @id AND rv = @rv_read_earlier;
```

always matches. Concurrent-edit conflicts stop being detected and edits
silently overwrite each other — exactly the scenario the column was
introduced to prevent.

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16. Source
dialect: MSSQL (`ora2pg -M`).

## Verdict

**Gap confirmed, severity high, failure_stage semantic.** Restored with
a `BEFORE UPDATE` trigger incrementing a version counter, or by moving to
`xmin` — PostgreSQL's system column, which changes on every row update by
itself. Check columns of type `timestamp` separately: in T-SQL that is a
deprecated synonym for `ROWVERSION`, and the detector deliberately does
not flag it, so as not to confuse it with a column that is merely named
`timestamp`. Implemented:
`ora2pg_gap_report/detectors/mssql_rowversion.py`.
