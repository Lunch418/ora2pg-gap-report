# GAP-127: an index on a column prefix breaks the file

MySQL/MariaDB feature: an index on the first N characters of a column -
`KEY idx_note (note(20))`, `UNIQUE KEY uq_code (code(8))`. MySQL requires
it for TEXT and BLOB columns, and mysqldump writes it as it is.

## How it was found

`--migrate --dialect mysql --load-check docker` on a realistic mysqldump:
with the `INDEX` spelling (which GAP-073 points to), the converted file
loaded nothing at all and reported nothing either.

## Minimal example

`tests/fixtures/mysql_indexes/prefix_index_source.sql`:

```sql
CREATE TABLE `t1` (
  `id` int NOT NULL,
  `note` varchar(200) DEFAULT NULL,
  PRIMARY KEY (`id`),
  INDEX `idx_note` (`note`(20))
) ENGINE=InnoDB;
CREATE TABLE `t2` (`id` int NOT NULL, PRIMARY KEY (`id`)) ENGINE=InnoDB;
```

## ora2pg output (v25.0, `-m -t TABLE`)

```sql
CREATE INDEX idx_note ON t1 (note"(20);
```

for `INDEX`, and for `UNIQUE KEY uq (note(20))`:

```sql
ALTER TABLE t1 ADD UNIQUE ("note(20");
```

The `KEY` spelling is GAP-073's broken column.

## Observed problem

The `"` opens a quoted identifier that never closes: psql reads the whole
rest of the file into it, so `t2` and everything after the index is never
run. `--load-check` skips such a file and says so, instead of reporting it
loaded. The UNIQUE form fails on its own:

```
ERROR:  42703: column "note(20" named in key does not exist
```

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16. Source
dialect: MySQL (`ora2pg -m`).

## Verdict

**Gap confirmed, severity high, failure_stage deployment.** PostgreSQL has
no prefix index, so there is no one right rewrite, and `--prepare` leaves
these clauses as they are. Per index: an expression index on
`left(note, 20)` (what the prefix meant), an index on the whole column
(long TEXT values may exceed the btree row limit), or no index. A UNIQUE
on a prefix and a UNIQUE on the whole column are different constraints -
the first one rejects rows the second accepts.

Implemented: `ora2pg_gap_report/detectors/mysql_index_prefix.py`;
`--load-check` recognises the UNIQUE shape.
