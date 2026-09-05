# GAP-080: `AUTO_INCREMENT=<n>` — стартовое значение счётчика теряется

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

## Вывод ora2pg (v25.0, `-m -t TABLE`)

```sql
CREATE TABLE invoices (
	id serial,
	amount decimal(10,2)
) ;
ALTER TABLE invoices ADD PRIMARY KEY (id);
```

Сам столбец перенесён правильно — `AUTO_INCREMENT` стал `serial`. А вот
стартового значения нет: во всём файле ни одной строки `ALTER SEQUENCE
... RESTART WITH`, ни одного `setval()` (проверено `grep`).

## Наблюдаемая проблема

Схема загружается без единой ошибки. Последовательность начинает отсчёт
с 1 — то есть с значений, которые в перенесённых данных уже заняты.
Первая же вставка после миграции данных падает на нарушении первичного
ключа, и так до тех пор, пока счётчик не догонит реальные данные.

Обратите внимание: если данные не переносить, ошибки не будет вообще —
поэтому gap незаметен на прогоне «только схема» и проявляется ровно
тогда, когда миграцию считают состоявшейся.

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16. Source
dialect: MySQL (`ora2pg -m`).

## Вердикт

**Gap подтверждён, severity high, failure_stage runtime.** Стадия
именно runtime, а не semantic: молчаливого расхождения тут нет, есть
конкретная ошибка в конкретный момент — на первой вставке. Чинится
одной строкой на таблицу после загрузки данных:

```sql
SELECT setval(pg_get_serial_sequence('invoices', 'id'),
              (SELECT max(id) FROM invoices));
```

Реализовано: `ora2pg_gap_report/detectors/mysql_auto_increment_start.py`
— детектор помечает только опцию таблицы (`AUTO_INCREMENT=<n>`, со
знаком равенства), но не атрибут столбца `AUTO_INCREMENT`, который
переносится корректно.
