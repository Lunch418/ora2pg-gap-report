# GAP-069: `DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP`

MySQL/MariaDB feature: `ON UPDATE CURRENT_TIMESTAMP` — часть `DEFAULT`
у `TIMESTAMP`/`DATETIME`-столбца, авто-обновляющая значение на каждый
`UPDATE` строки (классический шаблон `updated_at`).

## Минимальный пример

```sql
CREATE TABLE sessions (
  id INT PRIMARY KEY AUTO_INCREMENT,
  token VARCHAR(64) NOT NULL,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);
```

## Вывод ora2pg (v25.0, `-m -t TABLE`)

```sql
CREATE TABLE sessions (
	id serial,
	token varchar(64) NOT NULL,
	updated_at timestamp without time zone NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ;
ALTER TABLE sessions ADD PRIMARY KEY (id);
```

`ON UPDATE CURRENT_TIMESTAMP` копируется в вывод дословно, прямо внутри
`DEFAULT`. У `DEFAULT` в PostgreSQL нет такого синтаксиса вообще —
`DEFAULT` описывает только значение при вставке, а не поведение при
обновлении.

## Наблюдаемая проблема

Подтверждено на реальном PostgreSQL 16:

```
ERROR:  syntax error at or near "ON"
LINE 4: ...hout time zone NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE ...
                                                             ^
```

`CREATE TABLE` падает немедленно, при загрузке схемы.

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16. Source
dialect: MySQL (`ora2pg -m`).

## Вердикт

**Gap подтверждён, severity high.** Аналога `ON UPDATE
CURRENT_TIMESTAMP` в PostgreSQL действительно нет — переносится либо на
триггер `BEFORE UPDATE`, выставляющий `NEW.<столбец> = now()`, либо (в
достаточно новых версиях PostgreSQL, для конкретного случая) на
`GENERATED ALWAYS`. Реализовано:
`ora2pg_gap_report/detectors/mysql_on_update_current_timestamp.py`.
