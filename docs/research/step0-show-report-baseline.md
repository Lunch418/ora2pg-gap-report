# Step 0: baseline ora2pg SHOW_REPORT — what is already there "out of the box"

Date: 2026-08-14
Author: research agent (as part of Task 0 of the `ora2pg-gap-report` project)

The purpose of this document is to establish empirically — and, where
empiricism is impossible, from the source code — what the `SHOW_REPORT`
mode of the open-source `ora2pg` already reports for the five declared
classes of "poorly ported" constructs, before designing detectors on top
of it. Conclusion: the hypothesis is **partially** confirmed, but not in
the form in which it was originally stated — details below.

## Methodology

### What was done

1. Cloned `https://github.com/darold/ora2pg` (commit `cc2c434f`,
   `$VERSION = '25.0'`) into `/workspace/ora2pg-src` (outside this
   repository, as required — the clone itself does not enter git).
2. Read `lib/Ora2Pg.pm` (23K lines) — the `SHOW_REPORT`/`_show_report`
   code (the `_show_infos('SHOW_REPORT')` method, lines ~17822–18487),
   plus `lib/Ora2Pg/PLSQL.pm` — the `%OBJECT_SCORE` / `%UNCOVERED_SCORE`
   tables and the `estimate_cost()` function that actually computes an
   object's "cost".
3. Checked whether an offline run (without Oracle) is possible — yes, it
   is, through `-i file.sql -t <TYPE>` for object types (PACKAGE,
   TRIGGER, FUNCTION, …), but **not** for `SHOW_REPORT` as a whole (see
   the "Offline mode" section below). The only missing dependency in the
   sandbox was the Perl module `DBI` (not `DBD::Oracle`!). It was
   installed with `apt-get install libdbi-perl` (the sandbox has root and
   access to the ordinary Ubuntu repositories through the proxy; several
   third-party PPAs are blocked by the proxy, but that did not matter —
   the package we needed is in the main Ubuntu archive). After that,
   `ora2pg -i file.sql -t PACKAGE --estimate_cost` and `-t TRIGGER` ran
   without a single live Oracle session.
4. Found and downloaded (`curl` against `raw.githubusercontent.com`, no
   `mcp__github__*`) real open-source PL/SQL examples:
   - **`OraOpenSource/Logger`** — `source/packages/logger.pks`/`logger.pkb`
     (≈3300 lines), a popular open-source logger for PL/SQL. It really
     does contain: `CREATE PACKAGE`/`PACKAGE BODY`, 9 occurrences of
     `PRAGMA` (including `PRAGMA AUTONOMOUS_TRANSACTION` in several
     logging procedures), `DBMS_OUTPUT`, `DBMS_UTILITY`, `DBMS_SESSION`,
     `DBMS_DB_VERSION`, `DBMS_FLASHBACK`, `UTL_LMS`.
   - **`mortenbra/alexandria-plsql-utils`** — `ora/file_util_pkg.pks/.pkb`
     and `ora/sql_util_pkg.pks/.pkb`, a well-known utility library for
     Oracle PL/SQL. `file_util_pkg` — 21 `UTL_FILE` calls, 23 `DBMS_LOB`
     calls, `UTL_RAW`; `sql_util_pkg` — 18 `DBMS_LOB` calls, `UTL_RAW`.
   - **`Apress/modern-oracle-database-programming`** — `Listing 1-7.
     Compound Trigger tr_constructors_cti.sql`, a real, compact,
     syntactically correct `COMPOUND TRIGGER` (all four sections: BEFORE
     STATEMENT / BEFORE EACH ROW / AFTER EACH ROW / AFTER STATEMENT) —
     exactly what was needed for the check.
   - For **CONNECT BY**, a real open-source *package* (rather than a
     standalone query or view) with a hierarchical query inside a
     procedure or function could not be found within a reasonable search
     time (`mortenbra/alexandria-plsql-utils`, `OraOpenSource/Logger`,
     `oracle-samples/db-sample-schemas` do not contain one). That is an
     observation in itself: in open-source code `CONNECT BY` almost
     always lives in ad-hoc SQL or a VIEW, not in a package body. To
     check the conversion path for `CONNECT BY` **inside a package**
     anyway (which matters, since packages and CONNECT BY are claimed
     separately), a minimal test package was assembled in
     `docs/research/samples/connect_by_hierarchy_pkg.sql` and honestly
     labelled as ours: it wraps the canonical Oracle EMP/DEPT pattern
     `START WITH ... CONNECT BY PRIOR ... SYS_CONNECT_BY_PATH` (the same
     query as in Oracle's official documentation and a thousand
     tutorials) in a function returning a `REF CURSOR`. It is marked
     explicitly as a synthetic fixture, not as a real repository.
   All downloaded files and the fixture live in `docs/research/samples/`
   in this repository, for reproducibility.
