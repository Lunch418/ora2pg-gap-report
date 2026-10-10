# GAP-139: `TO_CHAR(a/b)` становится `a/b::text`

Возможность Oracle: `TO_CHAR` без формата от выражения: `TO_CHAR(a/b)`, `TO_CHAR(-a)`.

## Как найдено

При проверке предыдущих пробелов: те же функции запускались в Oracle 23ai и, после ora2pg 25.0, в PostgreSQL 16.

## Минимальный пример

`tests/fixtures/char_to_char_round/oracle_functions.sql`, VALID в живом Oracle 23ai:

```sql
CREATE OR REPLACE FUNCTION gx_r1(a NUMBER, b NUMBER) RETURN VARCHAR2 IS
BEGIN
  RETURN TO_CHAR(a/b) || '|' || TO_CHAR(-a);
END;
/
```

## Вывод ora2pg (v25.0)

```sql
  RETURN a/b::text || '|' || -a::text;
```

`TO_CHAR` с одним аргументом становится приведением к text. Аргумент берётся в скобки, только если в нём есть пробел: `TO_CHAR(a / b)` даёт `(a / b)::text`, а `TO_CHAR(a/b)` - `a/b::text`, и `::` связывает сильнее, чем `/`, так что приводится только `b`. То же для `+`, `-`, `*` и унарного минуса.

## Наблюдаемая проблема

Функция загружается; первый вызов падает (Oracle 23ai: `gx_r1(1, 4)` = `.25|-1`):

```
ERROR:  operator does not exist: bigint / text
```

**Воспроизводится: ДА.** Версия Ora2Pg: 25.0, PostgreSQL 16, Oracle 23ai.

## Вердикт

**Пробел подтверждён, severity high, failure_stage runtime.** Возьмите выражение в скобки: `(a/b)::text`. ora2pg смотрит на пробелы после того, как спрятал каждый вызов функции за заглушкой, поэтому `TO_CHAR(abs(n - 1)+1)` и `TO_CHAR((n+1))` тоже теряют скобки; детектор применяет то же правило. Найдено в библиотеке Alexandria PL/SQL: `to_char(n+1)`, `to_char(i+1)`, `to_char(3+2*i)`.

Реализовано: `ora2pg_gap_report/detectors/to_char_operator.py`.
