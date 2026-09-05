# GAP-005: `CONNECT BY` — баг подстановки `LEVEL` в сгенерированном `WITH RECURSIVE`

Oracle feature: `START WITH ... CONNECT BY PRIOR ...` (иерархические
запросы) с `LEVEL`/`SYS_CONNECT_BY_PATH`.

## Что здесь на самом деле не так

Подтверждено запуском на синтетическом, честно помеченном как
синтетический fixture (`hierarchy_demo_pkg`, обёртка над каноническим
Oracle EMP/DEPT-запросом внутри реального пакета с `REF CURSOR`). Ora2pg
**реально конвертирует** `START WITH ... CONNECT BY PRIOR ...
SYS_CONNECT_BY_PATH` в рабочий `WITH RECURSIVE`-CTE:

```sql
WITH RECURSIVE cte AS (
SELECT employee_id,manager_id,1 AS depth,last_name AS org_path
      FROM   employees WHERE employee_id = p_top_employee_id
  UNION ALL
SELECT employee_id,manager_id,(c.level+1) AS depth,c.org_path || '/' || last_name AS org_path
      FROM   employees JOIN cte c ON (c.employee_id = manager_id)
) SELECT * FROM cte;
```

`LEVEL` превращён в счётчик глубины, `SYS_CONNECT_BY_PATH` — в конкатенацию
строк, `START WITH`/`CONNECT BY PRIOR` — в анкер и рекурсивный JOIN.
Механически это рабочий SQL, и стоимость учтена корректно (единственный из
пяти изначально проверенных классов, где `estimate_cost` не занижает).

Однако конвертация шаблонная и хрупкая: `(c.level+1)` — в CTE нет колонки
`level`, это баг подстановки regex-based конвертера, который взял
литеральное имя `LEVEL` и не подставил алиас `depth` из первой ветки
`UNION`. Сгенерированный SQL в буквальном виде не выполнится в PostgreSQL
без ручной правки (`c.level` → `c.depth`). Также конвертер не умеет более
сложные варианты: `CONNECT BY NOCYCLE`, множественные условия, `ORDER
SIBLINGS BY`, `CONNECT_BY_ROOT`, `CONNECT_BY_ISLEAF` — не покрыты ни одним
регулярным выражением в `PLSQL.pm`.

## Наблюдаемая проблема

`CONNECT BY` — единственный класс, где базовая оценка стоимости не
занижена. Но сама конвертация не безошибочна даже для базового случая —
здесь ценность не "мы видим то, что ora2pg не видит вообще", а "мы
предупреждаем, что даже при ненулевой оценённой стоимости сгенерированный
SQL нужно обязательно вручную вычитывать".

**Reproducible: YES.** Ora2Pg version: 25.0 (commit `cc2c434f`).

## Вердикт

**Gap подтверждён**, но нетипичный по механизму: единственный из детекторов
проекта, который анализирует не исходный Oracle-код, а сгенерированный
ora2pg вывод — соответственно, единственный, которому для проверки нужен
установленный `ora2pg` (флаг `--check-connect-by`).

Реализовано: `ora2pg_gap_report/detectors/connect_by.py`.
