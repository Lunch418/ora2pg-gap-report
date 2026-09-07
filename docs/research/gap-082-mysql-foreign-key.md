# GAP-082: `FOREIGN KEY` is dropped on the file-based path

MySQL/MariaDB feature: a foreign key declared in the `CREATE TABLE`
column list.

## Minimal example

As `mysqldump` writes it:

```sql
CREATE TABLE `customers` (
  `id` int(11) NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB;
CREATE TABLE `orders2` (
  `id` int(11) NOT NULL,
  `customer_id` int(11) NOT NULL,
  PRIMARY KEY (`id`),
  CONSTRAINT `fk_orders_customer` FOREIGN KEY (`customer_id`) REFERENCES `customers` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB;
```

## ora2pg output, file-based (v25.0, `-m -i schema.sql -t TABLE`)

```sql
CREATE TABLE orders2 (
	id integer NOT NULL,
	customer_id integer NOT NULL
) ;
ALTER TABLE orders2 ADD PRIMARY KEY (id);
```

`FOREIGN KEY` lines in the whole generated file: zero (verified with
`grep -c`). Neither inside the `CREATE TABLE` nor as a separate `ALTER
TABLE` after it. Same for the form without a constraint name (`FOREIGN
KEY (pid) REFERENCES parent7 (id)`) — also zero.

## The same schema against a live MySQL: the FK is there

This is the correction to an earlier version of this document, which
attributed the loss to `-t` having no export type for foreign keys.
That reasoning was wrong, and a reader who checked it against a live
`ora2pg -m -t TABLE` run (rather than the file-based `-i` input this
project scans) found the contradiction: loaded the exact schema above
into a real MariaDB, pointed `ora2pg -m` at it over a live `ORACLE_DSN`
connection instead of a file, and the same `-t TABLE` export produced

```sql
CREATE TABLE orders2 (
	id integer NOT NULL,
	customer_id integer NOT NULL
) ;
CREATE INDEX fk_orders_customer ON orders2 (customer_id);
ALTER TABLE orders2 ADD PRIMARY KEY (id);
ALTER TABLE orders2 ADD CONSTRAINT fk_orders_customer FOREIGN KEY (customer_id) REFERENCES customers(id) MATCH SIMPLE ON DELETE CASCADE ON UPDATE RESTRICT;
```

The foreign key is there, as a separate `ALTER TABLE ADD CONSTRAINT`.
Reproduced independently while fixing this document: same schema, same
`-t TABLE`, live MariaDB 10.11 this time, identical `ALTER TABLE ADD
CONSTRAINT` line. So `-t TABLE` does export foreign keys, and the
earlier claim that no `-t` value covers them was answering the wrong
question.

## Why the file-based path still loses it

Read `MySQL.pm::_foreign_key()` (ora2pg 25.0, `lib/Ora2Pg/MySQL.pm`,
line 607) to find the real mechanism rather than guess again. The whole
function is one unconditional live query:

```perl
sub _foreign_key
{
        my ($self, $table, $owner) = @_;
        ...
	my $sql = "SELECT DISTINCT A.COLUMN_NAME, ... FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE AS A
                    INNER JOIN INFORMATION_SCHEMA.REFERENTIAL_CONSTRAINTS AS B ...";
        my $sth = $self->{dbh}->prepare($sql) or $self->logit("FATAL: " . $self->{dbh}->errstr . "\n", 0, 1);
        $sth->execute or $self->logit("FATAL: " . $sth->errstr . "\n", 0, 1);
        ...
}
```

`$self->{dbh}` is the live DBI database handle. There is no branch in
this function, and no other function anywhere in `MySQL.pm`, that parses
`FOREIGN KEY (...) REFERENCES ...` out of DDL text. Foreign keys are
metadata ora2pg only ever asks the live `INFORMATION_SCHEMA` for. On the
file-based path (`-i <file>`, no `ORACLE_DSN`) there is no `$self->{dbh}`
to query, so this function is simply never reached with anything to
return, no matter how explicitly the `CONSTRAINT ... FOREIGN KEY` clause
is written in the file.

`PRIMARY KEY` survives the same file-based run (see the `ALTER TABLE
orders2 ADD PRIMARY KEY (id);` line above) because it is read a
different way, from `DESCRIBE`-shaped column metadata `mysqldump`-style
tools already put next to each column, not from a `KEY_COLUMN_USAGE`
join. Foreign keys are the one relationship that, in this codebase,
exists only in the database's own catalog view of itself.

## Observed problem

For a user working the way this project's own README says it scans
sources, an already-exported DDL/dump file with no live database access
(`ora2pg-gap-report`'s whole reason to exist: air-gapped and offline
migrations), there will be no error at load or afterwards. The schema
comes up, the application runs, and referential integrity simply ceases
to exist, along with the cascading deletes, if there were any. The only
way to notice is by the consequences: orphaned rows the database used to
prevent.

A user who instead points `ora2pg -m` at a live MySQL/MariaDB source
does not hit this at all: the foreign keys are exported correctly, as
shown above. This is scoped to the file-based path, not to `ora2pg -m`
in general, and MySQL/MariaDB's `-t TABLE` is not missing foreign-key
support: it simply cannot get at it without a database to ask.

**Reproducible: YES**, on the file-based path this project scans. Ora2Pg
version: 25.0, PostgreSQL 16. Source dialect: MySQL (`ora2pg -m`).

## Verdict

**Gap confirmed for file-based input, severity high, failure_stage
semantic.** By class this is exactly what the README calls an
"architecturally significant loss": a guarantee declared in the object
definition disappears without a trace, akin to GAP-066 (`WITH READ
ONLY`) and GAP-026 (`READ ONLY` on a table). Restored by hand: `ALTER
TABLE <table> ADD CONSTRAINT <name> FOREIGN KEY (<columns>) REFERENCES
<parent> (<columns>) ON DELETE ...` after all tables are loaded, or by
running `ora2pg` against a live connection to the source database
instead of an exported file, which the mechanism above shows resolves
this specific gap on its own. Implemented:
`ora2pg_gap_report/detectors/mysql_foreign_key.py`.