5. Ran `ora2pg -t PACKAGE -i <file> --estimate_cost` and `-t TRIGGER -i
   <file> --estimate_cost` on every example; the real output was saved
   into `/workspace/ora2pg-src/test-out/` (outside the repository; the
   key fragments are quoted verbatim below).
6. Read the code that **actually** runs `SHOW_REPORT`
   (`_show_infos('SHOW_REPORT')`) to find out whether it requires a live
   connection — it does, unconditionally (see below), so `SHOW_REPORT`
   itself was never run in the sandbox; instead, the mechanically
   equivalent `estimate_cost` path was used (the same
   `Ora2Pg::PLSQL::estimate_cost()` function and the same
   `%UNCOVERED_SCORE` table that `SHOW_REPORT` uses to compute its
   "detailed" per-object output), which gives empirically confirmed
   results — not merely code-derived ones — for 4 of the 5 classes of
   construct. For the 5th (real behaviour when connected to a live
   Oracle) the conclusions are marked "from the source code, not
   confirmed by a live run".

### Offline mode: what is and is not possible

This matters for the target audience (closed networks with no direct
access to a production Oracle):

- **Possible offline** (`-i file.sql`, no `ORACLE_DSN`, no
  `DBD::Oracle`, just `perl` plus the `DBI` module): export and cost
  estimation of individual object types — `PACKAGE`, `TRIGGER`,
  `FUNCTION`, `PROCEDURE`, `VIEW`, `TYPE`, `QUERY` and others, provided
  the input is a file with that object's DDL/PL-SQL text. That is exactly
  how every empirical result in this report was obtained.
