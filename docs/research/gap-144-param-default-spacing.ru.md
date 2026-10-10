# GAP-144: значение параметра по умолчанию как `тип:= значение`

Возможность Oracle: вокруг `:=` не нужны пробелы: `a_delimiter varchar2:= chr(10)`, `a_base integer :=0`.

## Как найдено

Прогон --migrate --load-check на чужом коде (utPLSQL, OraOpenSource Logger, библиотека Alexandria PL/SQL, демо-схемы Oracle) и разбор ошибок, которые не объяснял ни один известный пробел.

## Минимальный пример

`tests/fixtures/corpus_gaps/oracle_functions.sql`, VALID в живом Oracle 23ai:

```sql
CREATE OR REPLACE FUNCTION gx_c1(a_item VARCHAR2, a_c VARCHAR2:= '.', a_base INTEGER :=0) RETURN VARCHAR2 IS
BEGIN
  RETURN trim(leading a_c from a_item) || '|' || trim(trailing a_c from a_item) || '|' || a_base;
END;
/
```

## Вывод ora2pg (v25.0)

```sql
CREATE OR REPLACE FUNCTION gx_c1 (a_item text, a_c VARCHAR2DEFAULT '.', a_base integer DEFAULT0) RETURNS varchar AS $body$
```

`:=` становится DEFAULT, приклеенным к соседям, а `VARCHAR2` даже не конвертируется. В объявлении (`v NUMBER:=0;`) `:=` копируется и загружается.

## Наблюдаемая проблема

Функция не загружается:

```
ERROR:  syntax error at or near "'.'"
```

Найдено в utPLSQL: семь функций `ut_utils` (`a_delimiter varchar2:= chr(10)`) и `get_fixed_size_hash` (`a_base integer :=0`).

**Воспроизводится: ДА.** Версия Ora2Pg: 25.0, PostgreSQL 16, Oracle 23ai.

## Вердикт

**Пробел подтверждён, severity high, failure_stage deployment.** `--prepare` расставляет пробелы в списках параметров (`prepare_oracle_param_default_spacing`); ora2pg тогда пишет `a_c text DEFAULT '.', a_base integer DEFAULT 0`, проверено: функция загружается и возвращает то же, что Oracle.

Реализовано: `ora2pg_gap_report/detectors/param_default_spacing.py`.
