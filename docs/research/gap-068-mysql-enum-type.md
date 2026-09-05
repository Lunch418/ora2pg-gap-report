# GAP-068: `ENUM(...)` — reference to a type that is never created

The first gap from the MySQL/MariaDB research batch: ora2pg supports
MySQL as a source directly, via `-m`/`--mysql`, and works file-based
(`-i <file>`, no live MySQL connection) exactly the way the Oracle mode
does (`-t <TYPE> -i <file>`).

MySQL/MariaDB feature: `ENUM(...)` — an enumerated type declared inline
in the column definition.

## Minimal example

```sql
CREATE TABLE orders (
  id INT PRIMARY KEY AUTO_INCREMENT,
  status ENUM('new','paid','shipped','cancelled') NOT NULL DEFAULT 'new'
);
```

## ora2pg output (v25.0, `-m -t TABLE`)

```sql
CREATE TABLE orders (
	id serial,
	status ORDERS_STATUS_T NOT NULL DEFAULT 'new'
) ;
ALTER TABLE orders ADD PRIMARY KEY (id);
```

For the ENUM, ora2pg synthesizes a named PostgreSQL type
`orders_status_t` and substitutes that name into the column definition.
The approach itself is right (PostgreSQL does support `CREATE TYPE
... AS ENUM (...)`), but the statement that would have to declare that
type — `CREATE TYPE orders_status_t AS ENUM
('new','paid','shipped','cancelled');` — never makes it into the output
at all. The source of `lib/Ora2Pg.pm` contains an `#ORA2PGENUM#`
placeholder meant to be replaced by the generated `CREATE TYPE`; here the
substitution does not happen.

## Observed problem

Confirmed on a real PostgreSQL 16:

```
ERROR:  type "orders_status_t" does not exist
LINE 3:  status ORDERS_STATUS_T NOT NULL DEFAULT 'new'
                ^
```

`CREATE TABLE` fails immediately, at schema load — before any `INSERT`
or procedure call.

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16. Source
dialect: MySQL (`ora2pg -m`).

## Verdict

**Gap confirmed, severity high.** No enumeration values are lost along
the way — they are visible right there in the source `ENUM(...)` — so
the fix is mechanical: insert the missing `CREATE TYPE
<table>_<column>_t AS ENUM (...)` ahead of the `CREATE TABLE` for every
ENUM column. Severity here is high rather than medium (unlike the
spiritually similar `sdo_geometry`/GAP-067) because there the type
mapping is chosen correctly and only one universal `CREATE EXTENSION
postgis` line is missing, identical for any table; here every ENUM
column needs its own `CREATE TYPE` with its own set of values — not one
universal line, but one insertion per column. Implemented:
`ora2pg_gap_report/detectors/mysql_enum_type.py`.
