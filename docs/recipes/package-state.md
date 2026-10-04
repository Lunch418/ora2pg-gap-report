*English | [Русский](package-state.ru.md)*

# Package variables and application contexts

Covers: GAP-036 (`package_state`), GAP-015 (`context_object`).

## The problem

A variable or constant declared at the top of a package lives for the
whole session and is shared by the package's routines. PostgreSQL has no
packages; `ora2pg` emulates the variable with a custom setting
(`set_config('pkg.var', ...)` / `current_setting('pkg.var')`), which is the
right idea, but the generated calls fail: the value is passed without a
cast to `text`, and reading a variable nobody has set yet raises an error
instead of returning `NULL` (GAP-036). An application context
(`CREATE CONTEXT`, `SYS_CONTEXT`, `DBMS_SESSION.SET_CONTEXT`) is dropped
without a word (GAP-015), and with it whatever row-level security relied
on it.

## Session variables that behave like package variables

One getter and one setter per variable, named after the package, hide the
setting's name and its text type from every caller:

```sql
CREATE FUNCTION pkg_ctx_set_user(p_id bigint)
RETURNS void
LANGUAGE sql
AS $$
    -- false: the value lives for the session, like a package variable.
    SELECT set_config('pkg_ctx.g_user_id', p_id::text, false);
$$;

CREATE FUNCTION pkg_ctx_get_user()
RETURNS bigint
LANGUAGE sql
STABLE
AS $$
    -- true: missing_ok, so an unset variable reads as NULL, as in Oracle.
    -- NULLIF: once set and then reset, a setting reads as '' rather than NULL.
    SELECT NULLIF(current_setting('pkg_ctx.g_user_id', true), '')::bigint;
$$;

DO $$
BEGIN
    ASSERT pkg_ctx_get_user() IS NULL;      -- never set in this session
    PERFORM pkg_ctx_set_user(42);
    ASSERT pkg_ctx_get_user() = 42;
END $$;
```

The two fixes against `ora2pg`'s output are the `::text` in the setter and
`current_setting(..., true)` with `NULLIF` in the getter. The setting's
name needs a dot (`pkg_ctx.g_user_id`); the part before it is free to
choose, and using the package name keeps different packages apart.

### Constants

A package constant is not state. A function returning the value says so,
and PostgreSQL can inline it:

```sql
CREATE FUNCTION pkg_ctx_c_max_retries()
RETURNS integer
LANGUAGE sql
IMMUTABLE
AS $$ SELECT 3 $$;

DO $$
BEGIN
    ASSERT pkg_ctx_c_max_retries() = 3;
END $$;
```

### Collections and records

A setting holds text only. For a package-level collection or a record,
either serialize it (`jsonb` in and out of the setting, fine for a handful
of values) or keep it in a temporary table, which is per session just like
the package variable was. See [temporary tables](temporary-tables.md).

### Connection pools

A package variable belongs to an Oracle session. With a connection pool,
a PostgreSQL session is reused by many clients, and a value set with
`set_config(..., false)` stays for the next one. Two safe patterns:

- set the value at the start of every transaction with `is_local = true`
  (`set_config('pkg_ctx.g_user_id', '42', true)`, or `SET LOCAL`), so it
  disappears at commit; this also works with PgBouncer in transaction mode;
- or reset it when the connection goes back to the pool (`RESET ALL`, or
  `DISCARD ALL`, which most pools can run for you).

## Application contexts and row-level security

`SYS_CONTEXT('hr_ctx', 'tenant_id')` reads the same kind of value: map it to
a setting named after the context.

```pgsql
-- Oracle: SYS_CONTEXT('hr_ctx', 'tenant_id')
NULLIF(current_setting('hr_ctx.tenant_id', true), '')
```

**The difference that matters for security:** an Oracle context can only be
changed by the package named in `CREATE CONTEXT ... USING`. Any session
can change a PostgreSQL setting with `SET`. If the context was the basis of
a VPD policy, a setting alone lets a user pick their own tenant. Tie the
policy to something the user cannot change instead, such as their role:

```sql
CREATE TABLE tenants_by_role (role_name name PRIMARY KEY, tenant_id integer NOT NULL);
CREATE TABLE documents (doc_id integer PRIMARY KEY, tenant_id integer NOT NULL, body text);
INSERT INTO documents VALUES (1, 10, 'ours'), (2, 20, 'theirs');

-- DBMS_RLS.ADD_POLICY -> a row-level security policy
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON documents
    USING (tenant_id = (SELECT t.tenant_id FROM tenants_by_role t WHERE t.role_name = current_user));

CREATE ROLE recipe_app_user;
GRANT SELECT ON documents, tenants_by_role TO recipe_app_user;
INSERT INTO tenants_by_role VALUES ('recipe_app_user', 10);

SET ROLE recipe_app_user;
DO $$
BEGIN
    -- the policy shows only the user's own tenant, whatever they SET
    PERFORM set_config('hr_ctx.tenant_id', '20', true);
    ASSERT (SELECT array_agg(doc_id) FROM documents) = ARRAY[1];
END $$;
RESET ROLE;
```

When the tenant really has to be chosen per session (one database role for
the whole application), set it from a `SECURITY DEFINER` function that
checks the caller is allowed to, and make the policy read the setting. A
user who can run arbitrary SQL can still `SET` it, so this fits only
applications that never hand the database connection to the end user.

Superusers and the table's owner bypass row-level security unless the table
has `ALTER TABLE ... FORCE ROW LEVEL SECURITY`; test policies under the
application's own role, as above.
