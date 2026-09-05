# GAP-086: `SET(...)` becomes `text` with no validation

MySQL/MariaDB feature: `SET('a','b',...)` — a type for a set of values:
the column may hold any subset of the listed values at once (stored as a
bit mask).

## Minimal example

```sql
CREATE TABLE perms (
  id INT PRIMARY KEY,
  flags SET('read','write','admin') NOT NULL
);
```

## ora2pg output (v25.0, `-m -t TABLE`)

```sql
CREATE TABLE perms (
	id integer,
	flags text NOT NULL
) ;
ALTER TABLE perms ADD PRIMARY KEY (id);
```

## Observed problem

No error at load or afterwards, and data already accumulated is migrated
as-is. What is lost is exactly the validation: after the migration any
string can be written into the column, including a value not on the list,
or plain garbage.

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16. Source
dialect: MySQL (`ora2pg -m`).

## Verdict

**Gap confirmed, severity medium, failure_stage semantic.** Severity
here is deliberately lower than for the related `ENUM` (GAP-068): `ENUM`
breaks the schema load outright — a reference to a non-existent type is
generated — whereas here the schema comes up and works, existing values
are preserved, and no query starts returning a wrong answer. The only
question is validation of future writes. Restored with a `CHECK`
constraint, an array with a check on the allowed elements, or a separate
link table — the last being the most honest option when there are many
values. Implemented: `ora2pg_gap_report/detectors/mysql_set_type.py`.
