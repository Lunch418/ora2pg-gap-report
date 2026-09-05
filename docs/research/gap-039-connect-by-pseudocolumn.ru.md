# GAP-039: `CONNECT_BY_ROOT` / `CONNECT_BY_ISLEAF` / `CONNECT_BY_ISCYCLE`

Oracle feature: иерархические оператор и псевдостолбцы, используемые
вместе с `CONNECT BY`: значение выражения в корне текущей ветки, признак
листа, признак обнаруженного цикла.

Отличие от GAP-005 (`connect_by`): тот про баг подстановки `LEVEL` в уже
сгенерированном `WITH RECURSIVE`. Здесь — три отдельные конструкции,
которые ora2pg вообще не переносит.

## Минимальный пример

```sql
CREATE OR REPLACE VIEW v_emp_tree AS
SELECT employee_id,
       SYS_CONNECT_BY_PATH(last_name, '/') AS path,
       CONNECT_BY_ROOT last_name AS root_name,
       CONNECT_BY_ISLEAF AS is_leaf
FROM employees
START WITH manager_id IS NULL
CONNECT BY PRIOR employee_id = manager_id;
```

## Вывод ora2pg (v25.0, `-t VIEW`)

```sql
CREATE OR REPLACE VIEW v_emp_tree AS WITH RECURSIVE cte AS (
SELECT employee_id,last_name AS path,CONNECT_BY_ROOT last_name AS root_name,CONNECT_BY_ISLEAF AS is_leaf
FROM employees WHERE coalesce(manager_id::text, '') = ''
  UNION ALL
SELECT employee_id,c.path || '/' || last_name AS path,CONNECT_BY_ROOT last_name AS root_name,CONNECT_BY_ISLEAF AS is_leaf
FROM employees JOIN cte c ON (c.employee_id = manager_id)

) SELECT * FROM cte;
```

Сам `CONNECT BY` развёрнут в `WITH RECURSIVE` корректно, и
`SYS_CONNECT_BY_PATH` тоже конвертирован правильно — в конкатенацию
`c.path || '/' || last_name`. А вот `CONNECT_BY_ROOT` и
`CONNECT_BY_ISLEAF` перенесены в вывод дословно.

## Наблюдаемая проблема

Подтверждено на реальном PostgreSQL 16:

```
ERROR:  syntax error at or near "AS"
LINE 2: ...ee_id,last_name AS path,CONNECT_BY_ROOT last_name AS root_na...
```

Отдельно проверено (с реально существующей таблицей, чтобы отделить
ошибку конструкции от ошибки «нет такой таблицы»):

- `SYS_CONNECT_BY_PATH` **сам по себе конвертируется корректно** —
  оставшаяся ошибка на нём другого рода и не синтаксическая. Детектор
  его намеренно НЕ помечает. Подробности — в разделе «Побочная находка»
  ниже.
- `CONNECT_BY_ISCYCLE` ведёт себя так же, как `ISLEAF`: копируется
  дословно, PostgreSQL отвечает `column "connect_by_iscycle" does not
  exist`.

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16.

## Вердикт

**Gap подтверждён.** Реализовано:
`ora2pg_gap_report/detectors/connect_by_pseudocolumn.py`. Ручная
переработка: корень ветки протаскивается дополнительным столбцом
рекурсивного CTE, признак листа — отдельным `NOT EXISTS`-подзапросом,
признак цикла — секцией `CYCLE` рекурсивного CTE (PostgreSQL 14+).

## Побочная находка: неквалифицированные столбцы в сгенерированном CTE

При проверке границы (что именно ломается, а что нет) обнаружилось
отдельное поведение, к этому gap'у прямого отношения не имеющее, но
воспроизводимое. В рекурсивной ветке сгенерированного `WITH RECURSIVE`
ora2pg оставляет столбцы неквалифицированными:

```sql
SELECT employee_id, c.path || '/' || last_name AS path
FROM employees JOIN cte c ON (c.employee_id = manager_id)
```

`employee_id` есть и в `employees`, и в `cte c`, поэтому PostgreSQL 16
на реально существующей таблице отвечает:

```
ERROR:  column reference "employee_id" is ambiguous
```

Это баг в **сгенерированном** коде — то есть та же категория, что и
GAP-005 (`connect_by`), который линтит вывод ora2pg и требует
`--check-connect-by`. Отдельным GAP'ом здесь намеренно не оформлено:
детектор для него должен работать по сгенерированному коду, а не по
Oracle-исходнику, и его место — расширение существующей проверки
`connect_by`, а не новая запись в реестре. Зафиксировано здесь, чтобы
находка не потерялась.
