# GAP-102: `FOREIGN KEY` выбрасывается целиком (MSSQL)

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

## Вывод ora2pg (v25.0, `-M -t TABLE`)

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

## Это не «выгружается отдельным типом экспорта»

Отдельного типа экспорта под внешние ключи у ora2pg нет: в списке
поддерживаемых значений `-t` (`TABLE`, `VIEW`, `GRANT`, `TRIGGER`,
`FUNCTION`, `PROCEDURE`, `PARTITION`, `DBLINK`, `INSERT`, `COPY`,
`TEST*`, `SHOW_*`) нет ни `FKEY`, ни `CONSTRAINT`.

## Наблюдаемая проблема

Ошибки не будет ни на загрузке, ни потом: схема поднимется, приложение
заработает, и ссылочная целостность просто перестанет существовать —
вместе с каскадными удалениями.

Ровно то же самое ora2pg делает с внешними ключами на MySQL-стороне
(GAP-082), так что это не особенность одного диалекта.

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16. Source
dialect: MSSQL (`ora2pg -M`).

## Вердикт

**Gap подтверждён, severity high, failure_stage semantic.**
Восстанавливается вручную: `ALTER TABLE <таблица> ADD CONSTRAINT <имя>
FOREIGN KEY (<столбцы>) REFERENCES <родитель> (<столбцы>) ON DELETE
...` после загрузки всех таблиц. Реализовано:
`ora2pg_gap_report/detectors/mssql_foreign_key.py`.