- **Not possible offline**: `SHOW_REPORT` itself, as a single aggregated
  report. The reason is not an artificial restriction but an
  architectural one: `_show_infos` for the `SHOW_REPORT` type calls
  `_get_objects()`, `_get_version()`, `_get_database_size()`, `_tables()`,
  `_get_views()`, `_get_dblink()`, `_get_job()`, `_synonyms()`,
  `_encrypted_columns()` and so on — that is, it builds SQL directly and
  reads `$self->{dbh}` (see, for example,
  `Ora2Pg/Oracle.pm::_get_objects()`: `SELECT OBJECT_NAME,OBJECT_TYPE,STATUS
  FROM ALL_OBJECTS ...` through `$self->{dbh}->prepare(...)`). The general
  check in `Ora2Pg.pm` (~line 1834–1840) explicitly requires either
  `input_file` or `ORACLE_DSN` for *any* export type, but for
  `SHOW_REPORT` an `input_file` does not help — the report code still
  reaches into `$self->{dbh}` directly and fails with a DBI-level error
  if there is no real connection. Running `-t SHOW_REPORT` without
  `ORACLE_DSN` and without an input file gives:

  ```
  FATAL: you must set ORACLE_DSN in ora2pg.conf or use a DDL input file.
  ```

  The wording of the error is misleading — it suggests that a "DDL input
  file" covers `SHOW_REPORT` too, whereas in fact that is true only for
  object types, not for the report as a whole. We **could not** work
  around this and did not spend long fighting it (as instructed) — it is
  recorded as finding #1: **`SHOW_REPORT` fundamentally requires a live
  DBI connection to Oracle/MySQL/MSSQL and has no offline mode**, even
  though individual object types (including PACKAGE, the source of most
  of the constructs we care about) do support file input. This means that
  our tool, if it is to work in an air-gapped environment on an
  already-exported DDL dump (as the project's README states), **cannot**
  simply "run SHOW_REPORT and add to its output" in the offline scenario
  — it will have to either (a) require live access to Oracle for the
  baseline-comparison stage only, or (b) reproduce in its own code the
  part of SHOW_REPORT that is actually needed (`estimate_cost()` +
  `%UNCOVERED_SCORE`) on file input — which is exactly the path we used
  for the tests below, and it really does work offline.

## Results for the 5 classes of construct

### 1. CREATE PACKAGE / CREATE PACKAGE BODY

**Confirmed by a run.** Ora2pg **can** parse and convert packages from a
file offline — no crash, no refusal. On `logger.pkb` (≈3300 lines, dozens
of functions and procedures) and on `file_util_pkg.pkb`:

```
[...] 1/1 packages (100.0%) generating logger
```

— the package was successfully split into individual functions and
procedures, each converted into `CREATE OR REPLACE FUNCTION ... LANGUAGE
plpgsql`, the package's global variables moved into
`global_variables.conf` (GUC emulation through
`current_setting`/`set_config`), and a `-- Detailed cost per function:
...` block generated with an estimate per function.

`SHOW_REPORT` (per the code) gives an even coarser summary for a `PACKAGE
BODY` than a direct `-t PACKAGE --estimate_cost`: only the total
`cost_value` across all the package's functions plus a textual `detail` of
the form `function_name: cost\n`, with no per-keyword breakdown at the
level of the `SHOW_REPORT` output itself in the console/CSV/JSON (the
keyword breakdown is held in `%report_info{full_package_details}` but
reaches the final report only in `--dump_as_html`/the verbose text mode,
not in the basic CSV/JSON — see `_show_report`).

**Conclusion:** the bare fact that "a PACKAGE is a package" is recognised
by ora2pg and ported correctly in the overwhelming majority of cases (the
parser copes with real, not toy, code). The claim "PACKAGE does not port
correctly" is **not confirmed** in that general form — the basic structure
of a package (specification, body, functions/procedures, global
variables) does convert. The problem is not the fact of a CREATE PACKAGE
but the **contents** of packages — in particular, what happens to `PRAGMA
AUTONOMOUS_TRANSACTION` and to `DBMS_*/UTL_*` calls **inside** a package
(see below — and that is exactly where a non-obvious but real gap turned
up).

### 2. PRAGMA AUTONOMOUS_TRANSACTION

This is the most interesting and most counter-intuitive finding of the
report.

**ora2pg HAS real, non-trivial conversion logic for this pragma**
(`lib/Ora2Pg.pm`, ~line 15874, and `lib/Ora2Pg/PLSQL.pm`, ~lines
848–851): by default (the `AUTONOMOUS_TRANSACTION` config option is on,
`= 1`) ora2pg generates a **dblink wrapper**: the original
function/procedure is renamed to `<name>_atx`, the `COMMIT` inside it is
removed (`COMMIT` is forbidden in a PL/pgSQL function), and the calling
code gets a proxy function that calls `<name>_atx` over `dblink()` on a
separate connection — that is, it genuinely emulates the autonomy of the
transaction. This was confirmed by a live run on `logger.pkb`: for each
procedure carrying `pragma autonomous_transaction;` (for example
`logger.save_global_context`, `logger.log_apex_items`, `logger.purge`,
`logger.purge_all`) the output really does contain:

```sql
-- dblink wrapper to call function logger_save_global_context as an autonomous transaction
CREATE EXTENSION IF NOT EXISTS dblink;
...
	-- Change this to reflect the dblink connection string
	v_conn_str := ...
	v_query := 'CALL logger_save_global_context_atx ( ... )';
	PERFORM * FROM dblink(v_conn_str, v_query) AS p (ret boolean);
...
CREATE OR REPLACE PROCEDURE logger_save_global_context_atx (...) AS $body$
...
```

This is a real, workable conversion strategy (albeit one that requires
editing the connection string by hand and enabling `dblink`) — **not**
merely a warning in a comment. So the claim "PRAGMA
AUTONOMOUS_TRANSACTION does not port" is, taken literally, **wrong**:
ora2pg does port it, and sensibly.

**BUT.** In the process, a concrete, reproducible bug/blind spot was found
in ora2pg's own **cost estimation** (`estimate_cost`/`%UNCOVERED_SCORE`,
on which `SHOW_REPORT`'s detail is based), and specifically in packages:

- `%UNCOVERED_SCORE` contains `'PRAGMA' => 3` — the weight that *ought*
  to be added on seeing `PRAGMA AUTONOMOUS_TRANSACTION`.
- But for functions **inside a package body** (this applies both to
  `SHOW_REPORT` — `Ora2Pg.pm:18340` — and to a direct `-t PACKAGE
  --estimate_cost` — `Ora2Pg.pm:7275`) the cost is computed only from
  `estimate_cost($self, $infos{$f}{code}, ...)`, where `{code}` is the
  part of the function's text **after** the `BEGIN` keyword (see
  `Ora2Pg/Oracle.pm::_lookup_function`, line 1620: `($fct_detail{declare},
  $fct_detail{code}) = split(/\bBEGIN\b/i, $plsql, 2);`). And `PRAGMA
  AUTONOMOUS_TRANSACTION;` syntactically always sits in the declarative
  section — **before** `BEGIN` — so it lands in `{declare}`, not in
  `{code}`. For package functions and procedures, `{declare}` is simply
  never passed to `estimate_cost`.
