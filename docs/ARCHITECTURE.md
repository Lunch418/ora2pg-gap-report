# Архитектура

Этот документ — про то, как устроен инструмент внутри: лексер,
маскирование, атрибуция находок, обработка динамического SQL, файловая
структура. Для "что это и зачем" — см. [README.md](../README.md); для
"как разрабатывать/тестировать" — см. [DEVELOPMENT.md](DEVELOPMENT.md).

`ora2pg SHOW_REPORT` целиком не имеет офлайн-режима — он требует живого
подключения к Oracle (`ORACLE_DSN`). Офлайн от DDL-дампа работает только
анализ *отдельных типов объектов* (`-t PACKAGE`, `-t TRIGGER`, `-t FUNCTION`,
…) — именно так работает `ora2pg_wrapper.py`, а не через `SHOW_REPORT`. Это
принципиально для целевой аудитории — закрытые контуры, air-gapped среды,
госсектор.

Детекторов сейчас 38 (полная таблица — в README.md, «Детекторы»; 37 из
них привязаны к зарегистрированному GAP-NNN, `dbms_utl_calls` — нет, см.
README.md, «Почему почти всё high»), и почти все они устроены
одинаково: анализируют Oracle-исходник напрямую и не требуют
установленного `ora2pg` — чистый Python, без внешних зависимостей.
Исключение ровно одно — `connect_by`: он устроен иначе, линтит
*сгенерированный* ora2pg-код, а не исходник (ora2pg сам неплохо считает
CONNECT BY — ценность не в обнаружении, а в проверке качества
конвертации), поэтому ему нужен реальный `ora2pg` и он подключается
только через `--check-connect-by`. Это единственный детектор с таким
требованием — не "один из четырёх", как было на самых ранних версиях
README, когда детекторов и правда было всего четыре.

## Файловая структура

