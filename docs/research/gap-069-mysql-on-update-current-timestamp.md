# GAP-069: `DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP`

MySQL/MariaDB feature: `ON UPDATE CURRENT_TIMESTAMP` — part of the
`DEFAULT` on a `TIMESTAMP`/`DATETIME` column, auto-refreshing the value
on every `UPDATE` of the row (the classic `updated_at` pattern).

## Minimal example

```sql
CREATE TABLE sessions (
  id INT PRIMARY KEY AUTO_INCREMENT,
  token VARCHAR(64) NOT NULL,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);
```

## ora2pg output (v25.0, `-m -t TABLE`)

```sql
CREATE TABLE sessions (
	id serial,
	token varchar(64) NOT NULL,
	updated_at timestamp without time zone NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ;
ALTER TABLE sessions ADD PRIMARY KEY (id);
```

`ON UPDATE CURRENT_TIMESTAMP` is copied into the output verbatim, right
inside the `DEFAULT`. PostgreSQL's `DEFAULT` has no such syntax at all —
`DEFAULT` describes only the value used on insert, never behaviour on
update.

## Observed problem

Confirmed on a real PostgreSQL 16:

```
ERROR:  syntax error at or near "ON"
LINE 4: ...hout time zone NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE ...
                                                             ^
```

`CREATE TABLE` fails immediately, at schema load.

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16. Source
dialect: MySQL (`ora2pg -m`).

## Verdict

**Gap confirmed, severity high.** PostgreSQL genuinely has no
counterpart to `ON UPDATE CURRENT_TIMESTAMP` — it is ported either to a
`BEFORE UPDATE` trigger setting `NEW.<column> = now()`, or (on recent
enough PostgreSQL versions, for the specific case) to `GENERATED
ALWAYS`. Implemented:
`ora2pg_gap_report/detectors/mysql_on_update_current_timestamp.py`.
