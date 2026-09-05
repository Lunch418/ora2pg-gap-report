# GAP-101: фильтрованный индекс выбрасывается целиком

MSSQL feature: фильтрованный индекс — `CREATE INDEX ... WHERE
<условие>`, индекс по части строк таблицы.

## Минимальный пример

```sql
CREATE TABLE soft_del (
    id int NOT NULL PRIMARY KEY,
    deleted bit NOT NULL
);
CREATE NONCLUSTERED INDEX IX_alive ON soft_del (id) WHERE deleted = 0;
```

## Вывод ora2pg (v25.0, `-M -t TABLE`)

```sql
CREATE TABLE soft_del (
	id integer NOT NULL,
	deleted boolean NOT NULL
) ;
ALTER TABLE soft_del ADD PRIMARY KEY (id);
```

Индекса в выводе нет вообще.

## Это не общая проблема с индексами

Проверено отдельно: обычный индекс с `INCLUDE` тот же ora2pg в том же
прогоне переносит корректно.

```sql
CREATE NONCLUSTERED INDEX IX_lookup_a ON lookup1 (a) INCLUDE (b, c);
```

```sql
CREATE INDEX ix_lookup_a ON lookup1 (a) INCLUDE (b, c);
```

Загружается без ошибок (PostgreSQL поддерживает `INCLUDE` начиная с 11).
То есть теряется именно фильтрованная форма.

## Наблюдаемая проблема

Ошибки не будет ни на загрузке, ни потом: схема поднимется без индекса.
Разница проявится как деградация планов на больших таблицах, а если
индекс был `UNIQUE` — ещё и как исчезнувшее ограничение уникальности.

Обиднее всего, что переносить тут почти нечего: в PostgreSQL есть ровно
такие же частичные индексы и ровно с тем же синтаксисом.

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16. Source
dialect: MSSQL (`ora2pg -M`).

## Вердикт

**Gap подтверждён, severity high, failure_stage semantic.**
Восстанавливается дословным переносом оператора после загрузки схемы.
Реализовано: `ora2pg_gap_report/detectors/mssql_filtered_index.py`.
