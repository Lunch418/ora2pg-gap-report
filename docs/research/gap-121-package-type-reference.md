# GAP-121: a package type used in its own routines loses the package name

Oracle feature: a type declared in a package - `SUBTYPE t_code IS
VARCHAR2(10)`, `TYPE pair_rt IS RECORD (...)`, `TYPE num_tt IS TABLE OF
NUMBER INDEX BY PLS_INTEGER` - used by the package's routines without the
package name: a parameter `p IN t_code`, a variable `r pair_rt;`, a
`RETURN t_code`.

## How it was found

Reducing GAP-120: with the `%TYPE` written out by hand, the routines still
did not load. `--load-check` filed the errors as missing dependencies.
OraOpenSource Logger's `tab_param` parameters have the same shape.

## Minimal example

`tests/fixtures/gaps_120_123/calls_source.sql` (`gx_t_pkg`):

```sql
CREATE OR REPLACE PACKAGE gx_t_pkg AS
  SUBTYPE t_code IS VARCHAR2(10);
  TYPE pair_rt IS RECORD (a NUMBER(6), b VARCHAR2(10));
  TYPE num_tt IS TABLE OF NUMBER INDEX BY PLS_INTEGER;
  FUNCTION code_of(p IN t_code) RETURN t_code;
  FUNCTION pair_sum RETURN NUMBER;
  FUNCTION tab_count RETURN NUMBER;
END gx_t_pkg;
/
CREATE OR REPLACE PACKAGE BODY gx_t_pkg AS
  FUNCTION code_of(p IN t_code) RETURN t_code IS
    v t_code := p;
  BEGIN
    RETURN v || '!';
  END;
  FUNCTION pair_sum RETURN NUMBER IS
    r pair_rt;
  BEGIN
    r.a := 2;
    r.b := '3';
    RETURN r.a + TO_NUMBER(r.b);
  END;
  ...
END gx_t_pkg;
/
```

In a live Oracle 23ai: `code_of('ab')` is `ab!`, `pair_sum` is 5,
`tab_count` is 2.

## ora2pg output (v25.0, `-t PACKAGE`)

```sql
CREATE DOMAIN gx_t_pkg.t_code AS varchar(10);
CREATE TYPE gx_t_pkg.pair_rt AS (
a integer, b varchar(10)
);
CREATE OR REPLACE FUNCTION gx_t_pkg.code_of (p t_code) RETURNS T_CODE AS $body$
DECLARE
    v t_code := p;
...
CREATE OR REPLACE FUNCTION gx_t_pkg.pair_sum () RETURNS bigint AS $body$
DECLARE
    r pair_rt;
```

The types are created in the package's schema; the routines name them
bare.

## Observed problem

The package's schema is not on the search_path, so PostgreSQL 16 rejects
every routine that names one of the types, even though the types
themselves loaded:

```
ERROR:  42704: type t_code does not exist
ERROR:  42704: type "pair_rt" does not exist
ERROR:  42704: type "num_tt" does not exist
```

A reference written with the package name in Oracle (`gx_e_pkg.t_code`)
is kept as it is and loads.

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16, Oracle 23ai.

## Verdict

**Gap confirmed, severity high, failure_stage deployment.** Qualify the
type with the package's schema (`gx_t_pkg.t_code`), or give the function
`SET search_path` with that schema. Qualified, the GAP-120 fixture loads
and returns what Oracle returns (`tests/test_gaps_120_123_load.py`). A
`TABLE OF` type has GAP-003 on top.

A REF CURSOR type is GAP-115's. A body exported without its spec declares
no types, so the detector only knows types declared in the same file;
reported once per type.

Implemented: `ora2pg_gap_report/detectors/package_type_reference.py`;
`--load-check` ties `type "x" does not exist` to this gap when the same
file creates `x` in a package schema.
