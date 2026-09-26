"""plsql_lex._mask() is what every Oracle detector's view of the source
comes from -- which characters are code and which are comment or literal.
It used to walk the text one character per iteration, which made masking
most of the cost of scanning a large file (a 1.2 MB data script spent 6 of
its 9 seconds there). It now jumps between the positions where something
can happen, and must produce exactly what the one-character-at-a-time
version did. The original is kept here verbatim as the reference, and both
are run over every sample in the repository and over random text built
from the characters the tokenizer treats specially, in all three modes.

Before this landed the same comparison ran over 844 real files (15.7M
characters: utPLSQL, Alexandria, OOS-Utils, Logger, tePLSQL,
oracle-samples/db-sample-schemas) and 200,000 random strings per mode,
with no difference."""

import random
from pathlib import Path

import pytest

from ora2pg_gap_report import plsql_lex
from ora2pg_gap_report.plsql_lex import (
    _EXEC_IMMEDIATE_RE,
    _Q_QUOTE_PAIRS,
    _REM_RE,
    _at_line_start,
    _q_quote_open_delim_pos,
)

REPO = Path(__file__).resolve().parents[1]
MODES = [(False, False), (True, False), (False, True)]


def _reference_mask(source: str, reveal_dynamic_sql: bool, reveal_strings: bool = False) -> str:
    """plsql_lex._mask() as it was before it learned to copy runs of
    plain text in one piece -- one character per iteration."""
    out = []
    i, n = 0, len(source)
    in_dynamic_sql = False
    while i < n:
        if reveal_dynamic_sql and not in_dynamic_sql and source[i].upper() == "E":
            m = _EXEC_IMMEDIATE_RE.match(source, i)
            if m:
                out.append(source[i : m.end()])
                i = m.end()
                in_dynamic_sql = True
                continue
        two = source[i : i + 2]
        if two == "--":
            while i < n and source[i] != "\n":
                out.append(" ")
                i += 1
            continue
        if source[i] in "rR" and _at_line_start(source, i) and _REM_RE.match(source, i):
            while i < n and source[i] != "\n":
                out.append(" ")
                i += 1
            continue
        if two == "/*":
            out.append("  ")
            i += 2
            while i < n and source[i : i + 2] != "*/":
                out.append("\n" if source[i] == "\n" else " ")
                i += 1
            if i < n:
                out.append("  ")
                i += 2
            continue
        if source[i] in "nNqQ":
            open_pos = _q_quote_open_delim_pos(source, i)
            if open_pos is not None:
                open_delim = source[open_pos]
                close_delim = _Q_QUOTE_PAIRS.get(open_delim, open_delim)
                end = source.find(close_delim + "'", open_pos + 1)
                if end != -1:
                    if in_dynamic_sql or reveal_strings:
                        out.append(source[i : end + 2])
                    else:
                        for k in range(i, end + 2):
                            out.append("\n" if source[k] == "\n" else " ")
                    i = end + 2
                    continue
        if source[i] == "'":
            reveal = in_dynamic_sql or reveal_strings
            out.append("'" if reveal else " ")
            i += 1
            while i < n:
                if source[i] == "'":
                    if source[i : i + 2] == "''":
                        out.append("''" if reveal else "  ")
                        i += 2
                        continue
                    out.append("'" if reveal else " ")
                    i += 1
                    break
                if reveal:
                    out.append(source[i])
                else:
                    out.append("\n" if source[i] == "\n" else " ")
                i += 1
            continue
        if source[i] == ";" and in_dynamic_sql:
            in_dynamic_sql = False
        out.append(source[i])
        i += 1
    return "".join(out)


_SAMPLES = sorted(
    p
    for p in [*(REPO / "docs" / "research" / "samples").iterdir(), *(REPO / "tests" / "fixtures").iterdir()]
    if p.suffix.lower() in (".sql", ".pks", ".pkb")
)


@pytest.mark.parametrize("path", _SAMPLES, ids=lambda p: p.name)
@pytest.mark.parametrize(("reveal_dynamic_sql", "reveal_strings"), MODES)
def test_mask_matches_the_reference_on_every_sample(path, reveal_dynamic_sql, reveal_strings):
    source = path.read_text(encoding="utf-8")
    assert plsql_lex._mask(source, reveal_dynamic_sql, reveal_strings) == _reference_mask(
        source, reveal_dynamic_sql, reveal_strings
    )


# Single characters and whole tokens the tokenizer reacts to, mixed with
# ordinary text, so random strings keep landing on the edge cases: a REM
# that does or does not open its line, q-quotes with every delimiter kind
# and missing closers, '' escapes, unterminated comments and literals,
# EXECUTE IMMEDIATE with and without its terminating ';'.
_PIECES = [
    *"-/*'\n\t ;qQnNrReEaXx_()[]{}<>!$@",
    "REM ", "rem\t", "REMARK\n", "REMARKS",
    "EXECUTE IMMEDIATE ", "execute  immediate", "xEXECUTE IMMEDIATE",
    "q'[", "]'", "nq'<", ">'", "Q'!", "!'", "''", "/*", "*/", "--", "\r\n",
]


@pytest.mark.parametrize(("reveal_dynamic_sql", "reveal_strings"), MODES)
def test_mask_matches_the_reference_on_random_text(reveal_dynamic_sql, reveal_strings):
    rng = random.Random(20260926)
    for _ in range(20000):
        source = "".join(rng.choice(_PIECES) for _ in range(rng.randint(0, 40)))
        assert plsql_lex._mask(source, reveal_dynamic_sql, reveal_strings) == _reference_mask(
            source, reveal_dynamic_sql, reveal_strings
        ), repr(source)
