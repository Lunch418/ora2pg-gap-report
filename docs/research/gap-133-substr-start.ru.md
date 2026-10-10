# GAP-133: `SUBSTR` с позиции 0 или с отрицательной

Возможность Oracle: в `SUBSTR(s, pos[, len])` позиция 0 читается как 1, а
отрицательная отсчитывается с конца строки.

## Как найдено

Среди функций, которые сравнивались на Oracle 23ai и PostgreSQL 16 для
GAP-129..132.

## Минимальный пример

`tests/fixtures/silent_numbers/oracle_functions.sql`, VALID в живом
Oracle 23ai:

```sql
CREATE OR REPLACE FUNCTION gx_s1(p VARCHAR2) RETURN VARCHAR2 IS
BEGIN
  RETURN SUBSTR(p, 0, 3) || '|' || SUBSTR(p, -3) || '|' || SUBSTR(p, -3, 2)
      || '|' || SUBSTR(p, 0) || '|' || SUBSTR(p, 2, 2);
END;
/
```

## Вывод ora2pg (v25.0)

Вызов копируется как есть. В PostgreSQL есть `substr`, так что всё
загружается.

## Наблюдаемая проблема

`substr` в PostgreSQL считает позиции до первого символа настоящими:

| | Oracle 23ai | PostgreSQL 16 |
|---|---|---|
| `SUBSTR('abcdef', 0, 3)` | `abc` | `ab` |
| `SUBSTR('abcdef', -3)` | `def` | `abcdef` |
| `SUBSTR('abcdef', -3, 2)` | `de` | `` (пусто) |
| `SUBSTR('abcdef', 0)` | `abcdef` | `abcdef` |
| `SUBSTR('abcdef', 2, 2)` | `bc` | `bc` |

Найдено в `docs/research/samples/file_util_pkg.pkb`: `substr(p_dir, -1) =
g_dir_sep_win` - в Oracle последний символ, в PostgreSQL весь путь, и
проверка никогда не срабатывает.

**Воспроизводится: ДА.** Версия Ora2Pg: 25.0, PostgreSQL 16, Oracle 23ai.

## Вердикт

**Пробел подтверждён, severity high, failure_stage semantic.** Пишите 1
вместо 0; с конца - `right(s, n)` или `substr(s, length(s) - n + 1, len)`.

Детектор помечает литерал 0 с длиной и любой отрицательный литерал.
`SUBSTR(s, 0)` одинаков в обеих базах; позицию в переменной по тексту не
прочитать.

Реализовано: `ora2pg_gap_report/detectors/substr_start.py`.
