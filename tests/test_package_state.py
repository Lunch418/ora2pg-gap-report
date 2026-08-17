from ora2pg_gap_report.detectors.package_state import find_package_state


def test_package_level_number_variable_is_flagged():
    source = (
        "create or replace package body pkg_ctx as\n"
        "  g_user_id number;\n"
        "  procedure set_user(p_id number) is\n"
        "  begin\n"
        "    g_user_id := p_id;\n"
        "  end;\n"
        "  function get_user return number is\n"
        "  begin\n"
        "    return g_user_id;\n"
        "  end;\n"
        "end pkg_ctx;\n"
    )
    findings = find_package_state(source)
    assert len(findings) == 1
    assert findings[0].object_name == "PKG_CTX.G_USER_ID"
    assert findings[0].severity == "high"


def test_percent_type_anchored_declaration_is_flagged():
    source = (
        "create or replace package body pkg_ctx as\n"
        "  g_status orders.status%type;\n"
        "  procedure noop is\n"
        "  begin\n"
        "    null;\n"
        "  end;\n"
        "end pkg_ctx;\n"
    )
    findings = find_package_state(source)
    assert len(findings) == 1
    assert findings[0].object_name == "PKG_CTX.G_STATUS"


def test_package_with_no_top_level_variables_is_not_flagged():
    source = (
        "create or replace package body pkg_ctx as\n"
        "  procedure noop is\n"
        "  begin\n"
        "    null;\n"
        "  end;\n"
        "end pkg_ctx;\n"
    )
    assert find_package_state(source) == []


def test_local_variable_inside_a_member_routine_is_not_flagged():
    # A variable declared inside a routine's own declare section (after
    # the first ROUTINE_START_RE match) is ordinary local state, not
    # package-level -- it must not be confused with package state just
    # because the declaration shape looks identical.
    source = (
        "create or replace package body pkg_ctx as\n"
        "  procedure do_something is\n"
        "    v_local number;\n"
        "  begin\n"
        "    v_local := 1;\n"
        "  end;\n"
        "end pkg_ctx;\n"
    )
    assert find_package_state(source) == []


def test_package_level_constant_and_exception_are_not_flagged():
    # CONSTANT/EXCEPTION declarations don't match the scalar-type/%TYPE
    # shape this detector looks for, and aren't what ora2pg's
    # set_config/current_setting rewrite applies to.
    source = (
        "create or replace package body pkg_ctx as\n"
        "  c_max_retries constant pls_integer := 3;\n"
        "  invalid_state exception;\n"
        "  procedure noop is\n"
        "  begin\n"
        "    null;\n"
        "  end;\n"
        "end pkg_ctx;\n"
    )
    findings = find_package_state(source)
    # 'CONSTANT' sits between the variable name and its type
    # ('c_max_retries CONSTANT PLS_INTEGER'), so _PACKAGE_VAR_RE (which
    # requires the type immediately after the name) doesn't match it
    # either -- neither the constant nor the exception is flagged.
    assert findings == []


def test_multiple_package_level_variables_are_each_flagged():
    source = (
        "create or replace package body pkg_ctx as\n"
        "  g_user_id number;\n"
        "  g_tenant_id number;\n"
        "  procedure noop is\n"
        "  begin\n"
        "    null;\n"
        "  end;\n"
        "end pkg_ctx;\n"
    )
    findings = find_package_state(source)
    assert len(findings) == 2
    names = {f.object_name for f in findings}
    assert names == {"PKG_CTX.G_USER_ID", "PKG_CTX.G_TENANT_ID"}


def test_package_spec_alone_is_not_flagged():
    # This detector only looks at PACKAGE BODY -- a package spec's own
    # public variable declaration is a separate, unverified case.
    source = (
        "create or replace package pkg_ctx as\n"
        "  g_user_id number;\n"
        "  procedure set_user(p_id number);\n"
        "end pkg_ctx;\n"
    )
    assert find_package_state(source) == []


