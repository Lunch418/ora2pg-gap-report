from ora2pg_gap_report.detectors.statement_trigger import find_statement_trigger


def test_a_statement_level_dml_trigger_is_flagged():
    source = "CREATE OR REPLACE TRIGGER gx_t_ai AFTER INSERT ON gx_orders\nBEGIN\n  UPDATE gx_fired SET n = n + 1;\nEND;\n/\n"
    assert [(f.object_name, f.line, f.snippet) for f in find_statement_trigger(source)] == [
        ("GX_T_AI", 1, "AFTER INSERT (no FOR EACH ROW)")
    ]


def test_the_get_ddl_spelling_is_flagged():
    # Verbatim from DBMS_METADATA.GET_DDL on a live Oracle 23ai.
    source = (
        '  CREATE OR REPLACE EDITIONABLE TRIGGER "HR"."GX_T_AI" AFTER INSERT ON gx_orders\n'
        "BEGIN\n  UPDATE gx_fired SET n = n + 1;\nEND;\n/\n"
        'ALTER TRIGGER "HR"."GX_T_AI" ENABLE;\n'
    )
    assert [f.object_name for f in find_statement_trigger(source)] == ["GX_T_AI"]


def test_row_instead_of_compound_and_system_triggers_are_not_flagged():
    for source in (
        "CREATE TRIGGER a BEFORE INSERT ON t FOR EACH ROW BEGIN NULL; END;\n/\n",
        "CREATE TRIGGER b BEFORE UPDATE OF x ON t REFERENCING NEW AS n FOR EACH ROW WHEN (n.x > 0) BEGIN NULL; END;\n/\n",
        "CREATE TRIGGER c INSTEAD OF INSERT ON v BEGIN NULL; END;\n/\n",
        "CREATE TRIGGER d FOR INSERT ON t COMPOUND TRIGGER AFTER STATEMENT IS BEGIN NULL; END AFTER STATEMENT; END;\n/\n",
        "CREATE TRIGGER e AFTER LOGON ON DATABASE BEGIN NULL; END;\n/\n",
        "CREATE TRIGGER f BEFORE DROP ON SCHEMA BEGIN NULL; END;\n/\n",
    ):
        assert find_statement_trigger(source) == [], source


def test_multi_event_statement_trigger():
    source = "CREATE TRIGGER g AFTER INSERT OR UPDATE OR DELETE ON t\nBEGIN\n  NULL;\nEND;\n/\n"
    assert [f.snippet for f in find_statement_trigger(source)] == ["AFTER INSERT (no FOR EACH ROW)"]


def test_postgresqls_own_statement_trigger_is_not_flagged():
    # What --migrate writes after restoring a statement-level trigger.
    source = (
        "CREATE TRIGGER gx_t_ai\n\tAFTER INSERT ON gx_orders FOR EACH STATEMENT\n"
        "\tEXECUTE PROCEDURE trigger_fct_gx_t_ai();\n"
        "CREATE OR REPLACE FUNCTION f() RETURNS trigger AS $BODY$\nBEGIN\n  RETURN NULL;\nEND\n$BODY$ LANGUAGE plpgsql;\n"
    )
    assert find_statement_trigger(source) == []