- Empirically confirmed: in the real conversion output for `logger.pkb`,
  for `logger.save_global_context` (a function where ora2pg ITSELF
  generated the dblink wrapper, so it definitely "saw" the pragma at
  conversion time) the resulting estimate is `total estimated cost: 6`,
  with the breakdown `TEST => 2`, `SIZE => 1`, `DBMS_ => 1 (cost: 3)` —
  **there is no `PRAGMA` line in the breakdown at all**, even though a
  weight of 3 is defined for it in the table. This is not a one-off — of
  the 9 occurrences of `pragma` in `logger.pkb`, not one is reflected in a
  `PRAGMA => N (cost: 3)` line in any of the per-function reports for the
  package.

  As a control: when that same kind of construct — `CONNECT BY` — occurs
  **inside** the body of a package function (after `BEGIN`, where
  hierarchical queries always are), it lands in `{code}` and is counted
  correctly in the cost (see section 3 — on our `hierarchy_demo_pkg`
  fixture the line `CONNECT BY => 1 (cost: 3)` is present). That confirms
  the cause is the construct's position relative to `BEGIN`, not that
  `PRAGMA` as a keyword is never searched for at all.

**Conclusion:** ora2pg really does *convert* `PRAGMA
AUTONOMOUS_TRANSACTION` through dblink emulation (it is not a case of
"does not port"), but it **systematically underestimates the effort and
risk** of the construct in `SHOW_REPORT` and in `--estimate_cost` for
package functions — the cost for this construct is lost while the
function is being parsed (the declare/code split), not merely "not shown
in detail". This is a concrete, narrow, easily explained and easily
reproduced hole — an excellent task for our tool: (1) count the real
number of `PRAGMA AUTONOMOUS_TRANSACTION` occurrences in packages (which
`SHOW_REPORT` does not do for packages at all), and (2) explain to a
person that "ported" here actually means "the code will call another
database over `dblink`, with a manually configured connection string,
which for an environment with strict requirements on transactional
integrity and on the absence of network dependencies between procedures
may be unacceptable" — that is, not just a number but an architectural
warning, which `SHOW_REPORT` does not give in principle (at best it will
show an understated number, at worst nothing specific to the construct at
all).

### 3. CONNECT BY (hierarchical queries)

**Confirmed by a run** (on a synthetic but honestly labelled fixture,
`hierarchy_demo_pkg`, a wrapper around the canonical Oracle EMP/DEPT
query, inside a real package with a `REF CURSOR`). Ora2pg **really does
convert** `START WITH ... CONNECT BY PRIOR ... SYS_CONNECT_BY_PATH` into a
working PostgreSQL `WITH RECURSIVE` CTE:

```sql
WITH RECURSIVE cte AS (
SELECT employee_id,manager_id,1 AS depth,last_name AS org_path
      FROM   employees WHERE employee_id = p_top_employee_id
  UNION ALL
SELECT employee_id,manager_id,(c.level+1) AS depth,c.org_path || '/' || last_name AS org_path
      FROM   employees JOIN cte c ON (c.employee_id = manager_id)
) SELECT * FROM cte;
```

— `LEVEL` has become a depth counter, `SYS_CONNECT_BY_PATH` string
concatenation, `START WITH`/`CONNECT BY PRIOR` an anchor and a recursive
JOIN. Mechanically this is working SQL. The cost is counted correctly:
`CONNECT BY => 1 (cost: 3)` is present in the detailed per-function
report — because the query is in the function's body (after `BEGIN`),
unlike the `PRAGMA` of section 2.

The conversion is, however, **templated and fragile** (visible directly in
the generated code, without having to run the result on a real Postgres):
`(c.level+1)` — there is no `level` column in the CTE. This is a
substitution bug in the regex-based converter, which simply took the
literal name `LEVEL` and did not substitute the `depth` alias from the
first branch of the `UNION`; the generated SQL, taken literally, **will
not work** without a manual fix (`c.level` has to become `c.depth`). The
converter also cannot handle the more complex variants of `CONNECT BY` —
`CONNECT BY NOCYCLE`, multiple conditions in `CONNECT BY`, `ORDER
SIBLINGS BY`, `CONNECT_BY_ROOT`, `CONNECT_BY_ISLEAF` — none of them is
covered by any regular expression in `PLSQL.pm` (verified by reading the
code: the only `CONNECT BY`-specific transformations there target the
basic `START WITH ... CONNECT BY PRIOR`).

