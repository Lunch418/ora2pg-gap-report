# GAP-048: `IGNORE NULLS` / `RESPECT NULLS` в аналитических функциях

Oracle feature: оговорка обработки NULL у аналитических функций
(`LAG`, `LEAD`, `FIRST_VALUE`, `LAST_VALUE`, `NTH_VALUE`).

## Минимальный пример

```sql
SELECT emp_id,
       LAST_VALUE(salary IGNORE NULLS) OVER (PARTITION BY dept ORDER BY hired) AS last_sal,
       LAG(bonus, 1) IGNORE NULLS OVER (ORDER BY hired) AS prev_bonus
  FROM employees;
```

## Вывод ora2pg (v25.0, `-t QUERY`)

```sql
SELECT emp_id,
       LAST_VALUE(salary IGNORE NULLS) OVER (PARTITION BY dept ORDER BY hired) AS last_sal,
       LAG(bonus, 1) IGNORE NULLS OVER (ORDER BY hired) AS prev_bonus
  FROM employees;
```

Скопировано как есть.

## Наблюдаемая проблема

Подтверждено на реальном PostgreSQL 16 (запрос выполнялся против
реально существующей таблицы `employees`, чтобы ошибка «relation does
not exist» не могла замаскировать настоящую):

```
ERROR:  syntax error at or near "IGNORE"
LINE 2:        LAST_VALUE(salary IGNORE NULLS) OVER (PARTITION BY de...
                                 ^
```

Отдельно проверен вариант `RESPECT NULLS` (в Oracle это поведение по
умолчанию, но его можно выписать явно) — ora2pg точно так же копирует
его в вывод, и PostgreSQL так же падает:

```
ERROR:  syntax error at or near "RESPECT"
LINE 1: SELECT FIRST_VALUE(salary RESPECT NULLS) OVER (ORDER BY hire...
                                  ^
```

Поэтому детектор помечает обе формы, а не только «интересную».

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16.

## Вердикт

**Gap подтверждён.** Реализовано:
`ora2pg_gap_report/detectors/ignore_nulls.py`. Ручная переработка:
прямого синтаксиса в PostgreSQL 16 нет, `IGNORE NULLS` эмулируется —
обычно через группирующий ключ `count(col) FILTER (WHERE col IS NOT
NULL)` плюс `first_value` внутри группы, либо через боковой подзапрос.
