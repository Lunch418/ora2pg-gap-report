import csv
import html
import io
import json
from dataclasses import asdict, fields
from pathlib import PurePath
from urllib.parse import quote

from . import i18n
from .effort_estimator import estimate_hours, ordered_counts, summarize_by_severity
from .gap_registry import gap_by_detector, gap_metadata, research_doc_url
from . import messages
from .models import Finding
from .verification import DetectorVerification, NewInOutput

# Bumped when the shape of --format json changes. 2 introduced the
# object envelope with a shared `messages` table, replacing the bare
# array of findings that inlined each explanation.
REPORT_SCHEMA_VERSION = 2

SARIF_SCHEMA_URI = "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json"
_TOOL_INFORMATION_URI = "https://github.com/Lunch418/ora2pg-gap-report"

_SARIF_LEVEL = {"high": "error", "medium": "warning", "low": "note"}


def _enrich(f: Finding) -> dict:
    """A finding's own dict shape plus gap_number/failure_stage, looked
    up from the registry rather than stored on Finding itself -- Finding
    represents what a detector found, not what the registry separately
    knows about it (same reasoning as verification.py's
    DetectorVerification, built the same way from gap_by_detector()).
    Shared by to_json()/to_csv() and baseline.py's save_baseline(), so
    every JSON-shaped output computes these two fields identically."""
    gap_number, failure_stage = gap_metadata(f.detector)
    return {**asdict(f), "gap_number": gap_number, "failure_stage": failure_stage}


def message_map(findings: list[Finding], lang: str) -> dict[str, str]:
    """The `message_id` -> text map for exactly the messages `findings`
    actually reference, in `lang`. Sorted so two runs over the same
    findings produce byte-identical output."""
    return {mid: messages.text(mid, lang) for mid in sorted({f.message_id for f in findings})}


def to_json(findings: list[Finding], lang: str = "ru") -> str:
    """Findings plus a shared message table, not one inlined paragraph per
    finding.

    A finding's explanation is 400-600 characters and identical for every
    finding the same detector produced, so inlining it cost roughly 30 MB
    of a 72 MB report on a 2,000-file scan -- the same few paragraphs
    repeated 80,000 times. Emitting `message_id` per finding and the text
    once under `messages` says the same thing at a fraction of the size,
    and the id is a stable key a consumer can group or filter on, which
    the prose never was.

    This is why the payload is an object with `schema_version` rather than
    the bare array it used to be: consumers need to be able to tell the
    two shapes apart, and a version they can branch on is a better way to
    say that than making them sniff for a leading '['.
    """
    payload = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "messages": message_map(findings, lang),
        "findings": [_enrich(f) for f in findings],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def to_verification_json(
    results: list[DetectorVerification], new_in_output: list[NewInOutput] | None = None
) -> str:
    """--verify's machine-readable output. gap_number is a plain string
    or null (JSON has no distinct "GAP-NNN" type) -- callers that need
    the "GAP-" prefix add it themselves, same as everywhere else in this
    project's JSON output (e.g. Finding.detector has no GAP- prefix
    either).

    `new_in_output` carries detectors that fired on the generated output
    but were never in the baseline -- constructs the conversion itself
    introduced. Always present as a key (empty list when there are none)
    so a consumer can tell "checked, found nothing" from "this version
    didn't check", which an absent key can't express."""
    entries = new_in_output or []
    payload = {
        "baseline_detectors": len(results),
        "still_present": sum(1 for r in results if r.status == "still_present"),
        "not_detected": sum(1 for r in results if r.status == "not_detected"),
        "not_verifiable": sum(1 for r in results if r.status == "not_verifiable"),
        "new_in_output_detectors": len(entries),
        "results": [asdict(r) for r in results],
        "new_in_output": [asdict(e) for e in entries],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


_CSV_FIELDNAMES = [
    *(f.name for f in fields(Finding)),
    "message",
    "gap_number",
    "failure_stage",
]

# A cell starting with one of these opens as a formula, not text, the
# instant the CSV is opened in Excel/LibreOffice/Google Sheets -- and
# object_name/snippet/source_file all come straight from scanned Oracle
# source, not from this codebase's own fixed strings. Prefixing a single
# quote is the standard mitigation (OWASP's CSV Injection guidance): every
# affected spreadsheet application already treats a leading "'" as "the
# rest of this cell is literal text", stripping the quote itself from the
# displayed value, so this is neutralization, not visible mangling. Tab and
# CR are included too -- both can also anchor a formula in some clients.
_CSV_FORMULA_TRIGGER_CHARS = ("=", "+", "-", "@", "\t", "\r")


def _csv_safe(value: object) -> object:
    if isinstance(value, str) and value.startswith(_CSV_FORMULA_TRIGGER_CHARS):
        return "'" + value
    return value


def to_csv(findings: list[Finding], lang: str = "ru") -> str:
    """Flat CSV, one row per finding, same fields/order as to_json()'s
    dict keys (Finding's own field order).

    Explicitly '\\n' line endings, not csv.writer's RFC-4180 '\\r\\n'
    default: this string ends up written via cli.py's
    args.output.write_text(report, encoding="utf-8") the same as every
    other --format, which opens in text mode with newline=None -- that
    translates each '\\n' it finds to os.linesep on write. On Windows
    (os.linesep == '\\r\\n'), a string that already contained '\\r\\n'
    would come out as '\\r\\r\\n'. Plain '\\n' throughout, matching
    to_json()/to_markdown(), sidesteps that rather than special-casing
    this one format's write path.

    Every string field goes through _csv_safe() -- not just the ones
    that plausibly start with scanned content today -- so a future field
    added to Finding doesn't silently reopen the same formula-injection
    hole (see _csv_safe's own docstring)."""
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=_CSV_FIELDNAMES, lineterminator="\n")
    writer.writeheader()
    for f in findings:
        # message_id stays (a stable key to group on), and the prose it
        # resolves to is written beside it -- a spreadsheet is read by a
        # person, and an id alone tells them nothing.
        row = {**_enrich(f), "message": messages.text(f.message_id, lang)}
        writer.writerow({k: _csv_safe(v) for k, v in row.items()})
    return buffer.getvalue()


