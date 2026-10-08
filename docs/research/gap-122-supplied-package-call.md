# GAP-122: a supplied package's procedure called as a statement loses `CALL`

Oracle feature: a procedure of an Oracle-supplied package called as a
statement - `DBMS_APPLICATION_INFO.SET_MODULE('m', 'a');`,
`DBMS_STATS.GATHER_TABLE_STATS(USER, 'GX_EMP');`, `UTL_FILE.FCLOSE_ALL;`,
`HTP.P('x');`, `OWA_UTIL.MIME_HEADER('text/plain');`,
`DBMS_OUTPUT.DISABLE;`.

## How it was found

`--migrate --load-check docker` on the sample packages: OraOpenSource
Logger's `display_output` failed with `syntax error at or near "htp"`,
and no gap explained it. The samples have 30 more such calls
(`DBMS_LOB`, `UTL_FILE`, `DBMS_SESSION` in `file_util_pkg`,
`sql_util_pkg`, Logger); their routines fail earlier on other errors,
since PostgreSQL reports the first one only.

## Minimal example

`tests/fixtures/gaps_120_123/calls_source.sql` (`gx_ext_pkg`):

```sql
CREATE OR REPLACE PACKAGE BODY gx_ext_pkg AS
  PROCEDURE run_it IS
  BEGIN
    DBMS_OUTPUT.PUT_LINE('a');
    DBMS_SESSION.SLEEP(0);
    DBMS_APPLICATION_INFO.SET_MODULE('m', 'a');
    DBMS_APPLICATION_INFO.SET_ACTION('x');
    DBMS_STATS.GATHER_TABLE_STATS(USER, 'GX_EMP');
    DBMS_SCHEDULER.RUN_JOB('J1');
    UTL_FILE.FCLOSE_ALL;
    gx_out_pkg.note('x');
    HTP.P('x');
    OWA_UTIL.MIME_HEADER('text/plain');
    DBMS_UTILITY.EXEC_DDL_STATEMENT('x');
  END;
END gx_ext_pkg;
/
```

VALID in a live Oracle 23ai.

## ora2pg output (v25.0, `-t PACKAGE`)

```sql
BEGIN
    RAISE NOTICE 'a';
    pg_sleep(0);
    DBMS_APPLICATION_INFO.SET_MODULE('m', 'a');
    DBMS_APPLICATION_INFO.SET_ACTION('x');
    DBMS_STATS.GATHER_TABLE_STATS(USER, 'GX_EMP');
    DBMS_SCHEDULER.RUN_JOB('J1');
    UTL_FILE.FCLOSE_ALL;
    gx_out_pkg.note('x');
    HTP.P('x');
    OWA_UTIL.MIME_HEADER('text/plain');
    DBMS_UTILITY.EXEC_DDL_STATEMENT('x');
  END;
```

ora2pg writes `CALL pkg.proc(...)` only for procedures of packages it has
in the same run: with `gx_out_pkg` in the input the call is `CALL
gx_out_pkg.note('x')`, without it the call is bare like the rest.
`DBMS_OUTPUT.PUT_LINE` becomes `RAISE NOTICE` and `DBMS_OUTPUT.ENABLE` is
commented out; `DBMS_OUTPUT.DISABLE` is copied. Triggers get the same.

## Observed problem

PL/pgSQL has no bare procedure call, so PostgreSQL 16 rejects the whole
routine at load time - whether or not a replacement for the package
exists:

```
ERROR:  42601: syntax error at or near "DBMS_APPLICATION_INFO"
```

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16, Oracle 23ai.

## Verdict

**Gap confirmed, severity high, failure_stage deployment.** Replace each
call with its PostgreSQL counterpart - `CALL`/`PERFORM` of your own
implementation, `set_config('application_name', ...)`, `ANALYZE`, an
extension such as orafce - or remove it. With that done, the fixture loads
and `CALL gx_ext_pkg.run_it()` runs (`tests/test_gaps_120_123_load.py`).

Not flagged: what ora2pg does convert at statement level (DBMS_OUTPUT's
printing and ENABLE, DBMS_SQL's open/parse/execute sequence,
DBMS_STANDARD), SLEEP (GAP-123), and function calls inside expressions
(`n := DBMS_RANDOM.VALUE`). `dbms_utl_calls` keeps reporting those other
uses; it no longer reports the statement calls this gap covers. Calls to a
user package outside the converted input have the same problem, but a
single file cannot tell which packages the input contains; `--migrate`
converts all of them in one run, so for it the problem is only the
supplied packages.

Implemented: `ora2pg_gap_report/detectors/supplied_package_call.py`.
