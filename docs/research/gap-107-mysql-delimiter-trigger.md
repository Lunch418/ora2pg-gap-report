# GAP-107: a trigger written under `DELIMITER //` disappears

MySQL/MariaDB feature: a trigger with a `BEGIN … END` body, written under
a `DELIMITER` so the `mysql` client sends it as one statement.

## Minimal example

```sql
DELIMITER //
CREATE TRIGGER t_bi BEFORE INSERT ON t FOR EACH ROW
BEGIN
  SET NEW.b = NEW.a;
END //
DELIMITER ;
```

## ora2pg output (v25.0, `-m -t TRIGGER`)

```sql
\set ON_ERROR_STOP ON
```

Nothing else: no trigger, no trigger function, no error, and no line in
the log.

## Observed problem

ora2pg's trigger parser finds the end of a trigger by a `;`. Under a
delimiter that contains none it finds no trigger at all. Tried:

| Delimiter | Triggers generated |
|---|---|
| `;;` | 1 (converted) |
| `//` | 0 |
| `$$` | 0 |
| `\|` | 0 |
| `$` | 0 |

The schema loads, and the table in PostgreSQL simply has no trigger:
whatever it did — filling columns, auditing, keeping a summary table in
step — silently stops happening. Nothing fails until someone notices the
data.

`;;` is `mysqldump`'s own choice for triggers, so a dump is not affected
by this gap (its triggers are lost to GAP-109 instead); hand-written
scripts, which overwhelmingly use `//` or `$$`, are.

**Reproducible: YES.** Ora2Pg version: 25.0. Source dialect: MySQL
(`ora2pg -m`).

## Verdict

**Gap confirmed, severity high, failure_stage conversion** — the loss is
only visible in what ora2pg did not output, the same stage as GAP-059.
Fixed before converting: switch the delimiter to `;;` or drop the
`DELIMITER` directives.

Implemented: `ora2pg_gap_report/detectors/mysql_delimiter_trigger.py` —
flags each `CREATE TRIGGER` that stands where a delimiter without `;` is
in force.