def to_markdown(findings: list[Finding], lang: str = "ru") -> str:
    if not findings:
        return i18n.t(lang, "md_no_findings")

    lines = [
        i18n.t(lang, "md_table_header"),
        "|---|---|---|---|---|---|---|---|",
    ]
    for f in findings:
        source_file = f.source_file.replace("|", "\\|")
        object_name = f.object_name.replace("|", "\\|")
        snippet = f.snippet.replace("|", "\\|")
        message = messages.text(f.message_id, lang).replace("|", "\\|").replace("\n", " ")
        gap_number, failure_stage = gap_metadata(f.detector)
        gap_cell = f"GAP-{gap_number}" if gap_number else "—"
        stage_cell = i18n.t(lang, f"failure_stage_short_{failure_stage}") if failure_stage else "—"
        lines.append(
            f"| {source_file} | `{object_name}` | {f.line} | {f.severity} "
            f"| `{snippet}` | {message} | {gap_cell} | {stage_cell} |"
        )
    return "\n".join(lines) + "\n"


_HTML_SEVERITY_CLASS = {"high": "sev-high", "medium": "sev-medium", "low": "sev-low"}

_HTML_STYLE = """
  body { font-family: system-ui, -apple-system, "Segoe UI", sans-serif; margin: 2rem;
         color: #1a1a1a; background: #ffffff; }
  h1 { font-size: 1.4rem; }
  .summary { margin: 1rem 0 1.5rem; padding: 1rem 1.25rem; border: 1px solid #d0d0d0;
             border-radius: 6px; background: #f7f7f7; }
  .summary p { margin: 0.25rem 0; }
  .caveat { color: #555; font-size: 0.9rem; }
  table { border-collapse: collapse; width: 100%; font-size: 0.9rem; }
  th, td { border: 1px solid #d8d8d8; padding: 0.5rem 0.6rem; text-align: left;
           vertical-align: top; }
  th { background: #eeeeee; position: sticky; top: 0; }
  td.mono, th.mono { font-family: ui-monospace, "SF Mono", Consolas, monospace; }
  .badge { display: inline-block; padding: 0.1rem 0.5rem; border-radius: 4px;
           font-weight: 600; font-size: 0.8rem; color: #ffffff; white-space: nowrap; }
  .sev-high .badge { background: #b3261e; }
  .sev-medium .badge { background: #9a6700; }
  .sev-low .badge { background: #1a5fb4; }
  .empty { padding: 1rem; color: #555; }
"""


