# GAP-147: имя с `#`

Возможность Oracle: в именах без кавычек допустим `#` (и `$`): `n#count`, `emp#`.

## Как найдено

Прогон --migrate --load-check на чужом коде (utPLSQL, OraOpenSource Logger, библиотека Alexandria PL/SQL, демо-схемы Oracle) и разбор ошибок, которые не объяснял ни один известный пробел.

## Минимальный пример

`tests/fixtures/corpus_gaps/oracle_functions.sql`, VALID в живом Oracle 23ai:

```sql
CREATE OR REPLACE FUNCTION gx_c3(p NUMBER) RETURN NUMBER IS
  n#count NUMBER(5) := p;
BEGIN
  RETURN n#count * 2;
END;
/
```

## Вывод ora2pg (v25.0)

```sql
  n#count integer := p;
  RETURN n#count * 2;
```

Имя копируется как есть.

## Наблюдаемая проблема

PostgreSQL не принимает `#` в имени (а `$` принимает):

```
ERROR:  syntax error at or near "#"
```

Найдено в демо-схемах Oracle: `COUNT(*) as #_OF_PRODUCTS` во view.

**Воспроизводится: ДА.** Версия Ora2Pg: 25.0, PostgreSQL 16, Oracle 23ai.

## Вердикт

**Пробел подтверждён, severity high, failure_stage deployment.** Переименуйте или возьмите имя в кавычки в выводе (`"n#count"`). Сообщается один раз на имя и объект.

Реализовано: `ora2pg_gap_report/detectors/hash_identifier.py`.
