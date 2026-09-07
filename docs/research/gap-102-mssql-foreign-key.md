# GAP-102: `FOREIGN KEY` is dropped on the file-based path (MSSQL)

MSSQL feature: a foreign key declared in the `CREATE TABLE` column list.

## Minimal example

```sql
CREATE TABLE parentx (id int NOT NULL PRIMARY KEY);
CREATE TABLE childx (
    id int NOT NULL PRIMARY KEY,
    pid int NOT NULL,
    CONSTRAINT FK_childx_parentx FOREIGN KEY (pid) REFERENCES parentx (id) ON DELETE CASCADE
);
```

## ora2pg output, file-based (v25.0, `-M -i schema.sql -t TABLE`)

```sql
CREATE TABLE parentx (
	id integer NOT NULL
) ;
ALTER TABLE parentx ADD PRIMARY KEY (id);


CREATE TABLE childx (
	id integer NOT NULL,
	pid integer NOT NULL
) ;
ALTER TABLE childx ADD PRIMARY KEY (id);
```

There is not a single `FOREIGN KEY` line in the output, neither inside
the `CREATE TABLE` nor as a separate `ALTER TABLE` after it.

## Same mechanism as GAP-082, verified in the source this time

An earlier version of this document said this was because `-t` has no
export type for foreign keys. That reasoning does not hold: `-t TABLE`
does export foreign keys, just not on the file-based path, and GAP-082
has a live MySQL run proving it for that dialect. This document was
wrong the same way.

For MSSQL specifically, read `MSSQL.pm::_foreign_key()` (ora2pg 25.0,
`lib/Ora2Pg/MSSQL.pm`, line 541) rather than repeat the same guess. It is
the same shape as the MySQL function GAP-082 quotes, one unconditional
live query:

```perl
sub _foreign_key
{
        my ($self, $table, $owner) = @_;
        ...
	my $sql = qq{SELECT fk.name AS ConsName, ...
FROM sys.foreign_keys fk
INNER JOIN sys.foreign_key_columns fkc ON fkc.constraint_object_id = fk.object_id
INNER JOIN sys.tables t_parent ON t_parent.object_id = fk.parent_object_id
...};
        my $sth = $self->{dbh}->prepare($sql) or $self->logit("FATAL: " . $self->{dbh}->errstr . "\n", 0, 1);
        $sth->execute or $self->logit("FATAL: " . $sth->errstr . "\n", 0, 1);
        ...
}
```

`$self->{dbh}` is the live DBI handle to the source SQL Server. Nothing
else in `MSSQL.pm` parses `FOREIGN KEY (...) REFERENCES ...` out of DDL
text. On the file-based path there is no `$self->{dbh}` to query, so
this function has nothing to return, independent of what the `CONSTRAINT
... FOREIGN KEY` clause in the file says.

This document does not have a live SQL Server run the way GAP-082 has a
live MySQL one (no SQL Server instance was available to test against
directly); the claim above rests on the source, not on a second live
export. The two functions are close enough in shape, both a single
`$self->{dbh}->prepare()` against the source engine's own catalog views
with no DDL-text branch at all, that this is a reasonable read of the
code, but it is one degree less directly verified than GAP-082's.

## Observed problem

On the file-based path (an already-exported DDL/script file, no live
database access, exactly what `ora2pg-gap-report` scans), there will be
no error at load or afterwards: the schema comes up, the application
runs, and referential integrity simply ceases to exist, along with the
cascading deletes.

**Reproducible: YES**, on the file-based path this project scans. Ora2Pg
version: 25.0, PostgreSQL 16. Source dialect: MSSQL (`ora2pg -M`).

## Verdict

**Gap confirmed for file-based input, severity high, failure_stage
semantic.** Restored by hand: `ALTER TABLE <table> ADD CONSTRAINT <name>
FOREIGN KEY (<columns>) REFERENCES <parent> (<columns>) ON DELETE ...`
after all tables are loaded, or by exporting from a live connection to
the source SQL Server instead of a file, if that access is available.
Implemented: `ora2pg_gap_report/detectors/mssql_foreign_key.py`.
