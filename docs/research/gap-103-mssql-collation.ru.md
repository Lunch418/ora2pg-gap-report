# GAP-103: `COLLATE` выбрасывается, всё становится `citext`

MSSQL feature: `COLLATE` на столбце — правило сравнения и сортировки
строк.

## Минимальный пример

Взято правило с `_CS_` — регистрозависимое:

```sql
CREATE TABLE cs1 (
    id int NOT NULL PRIMARY KEY,
    code varchar(20) COLLATE SQL_Latin1_General_CP1_CS_AS NOT NULL
);
```

## Вывод ora2pg (v25.0, `-M -t TABLE`)

```sql
CREATE TABLE cs1 (
	id integer NOT NULL,
	code citext NOT NULL
) ;
```

Оговорка `COLLATE` выброшена, а сам столбец отображён в `citext` —
регистронезависимый тип.

## Наблюдаемая проблема

Для исходных правил с `_CI_` это попадание в цель. Для `_CS_` — молчаливая
подмена смысла на противоположный. Проверено на живых данных, реальный
PostgreSQL 16:

```
=# INSERT INTO cs1 VALUES (1,'ABC');
=# SELECT count(*) FROM cs1 WHERE code = 'abc';
 matches_lowercase_abc
-----------------------
                     1
```

SQL Server с правилом `..._CS_AS` не нашёл бы здесь ничего.

Ошибки при этом нет ни на одном этапе — меняется только выдача
запросов, и заметно это в бою: ломаются проверки уникальности, поиск по
коду, сравнение идентификаторов.

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16. Source
dialect: MSSQL (`ora2pg -M`).

## Вердикт

**Gap подтверждён, severity high, failure_stage semantic.** Severity
здесь high, а не medium, именно потому, что меняется результат запросов,
а не план их выполнения (ср. GAP-025/`invisible_index`, где теряется
только подсказка оптимизатору). Чинится заменой `citext` на `text` с
явным `COLLATE` нужной чувствительности — в PostgreSQL для этого есть
ICU-правила. Родственный gap на MySQL-стороне — GAP-085, но там
направление подмены обратное: регистронезависимое сравнение становится
регистрозависимым. Реализовано:
`ora2pg_gap_report/detectors/mssql_collation.py`.
