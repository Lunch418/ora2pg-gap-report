# GAP-036: a package variable (session-level state) — broken emulation through `set_config`

Oracle feature: a variable declared at the top level of a `PACKAGE BODY`
(not inside a particular procedure or function) — state that lives for the
whole session and is shared by all of the package's procedures. A common
pattern is a context package (`g_user_id`, `g_tenant_id` and the like),
set once at the start of a session and read many times inside different
procedures of the same package.

## Minimal example

```sql
CREATE OR REPLACE PACKAGE pkg_ctx AS
  g_user_id NUMBER;
  PROCEDURE set_user(p_id NUMBER);
  FUNCTION get_user RETURN NUMBER;
END pkg_ctx;
/
CREATE OR REPLACE PACKAGE BODY pkg_ctx AS
  PROCEDURE set_user(p_id NUMBER) IS
  BEGIN
    g_user_id := p_id;
  END;
  FUNCTION get_user RETURN NUMBER IS
  BEGIN
    RETURN g_user_id;
  END;
END pkg_ctx;
```

## ora2pg output (v25.0, `-t PACKAGE`)

```sql
CREATE OR REPLACE PROCEDURE pkg_ctx_set_user (p_id bigint) AS $body$
BEGIN
    PERFORM set_config('pkg_ctx.g_user_id', p_id, false);
  END;
$body$
LANGUAGE PLPGSQL
;

CREATE OR REPLACE FUNCTION pkg_ctx_get_user () RETURNS bigint AS $body$
BEGIN
    RETURN current_setting('pkg_ctx.g_user_id')::bigint;
  END;
$body$
LANGUAGE PLPGSQL
;
```

The idea behind the solution is sound — `set_config()`/`current_setting()`
with a custom GUC parameter (`pkg_ctx.g_user_id`), and `set_config`'s
third argument `false` (not transaction-local), which does match the
lifetime of an Oracle package variable (the whole session). But the
implementation is broken in two places.

## Observed problem

**First:** `set_config()` takes `text` as its second argument, while
`p_id` is `bigint`. ora2pg does not add an explicit cast. Confirmed
against a real PostgreSQL 16 — it fails on the very first call, without
exception:

```sql
CALL pkg_ctx_set_user(42);
-- ERROR:  function set_config(unknown, bigint, boolean) does not exist
-- HINT:  No function matches the given name and argument types.
```

**Second (which shows up even after adding `::text` by hand):** in Oracle
an unset numeric package variable defaults to `NULL`, so reading it before
the first `SET` simply returns `NULL`, with no error. `current_setting()`
on a custom GUC parameter that has not been set yet raises an error in
PostgreSQL unless the second argument `missing_ok => true` is passed:

```sql
SELECT pkg_ctx_get_user();
-- ERROR:  unrecognized configuration parameter "pkg_ctx.g_user_id"
```

Neither error is syntactic — `CREATE PROCEDURE`/`CREATE FUNCTION` succeed
without trouble (`check_function_bodies` is disabled), and the failure
happens only on the call. The first error reproduces on any use whatsoever
— it is not an edge case. The second depends on the order of calls within
a session: the ordinary scenario is `get_user()` being called in a session
where `set_user()` has not been called yet, which happens regularly for
many real context packages — with pooled connections, for instance.

**Reproducible: YES.** Ora2Pg version: 25.0.

## Also checked: package-level CONSTANT, and declaration in the spec

The detector's first version (see `git log` for `package_state.py`) looked
only at declarations in the `PACKAGE BODY` and skipped `CONSTANT`. Both
cases were checked with a separate real ora2pg 25.0 run:

**CONSTANT.** A package constant gets the same rewrite as an ordinary
variable — ora2pg makes no real distinction:

```sql
CREATE OR REPLACE PACKAGE BODY pkg_ctx AS
  c_max_retries CONSTANT PLS_INTEGER := 3;
  FUNCTION get_retries RETURN PLS_INTEGER IS
  BEGIN
    RETURN c_max_retries;
  END;
END pkg_ctx;
```

generated output:

```sql
CREATE OR REPLACE FUNCTION pkg_ctx_get_retries () RETURNS integer AS $body$
BEGIN
    RETURN current_setting('pkg_ctx.c_max_retries')::integer;
  END;
$body$
```

Worse than for an ordinary variable: a constant has no "first `SET`" at
all — ora2pg generates no `set_config()` for its initial value (`:= 3`),
so `current_setting()` is guaranteed to fail with `unrecognized
configuration parameter` on any access, not merely before the first call
to a writing procedure.

**Declared in the spec rather than the body.** `PACKAGE ... AS <var>; ...
END;` (with no redeclaration in the `PACKAGE BODY`) is fully subject to
the same rewrite; ora2pg does not distinguish where the package variable
came from. The detector originally looked only at the `PACKAGE BODY` —
this document's own minimal example declares the variable in the spec and
so was not detected at all, which was a bug rather than a separate
unconfirmed case. Found by a code audit and fixed.

## Verdict

**Gap confirmed.** Implemented in
`ora2pg_gap_report/detectors/package_state.py`.
