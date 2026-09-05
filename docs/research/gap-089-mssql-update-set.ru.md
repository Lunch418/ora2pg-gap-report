# GAP-089: `UPDATE ... SET` превращается в присваивание `:=`

MSSQL feature: обычный `UPDATE ... SET` — не что-то экзотическое, а
самый частый оператор в хранимых процедурах.

## Минимальный пример

```sql
CREATE PROCEDURE dbo.upd_only @x int AS
BEGIN
    UPDATE orders SET amount = @x, nm = 'y' WHERE id = 1;
END;
```

## Вывод ora2pg (v25.0, `-M -t PROCEDURE`)

```sql
CREATE OR REPLACE PROCEDURE dbo.upd_only (p_x integer) AS $body$
BEGIN
BEGIN 
     UPDATE  orders amount := p_x, nm = 'y' WHERE id = 1;
END;
END;
$body$
LANGUAGE PLPGSQL
;
```

Слово `SET` из запроса исчезло, а первое присваивание получило `:=`
вместо `=`. Причина понятна: в T-SQL `SET` — это ещё и оператор
присваивания переменной (`SET @x = 1`), и ora2pg применил к запросу
правила присваивания.

## Наблюдаемая проблема

Загрузка проходит чисто — ora2pg выставляет в своём выводе
`check_function_bodies = false`, поэтому тело не разбирается. При
разборе тела на реальном PostgreSQL 16:

```
ERROR:  syntax error at or near ":="
```

Проверено на трёх разных процедурах — с параметром, без параметра и с
`IF`-блоком: `UPDATE` ломается во всех.

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16. Source
dialect: MSSQL (`ora2pg -M`).

## Вердикт

**Gap подтверждён, severity high, failure_stage runtime.** Под это
попадает каждый `UPDATE` в каждой процедуре, так что после конвертации
их придётся просмотреть все. Правится возвратом к обычному SQL:
`UPDATE <таблица> SET <столбец> = <значение>`. Реализовано:
`ora2pg_gap_report/detectors/mssql_update_set.py` — детектор намеренно
не помечает настоящее присваивание переменной T-SQL (`SET @x = 1`),
которое ora2pg переводит верно.
