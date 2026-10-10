# GAP-146: параметр без значения по умолчанию после параметра со значением

Возможность Oracle: значение по умолчанию может быть у любого параметра, где бы он ни стоял; пропуская аргументы, их передают по имени.

## Как найдено

Прогон --migrate --load-check на чужом коде (utPLSQL, OraOpenSource Logger, библиотека Alexandria PL/SQL, демо-схемы Oracle) и разбор ошибок, которые не объяснял ни один известный пробел.

## Минимальный пример

`tests/fixtures/corpus_gaps/oracle_functions.sql`, VALID в живом Oracle 23ai:

```sql
CREATE OR REPLACE PROCEDURE gx_c2(p_text VARCHAR2 DEFAULT NULL, p_id OUT NUMBER) IS
BEGIN
  p_id := NVL(LENGTH(p_text), 0);
END;
/
```

## Вывод ora2pg (v25.0)

```sql
CREATE OR REPLACE PROCEDURE gx_c2 (p_text text DEFAULT NULL, p_id OUT bigint) AS $body$
```

Порядок сохраняется.

## Наблюдаемая проблема

PostgreSQL 16 его отвергает - проверено для каждой формы: входной параметр (IN или IN OUT) без значения по умолчанию после параметра со значением не проходит ни в функции, ни в процедуре; OUT-параметр не проходит в процедуре и допустим в функции.

```
ERROR:  procedure OUT parameters cannot appear after one with a default value
ERROR:  input parameters after one with a default value must also have defaults
```

Найдено в OraOpenSource Logger: `ins_logger_logs` и `ins_logger_logs_atx`.

**Воспроизводится: ДА.** Версия Ora2Pg: 25.0, PostgreSQL 16, Oracle 23ai.

## Вердикт

**Пробел подтверждён, severity high, failure_stage deployment.** Механического исправления нет: перенос параметров со значениями по умолчанию в конец меняет каждый вызов с позиционными аргументами. Дайте значения по умолчанию и следующим параметрам или переставьте их и проверьте вызовы.

Реализовано: `ora2pg_gap_report/detectors/param_after_default.py`.