def to_html(findings: list[Finding], lang: str = "ru") -> str:
    """Self-contained HTML report (inline CSS only, no external resources
    -- this project's other formats are all designed to work in an
    air-gapped/closed-network setting, see README's "Установка без
    интернета" section, and there is no reason for this one format alone
    to require network access to render correctly). Same counts/effort
    estimate as the Markdown/terminal header, same "uncalibrated
    heuristic, not a measurement" caveat -- see effort_estimator.py's
    docstring for why no other score (a "readiness %", a risk level) is
    invented here either."""
    counts = summarize_by_severity(findings)
    counts_text = ", ".join(f"{name}: {n}" for name, n in ordered_counts(counts))
    lo, hi = estimate_hours(findings)

    rows = []
    for f in findings:
        sev_class = _HTML_SEVERITY_CLASS.get(f.severity, "")
        gap_number, failure_stage = gap_metadata(f.detector)
        gap_cell = f"GAP-{gap_number}" if gap_number else "—"
        stage_cell = html.escape(i18n.t(lang, f"failure_stage_short_{failure_stage}")) if failure_stage else "—"
        rows.append(
            f'<tr class="{sev_class}">'
            f"<td>{html.escape(f.source_file)}</td>"
            f'<td class="mono">{html.escape(f.object_name)}</td>'
            f"<td>{f.line}</td>"
            f'<td><span class="badge">{html.escape(f.severity)}</span></td>'
            f'<td class="mono">{html.escape(f.snippet)}</td>'
            f"<td>{html.escape(messages.text(f.message_id, lang))}</td>"
            f'<td class="mono">{gap_cell}</td>'
            f"<td>{stage_cell}</td>"
            "</tr>"
        )

    if findings:
        table = (
            "<table>\n<thead><tr>"
            f"{i18n.t(lang, 'html_table_header')}"
            "</tr></thead>\n<tbody>\n" + "\n".join(rows) + "\n</tbody>\n</table>"
        )
    else:
        table = f'<p class="empty">{i18n.t(lang, "html_no_findings")}</p>'

    html_lang = "en" if lang == "en" else "ru"
    return f"""<!doctype html>
<html lang="{html_lang}">
<head>
<meta charset="utf-8">
<title>{i18n.t(lang, "html_title")}</title>
<style>{_HTML_STYLE}</style>
</head>
<body>
<h1>{i18n.t(lang, "html_h1")}</h1>
<div class="summary">
<p>{i18n.t(lang, "html_findings_found", n=len(findings), counts=html.escape(counts_text))}</p>
<p class="caveat">{i18n.t(lang, "html_effort_caveat", lo=lo, hi=hi)}</p>
</div>
{table}
</body>
</html>
"""


def _sarif_rule_id(detector: str, message_id: str) -> str:
    """A single detector can legitimately emit more than one distinct
    message -- bulk_collect attaches one of three, depending on which
    sub-pattern matched, all under detector="bulk_collect" -- so a rule
    per detector would file results under a fullDescription that doesn't
    describe them. The message_id is exactly the right granularity, and
    for the 105 detectors that emit one message it simply is the detector
    name.

    This used to be the detector plus a hash of the message prose. That
    was stable across runs but not across releases: fixing a typo in a
    message changed every ruleId it appeared under, and GitHub code
    scanning tracks alerts by ruleId -- so a text edit closed every open
    alert for that rule and opened fresh ones. An id survives edits to the
    text it names, which is the whole point of having one."""
    return message_id if message_id != detector else detector