```
pyproject.toml                 # единственный источник правды по зависимостям/точкам входа
ora2pg_gap_report/
├── models.py                  # Finding — общая структура находки для всех детекторов
├── plsql_lex.py                # общая инфраструктура: маскирование строк/комментариев
│                               # (включая q-quote) в двух видах — безопасном и с видимым
│                               # аргументом EXECUTE IMMEDIATE, сопоставление блоков
│                               # BEGIN/CASE/IF/LOOP...END, разбор идентификаторов —
│                               # используется всеми детекторами
├── oracle_connector.py         # живая выгрузка PACKAGE BODY/TRIGGER через DBMS_METADATA.GET_DDL
├── oracle_export.py            # консольная команда ora2pg-gap-export
├── detectors/
│   ├── autonomous_tx.py        # PRAGMA AUTONOMOUS_TRANSACTION в PACKAGE BODY
│   ├── compound_triggers.py    # COMPOUND TRIGGER — тихий провал парсинга у ora2pg
│   ├── dbms_utl_calls.py       # классификатор конкретных DBMS_*/UTL_* функций
│   ├── connect_by.py            # линтинг сгенерированного WITH RECURSIVE (нужен ora2pg)
│   ├── merge_delete_clause.py   # MERGE ... DELETE WHERE — не имеет аналога в MERGE PostgreSQL
│   ├── bulk_collect.py          # TYPE ... IS TABLE OF / BULK COLLECT INTO / FORALL
│   ├── database_link.py         # table@dblink_name — прямая ссылка на удалённую БД
│   ├── model_clause.py          # MODEL PARTITION BY / DIMENSION BY / MEASURES / RULES
│   ├── pivot_clause.py          # PIVOT / UNPIVOT
│   ├── object_type.py           # CREATE TYPE ... AS OBJECT / TYPE BODY
│   ├── with_function.py         # WITH FUNCTION / WITH PROCEDURE
│   ├── flashback_query.py       # AS OF TIMESTAMP / AS OF SCN
│   ├── global_temp_table.py     # CREATE GLOBAL TEMPORARY TABLE — теряется ON COMMIT
│   ├── table_partitioning.py    # PARTITION BY RANGE/LIST/HASH — отбрасывается целиком
│   ├── connect_by_nocycle.py    # CONNECT BY NOCYCLE / ORDER SIBLINGS BY
│   ├── context_object.py        # CREATE CONTEXT — application context
│   ├── insert_all.py            # INSERT ALL / INSERT FIRST — многотабличная вставка
│   ├── json_table.py            # JSON_TABLE(...) — нет в PostgreSQL 16 и старше
│   ├── external_table.py        # CREATE TABLE ... ORGANIZATION EXTERNAL
│   ├── sql_macro.py             # SQL_MACRO — конвертируется в обычную функцию
│   ├── invisible_column.py      # столбец INVISIBLE теряет своё скрытие
│   ├── collection_type.py       # CREATE TYPE ... TABLE OF / VARRAY OF
│   ├── cross_apply.py           # CROSS APPLY / OUTER APPLY
│   ├── oracle_text.py           # Oracle Text — INDEXTYPE / CONTAINS / CATSEARCH / MATCHES
│   ├── recursive_with.py        # рекурсивная WITH без RECURSIVE
│   ├── invisible_index.py       # INVISIBLE-индекс
│   ├── read_only_table.py       # CREATE TABLE ... READ ONLY
│   ├── materialized_view_log.py # CREATE MATERIALIZED VIEW LOG
│   ├── identity_column.py       # GENERATED ... AS IDENTITY (...) — баг двойных скобок
│   ├── rowid_type.py            # ROWID/UROWID как тип столбца — конвертируется в oid
│   ├── sequence_cycle.py        # CREATE SEQUENCE ... CYCLE — секция отбрасывается
│   ├── default_on_null.py       # DEFAULT ... ON NULL — копируется verbatim, syntax error
│   ├── public_synonym.py        # CREATE [PUBLIC] SYNONYM — теряет схему целевого объекта
│   ├── virtual_column.py        # GENERATED ALWAYS AS (...) VIRTUAL — теряет защиту ORA-54016
│   ├── nested_subprogram.py     # локальная вложенная процедура/функция — портится при экспорте
│   ├── conditional_compilation.py # $IF/$ELSIF/$ELSE/$END — копируются verbatim
│   ├── package_state.py         # пакетная переменная — сломанная эмуляция через set_config
│   └── index_organized_table.py # ORGANIZATION INDEX (IOT) — отбрасывается
├── ora2pg_wrapper.py            # запуск ora2pg по типам объектов, парсинг --estimate_cost
├── i18n.py                     # язык вывода (--lang/--set-lang): резолюция, английские
│                               # строки UI и переводы объяснений детекторов
├── verification.py             # --verify: детекторный (не построчный) статус
│                               # STILL_PRESENT/NOT_DETECTED/NOT_VERIFIABLE
├── cli.py                      # консольная команда ora2pg-gap-report
├── effort_estimator.py          # грубая эвристика по severity, диапазон часов
├── report_generator.py          # JSON + Markdown (машиночитаемые форматы)
└── terminal_report.py           # цветной вывод через rich (единственная зависимость;
                                 #  библиотеки-детекторов не касается, только CLI)
tests/
├── fixtures/                   # реальные захваченные прогоны ora2pg — тесты парсера не требуют
│                               # установленного ora2pg, кроме нескольких live-тестов
│                               # (пропускаются автоматически, если ora2pg не найден в PATH)
docs/research/                  # эмпирическая проверка предпосылок, реальные PL/SQL примеры
docs/examples/                  # примеры вывода детекторов на реальных данных
scripts/
├── build_offline_bundle.py     # сборка автономного архива для установки без интернета
├── oracle-test-compose.yml     # Oracle Free 23ai в Docker для живой проверки
├── setup_oracle_test_schema.sql
└── verify_against_live_oracle.py
.github/workflows/tests.yml     # CI: pytest на 3.10-3.13 + сборка и smoke-test пакета
```

## Конструкции, спрятанные в динамическом SQL

Инструмент — статический анализатор: он ищет синтаксические паттерны в
тексте, а не анализирует семантику выполнения. Один реальный частный
случай этого ограничения — конструкция, построенная как строка внутри
`EXECUTE IMMEDIATE`, обычной масштабной маскировкой строк/комментариев
не видна вообще (маскировка намеренно ослепляет содержимое всех
строковых литералов, чтобы ключевые слова не находились внутри
комментария или обычной строки).

