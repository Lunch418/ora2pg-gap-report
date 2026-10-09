# GAP-126: подпрограмма, за которой идёт `GO`, - `GO` попадает в её тело

Возможность MSSQL: `GO` - разделитель пакетов, который SSMS и sqlcmd
пишут после каждого выгружаемого объекта. Это команда клиента, а не T-SQL,
и стоит она на отдельной строке.

## Как найден

`--migrate --dialect mssql --load-check docker` на скрипте в стиле SSMS
после того, как схема из GAP-125 была создана: процедура всё равно падала
с `end label "go" specified for unlabeled block`.

## Минимальный пример

```sql
CREATE PROCEDURE add_order @id int
AS
BEGIN
    INSERT INTO orders (id) VALUES (@id);
END
GO
CREATE FUNCTION next_id (@a int) RETURNS int
AS
BEGIN
    RETURN @a + 1;
END
GO
```

## Вывод ora2pg (v25.0, `-M -t PROCEDURE`)

```sql
CREATE OR REPLACE PROCEDURE add_order (p_id integer) AS $body$
BEGIN
BEGIN
     INSERT INTO orders(id) VALUES (p_id);
END
GO
END;
$body$
```

ora2pg читает подпрограмму до следующего `CREATE`, поэтому `GO` оказывается
внутри тела, а `END;`, которым он закрывает свой обёрточный `BEGIN`,
идёт после него.

## Наблюдаемая проблема

PostgreSQL 16 не загружает ни одну из подпрограмм:

```
ERROR:  42601: end label "go" specified for unlabeled block
```

С `END;` перед `GO` вместо этого `syntax error at or near "GO"`. Без строк
`GO` подпрограмма, которая кончается голым `END`, теряет один `END`
(`syntax error at end of input`); записанные с `END;` и без `GO` обе
подпрограммы конвертируются, загружаются и работают: `CALL add_order(5)`
вставляет строку, `next_id(1)` возвращает 2.

**Воспроизводится: ДА.** Версия Ora2Pg: 25.0, PostgreSQL 16.

## Вердикт

**Gap подтверждён, severity high, failure_stage deployment.** Механически,
в исходнике: `--prepare --dialect mssql` (`prepare_mssql_go_separator`)
убирает строки `GO` и ставит `;` после голого `END`, закрывавшего пакет.
`GO` разделяет пакеты только для клиента, а ora2pg и так делит объекты по
`CREATE`, так что ничего не теряется; счётчик повторов `GO n` уходит
вместе с ним (он лишь повторно выполняет пакет). `--migrate` это применяет.

Реализовано: `ora2pg_gap_report/detectors/mssql_go_separator.py` -
сообщается на строке `GO`, один раз на подпрограмму; детектор узнаёт и
вывод ora2pg с `GO` внутри, поэтому `--load-check` связывает ошибку с ним.
