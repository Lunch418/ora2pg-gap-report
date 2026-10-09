# GAP-124: имя со схемой сохраняет схему, которую никто не создаёт

Возможность Oracle: объект, созданный под именем владельца, - `CREATE
TABLE "HR"."GX_EMP"`. `DBMS_METADATA.GET_DDL` пишет так каждое имя, поэтому
выгрузка, сделанная им, вся выглядит именно так.

## Как найден

`--migrate --load-check docker` на выгрузке в стиле `GET_DDL`: на чистом
PostgreSQL не загрузилось ничего, все ошибки - `schema "hr" does not
exist`.

## Минимальный пример

`tests/fixtures/gaps_124_125/oracle_source.sql`:

```sql
CREATE TABLE "HR"."GX_EMP" ("ID" NUMBER(6,0) NOT NULL ENABLE, CONSTRAINT "GX_EMP_PK" PRIMARY KEY ("ID"));
CREATE SEQUENCE "HR"."GX_SEQ" MINVALUE 1 START WITH 1;
CREATE OR REPLACE FORCE EDITIONABLE VIEW "HR"."GX_V" ("ID") AS SELECT id FROM gx_emp;
CREATE OR REPLACE EDITIONABLE TRIGGER "HR"."GX_TRG" BEFORE INSERT ON "HR"."GX_EMP" FOR EACH ROW
BEGIN
  NULL;
END;
/
```

плюс пакет `"HR"."GX_PKG"`. В живом Oracle 23ai (под `HR`) все объекты
VALID, вставка запускает триггер, представление видит строку.

## Вывод ora2pg (v25.0)

```sql
CREATE TABLE hr.gx_emp (...);
ALTER TABLE hr.gx_emp ADD PRIMARY KEY (id);
CREATE SEQUENCE hr.gx_seq INCREMENT 1 MINVALUE 1 NO MAXVALUE START 1;
CREATE OR REPLACE VIEW hr.gx_v (id) AS SELECT id FROM gx_emp;
CREATE TRIGGER gx_trg
	BEFORE INSERT ON gx_emp FOR EACH ROW
	EXECUTE PROCEDURE trigger_fct_gx_trg();
```

Схема остаётся у таблиц, последовательностей, представлений и
подпрограмм и пропадает из `ON` триггера и из тела представления. `CREATE
SCHEMA hr` нет нигде. (Пакета это не касается: ora2pg превращает его в
схему с именем пакета и её создаёт.)

## Наблюдаемая проблема

На чистом PostgreSQL 16:

```
ERROR:  3F000: schema "hr" does not exist
```

для таблицы, последовательности и представления. Если сначала выполнить
`CREATE SCHEMA hr`, триггер и представление всё равно падают, потому что
потеряли схему:

```
ERROR:  42P01: relation "gx_emp" does not exist
```

Со схемой, которая создана **и** есть в search_path (`SET search_path =
hr, public`), всё загружается и работает как в Oracle
(`tests/test_gaps_124_125_load.py`).

**Воспроизводится: ДА.** Версия Ora2Pg: 25.0, PostgreSQL 16, Oracle 23ai.

## Вердикт

**Gap подтверждён, severity high, failure_stage deployment.** Либо
создайте схему и добавьте её в search_path насовсем (`ALTER ROLE app SET
search_path = hr, public` или то же для базы), либо уберите `"HR".` из
исходника до ora2pg, чтобы всё легло в одну схему единообразно. Это
решение о том, где должны жить объекты, поэтому `--fix` его не принимает.

Реализовано: `ora2pg_gap_report/detectors/schema_qualified_name.py` -
сообщается один раз на схему в файле; схема, которую файл создаёт сам, не
сообщается, поэтому собственный вывод ora2pg для пакетов остаётся чистым.
