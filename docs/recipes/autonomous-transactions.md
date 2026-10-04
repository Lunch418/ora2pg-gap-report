*English | [Русский](autonomous-transactions.ru.md)*

# Autonomous transactions

Covers: GAP-001 (`autonomous_tx`).

## The problem

`PRAGMA AUTONOMOUS_TRANSACTION` runs a routine in its own transaction: what
it commits stays committed even if the caller rolls back. PostgreSQL has
no such thing inside one session. `ora2pg` does convert it, by default
into a `dblink` wrapper: the routine becomes `<name>_atx` and a proxy
calls it over a second connection. GAP-001 is that `--estimate_cost`
charges nothing for this inside a package body, while it brings in an
extension, a connection string and a network round trip on every call.

So the work is a decision per routine, not a syntax fix. First find out
*why* each routine is autonomous; most fall into one of the three cases
below.

## Case 1: logging that must survive a rollback

The most common reason: write an error log row, then let the caller roll
back. There are two PostgreSQL answers.

**If the log can go to the server log**, there is nothing to convert:
`RAISE LOG` is not transactional.

```sql
CREATE PROCEDURE log_event(p_message text)
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE LOG 'app: %', p_message;
END;
$$;
```

**If the log must be a table row**, it needs its own connection, which is
exactly what `ora2pg`'s wrapper does. Written by hand it is short:

```pgsql
CREATE TABLE app_log (
    logged_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    message   text NOT NULL
);
```

```sql
CREATE EXTENSION IF NOT EXISTS dblink;

CREATE PROCEDURE log_autonomous(p_message text)
LANGUAGE plpgsql
AS $$
BEGIN
    -- A second connection to the same database commits on its own.
    -- Fill in user/password (or use ~/.pgpass) for your setup.
    PERFORM dblink_exec(
        'dbname=' || current_database(),
        format('INSERT INTO app_log (message) VALUES (%L)', p_message)
    );
END;
$$;
```

This one is checked against a real server: the plain insert is undone with
the failed block, the autonomous one is not.

```sql
CREATE TABLE app_log_plain (message text);

-- The second connection sees only committed tables. In your database
-- app_log is already there; this check creates it the same way.
SELECT dblink_exec(
    'dbname=' || current_database(),
    'CREATE TABLE IF NOT EXISTS app_log (
         logged_at timestamptz NOT NULL DEFAULT clock_timestamp(),
         message   text NOT NULL)'
);

DO $$
BEGIN
    BEGIN
        INSERT INTO app_log_plain VALUES ('plain');
        CALL log_autonomous('autonomous');
        RAISE EXCEPTION 'business error';
    EXCEPTION WHEN raise_exception THEN
        NULL;  -- the block's own work is rolled back here
    END;
    ASSERT (SELECT count(*) FROM app_log_plain) = 0;
    ASSERT (SELECT count(*) FROM app_log WHERE message = 'autonomous') = 1;
END $$;
```

Things to know before choosing the table version:

- Every call opens a connection. Logging inside a hot loop gets slow; log
  once per failure, or collect messages and write them in one call.
- A non-superuser can only use `dblink` with a password in the connection
  string (or a `postgres_fdw`-style user mapping). Keep it out of the code:
  `ora2pg`'s `DBLINK_CONN` directive in `ora2pg.conf` sets it once for the
  generated wrappers.
- The second connection does not see the caller's uncommitted rows, the
  same as in Oracle.

## Case 2: commit inside a trigger or a function

Some code is autonomous only because it wants to `COMMIT` where Oracle
does not allow it otherwise. In PostgreSQL:

- A **procedure** called with `CALL` outside an explicit transaction block
  may `COMMIT` and `ROLLBACK` itself. If the autonomous routine was the
  top-level unit of work, make it a procedure and drop the pragma.
- A **function** or **trigger** cannot commit. If it truly must, it is
  case 1 (a second connection). Often it does not: the commit was there to
  release locks early, and in PostgreSQL the caller's commit does that.

## Case 3: a background job

Code that kicks off work which must outlive the caller (send an email,
refresh a summary) is a queue, not a transaction. Insert a row into a
job table in the caller's transaction and let a worker process it after
the commit, or use an extension built for it (`pg_cron` for schedules,
`pg_background` for one-off background statements).

## The ora2pg side

- `AUTONOMOUS_TRANSACTION 1` (the default) makes `ora2pg` generate the
  `dblink` wrapper; `0` exports the routine as an ordinary one, without
  the pragma, which is what you want for case 2.
- `PG_BACKGROUND 1` generates a `pg_background` wrapper instead of a
  `dblink` one. The extension is not part of PostgreSQL itself; install it
  on the server first.
- Budget for this in the plan yourself: `--estimate_cost` does not, for a
  routine in a package body (GAP-001).
