# GAP-108: `-t PROCEDURE` skips a procedure with `DEFINER`

MySQL/MariaDB feature: `CREATE DEFINER=<user> PROCEDURE …`, the security
context a routine runs in. `mysqldump` writes a `DEFINER` on every
procedure it dumps.

## Minimal example

```sql
DELIMITER ;;
CREATE DEFINER=`app`@`%` PROCEDURE `close_order`(p_id INT)
BEGIN
  UPDATE orders SET status = 'closed' WHERE id = p_id;
END ;;
DELIMITER ;
```

## ora2pg output (v25.0, `-m -t PROCEDURE`)

```sql
\set ON_ERROR_STOP ON
```

The procedure is not there, and nothing says so. Without `DEFINER`, the
same procedure is exported. Every spelling of the definer was tried —
`` `root`@`localhost` ``, `root@localhost`, `'root'@'localhost'`,
`` `root`@`%` ``, `CURRENT_USER` — with the same result.

## Why: ora2pg's source

`export_procedure()` (lib/Ora2Pg.pm, 25.0) recognises the start of a
procedure in the input file with

```perl
if ($l =~ /^\s*CREATE\s*(?:OR REPLACE)?\s*(?:EDITIONABLE|NONEDITIONABLE)?\s*(FUNCTION|PROCEDURE)\s*$/i)
...
$l =~ s/^\s*CREATE (?:OR REPLACE)?\s*(?:EDITIONABLE|NONEDITIONABLE)?\s*(FUNCTION|PROCEDURE)/$1/i;
```

while `export_function()`, a few hundred lines above, has

```perl
$l =~ s/^\s*CREATE (?:OR REPLACE)?\s*(?:EDITIONABLE|NONEDITIONABLE|DEFINER=[^\s]+)?\s*(FUNCTION|PROCEDURE)/$1/i;
```

— the same patterns with `DEFINER=[^\s]+` as an alternative. Without it,
a `CREATE DEFINER=… PROCEDURE` line never becomes `PROCEDURE <name>`, the
routine's name is never picked up, and every line of it is skipped.

That also gives the way around it: `-t FUNCTION` exports the procedure.
On the example above it generated both routines of a file holding a
`DEFINER` procedure and a `DEFINER` function. (In a real dump they still
carry `DELIMITER`, and so do not load — GAP-106.)

## Observed problem

On a real `mysqldump --routines` of sakila (MySQL 8.0.46), `-t PROCEDURE`
exported 0 of its 4 procedures. The schema loads; the first `CALL` fails
with `procedure … does not exist`.

**Reproducible: YES.** Ora2Pg version: 25.0. Source dialect: MySQL
(`ora2pg -m`).

## Verdict

**Gap confirmed, severity high, failure_stage conversion.** Fixed either
by stripping `DEFINER=…` before converting, or by exporting procedures
with `-t FUNCTION` instead of `-t PROCEDURE`.

Implemented: `ora2pg_gap_report/detectors/mysql_definer_procedure.py` —
flags `CREATE … DEFINER=… PROCEDURE`, in every spelling of the definer.
A function with `DEFINER` is not flagged: `-t FUNCTION` handles it.
