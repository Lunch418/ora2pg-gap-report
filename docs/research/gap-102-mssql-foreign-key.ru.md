# GAP-102: `FOREIGN KEY` выбрасывается, если `PG_VERSION` оставлен по умолчанию (MSSQL)

MSSQL feature: внешний ключ, объявленный в списке столбцов `CREATE
TABLE`.

## Минимальный пример

```sql
CREATE TABLE parentx (id int NOT NULL PRIMARY KEY);
CREATE TABLE childx (
    id int NOT NULL PRIMARY KEY,
    pid int NOT NULL,
    CONSTRAINT FK_childx_parentx FOREIGN KEY (pid) REFERENCES parentx (id) ON DELETE CASCADE
);
```

## Вывод ora2pg с ненастроенным `PG_VERSION` (v25.0, `-M -i schema.sql -t TABLE`)

```sql
CREATE TABLE parentx (
	id integer NOT NULL
) ;
ALTER TABLE parentx ADD PRIMARY KEY (id);


CREATE TABLE childx (
	id integer NOT NULL,
	pid integer NOT NULL
) ;
ALTER TABLE childx ADD PRIMARY KEY (id);
```

Строк `FOREIGN KEY` в выводе нет ни одной.

```sh
ora2pg -c myconf.conf -M -i schema.sql -t TABLE -o out.sql -b out   # в myconf.conf задан PG_VERSION 16
```

```sql
ALTER TABLE childx ADD CONSTRAINT fk_childx_parentx FOREIGN KEY (pid) REFERENCES parentx(id) ON DELETE NO ACTION INITIALLY IMMEDIATE;
```

Та же схема, тот же `-M -i -t TABLE`, единственная разница — `PG_VERSION`
в конфиге.

## Та же первопричина, что и в GAP-082, а не файловый путь

Две более ранние версии этого документа называли два разных неверных
механизма: сначала что у `-t` нет типа экспорта под внешние ключи,
затем что у файлового входа нет живого каталога для запроса, а значит
диалект-специфичная `_foreign_key()` (функция, работающая только через
живой запрос) не может ничего вернуть. Оба объяснения выглядели
разумно для наблюдаемого нулевого вывода FK; ни одно из них не было
настоящей причиной.

Настоящий механизм живёт в диалект-независимом коде, общем для всех
исходных движков, — `_create_unique_keys()` и `_create_foreign_keys()`
в `lib/Ora2Pg.pm`, и GAP-082 прослеживает его целиком трассировкой в
стиле `perl -d`, а не просто чтением: проверка `exists
$self->{partitions_list}{$table}{refrtable}`, написанная для
обнаружения таблиц с partition-by-reference, молча создаёт фантомную
запись в `partitions_list` для *каждой* таблицы, которая проходит через
`_create_unique_keys()`, партиционирована она или нет, — потому что
`exists` на многоуровневом разыменовании хеша создаёт промежуточный
уровень как побочный эффект. `_create_foreign_keys()` затем принимает
эту фантомную запись за доказательство, что целевая таблица
партиционирована, и пропускает ограничение, но только когда
`$self->{pg_version} <= 12` — а это ровно дефолт (11) для конфига, в
котором `PG_VERSION` никогда не задавали.

Проверено напрямую для MSSQL, а не просто предположено по результату
для MySQL:

```sh
ora2pg -M -i schema.sql -t TABLE -o out.sql -b out          # PG_VERSION не задан -> 0 строк FOREIGN KEY
ora2pg -c myconf.conf -M -i schema.sql -t TABLE -o out.sql -b out   # PG_VERSION 16 -> ограничение на месте
```

И `_foreign_key()` (диалект-специфичная функция, работающая только
через живой запрос, которую этот документ раньше обвинял), и
`_create_foreign_keys()`/`_create_unique_keys()` (настоящие виновники)
находятся в коде, общем для источников MySQL, MSSQL и Oracle, поэтому
и причина, и способ починки идентичны GAP-082: дело в `PG_VERSION`, а
не в диалекте и не в режиме входа. Живого экземпляра SQL Server под
рукой не было, чтобы повторить для MSSQL живую половину
четырёхкомбинационной таблицы проверки из GAP-082, но файловая половина
подтверждена напрямую выше, а ответственный код в принципе не
MSSQL-специфичен.

## Наблюдаемая проблема

При конфиге, в котором `PG_VERSION` никогда явно не выставлялся (или
выставлен в 12 либо ниже), внешний ключ молча исчезает: ошибки нет ни
при загрузке, ни потом, схема поднимается, приложение работает, а
ссылочная целостность просто перестаёт существовать, вместе с
каскадным удалением.

**Reproducible: YES**, при `PG_VERSION` не заданном или равном 12 либо
ниже. Ora2Pg version: 25.0, PostgreSQL 16. Source dialect: MSSQL
(`ora2pg -M`).

## Вердикт

**Gap подтверждён, severity high, failure_stage semantic**, при условии
`PG_VERSION <= 12` (включая незаданное значение по умолчанию). Чинится
установкой `PG_VERSION` в реальную целевую версию PostgreSQL (13 или
выше) перед конвертацией; если цель действительно PostgreSQL ≤12,
ограничение приходится восстанавливать вручную: `ALTER TABLE <таблица>
ADD CONSTRAINT <имя> FOREIGN KEY (<столбцы>) REFERENCES <родитель>
(<столбцы>) ON DELETE ...` после загрузки всех таблиц. Реализовано:
`ora2pg_gap_report/detectors/mssql_foreign_key.py`.
