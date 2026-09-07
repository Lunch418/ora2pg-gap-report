# GAP-080: `AUTO_INCREMENT=<n>` — the counter's start value is lost on the file-based path

MySQL/MariaDB feature: the table option `AUTO_INCREMENT=<n>` — the next
value the counter will hand out. `mysqldump` always writes it for a
non-empty table, and it is always greater than the largest existing `id`.

## Minimal example

```sql
CREATE TABLE invoices (
  id INT PRIMARY KEY AUTO_INCREMENT,
  amount DECIMAL(10,2)
) ENGINE=InnoDB AUTO_INCREMENT=1000 DEFAULT CHARSET=utf8mb4;
```

## ora2pg output, file-based (v25.0, `-m -i schema.sql -t TABLE`)

```sql
CREATE TABLE invoices (
	id serial,
	amount decimal(10,2)
) ;
ALTER TABLE invoices ADD PRIMARY KEY (id);
```

The column itself is ported correctly — `AUTO_INCREMENT` became
`serial`. The start value, however, is gone: nowhere in the whole file is
there an `ALTER SEQUENCE ... RESTART WITH` or a `setval()` (verified with
`grep`), even though `AUTO_INCREMENT=1000` is sitting right there in the
`CREATE TABLE` text ora2pg is holding.

## The same schema against a live MySQL: the start value is there

Loaded the exact table above into a real MariaDB and pointed `ora2pg -m`
at it over a live connection instead of the file:

```sql
ALTER SEQUENCE invoices_id_seq RESTART WITH 1000;
```

present, correct, and in the right place in the output. So this is not
"ora2pg cannot know the start value"; it is scoped to the file-based
path, the same way GAP-082's foreign-key loss is. Read
`MySQL.pm` (ora2pg 25.0) to see why: the value comes from

```perl
my $sql = "SELECT TABLE_NAME, AUTO_INCREMENT FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_TYPE='BASE TABLE' AND TABLE_SCHEMA = '$self->{schema}'
            AND AUTO_INCREMENT IS NOT NULL";
```

a live query against `INFORMATION_SCHEMA.TABLES`, never from parsing the
`AUTO_INCREMENT=<n>` table option out of the `CREATE TABLE` text itself.
On the file-based path there is no database to run that query against,
so the number is lost, not because it is hard to find, it is unquoted
and unambiguous right there in the file, but because this code path
never looks at the file for it at all.

## Observed problem

The schema loads without a single error. The sequence starts counting
from 1 — that is, from values already taken in the migrated data. The
first insert after the data migration fails on a primary-key violation,
and keeps failing until the counter catches up with the real data.

Note: if the data is not migrated, there is no error at all — which is
why the gap is invisible on a schema-only run and shows up exactly when
the migration is considered done.

**Reproducible: YES**, on the file-based path this project scans. Ora2Pg
version: 25.0, PostgreSQL 16. Source dialect: MySQL (`ora2pg -m`).

## Verdict

**Gap confirmed for file-based input, severity high, failure_stage
runtime.** The stage is runtime rather than semantic: there is no silent
divergence here, there is a concrete error at a concrete moment, on the
first insert. Also resolved by exporting from a live connection to the
source database instead of a file, per the mechanism above. Otherwise
fixed with one line per table after the data is loaded:

```sql
SELECT setval(pg_get_serial_sequence('invoices', 'id'),
              (SELECT max(id) FROM invoices));
```

Implemented: `ora2pg_gap_report/detectors/mysql_auto_increment_start.py`
— the detector flags only the table option (`AUTO_INCREMENT=<n>`, with
the equals sign), not the column attribute `AUTO_INCREMENT`, which is
ported correctly.
