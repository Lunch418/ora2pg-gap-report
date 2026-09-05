# GAP-035: conditional-compilation directives (`$IF`/`$THEN`/`$ELSE`/`$END`) copied verbatim

Oracle feature: PL/SQL conditional compilation (`$IF <condition> $THEN ...
$ELSIF ... $ELSE ... $END`) — preprocessor directives handled by Oracle's
compiler before the body is compiled at all: code inside a branch that is
not selected is not merely skipped at run time, it is never compiled.
Common uses are version-dependent code (`$IF DBMS_DB_VERSION.VERSION >= 12
$THEN ...`) and debug sections controlled by an inquiry flag
(`$$flag_name`).

## Minimal example

```sql
CREATE OR REPLACE PROCEDURE proc_debug AS
BEGIN
$IF $$debug_mode $THEN
  DBMS_OUTPUT.PUT_LINE('debug on');
$ELSE
  DBMS_OUTPUT.PUT_LINE('debug off');
$END
  NULL;
END;
```

## ora2pg output (v25.0, `-t PROCEDURE`)

```sql
CREATE OR REPLACE PROCEDURE proc_debug () AS $body$
BEGIN
$IF $$debug_mode $THEN
  RAISE NOTICE 'debug on';
$ELSE
  RAISE NOTICE 'debug off';
$END;
END;
$body$
LANGUAGE PLPGSQL
;
```

`DBMS_OUTPUT.PUT_LINE` is converted as usual, but the
`$IF`/`$THEN`/`$ELSE`/`$END` directives themselves are copied into the
output literally, as ordinary text. PL/pgSQL has no conditional-compilation
preprocessor at all — this is not valid syntax in any form.

## Observed problem

The `CREATE PROCEDURE` in the output runs without a single error — ora2pg
disables `check_function_bodies` at the very start of the generated file.
The failure happens only on the first real call:

```sql
CALL proc_debug();
-- ERROR:  syntax error at or near "$"
-- LINE 3: $IF $$debug_mode $THEN
--         ^
-- CONTEXT:  compilation of PL/pgSQL function "proc_debug" near line 1
```

The same pattern as nested subprograms (GAP-034): the migration script
applies cleanly all the way through, and the failure surfaces only when a
call actually reaches the code — not during migration testing but in
production, on the first use of that particular branch. That is especially
likely for `$IF` branches governed by rarely toggled flags such as a debug
mode.

**Reproducible: YES.** Ora2Pg version: 25.0.

## Verdict

**Gap confirmed.** Implemented in
`ora2pg_gap_report/detectors/conditional_compilation.py`.
