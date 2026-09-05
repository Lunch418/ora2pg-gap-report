# GAP-046: `CREATE BITMAP INDEX` → `USING gin` без класса операторов

Oracle feature: битовый индекс, рассчитанный на столбцы малой
кардинальности и на комбинирование нескольких таких индексов побитовыми
операциями.

## Минимальный пример

```sql
CREATE TABLE emp_idx (
    employee_id NUMBER PRIMARY KEY,
    gender      VARCHAR2(1),
    last_name   VARCHAR2(50)
);
CREATE BITMAP INDEX idx_emp_gender ON emp_idx (gender);
CREATE INDEX idx_emp_rev ON emp_idx (last_name) REVERSE;
```

## Вывод ora2pg (v25.0, `-t TABLE`)

```sql
CREATE TABLE emp_idx (
	employee_id bigint,
	gender varchar(1),
	last_name varchar(50)
) ;
CREATE INDEX idx_emp_gender ON emp_idx USING gin(gender);
CREATE INDEX idx_emp_rev ON emp_idx (last_name);
ALTER TABLE emp_idx ADD PRIMARY KEY (employee_id);
```

`BITMAP` заменён на `USING gin`.

## Наблюдаемая проблема

Подтверждено на реальном PostgreSQL 16 — индекс не создаётся вообще:

```
ERROR:  data type character varying has no default operator class for access method "gin"
HINT:  You must specify an operator class for the index or define a default operator class for the data type.
```

У `gin` по умолчанию нет класса операторов ни для `varchar`, ни для
чисел — он рассчитан на составные типы (массивы, `jsonb`, `tsvector`).
То есть замена не просто меняет характеристики индекса, она не проходит
загрузку.

Отдельно замечено (не выделено в отдельный gap): `REVERSE`-индекс молча
теряет свою реверсивность, превращаясь в обычный.

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16.

## Вердикт

**Gap подтверждён.** Реализовано:
`ora2pg_gap_report/detectors/bitmap_index.py`. У PostgreSQL нет битовых
индексов как типа. Практическая замена — обычный btree (планировщик сам
умеет комбинировать несколько btree через bitmap scan во время
выполнения), либо `gin` с явным классом операторов из расширения
`btree_gin`.
