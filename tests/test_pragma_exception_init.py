from ora2pg_gap_report.detectors.pragma_exception_init import find_pragma_exception_init


def test_a_pragma_exception_init_is_flagged():
    source = (
        "CREATE OR REPLACE PROCEDURE ins_one IS\n"
        "  dup_key EXCEPTION;\n"
        "  PRAGMA EXCEPTION_INIT(dup_key, -1);\n"
        "BEGIN\n"
        "  INSERT INTO uniq_t (id) VALUES (1);\n"
        "END;\n"
    )
    findings = find_pragma_exception_init(source)
    assert len(findings) == 1
    assert findings[0].object_name == "INS_ONE"
    assert findings[0].snippet == "PRAGMA EXCEPTION_INIT(DUP_KEY, -1)"
    assert findings[0].severity == "high"
    assert findings[0].line == 3


def test_the_ora_number_is_carried_into_the_snippet():
    # Both -1 and -60 were verified to collapse onto the same placeholder
    # SQLSTATE, so keeping the real number visible in the report matters.
    source = "DECLARE\n  PRAGMA EXCEPTION_INIT(deadlock_detected, -60);\nBEGIN\n NULL;\nEND;\n"
    assert find_pragma_exception_init(source)[0].snippet.endswith("-60)")


def test_extra_whitespace_is_tolerated():
    source = "PRAGMA   EXCEPTION_INIT ( e , -54 )\n"
    assert len(find_pragma_exception_init(source)) == 1


def test_another_pragma_is_not_flagged():
    source = "CREATE PACKAGE p IS\n  PRAGMA SERIALLY_REUSABLE;\nEND p;\n"
    assert find_pragma_exception_init(source) == []


def test_a_plain_exception_declaration_is_not_flagged():
    assert find_pragma_exception_init("DECLARE\n  e EXCEPTION;\nBEGIN\n NULL;\nEND;\n") == []


def test_real_open_source_logger_pragma_is_flagged():
    # Real shape from OraOpenSource/Logger (logger.pkb around line 296):
    # a user-defined exception bound to ORA-02003 and caught by name. This
    # is what the gap costs in practice -- after conversion the handler
    # would wait for a SQLSTATE PostgreSQL never raises, and the error
    # would escape instead of being swallowed as the author intended.
    source = (
        "      l_value varchar2(100);\n"
        "\n"
        "      invalid_userenv_parm exception;\n"
        "      pragma exception_init(invalid_userenv_parm, -2003);\n"
        "\n"
        "    begin\n"
        "      l_value := sys_context('USERENV', p_parm);\n"
        "    exception\n"
        "      when invalid_userenv_parm then\n"
        "        return null;\n"
        "    end;\n"
    )
    findings = find_pragma_exception_init(source)
    assert len(findings) == 1
    assert findings[0].snippet == "PRAGMA EXCEPTION_INIT(INVALID_USERENV_PARM, -2003)"
    assert findings[0].line == 4