**Conclusion:** `CONNECT BY` is the only one of the five classes where the
baseline `SHOW_REPORT`/`estimate_cost` does not understate but correctly
counts the cost (weight 3 per occurrence). Yet the conversion into `WITH
RECURSIVE` is **not error-free in practice** (the generated `LEVEL`/alias
bug is right there) and **does not cover** the more complex syntax
variants. `SHOW_REPORT` signals only "there is a CONNECT BY here, it costs
N units" and does not say that the automatic conversion may in principle
be incorrect even for the basic case — so our added value here is not "we
detect what ora2pg does not see at all" but "we warn that even when
ora2pg converts and reports a non-zero cost, the generated SQL must be
proofread by hand — the risk is higher than the bare number suggests".

### 4. DBMS_*/UTL_* calls (DBMS_OUTPUT, DBMS_LOB, UTL_FILE, DBMS_SCHEDULER)

A mixed picture, confirmed both by runs and by reading the code:

- **`DBMS_OUTPUT.put_line/put/new_line`** — there is a targeted
  conversion: a regex in `PLSQL.pm` (~line 976) rewrites the calls into a
  `PERFORM` wrapper / `raise_output()` helper (in effect, a message
  through a `RAISE NOTICE`-like mechanism). `DBMS_OUTPUT.ENABLE` is
  simply commented out. The special weight in `%UNCOVERED_SCORE` —
  `'DBMS_OUTPUT.put' => 1` — is lower than the general `DBMS_ => 3`, so
  this particular, broadly harmless construct is already singled out and
  scored below the other `DBMS_*` calls.
- **`DBMS_LOB`** — only 2 functions out of dozens have a direct
  replacement: `DBMS_LOB.GETLENGTH` → `octet_length`,
  `DBMS_LOB.SUBSTR(...)` → `substr(...)` (with the arguments reordered).
  Everything else (`READ`, `WRITE`, `LOADFROMFILE`, `COMPARE`, `INSTR`,
  `APPEND`, `CREATETEMPORARY` and so on — and that is exactly what
  `file_util_pkg.pkb`/`sql_util_pkg.pkb` use) is left unchanged and
  simply falls into the general `DBMS_` counter (weight 3), with no
  indication of which of the ~20 `DBMS_LOB` functions was used and which
  of them have no meaningful PostgreSQL equivalent at all without
  `orafce` or a manual rewrite onto large objects.
- **`UTL_FILE`** — **there is no special conversion whatsoever**
  (verified in the code — the only mention of `UTL_FILE` in `PLSQL.pm` is
  the counting line for cost estimation). The 21 `UTL_FILE.*` calls in
  `file_util_pkg.pkb` (real code: `fopen`, `put_line`, `get_line`,
  `fclose`, the `w`/`r`/`wb` modes) stay in the output as-is — syntax that
  does not exist in PostgreSQL without `orafce`. They are counted only by
  the generic bucket `UTL_ => 5 (cost: 3)` / `UTL_ => 6 (cost: 3)` per
  function — with no indication that `fopen`/`put_line`/`fclose`
  specifically are used, and that one must either bring in `orafce` or
  rewrite the logic through `pg_read_file`/COPY/large objects —
  fundamentally different architectural decisions with different amounts
  of work, all shown by ora2pg under one impersonal `UTL_` label.
- **`DBMS_SCHEDULER`** — as a *call inside a procedure* (not as a separate
  `JOB` object) it is not mentioned anywhere in `PLSQL.pm`/`Ora2Pg.pm`
  except the general `DBMS_\w` regex in `estimate_cost` (which will of
  course also catch it as a `DBMS_` with weight 3, since it matches the
  general `DBMS_\w` pattern) — but there is no scheduler-specific logic or
  warning. Separately, for objects of type `JOB` (that is, scheduled tasks
  created as `CREATE JOB`/through `DBMS_SCHEDULER` at schema level, rather
  than calls inside arbitrary code) `SHOW_REPORT` **does** give a
  meaningful, specific comment (confirmed by reading the code,
  `Ora2Pg.pm:18441`): `"Job are not exported. You may set external cron
  job with them."` — so here, for a whole class of objects, SHOW_REPORT
  already gives what was expected of our tool (a textual explanation on
  top of the number), but that covers only first-class `JOB` objects, not
  arbitrary `DBMS_SCHEDULER.*` calls from procedural code.

