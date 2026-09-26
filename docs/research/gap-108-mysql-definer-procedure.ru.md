# GAP-108: `-t PROCEDURE` пропускает процедуру с `DEFINER`

MySQL/MariaDB feature: `CREATE DEFINER=<user> PROCEDURE …` — контекст
безопасности, в котором выполняется подпрограмма. `mysqldump` пишет
`DEFINER` у каждой выгружаемой процедуры.

## Минимальный пример

```sql
DELIMITER ;;
CREATE DEFINER=`app`@`%` PROCEDURE `close_order`(p_id INT)
BEGIN
  UPDATE orders SET status = 'closed' WHERE id = p_id;
END ;;
DELIMITER ;
```

## Вывод ora2pg (v25.0, `-m -t PROCEDURE`)

```sql
\set ON_ERROR_STOP ON
```

Процедуры нет, и ничто об этом не сообщает. Без `DEFINER` та же
процедура выгружается. Проверены все варианты записи —
`` `root`@`localhost` ``, `root@localhost`, `'root'@'localhost'`,
`` `root`@`%` ``, `CURRENT_USER` — результат одинаковый.

## Почему: исходный код ora2pg

`export_procedure()` (lib/Ora2Pg.pm, 25.0) распознаёт начало процедуры во
входном файле так:

```perl
if ($l =~ /^\s*CREATE\s*(?:OR REPLACE)?\s*(?:EDITIONABLE|NONEDITIONABLE)?\s*(FUNCTION|PROCEDURE)\s*$/i)
...
$l =~ s/^\s*CREATE (?:OR REPLACE)?\s*(?:EDITIONABLE|NONEDITIONABLE)?\s*(FUNCTION|PROCEDURE)/$1/i;
```

а в `export_function()`, несколькими сотнями строк выше:

```perl
$l =~ s/^\s*CREATE (?:OR REPLACE)?\s*(?:EDITIONABLE|NONEDITIONABLE|DEFINER=[^\s]+)?\s*(FUNCTION|PROCEDURE)/$1/i;
```

— те же шаблоны с `DEFINER=[^\s]+` в качестве варианта. Без него строка
`CREATE DEFINER=… PROCEDURE` не превращается в `PROCEDURE <имя>`, имя
подпрограммы не подхватывается, и все её строки пропускаются.

Отсюда же и обход: `-t FUNCTION` процедуру выгружает. На примере выше он
сгенерировал обе подпрограммы файла с процедурой и функцией, обе с
`DEFINER`. (В настоящем дампе они всё равно несут `DELIMITER` и поэтому
не загружаются — GAP-106.)

## Наблюдаемая проблема

На настоящем `mysqldump --routines` базы sakila (MySQL 8.0.46)
`-t PROCEDURE` выгрузил 0 из 4 процедур. Схема загружается; первый `CALL`
падает с `procedure … does not exist`.

**Воспроизводится: ДА.** Версия Ora2Pg: 25.0. Исходный диалект: MySQL
(`ora2pg -m`).

## Вердикт

**Gap подтверждён, severity high, failure_stage conversion.** Исправляется
либо удалением `DEFINER=…` до конвертации, либо выгрузкой процедур через
`-t FUNCTION` вместо `-t PROCEDURE`.

Реализовано: `ora2pg_gap_report/detectors/mysql_definer_procedure.py` —
отмечает `CREATE … DEFINER=… PROCEDURE` при любой записи владельца.
Функция с `DEFINER` не отмечается: `-t FUNCTION` с ней справляется.
