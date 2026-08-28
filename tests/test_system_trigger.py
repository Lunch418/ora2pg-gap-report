from ora2pg_gap_report.detectors.system_trigger import find_system_triggers


def test_a_logon_trigger_on_database_is_flagged():
    source = (
        "CREATE OR REPLACE TRIGGER trg_logon\n"
        "AFTER LOGON ON DATABASE\n"
        "BEGIN\n"
        "  INSERT INTO login_audit (who, when_) VALUES (USER, SYSDATE);\n"
        "END;\n"
    )
    findings = find_system_triggers(source)
    assert len(findings) == 1
    assert findings[0].object_name == "TRG_LOGON"
    assert findings[0].snippet == "ON DATABASE"
    assert findings[0].severity == "high"
    assert findings[0].line == 2


def test_a_ddl_trigger_on_schema_is_flagged():
    source = (
        "CREATE OR REPLACE TRIGGER trg_ddl\n"
        "BEFORE DDL ON SCHEMA\n"
        "BEGIN\n"
        "  NULL;\n"
        "END;\n"
    )
    findings = find_system_triggers(source)
    assert len(findings) == 1
    assert findings[0].snippet == "ON SCHEMA"


def test_a_servererror_trigger_is_flagged_without_an_event_keyword_list():
    # The detector keys off the scope, not the event, so events it was
    # never told about are still covered.
    source = "CREATE TRIGGER trg_err\nAFTER SERVERERROR ON DATABASE\nBEGIN\n NULL;\nEND;\n"
    assert len(find_system_triggers(source)) == 1


def test_an_ordinary_table_trigger_is_not_flagged():
    source = (
        "CREATE OR REPLACE TRIGGER trg_emp\n"
        "BEFORE INSERT ON employees\n"
        "FOR EACH ROW\n"
        "BEGIN\n"
        "  :NEW.created := SYSDATE;\n"
        "END;\n"
    )
    assert find_system_triggers(source) == []


def test_the_words_in_the_trigger_body_do_not_trigger_a_finding():
    # `ON DATABASE` appearing after BEGIN is out of the header window.
    source = (
        "CREATE TRIGGER trg_emp\n"
        "BEFORE INSERT ON employees FOR EACH ROW\n"
        "BEGIN\n"
        "  INSERT INTO audit (note) VALUES (comment_on_database);\n"
        "END;\n"
    )
    assert find_system_triggers(source) == []


def test_one_finding_per_trigger_not_one_per_scope_word():
    source = (
        "CREATE TRIGGER a\nAFTER LOGON ON DATABASE\nBEGIN\n NULL;\nEND;\n"
        "CREATE TRIGGER b\nAFTER LOGOFF ON DATABASE\nBEGIN\n NULL;\nEND;\n"
    )
    findings = find_system_triggers(source)
    assert [f.object_name for f in findings] == ["A", "B"]


def test_real_open_source_utplsql_ddl_trigger_is_flagged():
    # Real shape from utPLSQL
    # (source/core/annotations/ut_trigger_annotation_parsing.trg): a DDL
    # system trigger whose scope keyword sits on its own line.
    source = (
        "create or replace trigger ut_trigger_annotation_parsing\n"
        "  after create or alter or drop\n"
        "on database\n"
        "begin\n"
        "  null;\n"
        "end;\n"
    )
    findings = find_system_triggers(source)
    assert len(findings) == 1
    assert findings[0].object_name == "UT_TRIGGER_ANNOTATION_PARSING"
    assert findings[0].line == 3
