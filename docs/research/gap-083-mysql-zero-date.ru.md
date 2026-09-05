# GAP-083: `'0000-00-00'` молча превращается в `'1970-01-01'`

MySQL/MariaDB feature: «нулевая» дата — не настоящая дата, а признак
«значение не задано», который MySQL допускает в `DATE`/`DATETIME` по
историческим причинам.

## Минимальный пример

```sql
CREATE TABLE events (
  id INT PRIMARY KEY,
  happened_on DATE NOT NULL DEFAULT '0000-00-00'
);
```

## Вывод ora2pg (v25.0, `-m -t TABLE`)

```sql
CREATE TABLE events (
	id integer,
	happened_on date NOT NULL DEFAULT '1970-01-01'
) ;
ALTER TABLE events ADD PRIMARY KEY (id);
```

Признак «не задано» заменён на конкретную дату — начало эпохи Unix.

## Наблюдаемая проблема

Ошибки нет ни на загрузке, ни потом. Проверено на живых данных,
реальный PostgreSQL 16:

```
=# INSERT INTO events (id) VALUES (1);
INSERT 0 1
=# SELECT id, happened_on FROM events;
 id | happened_on
----+-------------
  1 | 1970-01-01
```

Строка, у которой в MySQL дата была бы «не задана», после миграции
имеет вполне осмысленную дату 1 января 1970 года. Последствия чисто
смысловые и потому незаметные: запросы вида `WHERE d = '0000-00-00'`
(поиск незаполненных) перестают находить что-либо, а отчёты по датам
начинают показывать 1970 год как реальное событие.

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16. Source
dialect: MySQL (`ora2pg -m`).

## Вердикт

**Gap подтверждён, severity high, failure_stage semantic.** Правильный
перенос — `NULL` (и, если нужно, снятие `NOT NULL`) либо отдельный
признак «не задано». Проверять надо не только `DEFAULT`, но и сами
данные: нулевые даты в существующих строках переносятся тем же
механизмом. Реализовано:
`ora2pg_gap_report/detectors/mysql_zero_date.py` — детектор читает
comments-only-представление исходника, потому что литерал даты лежит
внутри строковой константы, которую обычное маскирование затирает.
