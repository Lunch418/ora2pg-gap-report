*[English](ARCHITECTURE.md) | Русский*

# Архитектура

Этот документ — про то, как устроен инструмент внутри: лексер,
маскирование, атрибуция находок, обработка динамического SQL, файловая
структура. Для "что это и зачем" — см. [README.md](../README.ru.md); для
"как разрабатывать/тестировать" — см. [DEVELOPMENT.md](DEVELOPMENT.ru.md).

`ora2pg SHOW_REPORT` целиком не имеет офлайн-режима — он требует живого
подключения к Oracle (`ORACLE_DSN`). Офлайн от DDL-дампа работает только
анализ *отдельных типов объектов* (`-t PACKAGE`, `-t TRIGGER`, `-t FUNCTION`,
…) — именно так работает `ora2pg_wrapper.py`, а не через `SHOW_REPORT`. Это
принципиально для целевой аудитории — закрытые контуры, air-gapped среды,
госсектор.

Детекторов сейчас 124 (полная таблица — в README.md, «Детекторы»; 123 из
них привязаны к зарегистрированному GAP-NNN, `dbms_utl_calls` — нет, см.
README.md, «Почему почти всё high»), в трёх исходных диалектах: 79 Oracle,
25 MySQL/MariaDB (`ora2pg -m`) и 19 T-SQL/SQL Server (`ora2pg -M`). У
каждого диалекта свой лексер (`plsql_lex.py`, `mysql_lex.py`,
`mssql_lex.py`) и свой кортеж детекторов в `core.py`; они разделены
структурно, так что файл, просканированный не с тем `--dialect`, не может
вызвать детекторы другого диалекта. Почти все детекторы устроены
одинаково: анализируют исходник напрямую и не требуют установленного
`ora2pg` — чистый Python, без внешних зависимостей. Исключение ровно
одно — `connect_by`: он устроен иначе, линтит *сгенерированный* ora2pg-код,
а не исходник (ora2pg сам неплохо считает CONNECT BY — ценность не в
обнаружении, а в проверке качества конвертации), поэтому ему нужен
реальный `ora2pg` и он подключается только через `--check-connect-by`. Это
единственный детектор с таким требованием — не "один из четырёх", как было
на самых ранних версиях README, когда детекторов и правда было всего
четыре.

## Файловая структура

