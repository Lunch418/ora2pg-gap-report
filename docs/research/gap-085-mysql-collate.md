# GAP-085: `COLLATE`/`CHARACTER SET` on a column is dropped

MySQL/MariaDB feature: the comparison and sorting rule for strings, set
on a specific column.

## Minimal example

```sql
CREATE TABLE col1 (
  id INT PRIMARY KEY,
  name VARCHAR(50) COLLATE utf8mb4_general_ci NOT NULL
);
```

`utf8mb4_general_ci` is a case-insensitive collation, one of the most
common in real MySQL schemas.

## ora2pg output (v25.0, `-m -t TABLE`)

```sql
CREATE TABLE col1 (
	id integer,
	name varchar(50) NOT NULL
) ;
ALTER TABLE col1 ADD PRIMARY KEY (id);
```

`COLLATE` lines in the output: zero. Same for `CHARACTER SET utf8mb4
COLLATE utf8mb4_bin`.

## Observed problem

No error at load or afterwards, but string comparison silently changes
meaning: MySQL's `*_ci` collations are case-insensitive, while comparison
in PostgreSQL is case-sensitive by default. Verified on live data, real
PostgreSQL 16:

```
=# INSERT INTO col1 VALUES (1,'Alice');
=# SELECT count(*) FROM col1 WHERE name = 'alice';
 rows_matching_lowercase_alice
-------------------------------
                             0
```

In MySQL with the original collation the same query would have found one
row. So it is not the schema that breaks but query results: logins, name
searches and uniqueness checks start behaving differently.

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16. Source
dialect: MySQL (`ora2pg -m`).

## Verdict

**Gap confirmed, severity high, failure_stage semantic.** Severity is
high rather than medium precisely because query results change, not just
the execution plan (cf. GAP-018/`invisible_index`, where only an
optimizer hint is lost and severity is medium). Restored with an explicit
`COLLATE` on the column (PostgreSQL offers ICU collations with the
required sensitivity), with the `citext` type, or by wrapping both sides
of the comparison in `lower()`. Implemented:
`ora2pg_gap_report/detectors/mysql_collate.py`.
