# GAP-112: Oracle 23ai `CREATE TABLE IF NOT EXISTS` becomes a table called `if`

Oracle feature (23ai and later): `CREATE TABLE IF NOT EXISTS`.
`DBMS_METADATA.GET_DDL` never writes it; hand-maintained deployment
scripts written for 23ai do.

## Minimal example

```sql
CREATE TABLE IF NOT EXISTS customers (
  id NUMBER PRIMARY KEY,
  name VARCHAR2(50)
);
```

## ora2pg output (v25.0, `-t TABLE`)

```sql
\set ON_ERROR_STOP ON
CREATE TABLE if (
	not EXISTS
) ;
ALTER TABLE if ADD PRIMARY KEY (not);
```

The table parser takes the word after `TABLE` as the table's name — the
same failure as MySQL's GAP-110, in the same shared code.

## Observed problem

```
ERROR:  syntax error at or near "not"
```

at load time, and `\set ON_ERROR_STOP ON` stops the load of the whole
schema there. A/B: the same table without `IF NOT EXISTS` converts and
loads.

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16.

## Verdict

**Gap confirmed, severity high, failure_stage deployment.** Fixed before
converting by dropping `IF NOT EXISTS`.

Implemented: `ora2pg_gap_report/detectors/table_if_not_exists.py`.
