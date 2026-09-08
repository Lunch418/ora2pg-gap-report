# GAP-082: `FOREIGN KEY` is dropped when `PG_VERSION` is left at its default

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

## ora2pg output with an unconfigured `PG_VERSION` (v25.0, `-m -i schema.sql -t TABLE`)

```sql
CREATE TABLE orders2 (
	id integer NOT NULL,
	customer_id integer NOT NULL
) ;
ALTER TABLE orders2 ADD PRIMARY KEY (id);
```

```
WARNING: target PostgreSQL version must be set in PG_VERSION configuration directive. Using default: 11
```

`FOREIGN KEY` lines in the whole generated file: zero (verified with
`grep -c`).

## Two earlier explanations for this, both wrong

The first version of this document said `-t` has no export type for
foreign keys. A reader disproved that with a live MariaDB run showing
`-t TABLE` exporting the FK correctly over a live connection, which led
to a second version: that file-based input has no live catalog to query
and foreign keys are metadata ora2pg only ever asks the live database
for, so they are lost specifically on the file-based path.

That explanation looked solid, source and all, but a second reader
could not reproduce it: neither on file input with several schema
variants, nor live, in five separate attempts. Rerunning the exact
`ora2pg -m -i schema.sql -t TABLE` command above against this project's
own default sandbox config reproduced the missing FK; running the same
command with `PG_VERSION 16` added to the config did not. The
discriminator was never file versus live. It is `PG_VERSION`.

## The real mechanism, from source and a live database both

Confirmed with `perl -d`-style tracing through `lib/Ora2Pg.pm`, not
just by reading it. `_create_unique_keys()` (called for every table
that has a `PRIMARY KEY` or `UNIQUE` constraint, which is nearly every
table) contains this, meant only to detect partition-by-reference
tables:

```perl
my $reftable = $table;
$reftable = $self->{partitions_list}{"\L$table\E"}{refrtable}
    if (exists $self->{partitions_list}{"\L$table\E"}{refrtable});
```

`exists` on a multi-level hash dereference is a well-known Perl trap:
checking for `{refrtable}` this way silently creates
`$self->{partitions_list}{$table} = {}` even when `$table` is not
partitioned at all, just because the intermediate hash level had to be
materialized to check the final key. A few lines later, the same
function does:

```perl
next if (!grep(/^$k$/i, @{$self->{partitions_list}{"\L$reftable\E"}{columns}}));
```

which dereferences `{columns}` as an array, autovivifying it too. After
`_create_unique_keys()` has run once for a table, `partitions_list`
holds `{ $table => { columns => [] } }` for it, permanently, whether or
not that table has ever been partitioned. A later cleanup pass
(`delete $self->{partitions_list}{$t} if ($nb == 0)`, counting hash
*keys*) does not catch this, because `{columns => []}` already has one
key.

`_create_foreign_keys()` then checks, for every foreign key, whether its
target table looks partitioned before emitting the constraint:

```perl
next if ($self->{pg_supports_partition}
    && exists $self->{partitions_list}{lc($desttable)}
    && $self->{pg_version} <= 12);
```

`exists $self->{partitions_list}{lc($desttable)}` is now true for
`customers`, purely as a side effect of the earlier accident, so the
`next` fires and the foreign key is silently skipped, provided
`$self->{pg_version} <= 12`. `PG_VERSION` defaults to 11 when it is not
set in the config, which is exactly the state of a config nobody has
edited yet. Set `PG_VERSION` to 13 or higher and the same `next`
condition is false, the accidental `partitions_list` entry is
harmless, and the constraint comes out.

Verified across four combinations, file input and a live MariaDB
connection crossed with `PG_VERSION` unset/11/12 versus 13:

| Input | `PG_VERSION` | Foreign key emitted |
|---|---|---|
| file (`-i schema.sql`) | unset (11) | no |
| file (`-i schema.sql`) | 12 | no |
| file (`-i schema.sql`) | 13 | yes |
| live MariaDB connection | unset (11) | no |

The live-connection row is the one that overturns the previous version
of this document: given the same default config, a live source loses
the foreign key exactly like file input does. This has nothing to do
with how ora2pg is fed its schema.

`PRIMARY KEY` is unaffected because `_get_primary_keys()` builds it
directly from column metadata gathered earlier, with no dependency on
`partitions_list`.

## Observed problem

With a config that has never had `PG_VERSION` set explicitly (or has it
set to 12 or below), any foreign key export through this code path
silently disappears: no error at load or afterwards, the schema comes
up, the application runs, and referential integrity simply ceases to
exist, along with the cascading deletes, if there were any. Whether the
source is a file or a live database makes no difference; the trigger is
the config, not the input mode.

**Reproducible: YES**, with `PG_VERSION` unset or set to 12 or lower.
Ora2Pg version: 25.0, PostgreSQL 16. Source dialect: MySQL (`ora2pg
-m`).

## Verdict

**Gap confirmed, severity high, failure_stage semantic**, conditional on
`PG_VERSION <= 12` (including the unset default). By class this is
exactly what the README calls an "architecturally significant loss": a
guarantee declared in the object definition disappears without a trace,
akin to GAP-066 (`WITH READ ONLY`) and GAP-026 (`READ ONLY` on a table).
Fixed by setting `PG_VERSION` to the real target PostgreSQL version
(13 or higher) before conversion; if the target genuinely is
PostgreSQL ≤12, the constraint has to be restored by hand: `ALTER TABLE
<table> ADD CONSTRAINT <name> FOREIGN KEY (<columns>) REFERENCES
<parent> (<columns>) ON DELETE ...` after all tables are loaded.
Implemented: `ora2pg_gap_report/detectors/mysql_foreign_key.py`.
