# GAP-141: `CHAR(n)` теряет хвостовые пробелы

Возможность Oracle: `CHAR(n)` дополняется пробелами до n символов, и эти пробелы учитываются: в `LENGTH`, в `||` и при сравнении с `VARCHAR2`.

## Как найдено

При проверке предыдущих пробелов: те же функции запускались в Oracle 23ai и, после ora2pg 25.0, в PostgreSQL 16.

## Минимальный пример

`tests/fixtures/char_to_char_round/oracle_functions.sql`, VALID в живом Oracle 23ai:

```sql
CREATE TABLE gx_codes (id NUMBER(5), code CHAR(5), flag CHAR(1));

CREATE OR REPLACE FUNCTION gx_r3 RETURN VARCHAR2 IS
  c CHAR(5) := 'AB';
  v VARCHAR2(5) := 'AB';
  l NUMBER(5);
BEGIN
  SELECT LENGTH(code) INTO l FROM gx_codes WHERE id = 1;
  RETURN LENGTH(c) || '|' || (c || 'x') || '|' || CASE WHEN c = v THEN 'equal' ELSE 'not equal' END || '|' || l;
END;
/
```

## Вывод ora2pg (v25.0)

```sql
	code char(5),
...
  c char(5) := 'AB';
  v varchar(5) := 'AB';
```

`CHAR(n)` становится `char(n)` - тот же тип, но с другими правилами: PostgreSQL считает хвостовые пробелы `char(n)` незначащими и отбрасывает их, когда значение используется как текст.

## Наблюдаемая проблема

Всё загружается и выполняется; в строке 1 `code = 'AB'`:

| | Oracle 23ai | PostgreSQL 16 |
|---|---|---|
| `LENGTH(c)` | 5 | 2 |
| `c \|\| 'x'` | `AB   x` | `ABx` |
| `c = v` (`VARCHAR2`) | не равно | равно |
| `LENGTH(code)` у столбца | 5 | 2 |

**Воспроизводится: ДА.** Версия Ora2Pg: 25.0, PostgreSQL 16, Oracle 23ai.

## Вердикт

**Пробел подтверждён, severity high, failure_stage semantic.** Сообщается один раз на файл, на первом `CHAR(n)` или `NCHAR(n)` с n > 1: решение - `varchar(n)` с явным `rpad` или `char(n)` с проверкой `LENGTH`, `||` и сравнений - принимается один раз для схемы. Флаги `CHAR(1)` не помечаются: у одного символа нет хвостовых пробелов.

Реализовано: `ora2pg_gap_report/detectors/char_semantics.py`.
