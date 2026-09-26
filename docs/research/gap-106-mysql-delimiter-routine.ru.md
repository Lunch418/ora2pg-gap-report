# GAP-106: подпрограмма, записанная под `DELIMITER`, не загружается

MySQL/MariaDB feature: клиентская директива `DELIMITER`. В теле процедуры
или функции есть `;`, поэтому клиенту `mysql` нужен другой разделитель
инструкций, чтобы отправить подпрограмму целиком. Так `mysqldump`
записывает каждую подпрограмму (`DELIMITER ;;` … `END ;;` …
`DELIMITER ;`), и так же — практически любой рукописный MySQL-скрипт.

## Минимальный пример

```sql
DELIMITER //
CREATE FUNCTION add_one(p INT) RETURNS int DETERMINISTIC
BEGIN
  RETURN p + 1;
END //
DELIMITER ;
```

## Вывод ora2pg (v25.0, `-m -t FUNCTION`)

```sql
\set ON_ERROR_STOP ON
CREATE OR REPLACE FUNCTION add_one (p integer) RETURNS integer AS $body$
BEGIN
  RETURN p + 1;
END //
DELIMITER ;
$body$
LANGUAGE PLPGSQL
 IMMUTABLE;
```

ora2pg заканчивает тело подпрограммы на `END <имя>;` в стиле Oracle и
директиву `DELIMITER` не знает: закрывающий `//` и строка `DELIMITER ;`
оказываются внутри `$body$`. В файле `mysqldump` туда же попадает всё до
следующей подпрограммы — строки `/*!50003 SET sql_mode = ... */`, которые
mysqldump пишет вокруг каждой.

## Наблюдаемая проблема

Сгенерированный `CREATE` падает при загрузке:

```
ERROR:  syntax error at or near "//"
```

и собственный `\set ON_ERROR_STOP ON` вывода останавливает загрузку всего
файла. То же самое для каждого проверенного разделителя, у процедур
(`-t PROCEDURE`) и функций (`-t FUNCTION`) одинаково:

| Разделитель | Ошибка при загрузке |
|---|---|
| `;;` | `syntax error at or near "DELIMITER"` |
| `//` | `syntax error at or near "//"` |
| `$$` | `unterminated dollar-quoted string` |
| `\|` | `syntax error at or near "\|"` |
| `$` | `syntax error at or near "$"` |

A/B: та же функция, законченная обычным `;` и без `DELIMITER`,
загружается, и `SELECT add_one(41)` возвращает 42.

На настоящем `mysqldump --routines` базы sakila из MySQL 8.0.46 (её шесть
подпрограмм плюс одна тестовая процедура) `-t FUNCTION` сгенерировал все
семь, а загрузка файла в PostgreSQL 16 не создала ни одной.

**Воспроизводится: ДА.** Версия Ora2Pg: 25.0, PostgreSQL 16. Исходный
диалект: MySQL (`ora2pg -m`).

## Вердикт

**Gap подтверждён, severity high, failure_stage deployment.** Исправляется
до конвертации: убрать директивы `DELIMITER` и закончить каждую
подпрограмму обычным `;` — ora2pg читает файл сам, не через клиент
`mysql`, и директивы ему не нужны.

Реализовано: `ora2pg_gap_report/detectors/mysql_delimiter_routine.py` —
отмечает каждый `CREATE PROCEDURE`/`FUNCTION`, перед которым действует
разделитель, отличный от `;`. Подпрограмма внутри исполняемого
комментария (`/*!50003 ... */`) здесь не отмечается: такие ora2pg
выбрасывает целиком, это GAP-109.
