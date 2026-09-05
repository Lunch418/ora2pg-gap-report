# GAP-052: системные триггеры (`ON DATABASE` / `ON SCHEMA`)

Oracle feature: триггер не на таблицу, а на событие базы или схемы —
`LOGON`, `LOGOFF`, `SERVERERROR`, `DDL`, `STARTUP`, `SHUTDOWN` и т. п.

## Минимальный пример

```sql
CREATE OR REPLACE TRIGGER trg_logon
AFTER LOGON ON DATABASE
BEGIN
  INSERT INTO login_audit (who, when_) VALUES (USER, SYSDATE);
END;
/
```

## Вывод ora2pg (v25.0, `-t TRIGGER`)

```sql
DROP TRIGGER IF EXISTS trg_logon ON database CASCADE;
CREATE OR REPLACE FUNCTION trigger_fct_trg_logon() RETURNS trigger AS $BODY$
BEGIN
  INSERT INTO login_audit(who, when_) VALUES (USER, statement_timestamp());
RETURN NEW;
END
$BODY$
 LANGUAGE 'plpgsql';
CREATE TRIGGER trg_logon
	AFTER LOGON ON database FOR EACH ROW
	EXECUTE PROCEDURE trigger_fct_trg_logon();
```

Системный триггер перенесён как обычный табличный: слово `database`
подставлено на место имени таблицы, событие `LOGON` осталось как есть.

## Наблюдаемая проблема

Подтверждено на реальном PostgreSQL 16:

```
ERROR:  syntax error at or near "LOGON"
LINE 2:  AFTER LOGON ON database FOR EACH ROW
               ^
```

Проверен и вариант с областью `SCHEMA` и другим событием:

```
ERROR:  syntax error at or near "DDL"
LINE 2:  BEFORE DDL ON schema FOR EACH ROW
                ^
```

и `SERVERERROR`:

```
ERROR:  syntax error at or near "SERVERERROR"
LINE 2:  AFTER SERVERERROR ON database FOR EACH ROW
               ^
```

Поэтому детектор опирается на область (`ON DATABASE` / `ON SCHEMA`), а
не на перечень событий: список событий может устареть, область — нет.

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16.

## Вердикт

**Gap подтверждён.** Реализовано:
`ora2pg_gap_report/detectors/system_trigger.py`. Ручная переработка:
прямого аналога нет ни для одного события. DDL-события покрываются
событийными триггерами PostgreSQL (`CREATE EVENT TRIGGER ... ON
ddl_command_end`), а `LOGON`/`LOGOFF`/`SERVERERROR` — вообще не
триггерами, а журналированием на стороне сервера или логикой в
приложении.