14 детекторов, использующих общий индекс "какой объект окружает эту
позицию" (`bulk_collect`, `connect_by_nocycle`, `cross_apply`,
`database_link`, `flashback_query`, `insert_all`, `json_table`,
`merge_delete_clause`, `model_clause`, `oracle_text`, `pivot_clause`,
`recursive_with`, `sql_macro`, `with_function`), и отдельно
`autonomous_tx` (свой собственный, не общий механизм отслеживания границ
процедур) теперь используют второй, отдельный вид маскировки
(`mask_dynamic_sql_visible()` в `plsql_lex.py`), в котором именно
аргумент `EXECUTE IMMEDIATE` — одиночный литерал или конкатенация
`'...' || выражение || '...'`, вплоть до первой "голой" `;` — остаётся
видимым, а не заменяется пробелами. Подтверждено на реальном открытом
коде: у `utPLSQL` нашлась и скрытая `PRAGMA AUTONOMOUS_TRANSACTION`
(внутри динамически создаваемого пакета), и скрытый `BULK COLLECT INTO`
(внутри динамически выполняемого анонимного блока) — оба теперь
находятся, оба верно приписаны реальной, находимой в дереве исходников
процедуре (не вымышленному объекту, который существует только в момент
выполнения) — регрессионные тесты на этих же настоящих фрагментах лежат
в `tests/test_autonomous_tx.py`/`tests/test_bulk_collect.py`.

Важно, что индекс "какой объект окружает эту позицию" при этом всегда
строится из безопасного, полностью замаскированного текста, а не из
текста с видимым динамическим SQL — иначе пакет/процедура, которую
код создаёт динамически в момент выполнения, была бы принята за
настоящий объект, объявленный в дереве исходников, и испортила бы
атрибуцию не связанных с ней находок несуществующим в статике именем.
Эта деталь дизайна закреплена тестом
`test_dynamic_sql_that_creates_a_package_at_runtime_is_not_picked_up_as_a_real_container`
в `tests/test_plsql_lex.py`.

Не покрыто этим же способом: детекторы схемного уровня (`table_partitioning`,
`external_table`, `invisible_column` и т.д., включая часть `oracle_text`,
отвечающую за `CREATE INDEX ... INDEXTYPE`) по-прежнему не видят
одноимённую DDL-конструкцию, если она построена динамически — на
практике редкий случай (DDL почти всегда статичен), но не проверенный
эмпирически с той же строгостью, поэтому честно остаётся вне рамок этого
исправления, а не тихо считается решённым заодно.

Даже там, где видимость динамического SQL есть, у неё есть свои
границы. `mask_dynamic_sql_visible()` видит только сам аргумент
`EXECUTE IMMEDIATE` — одиночный строковый литерал или конкатенацию
`'...' || выражение || '...'` прямо в вызове. Если текст запроса
собирается по частям в переменную несколькими отдельными операторами
до самого `EXECUTE IMMEDIATE` (`l_sql := 'BULK'; l_sql := l_sql ||
' COLLECT INTO ...'; ... EXECUTE IMMEDIATE l_sql;`), видна только
финальная переменная — то, как именно она была собрана, не
отслеживается. И отдельно: динамический SQL через старый API
`DBMS_SQL.PARSE`/`DBMS_SQL.EXECUTE` (не `EXECUTE IMMEDIATE`) не
поддержан вообще — ни один детектор его не ищет. Оба случая на
практике реже, чем прямой `EXECUTE IMMEDIATE` с литералом или
конкатенацией (которого достаточно для реальных находок в `utPLSQL`,
см. выше), но не проверены эмпирически с той же строгостью.

## Пост-миграционная проверка (`--verify`)

