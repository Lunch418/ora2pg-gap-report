# GAP-103: `COLLATE` игнорируется, всё становится `citext` по умолчанию

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

## Не хардкод: документированный дефолт, который не смотрит на столбец, к которому применяется

Это `CASE_INSENSITIVE_SEARCH`, реальная, документированная опция ora2pg
(`doc/Ora2Pg.pod`): «Emulate the same behavior of MSSQL with
case-insensitive search. If the value is citext, it will use the citext
data type instead of char/varchar/text ... To disable case-insensitive
search set it to: none». По умолчанию она равна `citext` конкретно для
источников MSSQL (собственная инициализация MSSQL-блока в `Ora2Pg.pm`
устанавливает `$self->{case_insensitive_search} = 'citext'`), исходя из
того, что установки SQL Server по умолчанию часто регистронезависимы.

Опция существует и отключается одной строкой конфига. Чего она не
делает ни при каком значении, кроме `none`, — не смотрит на собственный
`COLLATE` конкретного столбца перед применением. В `Ora2Pg.pm` (~строка
8774) условие срабатывания подмены выглядит так:

```perl
if ($self->{case_insensitive_search} =~ /^citext$/i && $type =~ /^(?:char|varchar|text)/)
{
	...
	$type = 'citext';
}
```

проверяется только базовый тип (`char`/`varchar`/`text`), но никогда —
строка правила сортировки столбца. Так что с дефолтом из поставки любой
строковый столбец из источника MSSQL становится `citext`, был ли его
собственный `COLLATE` `_CI_` или `_CS_`. Пример ниже намеренно взят с
источником `_CS_`, чтобы расхождение было заметно; источник `_CI_`
попал бы в правильный ответ случайно, тем же дефолтом, применённым без
всякой проверки в обе стороны.

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
только подсказка оптимизатору). Чинится либо установкой
`CASE_INSENSITIVE_SEARCH none` перед конвертацией и добавлением
вручную явного `COLLATE` нужной чувствительности на каждый столбец — в
PostgreSQL для этого есть ICU-правила, — либо заменой `citext` на
`text` с тем же `COLLATE` постфактум. Родственный gap на MySQL-стороне
— GAP-085: та же категория (`COLLATE` не переносится в вывод
PostgreSQL), но у `-m`-пути MySQL вообще нет поведения «citext по
умолчанию», поэтому там `COLLATE` просто выбрасывается, а не
заменяется последовательно неверной догадкой. Реализовано:
`ora2pg_gap_report/detectors/mssql_collation.py`.