def test_default_keyword_initializer_is_flagged():
    # Oracle allows 'DEFAULT expr' as an equally valid alternative to
    # ':=' for a variable's initializer -- not just a special case for
    # constants.
    source = (
        "create or replace package body pkg_ctx as\n"
        "  g_counter number default 0;\n"
        "  procedure noop is\n"
        "  begin\n"
        "    null;\n"
        "  end;\n"
        "end pkg_ctx;\n"
    )
    findings = find_package_state(source)
    assert len(findings) == 1
    assert findings[0].object_name == "PKG_CTX.G_COUNTER"


def test_not_null_before_the_initializer_is_flagged():
    source = (
        "create or replace package body pkg_ctx as\n"
        "  g_counter number not null := 0;\n"
        "  procedure noop is\n"
        "  begin\n"
        "    null;\n"
        "  end;\n"
        "end pkg_ctx;\n"
    )
    findings = find_package_state(source)
    assert len(findings) == 1
    assert findings[0].object_name == "PKG_CTX.G_COUNTER"


def test_package_with_no_member_routines_does_not_leak_into_the_next_package():
    # A package body with no member routines at all used to have its
    # declare-section search run unbounded, past its own END and into a
    # later, unrelated package's own declarations -- misattributing that
    # later package's variables to this one as well.
    source = (
        "create or replace package body pkg1 as\n"
        "  g_a number;\n"
        "end pkg1;\n"
        "create or replace package body pkg2 as\n"
        "  g_b number;\n"
        "  procedure noop is\n"
        "  begin\n"
        "    null;\n"
        "  end;\n"
        "end pkg2;\n"
    )
    findings = find_package_state(source)
    names = {f.object_name for f in findings}
    assert names == {"PKG1.G_A", "PKG2.G_B"}


def test_editionable_package_body_is_flagged():
    # 'EDITIONABLE'/'NONEDITIONABLE' is a real, valid Oracle keyword
    # (edition-based redefinition) that can appear between 'CREATE [OR
    # REPLACE]' and 'PACKAGE BODY'.
    source = (
        "create or replace editionable package body pkg_ctx as\n"
        "  g_user_id number;\n"
        "  procedure noop is\n"
        "  begin\n"
        "    null;\n"
        "  end;\n"
        "end pkg_ctx;\n"
    )
    findings = find_package_state(source)
    assert len(findings) == 1
    assert findings[0].object_name == "PKG_CTX.G_USER_ID"


def test_real_open_source_logger_package_variables_are_flagged():
    # Verbatim excerpt (not paraphrased) from
    # docs/research/samples/logger.pkb (OraOpenSource/Logger, a real,
    # widely-used open-source PL/SQL logging framework) -- confirms this
    # detector fires on genuine real-world package-level session state,
    # not just synthetic examples.
    source = (
        "create or replace package body logger is\n"
        "\n"
        "  type ts_array is table of timestamp index by varchar2(100);\n"
        "\n"
        "  g_log_id number;\n"
        "  g_running_timers pls_integer := 0;\n"
        "\n"
        "  g_in_plugin_error boolean := false;\n"
        "\n"
        "  procedure noop is\n"
        "  begin\n"
        "    null;\n"
        "  end;\n"
        "\n"
        "end logger;\n"
    )
    findings = find_package_state(source)
    names = {f.object_name for f in findings}
    assert names == {"LOGGER.G_LOG_ID", "LOGGER.G_RUNNING_TIMERS", "LOGGER.G_IN_PLUGIN_ERROR"}


def test_reported_line_is_the_variable_declaration_line():
    source = (
        "create or replace package body pkg_ctx as\n"
        "  g_user_id number;\n"
        "  procedure noop is\n"
        "  begin\n"
        "    null;\n"
        "  end;\n"
        "end pkg_ctx;\n"
    )
    findings = find_package_state(source)
    assert len(findings) == 1
    assert findings[0].line == 2
