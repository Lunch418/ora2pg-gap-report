# GAP-126: a routine followed by `GO` - the `GO` goes into its body

MSSQL feature: `GO`, the batch separator SSMS and sqlcmd write after every
object they script. It is a client command, not T-SQL, and stands on a
line of its own.

## How it was found

`--migrate --dialect mssql --load-check docker` on an SSMS-style script,
after GAP-125's schema was created: the procedure still failed, with
`end label "go" specified for unlabeled block`.

## Minimal example

```sql
CREATE PROCEDURE add_order @id int
AS
BEGIN
    INSERT INTO orders (id) VALUES (@id);
END
GO
CREATE FUNCTION next_id (@a int) RETURNS int
AS
BEGIN
    RETURN @a + 1;
END
GO
```

## ora2pg output (v25.0, `-M -t PROCEDURE`)

```sql
CREATE OR REPLACE PROCEDURE add_order (p_id integer) AS $body$
BEGIN
BEGIN
     INSERT INTO orders(id) VALUES (p_id);
END
GO
END;
$body$
```

ora2pg reads a routine up to the next `CREATE`, so the `GO` is inside the
body, and the `END;` it adds to close its own wrapping `BEGIN` comes after
it.

## Observed problem

PostgreSQL 16 does not load either routine:

```
ERROR:  42601: end label "go" specified for unlabeled block
```

With `END;` before the `GO` it is `syntax error at or near "GO"` instead.
Without the `GO` lines, a routine whose last line is a bare `END` loses an
`END` (`syntax error at end of input`); written `END;` without `GO`, both
routines convert, load and work: `CALL add_order(5)` inserts the row and
`next_id(1)` returns 2.

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16.

## Verdict

**Gap confirmed, severity high, failure_stage deployment.** Mechanical, in
the source: `--prepare --dialect mssql` (`prepare_mssql_go_separator`)
removes the `GO` lines and puts a `;` after the bare `END` that closed a
batch. `GO` separates batches for the client only, and ora2pg splits
objects on `CREATE` anyway, so nothing is lost; a `GO n` repeat count is
dropped with it (it only re-runs a batch). `--migrate` applies it.

Implemented: `ora2pg_gap_report/detectors/mssql_go_separator.py` -
reported at the `GO`, once per routine; it recognises ora2pg's output with
the `GO` inside too, which is how `--load-check` ties the error to it.