```
pyproject.toml                 # единственный источник правды по зависимостям/точкам входа
ora2pg_gap_report/
├── models.py                  # Finding — общая структура находки для всех детекторов
├── detector_spec.py            # DetectorSpec + build(): пять стратегий сканирования, из
│                               # которых собраны декларативные детекторы (см. DEVELOPMENT.md)
├── messages.py                 # тексты каждой находки на ru/en, по идентификатору сообщения
├── lex_common.py               # части лексера, общие для всех диалектов, -- line_at, парные
│                               # скобки, границы списка столбцов, -- плюс протокол Lexer, по
│                               # которому build() проверяет лексер диалекта
├── plsql_lex.py                # общая инфраструктура: маскирование строк/комментариев
│                               # (включая q-quote) в двух видах — безопасном и с видимым
│                               # аргументом EXECUTE IMMEDIATE, сопоставление блоков
│                               # BEGIN/CASE/IF/LOOP...END, разбор идентификаторов —
│                               # используется всеми детекторами
├── oracle_connector.py         # живая выгрузка схемы (13 типов объектов) через DBMS_METADATA.GET_DDL
├── oracle_export.py            # консольная команда ora2pg-gap-export
├── detectors/
│   ├── autonomous_tx.py           # PRAGMA AUTONOMOUS_TRANSACTION в PACKAGE BODY
│   ├── compound_triggers.py       # COMPOUND TRIGGER — тихий провал парсинга у ora2pg
│   ├── dbms_utl_calls.py          # классификатор конкретных DBMS_*/UTL_* функций
│   ├── connect_by.py              # линтинг сгенерированного WITH RECURSIVE (нужен ora2pg)
│   ├── merge_delete_clause.py     # MERGE ... DELETE WHERE — не имеет аналога в MERGE PostgreSQL
│   ├── bulk_collect.py            # TYPE ... IS TABLE OF / BULK COLLECT INTO / FORALL
│   ├── database_link.py           # table@dblink_name — прямая ссылка на удалённую БД
│   ├── model_clause.py            # MODEL PARTITION BY / DIMENSION BY / MEASURES / RULES
│   ├── pivot_clause.py            # PIVOT / UNPIVOT
│   ├── object_type.py             # CREATE TYPE ... AS OBJECT / TYPE BODY
│   ├── with_function.py           # WITH FUNCTION / WITH PROCEDURE
│   ├── flashback_query.py         # AS OF TIMESTAMP / AS OF SCN
│   ├── global_temp_table.py       # CREATE GLOBAL TEMPORARY TABLE — теряется ON COMMIT
│   ├── table_partitioning.py      # PARTITION BY RANGE/LIST/HASH — отбрасывается целиком
│   ├── connect_by_nocycle.py      # CONNECT BY NOCYCLE / ORDER SIBLINGS BY
│   ├── context_object.py          # CREATE CONTEXT — application context
│   ├── insert_all.py              # INSERT ALL / INSERT FIRST — многотабличная вставка
│   ├── json_table.py              # JSON_TABLE(...) — нет в PostgreSQL 16 и старше
│   ├── external_table.py          # CREATE TABLE ... ORGANIZATION EXTERNAL
│   ├── sql_macro.py               # SQL_MACRO — конвертируется в обычную функцию
│   ├── invisible_column.py        # столбец INVISIBLE теряет своё скрытие
│   ├── collection_type.py         # CREATE TYPE ... TABLE OF / VARRAY OF
│   ├── cross_apply.py             # CROSS APPLY / OUTER APPLY
│   ├── oracle_text.py             # Oracle Text — INDEXTYPE / CONTAINS / CATSEARCH / MATCHES
│   ├── recursive_with.py          # рекурсивная WITH без RECURSIVE
│   ├── invisible_index.py         # INVISIBLE-индекс
│   ├── read_only_table.py         # CREATE TABLE ... READ ONLY
│   ├── materialized_view_log.py   # CREATE MATERIALIZED VIEW LOG
│   ├── identity_column.py         # GENERATED ... AS IDENTITY (...) — баг двойных скобок
│   ├── rowid_type.py              # ROWID/UROWID как тип столбца — конвертируется в oid
│   ├── sequence_cycle.py          # CREATE SEQUENCE ... CYCLE — секция отбрасывается
│   ├── default_on_null.py         # DEFAULT ... ON NULL — копируется verbatim, syntax error
│   ├── public_synonym.py          # CREATE [PUBLIC] SYNONYM — теряет схему целевого объекта
│   ├── virtual_column.py          # GENERATED ALWAYS AS (...) VIRTUAL — теряет защиту ORA-54016
│   ├── nested_subprogram.py       # локальная вложенная процедура/функция — портится при экспорте
│   ├── conditional_compilation.py # $IF/$ELSIF/$ELSE/$END — копируются verbatim
│   ├── package_state.py           # пакетная переменная — сломанная эмуляция через set_config
│   ├── index_organized_table.py   # ORGANIZATION INDEX (IOT) — отбрасывается
│   ├── match_recognize.py         # MATCH_RECOGNIZE — сопоставление с шаблоном, аналога в PG нет
│   ├── connect_by_pseudocolumn.py # CONNECT_BY_ROOT/ISLEAF/ISCYCLE — переносятся без конвертации
│   ├── keep_dense_rank.py         # KEEP (DENSE_RANK FIRST/LAST ORDER BY ...) — модификатор агрегата
│   ├── multiset_operator.py       # CAST(MULTISET(...)), MULTISET UNION, MEMBER OF, SUBMULTISET OF
│   ├── sample_clause.py           # SAMPLE (n) — в PG это TABLESAMPLE, ora2pg не конвертирует
│   ├── accessible_by.py           # ACCESSIBLE BY — копируется в заголовок сгенерированной функции
│   ├── local_time_zone.py         # TIMESTAMP WITH LOCAL TIME ZONE — становится простым timestamp
│   ├── temporal_validity.py       # PERIOD FOR — превращается в обрубок `period FOR`
│   ├── bitmap_index.py            # CREATE BITMAP INDEX — становится USING gin без класса операторов
│   ├── object_table.py            # CREATE TABLE ... OF <тип> — OF становится именем столбца
│   ├── ignore_nulls.py            # IGNORE/RESPECT NULLS — такого синтаксиса в PostgreSQL 16 нет
│   ├── nlssort.py                 # NLSSORT — становится COLLATE с несуществующим именем
│   ├── long_raw_type.py           # LONG RAW — отображается в text вместо документированного bytea
│   ├── anydata_type.py            # SYS.ANYDATA — имя типа копируется, схемы SYS нет
│   ├── system_trigger.py          # триггеры ON DATABASE/SCHEMA — выводятся как табличные
│   ├── trigger_follows.py         # FOLLOWS/PRECEDES — попадает внутрь тела функции триггера
│   ├── table_collection.py        # TABLE(...) — разворот коллекции, копируется как есть
│   ├── cursor_expression.py       # CURSOR(SELECT ...) — копируется как есть, аналога нет
│   ├── for_update_wait.py         # FOR UPDATE ... WAIT n — есть только NOWAIT/SKIP LOCKED
│   ├── rownum_dml.py              # ROWNUM в UPDATE/DELETE — превращается в недопустимый LIMIT
│   ├── to_date_rr.py              # формат RR в TO_DATE — молча даёт 1 год до нашей эры
│   ├── authid_clause.py           # AUTHID — процедура молча пропадает целиком
│   ├── pragma_exception_init.py   # PRAGMA EXCEPTION_INIT — обработчик получает чужой SQLSTATE
│   ├── subtype_range.py           # SUBTYPE ... RANGE — переносится в CREATE DOMAIN дословно
│   ├── alt_quote_literal.py       # q'[...]' — альтернативные кавычки, копируются как есть
│   ├── goto_statement.py          # GOTO — в PL/pgSQL такого оператора нет
│   ├── cursor_rowtype.py          # <курсор>%ROWTYPE — PL/pgSQL допускает только таблицу/представление
│   ├── wm_concat.py               # WM_CONCAT — копируется как есть, в отличие от LISTAGG
│   ├── read_only_view.py          # WITH READ ONLY — выбрасывается, представление становится обновляемым
│   ├── sdo_geometry.py            # SDO_GEOMETRY — тип PostGIS без CREATE EXTENSION
│   ├── table_if_not_exists.py     # CREATE TABLE IF NOT EXISTS из 23ai — становится таблицей `if`
│   ├── identity_on_null.py        # GENERATED BY DEFAULT ON NULL AS IDENTITY — ON NULL теряется
│   ├── package_constant_chain.py  # константа пакета из другой константы -- склеивается, не загружается
│   ├── ref_cursor_type.py         # TYPE ... IS REF CURSOR -- невалидный CREATE TYPE ... AS REFCURSOR
│   ├── repeated_package_call.py   # повторный pkg.proc; без скобок -- теряет CALL
│   ├── trigger_package_call.py    # вызов процедуры пакета из триггера -- копируется без CALL
│   ├── statement_trigger.py       # триггер уровня команды -- становится FOR EACH ROW
│   ├── package_constant_default.py  # константа пакета в умолчании параметра -- копируется, не загружается
│   ├── package_type_anchor.py   # %TYPE в RECORD/SUBTYPE пакета -- копируется в CREATE TYPE/DOMAIN
│   ├── package_type_reference.py  # тип пакета в его подпрограммах без имени пакета
│   ├── supplied_package_call.py  # процедура DBMS_/UTL_/HTP как оператор -- без CALL
│   ├── dbms_sleep.py            # DBMS_LOCK.SLEEP -> pg_sleep(n); без PERFORM (чинит --fix)
│   │                             # -- диалект MySQL/MariaDB (ora2pg -m; см. mysql_lex.py) --
│   ├── mysql_enum_type.py         # ENUM(...) -- нет CREATE TYPE для синтезированного типа
│   ├── mysql_on_update_current_timestamp.py  # ON UPDATE CURRENT_TIMESTAMP -- копируется в DEFAULT как есть
│   ├── mysql_on_duplicate_key_update.py      # ON DUPLICATE KEY UPDATE -- аналога в PostgreSQL нет, копируется как есть
│   ├── mysql_signal.py            # SIGNAL/RESIGNAL -- такого оператора в PL/pgSQL нет
│   ├── mysql_fulltext_index.py    # FULLTEXT KEY/INDEX -- выбрасывается, ключевые слова читаются как столбец
│   ├── mysql_key_index.py         # KEY <имя> (<столбцы>) -- запись mysqldump, ломает CREATE TABLE
│   ├── mysql_spatial_index.py     # SPATIAL KEY/INDEX -- выбрасывается, ключевые слова читаются как столбец
│   ├── mysql_limit_comma.py       # LIMIT n, m -- форму с запятой PostgreSQL отвергает
│   ├── mysql_replace_into.py      # REPLACE INTO -- копируется как есть, аналога в PostgreSQL нет
│   ├── mysql_insert_ignore.py     # INSERT IGNORE -- копируется как есть, такого синтаксиса INSERT нет
│   ├── mysql_prepare_from.py      # PREPARE ... FROM -- PREPARE в PostgreSQL пишется иначе
│   ├── mysql_last_insert_id.py    # LAST_INSERT_ID() -- такой функции в PostgreSQL нет
│   ├── mysql_auto_increment_start.py  # AUTO_INCREMENT=<n> -- старт последовательности теряется, PK сталкивается
│   ├── mysql_date_format.py       # DATE_FORMAT(...) -- становится конструктором строки, молча неверно
│   ├── mysql_foreign_key.py       # FOREIGN KEY -- выбрасывается целиком, целостность молча пропадает
│   ├── mysql_zero_date.py         # '0000-00-00' -- молча переписывается в настоящую 1970-01-01
│   ├── mysql_declare_handler.py   # DECLARE ... HANDLER -- выбрасывается, обработка ошибок исчезает
│   ├── mysql_collate.py           # COLLATE/CHARACTER SET -- выбрасывается, сравнения меняют смысл
│   ├── mysql_set_type.py          # SET(...) -- становится обычным text, проверка теряется
│   ├── mysql_delimiter_routine.py # подпрограмма под DELIMITER -- разделитель попадает в тело
│   ├── mysql_delimiter_trigger.py # триггер под DELIMITER // или $$ -- не генерируется вовсе
│   ├── mysql_definer_procedure.py # CREATE DEFINER=... PROCEDURE -- пропускается в -t PROCEDURE
│   ├── mysql_versioned_comment.py # объект внутри /*!50003 ... */ -- удаляется с комментариями
│   ├── mysql_create_table_if_not_exists.py  # CREATE TABLE IF NOT EXISTS -- таблица `if`
│   ├── mysql_temporary_table.py   # CREATE TEMPORARY TABLE -- постоянная и общая
│   │                             # -- диалект MSSQL / T-SQL (ora2pg -M; см. mssql_lex.py) --
│   ├── mssql_bracket_identifier.py    # [dbo].[Orders] -- скобки остаются в имени, ломается всё
│   ├── mssql_newid_default.py         # NEWID() -- uuid_generate_v4() без CREATE EXTENSION
│   ├── mssql_update_set.py            # UPDATE ... SET -- SET уничтожается, '=' становится ':='
│   ├── mssql_identity_column.py       # IDENTITY(1,1) -- выбрасывается целиком, ни serial, ни последовательности
│   ├── mssql_parameterless_procedure.py  # процедура без параметров получает неразбираемый пустой DECLARE
│   ├── mssql_if_statement.py          # IF -- с блоком нет END IF, без блока нет THEN
│   ├── mssql_raiserror.py             # RAISERROR/THROW -- копируются как есть
│   ├── mssql_try_catch.py             # BEGIN TRY/CATCH -- копируются как есть
│   ├── mssql_top_clause.py            # SELECT TOP n -- копируется как есть, TOP в PostgreSQL нет
│   ├── mssql_scope_identity.py        # SCOPE_IDENTITY()/@@IDENTITY -- копируются как есть
│   ├── mssql_output_clause.py         # OUTPUT INSERTED.* -- копируется как есть, аналог -- RETURNING
│   ├── mssql_iif.py                   # IIF() -- копируется как есть
│   ├── mssql_datediff.py              # DATEDIFF() -- копируется как есть (DATEADD/DATEPART конвертируются)
│   ├── mssql_charindex.py             # CHARINDEX() -- переводится, но с удвоенными кавычками
│   ├── mssql_filtered_index.py        # CREATE INDEX ... WHERE -- выбрасывается, хотя в PostgreSQL он есть
│   ├── mssql_foreign_key.py           # FOREIGN KEY -- выбрасывается целиком, целостность молча пропадает
│   ├── mssql_collation.py             # COLLATE -- выбрасывается, всё становится нечувствительным citext
│   ├── mssql_computed_column.py       # вычисляемый столбец получает тип citext, что бы ни вычислял
│   └── mssql_rowversion.py            # ROWVERSION -> bytea, перестаёт обновляться, блокировка ломается
├── mssql_lex.py                 # лексика диалекта T-SQL (идентификаторы в скобках, вложенные
│                               #  блочные комментарии -- общая основа детекторов mssql_*)
├── mysql_lex.py                 # лексика диалекта MySQL/MariaDB (mask_strings_and_comments,
│                               #  enclosing_object_name_index, delimiter_at -- общая основа
│                               #  детекторов mysql_*). Оба реэкспортируют независимую от
│                               #  диалекта половину lex_common.
├── ora2pg_wrapper.py            # запуск ora2pg по типам объектов, парсинг --estimate_cost
├── i18n.py                     # язык вывода (--lang/--set-lang): резолюция, английские
│                               # строки UI и переводы объяснений детекторов
├── load_check.py               # --load-check: загрузка сгенерированного кода в настоящий
│                               #  PostgreSQL (docker или DSN) в одной откатываемой транзакции,
│                               #  привязка каждой ошибки к GAP-NNN / --fix / более ранней ошибке
├── migrate.py                  # --migrate: скан -> подготовка -> ora2pg по типам -> исправления
│                               #  (-> загрузка), всё в один OUT_DIR
├── prepare.py                  # --prepare: переписывание исходника до ora2pg (DELIMITER, DEFINER,
│                               #  версионные комментарии, [скобки], q-строки), по диалектам
├── recipes.py                  # рецепты миграции (docs/recipes/): какие детекторы покрывает
│                               #  каждый и где страница; отчёты ссылаются на них с пробелов
├── checklist.py                # --format checklist: Markdown-список задач, который хранит
│                               #  отметки между запусками (сначала читает прежний --output)
├── pg_script.py                # разбивает PostgreSQL-скрипт на команды как psql; глушит то,
│                               #  что сломало бы --load-check, не сдвигая номера строк
├── verification.py             # --verify: детекторный (не построчный) статус
│                               # STILL_PRESENT/NOT_DETECTED/NOT_VERIFIABLE
├── core.py                      # scan_source/count_objects/expand_paths/connect_by_check —
├── cli.py                      # консольная команда ora2pg-gap-report
├── effort_estimator.py          # грубая эвристика по severity, диапазон часов
├── html_report.py              # --format html: рельс стадий, каждый пробел один раз, фильтры на CSS
├── report_generator.py          # JSON + Markdown (машиночитаемые форматы)
├── terminal_report.py           # цветной вывод через rich (единственная зависимость;
│                               #  библиотеки-детекторов не касается, только CLI)
└── tui_app.py                   # --tui: интерактивный экран на textual (опциональный
                                 #  extra [tui], не часть базовой установки)
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

## Память на большом сканировании

Каждый формат отчёта пишется прямо в место назначения — в атомарно
открытый файл или в stdout, — а не собирается сначала строкой.
`report_generator.py` даёт для каждого формата обе формы: `to_json()` и
подобные возвращают строку (ими пользуются тесты и `--verify`),
`write_json()` и подобные пишут в поток (ими пользуется сканирование). Это
один и тот же код; `tests/test_streaming_report.py` сравнивает их байт в
байт на обоих языках, для каждого формата, пустого и непустого.

Вторая точка входа стоит того, потому что потолком памяти было не
сканирование, а отчёт. Замер на корпусе из 1 800 файлов с 77 800 находками:

| | до | после |
|---|---|---|
| хранение всех находок | 39 МБ | 39 МБ |
| `--format json` | 246 МБ | 54 МБ |
| `--format csv` | 489 МБ | 54 МБ |
| `--format markdown` | 515 МБ | 54 МБ |
| `--format html` | 582 МБ | 54 МБ |
| `--format sarif` | 682 МБ | 54 МБ |

Платили за две вещи. `json.dumps` — это буквально
`"".join(iterencode(o))`, и для большого документа эта склейка — самое
крупное выделение памяти в процессе: несколько миллионов коротких строк и
список, который их держит. И каждый формат строил полную промежуточную
структуру, по словарю на находку, прежде чем начать кодирование. Запись
окружающего документа один раз и каждого элемента по мере появления
убирает и то, и другое; `_stream_json_with_array()` обрабатывает
JSON-подобные форматы, кодируя документ с заглушкой на месте большого
массива и разрезая его там, так что отступы и экранирование по-прежнему
делает стандартный кодировщик, а не скобки, написанные вручную.

Остаётся сам список находок — примерно 22 КБ на 1 000 находок. Это
настоящий нижний предел, а не недосмотр: `--save`, `--fail-on`,
`--baseline` и сортировка, упорядочивающая отчёт, — всем нужен полный
набор, прежде чем любой из них сможет ответить. Сканирование, достаточно
большое, чтобы это стало важно, потребовало бы сбрасывать находки на диск,
а это другая архитектура, чем эта, и ни одна реальная схема её пока не
потребовала.

## Пост-миграционная проверка (`--verify`)

`--verify` сравнивает pre-migration находки (снапшот `--save`) с тем, что
статически видно в уже сгенерированном ora2pg PostgreSQL-коде — на
уровне детектора, не отдельной находки (сопоставление по файлу/объекту/
фрагменту, как в `baseline.py`, не переживает границу Oracle->PostgreSQL:
ora2pg переименовывает объекты — например, `autonomous_tx` в своей
dblink-стратегии добавляет суффикс `_atx` — и файл в любом случае другой).
Реализовано в `verification.py`.

Не поведенческая/функциональная проверка: инструмент не подключается ни
к одной из баз, ничего не выполняет, не сравнивает данные. Он просто
запускает те же детекторы на сгенерированном файле вместо исходного
Oracle-файла — и это работает не для всех 106 детекторов одинаково,
потому что не все конструкции одинаково переживают конвертацию:

- **`VERBATIM`** (51 детектор) — `ora2pg` копирует помеченную
  конструкцию в вывод практически без изменений (подтверждено по
  собственному research-документу каждого детектора, разделу «что
  делает ora2pg»). Среди них: `bulk_collect`, `conditional_compilation`,
  `cross_apply`, `database_link`, `dbms_utl_calls`, `default_on_null`,
  `flashback_query`, `identity_column`, `insert_all`, `json_table`,
  `merge_delete_clause`, `model_clause`, `object_type`, `pivot_clause`,
  `recursive_with`. Для них повторный прогон того же детектора по
  сгенерированному файлу — реальная проверка: `STILL_PRESENT`, если
  паттерн остался, `NOT_DETECTED`, если пропал.

- **`NOT_VERIFIABLE`** (54 детектора) — `ora2pg` либо целиком
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
здесь) — [`docs/verification-capability-matrix.md`](verification-capability-matrix.ru.md).
