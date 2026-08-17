from ora2pg_gap_report.detectors.nested_subprogram import find_nested_subprograms


def test_nested_procedure_in_a_standalone_procedure_is_flagged():
    source = (
        "create or replace procedure outer_proc as\n"
        "  procedure inner_proc(p_val number) is\n"
        "  begin\n"
        "    dbms_output.put_line('inner: ' || p_val);\n"
        "  end;\n"
        "begin\n"
        "  inner_proc(42);\n"
        "end;\n"
    )
    findings = find_nested_subprograms(source)
    assert len(findings) == 1
    assert findings[0].object_name == "OUTER_PROC.INNER_PROC"
    assert findings[0].severity == "high"


def test_nested_function_in_a_package_body_member_is_flagged():
    source = (
        "create or replace package body pkg_demo as\n"
        "  procedure outer_proc is\n"
        "    procedure inner_proc(p_val number) is\n"
        "    begin\n"
        "      dbms_output.put_line('inner: ' || p_val);\n"
        "    end;\n"
        "  begin\n"
        "    inner_proc(42);\n"
        "  end;\n"
        "end pkg_demo;\n"
    )
    findings = find_nested_subprograms(source)
    assert len(findings) == 1
    assert findings[0].object_name == "PKG_DEMO.OUTER_PROC.INNER_PROC"


def test_routine_with_no_nested_subprogram_is_not_flagged():
    source = (
        "create or replace procedure outer_proc as\n"
        "  v_x number;\n"
        "begin\n"
        "  v_x := 1;\n"
        "end;\n"
    )
    assert find_nested_subprograms(source) == []


def test_ordinary_package_body_with_only_top_level_members_is_not_flagged():
    # Package-level member routines (matched by the same ROUTINE_START_RE
    # pattern as a genuinely nested one) must not be misdetected as
    # nested just because they share that pattern -- only a routine
    # declared *inside* another routine's own declare section counts.
    source = (
        "create or replace package body pkg_demo as\n"
        "  procedure proc_a is\n"
        "  begin\n"
        "    null;\n"
        "  end;\n"
        "  procedure proc_b is\n"
        "  begin\n"
        "    null;\n"
        "  end;\n"
        "end pkg_demo;\n"
    )
    assert find_nested_subprograms(source) == []


def test_forward_declaration_is_not_confused_with_a_nested_definition():
    # A forward declaration ('PROCEDURE helper;', mutual recursion) has
    # no IS/AS or body of its own -- declare_and_begin()/_own_is_as()
    # already treats it as "not a real definition" and skips past it;
    # this must not surface as a false-positive nested finding either.
    source = (
        "create or replace package body pkg_demo as\n"
        "  procedure helper;\n"
        "  procedure outer_proc is\n"
        "  begin\n"
        "    helper();\n"
        "  end;\n"
        "  procedure helper is\n"
        "  begin\n"
        "    null;\n"
        "  end;\n"
        "end pkg_demo;\n"
    )
    assert find_nested_subprograms(source) == []


def test_multiple_nested_subprograms_in_one_outer_routine_are_each_flagged():
    source = (
        "create or replace procedure outer_proc as\n"
        "  procedure inner_a is\n"
        "  begin\n"
        "    null;\n"
        "  end;\n"
        "  procedure inner_b is\n"
        "  begin\n"
        "    null;\n"
        "  end;\n"
        "begin\n"
        "  inner_a();\n"
        "  inner_b();\n"
        "end;\n"
    )
    findings = find_nested_subprograms(source)
    assert len(findings) == 2
    names = {f.object_name for f in findings}
    assert names == {"OUTER_PROC.INNER_A", "OUTER_PROC.INNER_B"}


def test_grant_statement_privilege_list_is_not_misread_as_a_routine_declaration():
    # 'GRANT CREATE PROCEDURE TO oe;' matches STANDALONE_ROUTINE_RE's own
    # 'CREATE ... PROCEDURE name' shape if the GRANT/REVOKE guard is
    # missing -- the phantom match (name captured as the grantee, 'TO')
    # would then consume the real routine that follows via
    # declare_and_begin(), corrupting attribution for its own real
    # nested finding. A GRANT statement (hand-written in a migration
    # script, not DBMS_METADATA.GET_DDL-exported) realistically has its
    # own trailing ';' -- confirmed against the real example
    # is_inside_grant_or_revoke_statement()'s own docstring cites
    # (oracle-samples/db-sample-schemas's hr_code.sql).
    source = (
        "grant create procedure to oe;\n"
        "\n"
        "create or replace procedure real_proc as\n"
        "  procedure inner_x is\n"
        "  begin\n"
        "    null;\n"
        "  end;\n"
        "begin\n"
        "  inner_x();\n"
        "end;\n"
    )
    findings = find_nested_subprograms(source)
    assert len(findings) == 1
    assert findings[0].object_name == "REAL_PROC.INNER_X"


def test_real_open_source_logger_nested_procedure_inside_conditional_compilation_is_flagged():
    # Verbatim excerpt (not paraphrased) of get_cgi_env() from
    # docs/research/samples/logger.pkb (OraOpenSource/Logger) --
    # append_cgi_env is a genuinely nested procedure, itself declared
    # inside a $IF/$END conditional-compilation block (GAP-035's own
    # territory). Confirms the nested-subprogram detection isn't thrown
    # off by $IF/$END tokens sitting in the same declare section --
    # real-world code combines both gaps in the same routine.
    source = (
        "  function get_cgi_env(\n"
        "    p_show_null   in boolean default false)\n"
        "    return clob\n"
        "  is\n"
        "    l_cgienv clob;\n"
        "\n"
        "    $if $$no_op is null or not $$no_op $then\n"
        "      procedure append_cgi_env(\n"
        "        p_name    in varchar2,\n"
        "        p_val   in varchar2)\n"
        "      is\n"
        "        r_pad number := 30;\n"
        "      begin\n"
        "        if p_show_null or p_val is not null then\n"
        "          l_cgienv := l_cgienv || rpad(p_name,r_pad,' ')||': '||p_val;\n"
        "        end if;\n"
        "      end append_cgi_env;\n"
        "    $end\n"
        "\n"
        "  begin\n"
        "    $if $$no_op $then\n"
        "      return null;\n"
        "    $else\n"
        "      for i in 1..nvl(owa.num_cgi_vars,0) loop\n"
        "        append_cgi_env(\n"
        "          p_name      => owa.cgi_var_name(i),\n"
        "          p_val       => owa.cgi_var_val(i));\n"
        "      end loop;\n"
        "      return l_cgienv;\n"
        "    $end\n"
        "  end get_cgi_env;\n"
    )
    findings = find_nested_subprograms(source)
    assert len(findings) == 1
    assert findings[0].object_name == "GET_CGI_ENV.APPEND_CGI_ENV"


def test_reported_line_is_the_nested_declaration_line():
    source = (
        "create or replace procedure outer_proc as\n"
        "  procedure inner_proc is\n"
        "  begin\n"
        "    null;\n"
        "  end;\n"
        "begin\n"
        "  inner_proc();\n"
        "end;\n"
    )
    findings = find_nested_subprograms(source)
    assert len(findings) == 1
    assert findings[0].line == 2
