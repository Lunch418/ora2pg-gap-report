# GAP-061: `SUBTYPE ... RANGE` → `CREATE DOMAIN ... RANGE`

Oracle feature: a PL/SQL subtype with a range constraint on its values.

## Minimal example

```sql
CREATE OR REPLACE PACKAGE types_pkg IS
  SUBTYPE small_int IS PLS_INTEGER RANGE 1 .. 100;
  SUBTYPE short_name IS VARCHAR2(30) NOT NULL;
END types_pkg;
/
```

## ora2pg output (v25.0, `-t PACKAGE`)

```sql
-- Oracle package 'types_pkg' declaration, please edit to match PostgreSQL syntax.
CREATE DOMAIN types_pkg.small_int AS integer RANGE 1 .. 100;
CREATE DOMAIN types_pkg.short_name AS varchar(30) NOT NULL;
-- End of Oracle package 'types_pkg' declaration
```

Translating to `CREATE DOMAIN` is correct in itself, but the `RANGE`
clause is carried over verbatim.

## Observed problem

Confirmed against a real PostgreSQL 16:

```
ERROR:  syntax error at or near "RANGE"
LINE 1: CREATE DOMAIN types_pkg.small_int AS integer RANGE 1 .. 100;
                                                     ^
```

The second subtype from the same example (`SUBTYPE short_name IS
VARCHAR2(30) NOT NULL`) converts into a correct `CREATE DOMAIN ... NOT
NULL` and would have loaded without question — it is specifically the
`RANGE` variant that fails. So the detector flags only that one and
deliberately leaves unconstrained subtypes (and the `NOT NULL` variant)
alone.

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16.

## Verdict

**Gap confirmed.** Implemented in
`ora2pg_gap_report/detectors/subtype_range.py`. Manual rework: the idea
carries over one to one, in different syntax — as a check: `CREATE DOMAIN
small_int AS integer CHECK (VALUE BETWEEN 1 AND 100)`.
