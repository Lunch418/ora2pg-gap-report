# GAP-031: `DEFAULT ON NULL` копируется verbatim — синтаксическая ошибка

Oracle feature (12c+): `<column> <type> DEFAULT ON NULL <expr>` —
отличается от обычного `DEFAULT`: обычный `DEFAULT` подставляется,
только когда столбец вообще не упомянут в `INSERT`; `DEFAULT ON NULL`
подставляется и тогда, когда столбец упомянут явно, но передано
`NULL` — типичное использование для столбцов вроде "статус",
"количество попыток", куда приложение может по ошибке (или намеренно,
для унификации кода) передать `NULL` вместо явного значения.

## Минимальный пример

```sql
CREATE TABLE orders (
    order_id NUMBER,
    status VARCHAR2(20) DEFAULT ON NULL 'PENDING'
);
```

## Вывод ora2pg (v25.0, `-t TABLE`)

```sql
CREATE TABLE orders (
	order_id bigint,
	status varchar(20) DEFAULT ON NULL 'PENDING'
) ;
```

Секция `ON NULL` копируется в вывод как есть — `PostgreSQL` не
поддерживает такой синтаксис у `DEFAULT` вообще (в PostgreSQL 16
единственный способ добиться похожего поведения — `BEFORE`-триггер или
`GENERATED ALWAYS AS ... STORED` с `COALESCE`, но не сам `DEFAULT`).

## Наблюдаемая проблема

В отличие от большинства gap'ов в этом реестре — это не тихая потеря
поведения, а немедленный отказ уже на этапе применения самого DDL.
Подтверждено на реальном PostgreSQL 16:

```sql
CREATE TABLE orders (
	order_id bigint,
	status varchar(20) DEFAULT ON NULL 'PENDING'
) ;
-- ERROR:  syntax error at or near "ON"
-- LINE 3:  status varchar(20) DEFAULT ON NULL 'PENDING'
--                              ^
```

Скрипт миграции обрывается на этой самой таблице — не позже, при первой
вставке, как в большинстве других "тихих" gap'ов, а сразу. Легко
заметить при первом прогоне сгенерированного дампа, но требует ручного
переписывания под триггер или `COALESCE` в `GENERATED ALWAYS AS`,
прежде чем миграция сможет продолжиться дальше этой таблицы.

**Reproducible: YES.** Ora2Pg version: 25.0.

## Вердикт

**Gap подтверждён.** Реализовано:
`ora2pg_gap_report/detectors/default_on_null.py`.
