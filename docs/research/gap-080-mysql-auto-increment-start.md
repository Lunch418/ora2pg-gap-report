# GAP-080: `AUTO_INCREMENT=<n>` — the counter's start value is lost

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

## ora2pg output (v25.0, `-m -t TABLE`)

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
`grep`).

## Observed problem

The schema loads without a single error. The sequence starts counting
from 1 — that is, from values already taken in the migrated data. The
first insert after the data migration fails on a primary-key violation,
and keeps failing until the counter catches up with the real data.

Note: if the data is not migrated, there is no error at all — which is
why the gap is invisible on a schema-only run and shows up exactly when
the migration is considered done.

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16. Source
dialect: MySQL (`ora2pg -m`).

## Verdict

**Gap confirmed, severity high, failure_stage runtime.** The stage is
runtime rather than semantic: there is no silent divergence here, there
is a concrete error at a concrete moment — on the first insert. Fixed
with one line per table after the data is loaded:

```sql
SELECT setval(pg_get_serial_sequence('invoices', 'id'),
              (SELECT max(id) FROM invoices));
```

Implemented: `ora2pg_gap_report/detectors/mysql_auto_increment_start.py`
— the detector flags only the table option (`AUTO_INCREMENT=<n>`, with
the equals sign), not the column attribute `AUTO_INCREMENT`, which is
ported correctly.
