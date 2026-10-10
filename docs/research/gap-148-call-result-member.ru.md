# GAP-148: член результата вызова - `f(x).y` становится `f[x].y`

Возможность Oracle: результат вызова можно использовать сразу: `p_xml.extract('/a').getstringval()`, `get_rec(1).name`.

## Как найдено

Прогон --migrate --load-check на чужом коде (utPLSQL, OraOpenSource Logger, библиотека Alexandria PL/SQL, демо-схемы Oracle) и разбор ошибок, которые не объяснял ни один известный пробел.

## Минимальный пример

`tests/fixtures/corpus_gaps/oracle_functions.sql`, VALID в живом Oracle 23ai:

```sql
CREATE OR REPLACE FUNCTION gx_c4(p_xml XMLTYPE) RETURN VARCHAR2 IS
BEGIN
  RETURN p_xml.extract('/a/text()').getstringval();
END;
/
```

## Вывод ora2pg (v25.0)

```sql
  RETURN p_xml.extract['/a/text()'].getstringval();
```

У ora2pg есть правило (`PLSQL.pm`), которое переписывает `name(args).field` в `name[args].field`, - верное для поля элемента коллекции, `t(i).name`, - и он применяет его и к вызову.

## Наблюдаемая проблема

Функция не загружается (Oracle 23ai: `gx_c4(XMLTYPE('<a>hi</a>'))` = `hi`):

```
ERROR:  syntax error at or near "("
```

Найдено в библиотеке Alexandria PL/SQL: `l_xml.extract('...').getstringval()` в пакетах для Amazon S3, FTP и веб-сервисов.

**Воспроизводится: ДА.** Версия Ora2Pg: 25.0, PostgreSQL 16, Oracle 23ai.

## Вердикт

**Пробел подтверждён, severity high, failure_stage deployment.** Сохраните результат вызова в переменную или перепишите через функции PostgreSQL (`xpath(...)` для XML). Детектор пропускает имя, объявленное переменной или параметром, - коллекцию, для которой правило и создано.

Реализовано: `ora2pg_gap_report/detectors/call_result_member.py`.