`--verify` сравнивает pre-migration находки (снапшот `--save`) с тем, что
статически видно в уже сгенерированном ora2pg PostgreSQL-коде — на
уровне детектора, не отдельной находки (сопоставление по файлу/объекту/
фрагменту, как в `baseline.py`, не переживает границу Oracle→PostgreSQL:
ora2pg переименовывает объекты — например, `autonomous_tx` в своей
dblink-стратегии добавляет суффикс `_atx` — и файл в любом случае другой).
Реализовано в `verification.py`.

Не поведенческая/функциональная проверка: инструмент не подключается ни
к одной из баз, ничего не выполняет, не сравнивает данные. Он просто
запускает те же детекторы на сгенерированном файле вместо исходного
Oracle-файла — и это работает не для всех 38 детекторов одинаково,
потому что не все конструкции одинаково переживают конвертацию:

- **`VERBATIM`** (15 детекторов) — `ora2pg` копирует помеченную
  Oracle-конструкцию в вывод практически без изменений (подтверждено по
  собственному research-документу каждого детектора, разделу «что
  делает ora2pg»): `bulk_collect`, `conditional_compilation`,
  `cross_apply`, `database_link`, `dbms_utl_calls`, `default_on_null`,
  `flashback_query`, `identity_column`, `insert_all`, `json_table`,
  `merge_delete_clause`, `model_clause`, `object_type`, `pivot_clause`,
  `recursive_with`. Для них повторный прогон того же детектора по
  сгенерированному файлу — реальная проверка: `STILL_PRESENT`, если
  паттерн остался, `NOT_DETECTED`, если пропал.

- **`NOT_VERIFIABLE`** (22 детектора) — `ora2pg` либо целиком
  отбрасывает конструкцию или полностью переписывает её в другую форму
  (`read_only_table`, `table_partitioning`, `invisible_column`,
  `invisible_index`, `external_table`, `collection_type`,
  `context_object`, `materialized_view_log`, `sql_macro`, `rowid_type`,
  `sequence_cycle`, `index_organized_table`, `public_synonym` — конструкция переписывается в
  `CREATE VIEW`, ключевые слова `SYNONYM`/`FOR` не переживают
  конвертацию, `virtual_column` — конструкция переписывается в обычный
  столбец + триггер, `GENERATED ALWAYS AS ... VIRTUAL` не переживает
  конвертацию, `package_state` — пакетная переменная переписывается в
  вызовы `set_config`/`current_setting`, само объявление не переживает
  конвертацию — конкретное ключевое слово/тип, которое ищет детектор,
  физически не может оказаться в выводе ни при какой миграции, вне
  зависимости от того, решил ли кто-то проблему вручную другим
  способом), либо настолько разваливает окружающую структуру
  (`with_function`, `connect_by_nocycle`, `nested_subprogram` —
  вложенность полностью расплющивается при экспорте, повторное
  обнаружение самой структуры нельзя доверять — см. их собственные
  research-документы, «разваливает структуру»), что чистое повторное
  обнаружение нельзя доверять. `oracle_text` смешанный (сам
  домен-индекс отбрасывается, вызовы `CONTAINS`/`CATSEARCH`/`MATCHES`
  копируются как есть) и консервативно отнесён целиком к
  `NOT_VERIFIABLE`. `autonomous_tx` — по другой причине: его находка
  вообще не про форму кода, а про недооценку стоимости в
  `SHOW_REPORT`/`--estimate_cost`, там нечего перепроверять
  постфактум. Для всех них показывать `NOT_DETECTED` было бы
  тавтологией (конструкции гарантированно не будет в выводе на *любой*
  миграции) — вместо этого `--verify` явно говорит `NOT_VERIFIABLE`.

- **`connect_by`** не входит ни в одну из категорий: он и так анализирует
  только сгенерированный код (`--check-connect-by`), поэтому у него нет
  отдельной pre-migration Oracle-находки, с которой `--verify` могло бы
  сравнивать.

`scripts/doctor.py` сверяет, что у каждого реального детектора на диске
есть запись в `VERIFICATION_MODE` — тот же класс проверки, что и для
`EXPLANATION_EN`/`REMEDIATION_HINT_EN`.

Таблица режима по каждому конкретному gap'у (не только по категориям, как
здесь) — [`docs/verification-capability-matrix.md`](verification-capability-matrix.md).
