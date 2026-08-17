# GAP-033: Виртуальный столбец теряет защиту от явного присваивания (`ORA-54016`)

Oracle feature: `<column> [<type>] [GENERATED ALWAYS] AS (<expr>)
[VIRTUAL]` — вычисляемый столбец. И `GENERATED ALWAYS`, и завершающее
`VIRTUAL` у Oracle необязательны — самая короткая форма выглядит как
`total_value AS (item_id * quantity + net_value)`. Помимо вычисления
значения, Oracle дополнительно гарантирует на уровне сервера, что в
такой столбец нельзя явно ничего записать: любая попытка передать
значение в `INSERT`/`UPDATE` для виртуального столбца падает с
`ORA-54016` ещё до выполнения — это защита от программных ошибок
(случайного или намеренного, "для унификации кода", присваивания
вычисляемому столбцу).

## Минимальный пример

```sql
CREATE TABLE employees (
    emp_id NUMBER,
    salary NUMBER,
    bonus  NUMBER,
    total_comp NUMBER GENERATED ALWAYS AS (salary + bonus) VIRTUAL
);
```

## Вывод ora2pg (v25.0, `-t TABLE`)

```sql
CREATE TABLE employees (
	emp_id bigint,
	salary bigint,
	bonus bigint,
	total_comp bigint
) ;
DROP TRIGGER IF EXISTS virt_col_employees_trigger ON employees CASCADE;

CREATE OR REPLACE FUNCTION fct_virt_col_employees_trigger() RETURNS trigger AS $BODY$
BEGIN
	NEW.total_comp = (NEW.salary + NEW.bonus);
RETURN NEW;
end
$BODY$
 LANGUAGE 'plpgsql' SECURITY DEFINER;

CREATE TRIGGER virt_col_employees_trigger
        BEFORE INSERT OR UPDATE ON employees FOR EACH ROW
        EXECUTE PROCEDURE fct_virt_col_employees_trigger();
```

Сам расчёт ora2pg переносит корректно — не через нативный `GENERATED
ALWAYS AS (...) STORED` PostgreSQL 12+, а через `BEFORE INSERT OR
UPDATE`-триггер, который пересчитывает значение сам. На первый взгляд
эквивалентно. Проверено также для обеих сокращённых форм — `... NUMBER
GENERATED ALWAYS AS (a+b)` (без `VIRTUAL`) и `total_value AS (item_id *
quantity + net_value)` (совсем без `GENERATED ALWAYS`, притом ora2pg
сам подставляет тип `text` с предупреждением "Virtual column ... has no
data type defined") — обе конвертируются в тот же паттерн триггера, с
той же потерей защиты ниже.

## Наблюдаемая проблема

Разница — не в вычисленном значении, а в защите от явного присваивания.
Подтверждено на реальном PostgreSQL 16:

```sql
INSERT INTO employees (emp_id, salary, bonus, total_comp)
VALUES (1, 100, 50, 999999);
-- INSERT 0 1  -- прошло успешно, без единой ошибки

SELECT * FROM employees;
--  emp_id | salary | bonus | total_comp
-- --------+--------+-------+------------
--       1 |    100 |    50 |        150
```

В Oracle тот же `INSERT` с явным `total_comp => 999999` гарантированно
завершился бы `ORA-54016` ещё до попытки что-либо записать. После
миграции — тихо принимается, триггер молча подменяет переданное
значение на вычисленное, без предупреждения и без ошибки. Итоговое
значение в столбце корректно (`150`), поэтому это не потеря данных — но
теряется ранняя диагностика: код, который по ошибке (или для
унификации логики со столбцами, не являющимися виртуальными) передаёт
значение в вычисляемый столбец, в Oracle был бы пойман сразу же на
тестировании, а после миграции проходит незамеченным.

**Reproducible: YES.** Ora2Pg version: 25.0.

## Вердикт

**Gap подтверждён.** Реализовано:
`ora2pg_gap_report/detectors/virtual_column.py`.
