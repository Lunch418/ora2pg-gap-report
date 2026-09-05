# GAP-032: `CREATE [PUBLIC] SYNONYM` теряет схему целевого объекта

Oracle feature: `CREATE [PUBLIC] SYNONYM name FOR [schema.]object` —
алиас на объект, часто в другой схеме. Обычная практика — синоним с тем
же базовым именем, что и целевая таблица (`CREATE PUBLIC SYNONYM
employees FOR hr.employees`), чтобы пользователи других схем могли
писать `employees` без указания владельца.

## Минимальный пример

```sql
CREATE TABLE hr.employees (emp_id NUMBER);
CREATE PUBLIC SYNONYM employees FOR hr.employees;
```

## Вывод ora2pg (v25.0, `-t SYNONYM`)

```sql
CREATE OR REPLACE VIEW employees AS SELECT * FROM employees;
```

Синоним конвертируется в `VIEW`, но целевой объект теряет схему
целиком — `hr.employees` становится просто `employees`, без какой-либо
квалификации. Проверено также с разными базовыми именами (`CREATE
PUBLIC SYNONYM employees FOR hr.emp_table`) — тот же результат, `SELECT
* FROM emp_table` без схемы.

## Наблюдаемая проблема

Когда имя синонима совпадает с базовым именем целевой таблицы (самый
частый в реальности случай — вся идея синонима обычно в этом) —
получается самоссылающийся `VIEW`. Подтверждено на реальном PostgreSQL 16:

```sql
CREATE SCHEMA hr;
CREATE TABLE hr.employees (emp_id bigint);
CREATE OR REPLACE VIEW employees AS SELECT * FROM employees;
-- ERROR:  relation "employees" does not exist
-- LINE 1: CREATE OR REPLACE VIEW employees AS SELECT * FROM employees;
```

Скрипт миграции обрывается прямо на этом объекте. Когда имена
различаются, отказа на этом этапе не будет, но представление всё равно
опирается на неквалифицированное имя — какая именно таблица `emp_table`
разрешится, целиком зависит от `search_path` в момент выполнения этого
`CREATE VIEW`, а не от исходной Oracle-привязки `hr.emp_table`. Если в
`search_path` окажется одноимённая таблица из другой схемы (обычное
дело при миграции нескольких Oracle-схем в одну базу PostgreSQL) —
представление молча привяжется не к той таблице, без единой ошибки.

**Reproducible: YES.** Ora2Pg version: 25.0.

## Вердикт

**Gap подтверждён.** Реализовано:
`ora2pg_gap_report/detectors/public_synonym.py`.
