# GAP-109: объект внутри `/*!50003 … */` пропадает

MySQL/MariaDB feature: исполняемые («версионные») комментарии. MySQL
выполняет содержимое `/*!NNNNN … */`, если его версия не ниже NNNNN, так
что для MySQL это код. `mysqldump` оборачивает в них каждый триггер и
каждое представление (а старые версии — и подпрограммы):

## Минимальный пример

```sql
DELIMITER ;;
/*!50003 CREATE*/ /*!50017 DEFINER=`root`@`localhost`*/ /*!50003 TRIGGER `trg` AFTER UPDATE ON `language` FOR EACH ROW BEGIN
  REPLACE INTO film_text (film_id, title) VALUES (1, 1);
END */;;
DELIMITER ;

/*!50001 CREATE ALGORITHM=UNDEFINED */
/*!50013 DEFINER=`root`@`localhost` SQL SECURITY DEFINER */
/*!50001 VIEW `v_probe` AS select 1 AS `x` */;
```

## Вывод ora2pg (v25.0, `-m -t TRIGGER` / `-t VIEW`)

```sql
\set ON_ERROR_STOP ON
```

для каждого — ora2pg удаляет комментарии до разбора, и объекты уходят
вместе с ними. Ни ошибки, ни строчки в логе.

A/B: тот же триггер как обычный `CREATE TRIGGER` конвертируется
(2 инструкции — триггерная функция и сам триггер); то же представление
как обычный `CREATE VIEW` конвертируется. Формы подпрограмм, которые
пишут старые версии mysqldump, — `/*!50003 CREATE*/ /*!50020 DEFINER=…*/
/*!50003 PROCEDURE …*/` и то же для `FUNCTION`, — дают 0 подпрограмм и в
`-t PROCEDURE`, и в `-t FUNCTION`.

## Наблюдаемая проблема

На настоящем `mysqldump` базы sakila (MySQL 8.0.46) `-t TRIGGER` и
`-t VIEW` не выдали ни одного триггера и ни одного представления. Схема
загружается без них; работа триггеров молча прекращается, а запросы к
представлениям падают с `relation … does not exist`.

**Воспроизводится: ДА.** Версия Ora2Pg: 25.0. Исходный диалект: MySQL
(`ora2pg -m`).

## Вердикт

**Gap подтверждён, severity high, failure_stage conversion.** Исправляется
до конвертации: снять обёртку комментариев, оставив `CREATE` внутри,
или получить DDL этих объектов иначе (например, `SHOW CREATE TRIGGER`/
`SHOW CREATE VIEW` возвращают его без обёртки).

Реализовано: `ora2pg_gap_report/detectors/mysql_versioned_comment.py` —
читает исходник без маскировки (то, что он ищет, само является
комментарием), склеивает подряд идущие исполняемые комментарии так, как
mysqldump разбивает на них один `CREATE`, и отмечает
`CREATE TRIGGER|VIEW|PROCEDURE|FUNCTION`. Остальные исполняемые
комментарии mysqldump — `SET`, `DROP … IF EXISTS`, `ALTER TABLE … KEYS` —
не отмечаются, как и строка, которая только похожа на такой комментарий.
