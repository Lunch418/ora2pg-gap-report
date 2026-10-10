# GAP-137: `INSTR` с позицией или номером вхождения

Возможность Oracle: `INSTR(s, sub, position[, occurrence])` - отрицательная позиция ищет с конца.

## Как найдено

При проверке GAP-130..133: те же функции запускались в Oracle 23ai и, после ora2pg 25.0, в PostgreSQL 16.

## Минимальный пример

`tests/fixtures/loud_types/oracle_functions.sql`, VALID в живом Oracle 23ai:

```sql
CREATE OR REPLACE FUNCTION gx_l5(p VARCHAR2) RETURN NUMBER IS
BEGIN
  RETURN INSTR(p, '.', -1) * 10 + INSTR(p, '.', 1, 2);
END;
/
```

## Вывод ora2pg (v25.0, `-t FUNCTION`)

```sql
  RETURN INSTR(p, '.', -1) * 10 + INSTR(p, '.', 1, 2);
```

`INSTR(s, sub)` с двумя аргументами становится `position(sub in s)`; длинные формы копируются.

## Наблюдаемая проблема

Функция загружается, и первый вызов падает (Oracle 23ai для `gx_l5('a.b.c')` возвращает 44):

```
ERROR:  function instr(text, unknown, integer) does not exist
```

Найдено в OraOpenSource Logger (`instr(l_callstack, chr(10), 1, 5)`) и `file_util_pkg` (`instr(p_file_name, l_dir_sep, -1)`).

**Воспроизводится: ДА.** Версия Ora2Pg: 25.0, PostgreSQL 16, Oracle 23ai.

## Вердикт

**Пробел подтверждён, severity high, failure_stage runtime.** Расширение orafce даёт `instr` с этими формами; без него напишите свою функцию. Детектор помечает `INSTR` с тремя или четырьмя аргументами.

Реализовано: `ora2pg_gap_report/detectors/instr_occurrence.py`.
