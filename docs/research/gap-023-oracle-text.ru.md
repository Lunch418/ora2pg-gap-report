# GAP-023: Oracle Text — домен-индекс отбрасывается, функции поиска не переносятся

Oracle feature: Oracle Text — полнотекстовый поиск через домен-индекс
(`CREATE INDEX ... INDEXTYPE IS CTXSYS.CONTEXT`, также `CTXCAT`/
`CTXRULE`) и функции `CONTAINS()`/`CATSEARCH()`/`MATCHES()`.

## Минимальный пример

```sql
CREATE TABLE articles (article_id NUMBER, body CLOB);

CREATE INDEX articles_body_idx ON articles(body)
INDEXTYPE IS CTXSYS.CONTEXT;
```

```sql
SELECT COUNT(*) INTO v_count
FROM articles
WHERE CONTAINS(body, 'oracle') > 0;
```

## Вывод ora2pg (v25.0, `-t TABLE` и `-t PACKAGE`)

```sql
CREATE TABLE articles (
	article_id bigint,
	body text
) ;
CREATE INDEX articles_body_idx ON articles (body);
```

Секция `INDEXTYPE IS CTXSYS.CONTEXT` пропадает без следа — индекс
конвертируется как обычный B-tree. Вызов `CONTAINS(body, 'oracle')`
копируется как есть.

## Наблюдаемая проблема

Создание индекса и таблицы проходит без ошибки — но это не обычная
таблица-с-обычным-индексом, а таблица, у которой полностью потеряна
возможность полнотекстового поиска, ради которой индекс изначально
создавался: обычный B-tree по `CLOB`/`text` столбцу не даёт ничего похожего
на `CONTAINS()`.

Подтверждено на реальном PostgreSQL 16 — вызов `CONTAINS()` падает при
первом вызове:

```
ERROR:  function contains(text, unknown) does not exist
HINT:  No function matches the given name and argument types.
```

У PostgreSQL есть архитектурный эквивалент — `tsvector`/`tsquery` +
GIN-индекс (`to_tsvector(...)`/`@@`), но это принципиально другой
синтаксис и модель (языковые словари, ранжирование через `ts_rank`),
требующий ручного переписывания, а не синтаксической замены.

**Reproducible: YES.** Ora2Pg version: 25.0.

## Вердикт

**Gap подтверждён.** Реализовано:
`ora2pg_gap_report/detectors/oracle_text.py` — покрывает как сам
домен-индекс (`INDEXTYPE IS CTXSYS.*`), так и функции поиска
(`CONTAINS`/`CATSEARCH`/`MATCHES`), поскольку оба конца одной и той же
фичи теряются одинаково молча.
