"""Every streaming writer must produce exactly what its to_* counterpart
produces.

The streaming versions exist for one reason -- a report over a large scan
was the biggest thing the process ever held, several times the report's
own size in intermediate objects -- and they are only worth having if
they are otherwise indistinguishable. A whitespace difference in one
format would be invisible in a unit test of that format alone, and would
silently change every consumer's input. Comparing the two
implementations against each other is what makes them one implementation
in two shapes rather than two implementations.
"""

import io

import pytest

from ora2pg_gap_report import report_generator as rg
from ora2pg_gap_report.cli import _render, _write_report
from ora2pg_gap_report.models import Finding

_FINDINGS = [
    Finding(
        detector="read_only_table",
        severity="high",
        object_name="HR.EMPLOYEES",
        line=12,
        snippet="READ ONLY",
        message_id="read_only_table",
        source_file="schema/tables.sql",
    ),
    Finding(
        detector="bitmap_index",
        severity="high",
        object_name="IDX_G",
        line=3,
        snippet="CREATE BITMAP INDEX",
        message_id="bitmap_index",
        source_file="schema/indexes.sql",
    ),
    # A detector with no GAP-NNN of its own, so gap_number/failure_stage
    # come back None -- the cells those become differ per format.
    Finding(
        detector="dbms_utl_calls",
        severity="medium",
        object_name="PKG.PROC",
        line=99,
        snippet="DBMS_LOB.READ",
        message_id="dbms_utl_calls",
        source_file="src/pkg.sql",
    ),
]


def _streamed(writer, findings, **kwargs):
    buffer = io.StringIO()
    writer(findings, buffer, **kwargs)
    return buffer.getvalue()


@pytest.mark.parametrize("lang", ["ru", "en"])
@pytest.mark.parametrize(
    ("to_fn", "write_fn"),
    [
        (rg.to_json, rg.write_json),
        (rg.to_csv, rg.write_csv),
        (rg.to_markdown, rg.write_markdown),
        (rg.to_html, rg.write_html),
        (rg.to_sarif, rg.write_sarif),
    ],
)
def test_the_streaming_writer_matches_its_string_counterpart(to_fn, write_fn, lang):
    assert _streamed(write_fn, _FINDINGS, lang=lang) == to_fn(_FINDINGS, lang=lang)


@pytest.mark.parametrize(
    ("to_fn", "write_fn"),
    [
        (rg.to_json, rg.write_json),
        (rg.to_csv, rg.write_csv),
        (rg.to_markdown, rg.write_markdown),
        (rg.to_html, rg.write_html),
        (rg.to_sarif, rg.write_sarif),
    ],
)
def test_they_also_match_on_no_findings_at_all(to_fn, write_fn):
    # The empty case takes a different branch in markdown and html, and
    # is what a clean scan actually produces.
    assert _streamed(write_fn, []) == to_fn([])


@pytest.mark.parametrize("fmt", ["json", "csv", "sarif", "html", "markdown"])
@pytest.mark.parametrize("findings", [_FINDINGS, []], ids=["with_findings", "empty"])
def test_the_cli_writes_exactly_what_it_used_to_render(fmt, findings):
    # _render() is still the string path (--verify and the tests use it);
    # _write_report() is what a scan takes. They must not drift.
    buffer = io.StringIO()
    _write_report(findings, fmt, buffer)
    assert buffer.getvalue() == _render(findings, fmt)


def test_a_streamed_json_report_is_still_valid_json():
    import json

    payload = json.loads(_streamed(rg.write_json, _FINDINGS))
    assert [f["detector"] for f in payload["findings"]] == [
        "read_only_table", "bitmap_index", "dbms_utl_calls"
    ]
    assert set(payload["messages"]) == {"read_only_table", "bitmap_index", "dbms_utl_calls"}


class _CountingStream:
    """Records how many separate writes it received."""

    def __init__(self):
        self.parts: list[str] = []

    def write(self, text: str) -> int:
        self.parts.append(text)
        return len(text)

    def getvalue(self) -> str:
        return "".join(self.parts)


@pytest.mark.parametrize(
    "write_fn", [rg.write_json, rg.write_csv, rg.write_markdown, rg.write_html, rg.write_sarif]
)
def test_a_writer_emits_progressively_rather_than_in_one_piece(write_fn):
    # The property the streaming writers exist for, stated as behaviour
    # rather than as a memory measurement: output arrives in pieces as
    # findings are consumed. A writer that built the document first and
    # handed it over would show up here as a single write, and would have
    # the peak memory this all exists to avoid, while still passing every
    # byte-for-byte test above.
    stream = _CountingStream()
    write_fn(_FINDINGS, stream)
    assert len(stream.parts) > len(_FINDINGS)


def test_the_array_placeholder_must_appear_exactly_once():
    # Splitting on the wrong occurrence would yield a plausible-looking
    # but wrong document rather than an error.
    with pytest.raises(ValueError, match="exactly one array placeholder"):
        rg._stream_json_with_array(
            {"a": rg._ARRAY_PLACEHOLDER, "b": rg._ARRAY_PLACEHOLDER}, [], io.StringIO()
        )
