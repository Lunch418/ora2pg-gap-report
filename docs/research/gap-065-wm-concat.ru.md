# GAP-065: `WM_CONCAT`

Oracle feature: недокументированная агрегатная функция, склеивающая
значения группы в одну строку через запятую. Официально не
поддерживалась никогда и убрана начиная с 12c, но в унаследованном коде
встречается постоянно.

## Минимальный пример

```sql
SELECT dept_id, WM_CONCAT(name) AS names FROM employees GROUP BY dept_id;
```

## Вывод ora2pg (v25.0, `-t QUERY`)

```sql
SELECT dept_id, WM_CONCAT(name) AS names FROM employees GROUP BY dept_id;
```

Скопировано как есть. Для сравнения: документированный `LISTAGG` тот же
ora2pg переписывает в `string_agg` — проверено в том же прогоне:

```sql
SELECT dept, LISTAGG(name, ',') WITHIN GROUP (ORDER BY name) AS names ...
```
```sql
SELECT dept, string_agg(name, ',' ORDER BY name) AS names ...
```

## Наблюдаемая проблема

Подтверждено на реальном PostgreSQL 16 (против реально существующей
таблицы `employees`):

```
ERROR:  function wm_concat(text) does not exist
LINE 1: SELECT dept_id, WM_CONCAT(name) AS names FROM employees GROU...
                        ^
```

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16.

## Вердикт

**Gap подтверждён.** Реализовано:
`ora2pg_gap_report/detectors/wm_concat.py`. Ручная переработка: заменить
на `string_agg(col, ',')`, и при замене сразу дописать порядок —
`string_agg(col, ',' ORDER BY col)`. `WM_CONCAT` порядок никак не
гарантировал, поэтому «как было» воспроизвести всё равно нельзя, а молча
недетерминированный результат лучше сделать явным.
