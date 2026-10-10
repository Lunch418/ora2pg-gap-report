# GAP-137: `INSTR` with a position or an occurrence

Oracle feature: `INSTR(s, sub, position[, occurrence])` - a negative position searches from the end.

## How it was found

While checking GAP-130..133: the same functions were run in Oracle 23ai and, after ora2pg 25.0, in PostgreSQL 16.

## Minimal example

`tests/fixtures/loud_types/oracle_functions.sql`, VALID in a live Oracle 23ai:

```sql
CREATE OR REPLACE FUNCTION gx_l5(p VARCHAR2) RETURN NUMBER IS
BEGIN
  RETURN INSTR(p, '.', -1) * 10 + INSTR(p, '.', 1, 2);
END;
/
```

## ora2pg output (v25.0, `-t FUNCTION`)

```sql
  RETURN INSTR(p, '.', -1) * 10 + INSTR(p, '.', 1, 2);
```

Two-argument `INSTR(s, sub)` becomes `position(sub in s)`; the longer forms are copied.

## Observed problem

The function loads, and its first call fails (Oracle 23ai returns 44 for `gx_l5('a.b.c')`):

```
ERROR:  function instr(text, unknown, integer) does not exist
```

Found in OraOpenSource Logger (`instr(l_callstack, chr(10), 1, 5)`) and `file_util_pkg` (`instr(p_file_name, l_dir_sep, -1)`).

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16, Oracle 23ai.

## Verdict

**Gap confirmed, severity high, failure_stage runtime.** The orafce extension provides `instr` with these forms; without it, write a function of your own. The detector flags `INSTR` with three or four arguments.

Implemented: `ora2pg_gap_report/detectors/instr_occurrence.py`.
