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


def test_package_level_constant_is_flagged():
    # CONSTANT gets the exact same set_config/current_setting rewrite as
    # an ordinary variable -- confirmed by a real ora2pg 25.0 run (see
    # docs/research/gap-036-package-state.md's "CONSTANT" addendum), and
    # arguably worse: ora2pg never generates a set_config() call for the
    # constant's own initializer at all, so current_setting() is
    # guaranteed to raise "unrecognized configuration parameter" on
    # every read, not just before the first write.
    source = (
        "create or replace package body pkg_ctx as\n"
        "  c_max_retries constant pls_integer := 3;\n"
        "  function get_retries return pls_integer is\n"
        "  begin\n"
        "    return c_max_retries;\n"
        "  end;\n"
        "end pkg_ctx;\n"
    )
    findings = find_package_state(source)
    assert len(findings) == 1
    assert findings[0].object_name == "PKG_CTX.C_MAX_RETRIES"


def test_package_level_exception_is_not_flagged():
    # An EXCEPTION isn't state data at all (nothing to read/write), so
    # ora2pg's set_config/current_setting rewrite has no reason to apply
    # to it -- unlike CONSTANT above, not empirically re-checked against
    # a real ora2pg run, just structurally not the shape this gap is
    # about.
    source = (
        "create or replace package body pkg_ctx as\n"
        "  invalid_state exception;\n"
        "  procedure noop is\n"
        "  begin\n"
        "    null;\n"
        "  end;\n"
        "end pkg_ctx;\n"
    )
    assert find_package_state(source) == []


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


def test_package_spec_variable_is_flagged():
    # A spec-level (public) package variable gets the same rewrite as a
    # body-level one -- ora2pg doesn't care where the declaration lives.
    # Also GAP-036's own documented minimal example's exact shape: a
    # spec-only declaration with an *empty* body declare section (the
    # body only has member routine bodies, no top-level state of its
    # own) -- this used to score zero findings entirely, on the gap's
    # own canonical example.
    source = (
        "create or replace package pkg_ctx as\n"
        "  g_user_id number;\n"
        "  procedure set_user(p_id number);\n"
        "  function get_user return number;\n"
        "end pkg_ctx;\n"
        "create or replace package body pkg_ctx as\n"
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


def test_package_spec_and_body_variables_are_both_flagged_independently():
    # A spec-level (public) variable and a body-level (private) one in
    # the same package are two distinct findings, not deduplicated --
    # they're different declarations serving different visibility.
    source = (
        "create or replace package pkg_ctx as\n"
        "  g_public_id number;\n"
        "  procedure noop;\n"
        "end pkg_ctx;\n"
        "create or replace package body pkg_ctx as\n"
        "  g_private_flag number;\n"
        "  procedure noop is\n"
        "  begin\n"
        "    null;\n"
        "  end;\n"
        "end pkg_ctx;\n"
    )
    findings = find_package_state(source)
    names = {f.object_name for f in findings}
    assert names == {"PKG_CTX.G_PUBLIC_ID", "PKG_CTX.G_PRIVATE_FLAG"}


def test_package_spec_with_no_top_level_variables_is_not_flagged():
    source = (
        "create or replace package pkg_ctx as\n"
        "  procedure noop;\n"
        "end pkg_ctx;\n"
    )
    assert find_package_state(source) == []


def test_a_second_unrelated_package_spec_does_not_absorb_the_first_ones_declarations():
    # Regression for the shared next_boundary() computation: a spec with
    # no member routines of its own must stop its declare-section search
    # at the *next* package container (spec or body), not run past it
    # into an unrelated package's own declarations.
    source = (
        "create or replace package pkg_a as\n"
        "  g_a number;\n"
        "end pkg_a;\n"
        "create or replace package pkg_b as\n"
        "  g_b number;\n"
        "  procedure noop;\n"
        "end pkg_b;\n"
    )
    findings = find_package_state(source)
    names = {f.object_name for f in findings}
    assert names == {"PKG_A.G_A", "PKG_B.G_B"}


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
