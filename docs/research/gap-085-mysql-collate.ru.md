# GAP-085: `COLLATE`/`CHARACTER SET` на столбце выбрасывается

MySQL/MariaDB feature: правило сравнения и сортировки строк, заданное
на конкретном столбце.

## Минимальный пример

```sql
CREATE TABLE col1 (
  id INT PRIMARY KEY,
  name VARCHAR(50) COLLATE utf8mb4_general_ci NOT NULL
);
```

`utf8mb4_general_ci` — регистронезависимое правило, одно из самых
распространённых в реальных схемах MySQL.

## Вывод ora2pg (v25.0, `-m -t TABLE`)

```sql
CREATE TABLE col1 (
	id integer,
	name varchar(50) NOT NULL
) ;
ALTER TABLE col1 ADD PRIMARY KEY (id);
```

Строк `COLLATE` в выводе — ноль. То же самое для `CHARACTER SET
utf8mb4 COLLATE utf8mb4_bin`.

## Наблюдаемая проблема

Ошибки нет ни на загрузке, ни потом, но сравнение строк молча меняет
смысл: правила `*_ci` в MySQL регистронезависимы, а сравнение в
PostgreSQL по умолчанию — регистрозависимо. Проверено на живых данных,
реальный PostgreSQL 16:

```
=# INSERT INTO col1 VALUES (1,'Alice');
=# SELECT count(*) FROM col1 WHERE name = 'alice';
 rows_matching_lowercase_alice
-------------------------------
                             0
```

В MySQL с исходным правилом сравнения тот же запрос нашёл бы одну
строку. То есть ломается не схема, а выдача запросов: логины, поиск по
имени, проверки уникальности начинают вести себя иначе.

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16. Source
dialect: MySQL (`ora2pg -m`).

## Вердикт

**Gap подтверждён, severity high, failure_stage semantic.** Severity
здесь high, а не medium, именно потому, что меняется результат
запросов, а не план их выполнения (ср. GAP-018/`invisible_index`, где
теряется только подсказка оптимизатору и severity medium).
Восстанавливается явным `COLLATE` на столбце (в PostgreSQL доступны
ICU-правила с нужной чувствительностью), типом `citext` либо
приведением обеих сторон сравнения к `lower()`. Реализовано:
`ora2pg_gap_report/detectors/mysql_collate.py`.
