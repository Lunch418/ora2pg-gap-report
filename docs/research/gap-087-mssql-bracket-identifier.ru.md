# GAP-087: идентификаторы в квадратных скобках ломают конвертацию целиком

Первый gap партии MSSQL. ora2pg поддерживает SQL Server как источник
напрямую, через `-M`/`--mssql`, и работает файлово (`-i <file>`, без
живого подключения) так же, как режимы Oracle и MySQL.

MSSQL feature: `[dbo].[Orders]`, `[Id]`, `[int]` — штатная запись имён в
T-SQL. Именно так их выводит SSMS и «Generate Scripts» по умолчанию, то
есть так выглядит практически любой реальный скрипт.

## Минимальный пример

```sql
CREATE TABLE [dbo].[Orders](
    [Id] [int] IDENTITY(1,1) NOT NULL,
    [CustomerName] [nvarchar](100) NOT NULL,
    [Total] [money] NULL,
    [CreatedAt] [datetime2](7) NOT NULL,
 CONSTRAINT [PK_Orders] PRIMARY KEY CLUSTERED ([Id] ASC)
);
```

## Вывод ora2pg (v25.0, `-M -t TABLE`)

```sql
CREATE TABLE "[dbo]"."[orders]" (
	"[id]" [INT] NOT NULL,
	"[customername]" [NVARCHAR] NOT NULL,
	"[total]" [MONEY],
	"[createdat]" [DATETIME2] NOT NULL
) ;
ALTER TABLE "[dbo]"."[orders]" ADD PRIMARY KEY ([id]);
```

Скобки не сняты: они остались частью имени и сверху ещё взяты в двойные
кавычки. Получилась таблица с именем `[orders]` в схеме `[dbo]` и
столбцы типов `[INT]`, `[NVARCHAR]`, `[MONEY]` — таких типов нет.

## Наблюдаемая проблема

Подтверждено на реальном PostgreSQL 16:

```
ERROR:  syntax error at or near "["
LINE 2:  "[id]" [INT] NOT NULL,
                ^
```

Загрузка падает на первом же столбце.

## Дело именно в скобках

Проверено отдельно — та же таблица, записанная без скобок,
конвертируется корректно:

```sql
CREATE TABLE dbo.Orders(
    Id int IDENTITY(1,1) NOT NULL,
    CustomerName nvarchar(100) NOT NULL,
    Total money NULL,
    CreatedAt datetime2(7) NOT NULL,
 CONSTRAINT PK_Orders PRIMARY KEY CLUSTERED (Id ASC)
);
```

```sql
CREATE TABLE dbo.orders (
	id integer NOT NULL,
	customername citext NOT NULL,
	total numeric(15,4),
	createdat timestamp without time zone NOT NULL
) ;
```

## Почему так

В исходниках ora2pg снятие скобок есть — регулярка вида
`s/[\[\]]+//g` встречается в `lib/Ora2Pg/MSSQL.pm` восемь раз. Но все
восемь лежат внутри подпрограмм, работающих с живым подключением, и
применяются к строкам, вычитанным из базы через DBI:

| строка | подпрограмма |
|---|---|
| 381, 384 | `_column_info` |
| 644 | `_get_views` |
| 832 | `_check_constraint` |
| 900 | `_get_functions` |
| 944 | `_get_procedures` |
| 2331 | `_column_attributes` |
| 2631 | `_get_materialized_views` |

Файловый путь через `-i` до них не доходит вовсе — отсюда и разница в
поведении между «выгрузить из живого SQL Server» и «сконвертировать
скрипт».

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16. Source
dialect: MSSQL (`ora2pg -M`).

## Вердикт

**Gap подтверждён, severity high.** По охвату это самый крупный gap
всей MSSQL-партии: под него попадает любой скрипт, выгруженный SSMS с
настройками по умолчанию, и падает он на первой же таблице, до того как
успеют проявиться остальные проблемы. Обходится двумя способами: снять
скобки в скрипте до конвертации либо выгружать схему через живое
подключение к SQL Server. Реализовано:
`ora2pg_gap_report/detectors/mssql_bracket_identifier.py` — по одной
находке на объект, а не на каждую скобку.
