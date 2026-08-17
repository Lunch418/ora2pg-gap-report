from ora2pg_gap_report.detectors.conditional_compilation import find_conditional_compilation


def test_if_then_else_end_are_each_flagged():
    source = (
        "create or replace procedure proc_debug as\n"
        "begin\n"
        "$if $$debug_mode $then\n"
        "  dbms_output.put_line('debug on');\n"
        "$else\n"
        "  dbms_output.put_line('debug off');\n"
        "$end\n"
        "  null;\n"
        "end;\n"
    )
    findings = find_conditional_compilation(source)
    directives = {f.snippet.upper() for f in findings}
    assert directives == {"$IF", "$ELSE", "$END"}
    assert all(f.severity == "high" for f in findings)
    assert all(f.object_name == "PROC_DEBUG" for f in findings)


def test_elsif_is_flagged():
    source = (
        "create or replace procedure proc_debug as\n"
        "begin\n"
        "$if $$a $then\n"
        "  null;\n"
        "$elsif $$b $then\n"
        "  null;\n"
        "$end\n"
        "end;\n"
    )
    findings = find_conditional_compilation(source)
    directives = {f.snippet.upper() for f in findings}
    assert "$ELSIF" in directives


def test_ordinary_procedure_without_directives_is_not_flagged():
    source = (
        "create or replace procedure proc_plain as\n"
        "begin\n"
        "  null;\n"
        "end;\n"
    )
    assert find_conditional_compilation(source) == []


def test_bare_inquiry_directive_without_a_controlling_if_is_not_flagged():
    # A standalone '$$identifier' compile-time constant, with no $IF
    # actually gating compilation, is comparatively harmless -- this
    # detector only fires on the directive keywords themselves.
    source = (
        "create or replace procedure proc_debug as\n"
        "  v_flag boolean := $$debug_mode;\n"
        "begin\n"
        "  null;\n"
        "end;\n"
    )
    assert find_conditional_compilation(source) == []


def test_real_open_source_logger_assert_procedure_is_flagged():
    # Verbatim excerpt (not paraphrased) of assert() from
    # docs/research/samples/logger.pkb (OraOpenSource/Logger, a real,
    # widely-used open-source PL/SQL logging framework) -- confirms this
    # detector fires on genuine real-world conditional compilation, not
    # just synthetic examples. Logger uses $IF/$ELSE/$END this way 229
    # times across the whole file to gate a no-op compile-time flag.
    source = (
        "  procedure assert(\n"
        "    p_condition in boolean,\n"
        "    p_message in varchar2)\n"
        "  as\n"
        "  begin\n"
        "    $if $$no_op $then\n"
        "      null;\n"
        "    $else\n"
        "      if not p_condition or p_condition is null then\n"
        "        raise_application_error(-20000, p_message);\n"
        "      end if;\n"
        "    $end\n"
        "  end assert;\n"
    )
    findings = find_conditional_compilation(source)
    directives = {f.snippet.upper() for f in findings}
    assert directives == {"$IF", "$ELSE", "$END"}
    assert all(f.object_name == "ASSERT" for f in findings)


def test_reported_line_is_the_directive_line():
    source = (
        "create or replace procedure proc_debug as\n"
        "begin\n"
        "  null;\n"
        "$if $$debug_mode $then\n"
        "  null;\n"
        "$end\n"
        "end;\n"
    )
    findings = find_conditional_compilation(source)
    if_finding = next(f for f in findings if f.snippet.upper() == "$IF")
    assert if_finding.line == 4