def _sarif_rule(detector: str, message_id: str, lang: str) -> dict:
    gap = gap_by_detector(detector)
    # Deliberately not "first sentence of the message" for shortDescription:
    # these messages are free-form prose about Oracle/ora2pg internals,
    # full of abbreviations and literal '...' (e.g. "TYPE ... IS TABLE OF"),
    # so splitting on '.' truncates mid-thought as often as not. The
    # detector name itself, lightly reformatted, is short but always
    # correct; fullDescription carries the real explanation, which is
    # exact for this rule since _sarif_rule_id() splits rules per distinct
    # message rather than per detector.
    rule: dict = {
        "id": _sarif_rule_id(detector, message_id),
        "name": detector,
        "shortDescription": {"text": detector.replace("_", " ").capitalize()},
        "fullDescription": {"text": messages.text(message_id, lang)},
    }
    if gap is not None:
        rule["helpUri"] = research_doc_url(gap)
        # SARIF's free-form properties bag -- not a spec-defined field,
        # but the closest fit for "when does this actually break" without
        # overloading `level` (already carries severity) or fabricating a
        # second helpUri. failure_stage is omitted (not just null) for
        # the two gaps in FAILURE_STAGE_EXEMPT_DETECTORS, same reasoning
        # as leaving it out of a rule with no gap at all.
        rule["properties"] = {"gapNumber": gap.number}
        if gap.failure_stage is not None:
            rule["properties"]["failureStage"] = gap.failure_stage
    return rule


def _sarif_uri(source_file: str) -> str:
    """SARIF's artifactLocation.uri must be a valid URI-reference (RFC
    3986, the schema's own "uri-reference" format on this field) --
    source_file is a raw filesystem path (str(pathlib.Path(...)), see
    cli.py), which regularly contains characters a URI-reference doesn't
    allow unescaped: a literal space, or -- on Windows -- '\\' path
    separators and a drive letter's ':' (which would otherwise look like
    a URI scheme, e.g. 'C:/Users/...' parsed as scheme "C"). Passing the
    raw path through unchanged used to produce a document GitHub/GitLab's
    SARIF ingestion could reject or mis-locate, while still passing this
    project's own tests -- jsonschema.validate() doesn't check "format"
    constraints (uri-reference included) unless a FormatChecker is
    explicitly requested, so an invalid uri here was never actually
    caught.

    PurePath(...).as_posix() normalizes separators to '/' (a no-op on
    POSIX, where source_file already uses '/'; converts '\\' to '/' on
    Windows, where PurePath() resolves to PureWindowsPath). quote(...,
    safe="/") then percent-encodes everything else RFC 3986 doesn't
    allow unescaped in a path -- spaces, ':', etc. -- while leaving the
    '/' path separators themselves readable."""
    return quote(PurePath(source_file).as_posix(), safe="/")


def _sarif_location(f: Finding) -> dict:
    physical_location: dict = {"artifactLocation": {"uri": _sarif_uri(f.source_file)}}
    # line == 0 is this project's own "not a line in this file" sentinel
    # (used by the --check-connect-by integration, whose findings come from
    # ora2pg's own generated output, not the scanned file — see cli.py's
    # _connect_by_check()) -- SARIF regions are 1-based, so a "region" with
    # startLine 0 would be an invalid SARIF document, not just a wrong one.
    # Omitting "region" entirely is valid SARIF for "location known only at
    # artifact granularity."
    if f.line > 0:
        physical_location["region"] = {"startLine": f.line}
    return {"physicalLocation": physical_location}


def to_sarif(
    findings: list[Finding], tool_version: str = "unknown", lang: str = "ru"
) -> str:
    """SARIF 2.1.0 (https://sarifweb.azurewebsites.net/), for GitHub/GitLab
    code scanning integrations. One rule per distinct (detector, message)
    pair actually present among `findings` (not all detectors/messages
    this project ships) -- see _sarif_rule_id()'s docstring for why it's
    that pair, not detector alone."""
    rules_by_id: dict[str, dict] = {}
    for f in findings:
        rule_id = _sarif_rule_id(f.detector, f.message_id)
        if rule_id not in rules_by_id:
            rules_by_id[rule_id] = _sarif_rule(f.detector, f.message_id, lang)

    results = [
        {
            "ruleId": _sarif_rule_id(f.detector, f.message_id),
            "level": _SARIF_LEVEL.get(f.severity, "warning"),
            "message": {"text": messages.text(f.message_id, lang)},
            "locations": [_sarif_location(f)],
        }
        for f in findings
    ]

    sarif = {
        "$schema": SARIF_SCHEMA_URI,
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "ora2pg-gap-report",
                        "informationUri": _TOOL_INFORMATION_URI,
                        "version": tool_version,
                        "rules": [rules_by_id[rule_id] for rule_id in sorted(rules_by_id)],
                    }
                },
                "results": results,
            }
        ],
    }
    return json.dumps(sarif, ensure_ascii=False, indent=2)