**Conclusion:** the hypothesis "`DBMS_*/UTL_*` do not port correctly" is
broadly **confirmed**, but not as a binary "sees it / does not see it"
story. It is more accurate to say: `SHOW_REPORT` **sees the fact of use**
(a generic `DBMS_`/`UTL_` counter, weight 3 per occurrence) but **does not
distinguish**, within that counter, (a) which specific function or package
was used, (b) whether ora2pg has any targeted replacement for it at all
(for 2 `DBMS_LOB` functions and all of `DBMS_OUTPUT` — yes; for the whole
of `UTL_FILE` and the overwhelming majority of `DBMS_LOB` — no), or (c)
what kind of architectural decision will be required (in the PL/pgSQL
runtime? in `orafce`? rewrite the logic?). This is where the distance is
greatest between what `SHOW_REPORT` says (a flat number) and what an
engineer needs to know in order to plan the work — which makes it,
apparently, the most convincing of the five areas for our tool, provided
we get specific down to the level of "which function from which package
was called and whether ora2pg has a ready replacement for it", rather than
re-inventing the bare fact that "`DBMS_*` is used here".

### 5. COMPOUND TRIGGER

**The strongest and most unambiguously confirmed finding of the report**,
and the only one where a real run gave a binary "not found" result rather
than "found, but imprecisely".

On a real file with a syntactically correct `COMPOUND TRIGGER`
(`Apress/modern-oracle-database-programming`, `tr_constructors_cti`, all
four sections — `BEFORE STATEMENT`, `BEFORE EACH ROW`, `AFTER EACH ROW`,
`AFTER STATEMENT`):

```
ora2pg -t TRIGGER -i compound_trigger_apress.sql --estimate_cost ...
[...] 0/0 triggers (100.0%) end of output.
-- Nothing found of type TRIGGER
```

A control run on a classic simple trigger (`BEFORE INSERT OR UPDATE ...
FOR EACH ROW BEGIN ... END`) from the very same session gave `1/1
triggers` and a correct conversion into `CREATE FUNCTION` + `CREATE
TRIGGER`. So this is not an environment or configuration problem — it is a
specific, reproducible parser failure **specifically** on compound
triggers.

