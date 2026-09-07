# GAP-102: `FOREIGN KEY` выбрасывается на файловом пути (MSSQL)

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

## Вывод ora2pg, файловый путь (v25.0, `-M -i schema.sql -t TABLE`)

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

Строк `FOREIGN KEY` в выводе нет ни одной — ни внутри `CREATE TABLE`,
ни отдельным `ALTER TABLE` после него.

## Тот же механизм, что и в GAP-082, на этот раз проверено по исходникам

Более ранняя версия этого документа объясняла потерю отсутствием у
`-t` типа экспорта под внешние ключи. Это объяснение не выдерживает
проверки: `-t TABLE` действительно экспортирует внешние ключи, просто
не на файловом пути, и у GAP-082 есть живой прогон на MySQL, который
это доказывает. Этот документ ошибался тем же способом.

Конкретно для MSSQL прочитан `MSSQL.pm::_foreign_key()` (ora2pg 25.0,
`lib/Ora2Pg/MSSQL.pm`, строка 541), а не повторено то же
предположение. Функция устроена так же, как MySQL-функция, которую
цитирует GAP-082, — один безусловный живой запрос:

```perl
sub _foreign_key
{
        my ($self, $table, $owner) = @_;
        ...
	my $sql = qq{SELECT fk.name AS ConsName, ...
FROM sys.foreign_keys fk
INNER JOIN sys.foreign_key_columns fkc ON fkc.constraint_object_id = fk.object_id
INNER JOIN sys.tables t_parent ON t_parent.object_id = fk.parent_object_id
...};
        my $sth = $self->{dbh}->prepare($sql) or $self->logit("FATAL: " . $self->{dbh}->errstr . "\n", 0, 1);
        $sth->execute or $self->logit("FATAL: " . $sth->errstr . "\n", 0, 1);
        ...
}
```

`$self->{dbh}` — живой хендл DBI к исходному SQL Server. Больше нигде в
`MSSQL.pm` нет разбора `FOREIGN KEY (...) REFERENCES ...` из текста
DDL. На файловом пути `$self->{dbh}` не существует, поэтому функции
нечего возвращать, независимо от того, что написано в предложении
`CONSTRAINT ... FOREIGN KEY`.

У этого документа нет живого прогона на SQL Server, каким располагает
GAP-082 для MySQL (живого экземпляра SQL Server под рукой не было);
утверждение выше опирается на исходный код, а не на второй живой
экспорт. Обе функции достаточно похожи по форме, один и тот же
`$self->{dbh}->prepare()` к собственным системным представлениям
движка-источника, без единой ветки разбора DDL-текста, так что это
разумное чтение кода, но на одну ступень менее напрямую подтверждённое,
чем у GAP-082.

## Наблюдаемая проблема

На файловом пути (уже выгруженный файл DDL/скрипта, без живого доступа
к базе — ровно то, что сканирует `ora2pg-gap-report`), ошибки не будет
ни на загрузке, ни потом: схема поднимется, приложение заработает, и
ссылочная целостность просто перестанет существовать — вместе с
каскадными удалениями.

**Reproducible: YES**, на файловом пути, который сканирует этот проект.
Ora2Pg version: 25.0, PostgreSQL 16. Source dialect: MSSQL (`ora2pg -M`).

## Вердикт

**Gap подтверждён для файлового входа, severity high, failure_stage
semantic.** Восстанавливается вручную: `ALTER TABLE <таблица> ADD
CONSTRAINT <имя> FOREIGN KEY (<столбцы>) REFERENCES <родитель>
(<столбцы>) ON DELETE ...` после загрузки всех таблиц, либо экспортом
через живое подключение к исходному SQL Server вместо файла, если такой
доступ есть. Реализовано:
`ora2pg_gap_report/detectors/mssql_foreign_key.py`.
