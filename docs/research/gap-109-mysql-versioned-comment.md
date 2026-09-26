# GAP-109: an object inside `/*!50003 … */` disappears

MySQL/MariaDB feature: executable ("versioned") comments. MySQL runs the
contents of `/*!NNNNN … */` when its version is at least NNNNN, so for
MySQL they are code. `mysqldump` wraps every trigger and every view in
them (and, in older versions, routines too):

## Minimal example

```sql
DELIMITER ;;
/*!50003 CREATE*/ /*!50017 DEFINER=`root`@`localhost`*/ /*!50003 TRIGGER `trg` AFTER UPDATE ON `language` FOR EACH ROW BEGIN
  REPLACE INTO film_text (film_id, title) VALUES (1, 1);
END */;;
DELIMITER ;

/*!50001 CREATE ALGORITHM=UNDEFINED */
/*!50013 DEFINER=`root`@`localhost` SQL SECURITY DEFINER */
/*!50001 VIEW `v_probe` AS select 1 AS `x` */;
```

## ora2pg output (v25.0, `-m -t TRIGGER` / `-t VIEW`)

```sql
\set ON_ERROR_STOP ON
```

for each — ora2pg removes comments before it parses, and the objects go
with them. No error, and nothing in the log.

A/B: the same trigger as a plain `CREATE TRIGGER` converts (2 statements,
the trigger function and the trigger); the same view as a plain
`CREATE VIEW` converts. The routine forms old mysqldump versions write —
`/*!50003 CREATE*/ /*!50020 DEFINER=…*/ /*!50003 PROCEDURE …*/` and the
same for `FUNCTION` — give 0 routines under both `-t PROCEDURE` and
`-t FUNCTION`.

## Observed problem

On a real `mysqldump` of sakila (MySQL 8.0.46), `-t TRIGGER` and
`-t VIEW` produced no trigger and no view. The schema loads without
them; the triggers' work silently stops, and queries against the views
fail with `relation … does not exist`.

**Reproducible: YES.** Ora2Pg version: 25.0. Source dialect: MySQL
(`ora2pg -m`).

## Verdict

**Gap confirmed, severity high, failure_stage conversion.** Fixed before
converting by unwrapping the comments and keeping the `CREATE` inside
them, or by producing the DDL some other way for these objects (for
instance `SHOW CREATE TRIGGER`/`SHOW CREATE VIEW`, which return it
unwrapped).

Implemented: `ora2pg_gap_report/detectors/mysql_versioned_comment.py` —
reads the raw source (what it looks for is a comment), joins consecutive
executable comments the way mysqldump splits one `CREATE` across them,
and flags a `CREATE TRIGGER|VIEW|PROCEDURE|FUNCTION`. mysqldump's other
executable comments — `SET`, `DROP … IF EXISTS`, `ALTER TABLE … KEYS` —
are not flagged, and neither is a string that only looks like one.
