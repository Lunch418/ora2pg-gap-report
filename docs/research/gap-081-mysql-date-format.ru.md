# GAP-081: `DATE_FORMAT(...)` — молча возвращает кортеж вместо строки

MySQL/MariaDB feature: `DATE_FORMAT(<дата>, <формат>)` — форматирование
даты в строку по MySQL-овским спецификаторам (`%Y`, `%m`, `%d`, `%H`,
`%i`, `%s`).

## Минимальный пример

```sql
CREATE TABLE t22 (id INT PRIMARY KEY, d DATE);
CREATE PROCEDURE p22()
BEGIN
  SELECT DATE_FORMAT(d, '%Y-%m-%d %H:%i:%s') FROM t22;
END;
```

## Вывод ora2pg (v25.0, `-m -t PROCEDURE`)

```sql
CREATE OR REPLACE PROCEDURE p22 () AS $body$
BEGIN
  SELECT (d::varchar::timestamp, 'YYYY-MM-%d HH24:MI:SS') FROM t22;
END;
$body$
LANGUAGE PLPGSQL
;
```

Здесь две отдельные проблемы. Во-первых, имени функции `to_char` в
выводе нет вообще — осталась голая скобка с двумя выражениями через
запятую, то есть конструктор строки-кортежа. Во-вторых, переведены не
все спецификаторы: `%Y`/`%m`/`%H`/`%i`/`%s` стали
`YYYY`/`MM`/`HH24`/`MI`/`SS`, а `%d` остался как был.

## Наблюдаемая проблема

Ошибки нет ни на одном этапе — ни на загрузке, ни при разборе тела, ни
при вызове: кортеж это совершенно законное выражение. Проверено на
живых данных, реальный PostgreSQL 16:

```
=# INSERT INTO t22 VALUES (1, DATE '2024-03-05');
=# SELECT (d::varchar::timestamp, 'YYYY-MM-%d HH24:MI:SS') FROM t22;
              what_ora2pg_generated
-------------------------------------------------
 ("2024-03-05 00:00:00","YYYY-MM-%d HH24:MI:SS")

=# SELECT to_char(d::timestamp, 'YYYY-MM-DD HH24:MI:SS') FROM t22;
       correct
---------------------
 2024-03-05 00:00:00
```

То есть вместо отформатированной строки возвращается пара из самой даты
и недопереведённой строки формата.

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16. Source
dialect: MySQL (`ora2pg -m`).

## Вердикт

**Gap подтверждён, severity high, failure_stage semantic.** Самый
неприятный класс: миграция «прошла успешно», тесты на загрузку схемы
зелёные, а в отчётах, выгрузках и API-ответах молча оказывается не то,
что было. Чинится переписыванием на `to_char(<дата>, 'YYYY-MM-DD
HH24:MI:SS')`, причём каждый спецификатор формата стоит сверить вручную
— как показывает `%d`, полагаться на автоматический перевод нельзя.
Реализовано: `ora2pg_gap_report/detectors/mysql_date_format.py`.
