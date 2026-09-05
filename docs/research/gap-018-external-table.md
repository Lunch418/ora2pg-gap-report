# GAP-018: `CREATE TABLE ... ORGANIZATION EXTERNAL` — the clause is dropped entirely

Oracle feature: an external table (`ORGANIZATION EXTERNAL`) — a table whose
data lives physically outside the database, in an external file (usually
through `ORACLE_LOADER`), and is read from there on every access.

## Minimal example

```sql
CREATE TABLE ext_orders (
    order_id NUMBER,
    amount   NUMBER
)
ORGANIZATION EXTERNAL (
    TYPE ORACLE_LOADER
    DEFAULT DIRECTORY ext_dir
    ACCESS PARAMETERS (
        RECORDS DELIMITED BY NEWLINE
        FIELDS TERMINATED BY ','
    )
    LOCATION ('orders.csv')
)
REJECT LIMIT UNLIMITED;
```

## ora2pg output (v25.0, `-t TABLE`, and separately `--estimate_cost -t TABLE`)

```sql
CREATE TABLE ext_orders (
	order_id bigint,
	amount bigint
) ;
```

The whole `ORGANIZATION EXTERNAL` clause (`TYPE`/`DEFAULT
DIRECTORY`/`ACCESS PARAMETERS`/`LOCATION`/`REJECT LIMIT`) disappears
without trace — the table is created as an ordinary, physically stored
one. No error, no warning — including from `--estimate_cost`, which
likewise records nothing about this table.

## Observed problem

This is not a syntax error — the `CREATE TABLE` runs without trouble. But
the result is fundamentally different: this table's only data source (the
external file) is gone completely. The table is created empty and will
never pick up the contents of `orders.csv` — and since `CREATE TABLE`
neither fails nor warns, it is easy to miss during a real migration, until
the application starts getting empty results where the file's rows used to
be.

The nearest equivalent in PostgreSQL is a foreign table through `file_fdw`
(or a specific fdw for the format in question), configured by hand along a
path entirely separate from an ordinary `CREATE TABLE`.

**Reproducible: YES.** Ora2Pg version: 25.0.

## Verdict

**Gap confirmed.** Implemented in
`ora2pg_gap_report/detectors/external_table.py`. The search for
`ORGANIZATION EXTERNAL` is confined to the text of one `CREATE TABLE` (up
to its terminating `;`) — the same approach as in `table_partitioning.py`,
so a finding is not attributed to some unrelated table in the file.
