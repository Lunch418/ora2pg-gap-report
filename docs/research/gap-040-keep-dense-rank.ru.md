# GAP-040: `KEEP (DENSE_RANK FIRST/LAST ORDER BY ...)`

Oracle feature: модификатор агрегатной функции, берущий значение не по
всей группе, а по строке, первой (или последней) в заданном порядке
внутри группы.

## Минимальный пример

```sql
CREATE OR REPLACE VIEW v_dept_top AS
SELECT department_id,
       MAX(salary) KEEP (DENSE_RANK FIRST ORDER BY hire_date) AS first_hire_salary,
       MIN(salary) KEEP (DENSE_RANK LAST ORDER BY hire_date) AS last_hire_salary
FROM employees
GROUP BY department_id;
```

## Вывод ora2pg (v25.0, `-t VIEW`)

```sql
CREATE OR REPLACE VIEW v_dept_top AS SELECT department_id,
       MAX(salary) KEEP(DENSE_RANK FIRST ORDER BY hire_date) AS first_hire_salary,
       MIN(salary) KEEP(DENSE_RANK LAST ORDER BY hire_date) AS last_hire_salary
FROM employees
GROUP BY department_id;
```

Скопировано как есть.

## Наблюдаемая проблема

Подтверждено на реальном PostgreSQL 16:

```
ERROR:  syntax error at or near "("
LINE 2:        MAX(salary) KEEP(DENSE_RANK FIRST ORDER BY hire_date)...
                               ^
```

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16.

## Вердикт

**Gap подтверждён.** Реализовано:
`ora2pg_gap_report/detectors/keep_dense_rank.py`. Ручная переработка:
оконная функция `FIRST_VALUE`/`LAST_VALUE` с той же `ORDER BY` внутри
`OVER`, либо `DISTINCT ON`, либо агрегат с `FILTER`.
