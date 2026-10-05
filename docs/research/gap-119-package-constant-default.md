# GAP-119: a package constant as a parameter default is copied as it is

Oracle feature: a routine parameter whose default value is a package-level
constant or variable - `p_os IN VARCHAR2 := g_os_windows`, or qualified,
`p_params tab_param DEFAULT logger.gc_empty_tab_param`.

## How it was found

`--load-check` on ora2pg's output for alexandria-plsql-utils'
`file_util_pkg` (`docs/research/samples/file_util_pkg.pks`/`.pkb`):
two functions failed with `column "g_os_windows" does not exist`.
OraOpenSource Logger has the qualified form in eleven routines.

## Minimal example

```sql
CREATE OR REPLACE PACKAGE file_pkg AS
  g_os_windows CONSTANT VARCHAR2(1) := 'w';
  FUNCTION sep(p_os IN VARCHAR2 := g_os_windows) RETURN VARCHAR2;
END file_pkg;
/
CREATE OR REPLACE PACKAGE BODY file_pkg AS
  FUNCTION sep(p_os IN VARCHAR2 := g_os_windows) RETURN VARCHAR2 IS
  BEGIN
    RETURN CASE WHEN p_os = g_os_windows THEN '\' ELSE '/' END;
  END;
END file_pkg;
/
```

In a live Oracle 23ai the package compiles and `file_pkg.sep` returns `\`.

## ora2pg output (v25.0, `-t PACKAGE`, from `DBMS_METADATA.GET_DDL`)

```sql
CREATE OR REPLACE FUNCTION file_pkg.sep (p_os text DEFAULT g_os_windows) RETURNS varchar AS $body$
BEGIN
    RETURN CASE WHEN p_os = current_setting('file_pkg.g_os_windows')::varchar(1) THEN '\' ELSE '/' END;
  END;
$body$
```

Inside the body the constant is rewritten into `current_setting()`
(GAP-036's emulation); in the parameter default it is not.

## Observed problem

PostgreSQL 16 rejects the function at load time:

```
ERROR:  42703: column "g_os_windows" does not exist
```

The qualified form, `DEFAULT file_pkg.g_os_windows`, fails too:

```
ERROR:  42P01: missing FROM-clause entry for table "file_pkg"
```

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16, Oracle 23ai.

## Verdict

**Gap confirmed, severity high, failure_stage deployment.** Put the
constant's value in the default as a literal, or a call to a function
that returns it.

Implemented: `ora2pg_gap_report/detectors/package_constant_default.py` -
a bare or package-qualified name as the default of a parameter of a
routine in a package spec or body. The name need not be declared in the
same file: a body is often exported without its spec.
