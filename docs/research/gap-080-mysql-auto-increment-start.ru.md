# GAP-080: `AUTO_INCREMENT=<n>` — стартовое значение теряется на файловом пути

MySQL/MariaDB feature: опция таблицы `AUTO_INCREMENT=<n>` — следующее
значение, которое выдаст счётчик. В дампе непустой таблицы `mysqldump`
всегда пишет её, и она всегда больше максимального существующего `id`.

## Минимальный пример

```sql
CREATE TABLE invoices (
  id INT PRIMARY KEY AUTO_INCREMENT,
  amount DECIMAL(10,2)
) ENGINE=InnoDB AUTO_INCREMENT=1000 DEFAULT CHARSET=utf8mb4;
```

## Вывод ora2pg, файловый путь (v25.0, `-m -i schema.sql -t TABLE`)

```sql
CREATE TABLE invoices (
	id serial,
	amount decimal(10,2)
) ;
ALTER TABLE invoices ADD PRIMARY KEY (id);
```

Сам столбец перенесён правильно — `AUTO_INCREMENT` стал `serial`. А вот
стартового значения нет: во всём файле ни одной строки `ALTER SEQUENCE
... RESTART WITH`, ни одного `setval()` (проверено `grep`), хотя
`AUTO_INCREMENT=1000` лежит прямо в тексте `CREATE TABLE`, который
ora2pg держит в руках.

## Та же схема против живой MySQL: стартовое значение на месте

Та же таблица загружена в реальную MariaDB, `ora2pg -m` натравлен на неё
через живое соединение вместо файла:

```sql
ALTER SEQUENCE invoices_id_seq RESTART WITH 1000;
```

присутствует, корректно, на своём месте. То есть дело не в том, что
ora2pg не может знать стартовое значение, а в том же ограничении
файлового пути, что и у потери внешних ключей в GAP-082. Причина — в
`MySQL.pm` (ora2pg 25.0):

```perl
my $sql = "SELECT TABLE_NAME, AUTO_INCREMENT FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_TYPE='BASE TABLE' AND TABLE_SCHEMA = '$self->{schema}'
            AND AUTO_INCREMENT IS NOT NULL";
```

живой запрос к `INFORMATION_SCHEMA.TABLES`, а не разбор опции
`AUTO_INCREMENT=<n>` из самого текста `CREATE TABLE`. На файловом пути
спрашивать не у кого, поэтому число теряется — не потому что его сложно
найти, оно однозначно и прямо в файле, а потому что этот код вообще не
смотрит в файл за ним.

## Наблюдаемая проблема

Схема загружается без единой ошибки. Последовательность начинает отсчёт
с 1 — то есть с значений, которые в перенесённых данных уже заняты.
Первая же вставка после миграции данных падает на нарушении первичного
ключа, и так до тех пор, пока счётчик не догонит реальные данные.

Обратите внимание: если данные не переносить, ошибки не будет вообще —
поэтому gap незаметен на прогоне «только схема» и проявляется ровно
тогда, когда миграцию считают состоявшейся.

**Reproducible: YES**, на файловом пути, который сканирует этот проект.
Ora2Pg version: 25.0, PostgreSQL 16. Source dialect: MySQL (`ora2pg -m`).

## Вердикт

**Gap подтверждён для файлового входа, severity high, failure_stage
runtime.** Стадия именно runtime, а не semantic: молчаливого
расхождения тут нет, есть конкретная ошибка в конкретный момент — на
первой вставке. Также решается экспортом через живое подключение к
исходной базе вместо файла, по механизму выше. Иначе чинится одной
строкой на таблицу после загрузки данных:

```sql
SELECT setval(pg_get_serial_sequence('invoices', 'id'),
              (SELECT max(id) FROM invoices));
```

Реализовано: `ora2pg_gap_report/detectors/mysql_auto_increment_start.py`
— детектор помечает только опцию таблицы (`AUTO_INCREMENT=<n>`, со
знаком равенства), но не атрибут столбца `AUTO_INCREMENT`, который
переносится корректно.
