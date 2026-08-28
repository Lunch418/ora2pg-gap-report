# GAP-062: альтернативные кавычки `q'[...]'`

Oracle feature: способ записать строку с апострофами внутри, не удваивая
их.

## Минимальный пример

```sql
CREATE OR REPLACE PROCEDURE say IS
  msg VARCHAR2(100) := q'[it's a test]';
BEGIN
  DBMS_OUTPUT.PUT_LINE(msg);
END;
/
```

## Вывод ora2pg (v25.0, `-t PROCEDURE`)

```sql
CREATE OR REPLACE PROCEDURE say () AS $body$
DECLARE
  msg varchar(100) := q'[it's a test]';
BEGIN
  RAISE NOTICE '%', msg;
END;
$body$
LANGUAGE PLPGSQL
;
```

Литерал скопирован как есть.

## Наблюдаемая проблема

Загрузка проходит чисто (`check_function_bodies = false` в выводе
ora2pg):

```
CREATE PROCEDURE
```

Падение — при первом вызове. Подтверждено на реальном PostgreSQL 16:

```
ERROR:  mismatched parentheses at or near "]"
LINE 4:   msg varchar(100) := q'[it's a test]';
                                            ^
```

PostgreSQL читает `q` как отдельный идентификатор, дальше начинается
обычный строковый литерал `'[it'`, и разбор уезжает.

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16.

## Вердикт

**Gap подтверждён.** Реализовано:
`ora2pg_gap_report/detectors/alt_quote_literal.py`. Это один из двух
детекторов, работающих поверх `mask_comments_only()`: `plsql_lex`
понимает q-кавычки и штатно вымарывает их вместе с остальными
литералами, то есть обычная маскировка стёрла бы ровно тот текст,
который здесь ищется. Сканировать сырой исходник тоже нельзя — тогда
детектор ловил бы закомментированный код.

Ручная переработка: заменить на обычный литерал с удвоенными
апострофами или, что ближе по духу, на долларовые кавычки PostgreSQL:
`$q$it's a test$q$` — внутри них экранировать не нужно ничего.