**The cause (per the code):** `read_trigger_from_file()` (`Ora2Pg.pm`,
~line 3868) parses the trigger body with two rigid regexes, both of which
require `FOR EACH ROW/STATEMENT` to come immediately after `ON <table>`,
then optionally `WHEN (...)`, and then `BEGIN`/`DECLARE` directly. The
`COMPOUND TRIGGER` syntax in principle contains neither a top-level `FOR
EACH ROW` (the timing is given separately in each of the four sections)
nor a single `BEGIN` right after the declaration — instead there is
`COMPOUND TRIGGER`, a declarative section, and then 4 named blocks `BEFORE
STATEMENT IS ... END BEFORE STATEMENT;` and so on. Neither regex is
designed for that shape → the trigger drops out of the result entirely,
**without a single warning** ("Nothing found" is the standard "the file is
empty" message, not "could not parse").

**An important caveat (not confirmed by a run, from the code only):** in
live mode (connected to Oracle, not file input) the trigger object as such
**will** be counted in the `SHOW_REPORT` `TRIGGER: number/invalid`
counter — because that counter comes straight from Oracle's
`ALL_OBJECTS`/`ALL_TRIGGERS` catalog (`_get_objects()`, `_get_triggers()`)
rather than through the file regex parser, and Oracle marks a valid
`COMPOUND TRIGGER` as `VALID`. So **the object count in SHOW_REPORT will
not show the problem** — a compound trigger will look like one ordinary
valid trigger. We could not check this in the sandbox (no live Oracle),
but per the code `export_trigger()` (`Ora2Pg.pm:5975+`) applies to the
trigger body — obtained from `TRIGGER_BODY` through that same DB column —
a series of transformations (`s/\s*EACH ROW//is`, parsing `trig->[1]`/
`trig->[2]` as "the BEFORE/AFTER/INSTEAD OF type" plus "the
INSERT/UPDATE/DELETE event") that are incompatible with `TRIGGER_TYPE =
'COMPOUND'` and with a body beginning with `COMPOUND TRIGGER` — so from
the whole structure of the code it is extremely likely that in live mode
too the actual conversion of a compound trigger's body would either
produce syntactically invalid PL/pgSQL or silently corrupt the logic
(there is no "this is a compound trigger, handle it differently" check
anywhere in the codebase — a grep for `COMPOUND` in `lib/` outside the
geometry module returns nothing). This is marked explicitly as a
conclusion from reading the code, not confirmed by a live run.

**Conclusion:** the hypothesis is **fully confirmed**, and even more
strongly than stated: `COMPOUND TRIGGER` is not "ported incorrectly", it
**drops out completely** of ora2pg's file mode without a single warning,
and per the code it looks as though in live mode the result would be
either a corrupted or a syntactically invalid trigger-function body —
while the "number of triggers / invalid triggers" metric in `SHOW_REPORT`
**will show nothing suspicious at all**, because it is taken from Oracle's
catalog rather than from an attempted conversion. This is exactly the kind
of gap that a person relying on `SHOW_REPORT`'s bare numbers will not
notice until they see empty or broken output after a real conversion —
that is, precisely the "after the fact, once it has already broken in
production" scenario the project's README describes as the original
problem.

## Summary table

| Class of construct | Does SHOW_REPORT see that it is used? | Does it give detail on the object/cause? | Does it really convert (not just count)? | Confirmed |
|---|---|---|---|---|
| CREATE PACKAGE / PACKAGE BODY | Yes (fully) | Partly (total cost + list of functions) | Yes, the basic structure works | By a run |
| PRAGMA AUTONOMOUS_TRANSACTION | **No** for functions inside packages (the declare/code bug) | No (the cost is lost) | Yes (dblink emulation), but the conversion and the cost accounting are out of sync | By a run + the code |
| CONNECT BY | Yes, correctly (weight 3) | Partly (a counter only, no warning about quality) | Yes, but with bugs even in the basic case (LEVEL/alias), and it does not cover NOCYCLE/ROOT/ISLEAF | By a run (on a fixture) |
| DBMS_*/UTL_* | Yes, but impersonally (a general DBMS_/UTL_ bucket, weight 3) | No (which function/package it was is not visible) | Selectively: DBMS_OUTPUT — yes; 2 DBMS_LOB functions — yes; UTL_FILE, DBMS_SCHEDULER calls, the rest of DBMS_LOB — no | By a run + the code |
| COMPOUND TRIGGER | In live mode — yes, as an object counter (per the code, not verified); in file mode — **no, it disappears entirely** | No | No; from the whole structure of the code — likely breaks or skips it | By a run (file mode) + the code (the live hypothesis) |

## Is the original hypothesis confirmed?

**Partly, and in a more specific form than originally stated.**

The original framing ("SHOW_REPORT does not see those 20% at all, our tool
detects them") is **inaccurate**: `SHOW_REPORT` **does see** that all five
constructs are used, at the keyword level (except COMPOUND TRIGGER in file
mode, where parsing fails completely), and in three cases out of five
(PACKAGE, CONNECT BY, part of `DBMS_*`) it actually attempts, or fully
succeeds at, the conversion — it does not merely warn.

A more accurate and, importantly, **experimentally confirmed** framing of
the tool's real added value:

1. **COMPOUND TRIGGER** — the only case of a true "blind spot" in the
   literal sense: nothing at all is visible, neither a number nor a
   warning (in file mode — confirmed; in live mode, per the code, the
   object count will be there, but with no indication that it is a
   compound trigger and that the conversion will most likely fail).
2. **PRAGMA AUTONOMOUS_TRANSACTION** — not "invisible" but a **specific,
   reproducible effort-underestimation bug**, specifically for functions
   inside packages (the most common case in practice — most autonomous
   transaction procedures live in packages, as in our Logger example),
   plus the absence of any warning that the "ported" code in fact requires
   `dblink`, a separate connection and a manually configured connection
   string — an architectural decision, not just syntax.
3. **DBMS_*/UTL_*** — not "invisible" but **impersonal**: there is a
   number, but no identification of the specific function or package and
   of whether ora2pg has a ready replacement for it.
4. **CONNECT BY** — not "invisible" but **an underestimated risk**: the
   number is there and is correct, the conversion happens, but it can be
   quietly wrong even in the basic case — there is simply no warning about
   that risk.
5. **PACKAGE as such** — the hypothesis is not confirmed: a package's
   structure ports fine, and a "there is a package here, that is a
   problem" detector is not needed on its own; the value lies inside the
   package, in the nested constructs listed above.

So the claim "SHOW_REPORT does not report those 20% in enough detail" is
**broadly confirmed**, but the right way to state the tool's value is not
"detecting what ora2pg does not see" but **"diagnosing what specifically
ora2pg either (a) skips entirely without warning (COMPOUND TRIGGER), or
(b) underestimates in cost because of its own parsing bugs (PRAGMA in
packages), or (c) makes so impersonal it loses relevance (DBMS_*/UTL_*),
or (d) silently converts, potentially incorrectly, with no risk flag
(CONNECT BY)"**.

## Recommendation: where to start Task 1 (the packages detector)

Given the findings above, the priorities for Task 1 should be adjusted:

1. **Do not start with a "detect the presence of CREATE PACKAGE"
   detector** — as shown above, that is not a problem in itself; ora2pg
   handles it fine.
2. **Start with a detector for PRAGMA AUTONOMOUS_TRANSACTION *inside
   package bodies* (PACKAGE BODY)** — a narrow, maximally specific,
   experimentally confirmed and easily explained finding (including to a
   client or an architect): we can quote ora2pg's specific bug directly
   (the declare/code split in `_lookup_function`) and show that for this
   case `SHOW_REPORT` either gives no number at all or gives an
   understated one. A practical implementation for Task 1: parse `CREATE
   OR REPLACE PACKAGE BODY`, find the boundaries of each function or
   procedure (`FUNCTION|PROCEDURE ... IS/AS ... BEGIN ... END`), search
   for `PRAGMA\s+AUTONOMOUS_TRANSACTION` in the declarative part (between
   `IS/AS` and `BEGIN`), and for every occurrence found emit a separate
   report entry with (a) the package.function name, (b) the exact code
   fragment, (c) a human-readable explanation — "ora2pg will port this
   through a dblink wrapper: the dblink extension must be enabled and the
   connection string set by hand; if cross-connections between procedures
   or network dependencies are unacceptable in your environment, a
   different strategy is needed (for example, a dedicated
   autonomous-transaction table plus fire-and-forget through `pg_notify`,
   or a manual refactor)" — and (d) a difficulty rating (not just "weight
   3" but one that takes the kind of operation into account: a commit
   inside a loop is clearly harder than a one-off commit).
3. Then the **COMPOUND TRIGGER detector** (second priority): maximally
   cheap to implement (look for `COMPOUND TRIGGER` as a token in the
   trigger's DDL — nobody in the pipeline does that today) and maximally
   valuable (a complete, silent failure in ora2pg).
4. A detector for `DBMS_*/UTL_*` makes sense not as "detecting that they
   are used" (`SHOW_REPORT` already does that, impersonally as it may be)
   but straight away as a **classifier of specific functions** consulting
   our own dictionary of "ora2pg has a replacement / has none / has one
   through orafce" — then it really does add what `SHOW_REPORT` lacks.
5. The `CONNECT BY` detector is low priority for the MVP (ora2pg counts it
   reasonably well itself), but if it is built, the focus should not be on
   "detection" but on **validating the conversion's result** (checking the
   generated `WITH RECURSIVE` for undeclared aliases such as `LEVEL`
   instead of the depth column — which is, in essence, a separate class of
   task: linting ora2pg's output rather than analysing its input).

## Materials for reproduction

All downloaded examples and the synthetic fixture live in
`docs/research/samples/` in this repository:

- `logger.pks`, `logger.pkb` — OraOpenSource/Logger
  (`github.com/OraOpenSource/Logger`, files `source/packages/logger.pk{s,b}`)
- `file_util_pkg.pks`, `file_util_pkg.pkb`, `sql_util_pkg.pks`,
  `sql_util_pkg.pkb` — mortenbra/alexandria-plsql-utils
  (`github.com/mortenbra/alexandria-plsql-utils`, the `ora/` directory)
- `compound_trigger_apress.sql` — Apress/modern-oracle-database-programming
  (`Listing 1-7. Compound Trigger tr_constructors_cti.sql`)
- `compound_trigger_dlee.sql` — dlee0113/oracle_pl_sql_programming
  (`11g_compound_mutating.sql`, an additional example with the
  mutating-table problem and a package-based workaround for compound
  triggers; not used directly for the empirical tests above, kept for
  reference)
- `connect_by_hierarchy_pkg.sql` — our synthetic fixture (see the
  explanation in the file); not presented as a real third-party repository

ora2pg (`darold/ora2pg`, commit `cc2c434f`, `VERSION=25.0`) was cloned
outside this repository and is not part of the commit; to repeat:

```sh
git clone https://github.com/darold/ora2pg.git
apt-get install -y libdbi-perl   # the only missing Perl dependency
mkdir -p /etc/ora2pg && touch /etc/ora2pg/ora2pg.conf
PERL5LIB=ora2pg/lib perl ora2pg/scripts/ora2pg \
  -t PACKAGE -i docs/research/samples/logger.pkb \
  --estimate_cost -o out.sql -b /tmp/out
```
