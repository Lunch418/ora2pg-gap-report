# GAP-055: курсорное выражение `CURSOR(SELECT ...)`

Oracle feature: вложенный запрос, возвращаемый как отдельный
столбец-курсор, который клиент затем открывает и читает построчно.

## Минимальный пример

```sql
SELECT d.dname,
       CURSOR(SELECT e.name FROM employees e WHERE e.dept_id = d.id) AS emps
  FROM departments d;
```

## Вывод ora2pg (v25.0, `-t QUERY`)

```sql
SELECT d.dname,
       CURSOR(SELECT e.name FROM employees e WHERE e.dept_id = d.id) AS emps
  FROM departments d;
```

Скопировано как есть.

## Наблюдаемая проблема

Подтверждено на реальном PostgreSQL 16:

```
ERROR:  syntax error at or near "SELECT"
LINE 2:        CURSOR(SELECT e.name FROM employees e WHERE e.dept_id...
                      ^
```

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16.

## Вердикт

**Gap подтверждён.** Реализовано:
`ora2pg_gap_report/detectors/cursor_expression.py`. Детектор помечает
только `CURSOR(` со следующим сразу `SELECT` — обычное объявление
курсора (`CURSOR c IS SELECT ...`) ora2pg конвертирует корректно, и оно
намеренно не помечается.

Ручная переработка: чаще всего имелось в виду соединение с агрегацией
дочерних строк в массив или json (`array_agg`, `json_agg`). Если клиент
действительно читает вложенный набор построчно — отдельная функция,
возвращающая `refcursor`.
