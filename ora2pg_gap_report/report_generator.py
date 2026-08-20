import csv
import hashlib
import html
import io
import json
from dataclasses import asdict, fields

from . import i18n
from .effort_estimator import estimate_hours, ordered_counts, summarize_by_severity
from .gap_registry import gap_by_detector, gap_metadata, research_doc_url
from .models import Finding
from .verification import DetectorVerification

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


def to_json(findings: list[Finding]) -> str:
    return json.dumps([_enrich(f) for f in findings], ensure_ascii=False, indent=2)


def to_verification_json(results: list[DetectorVerification]) -> str:
    """--verify's machine-readable output. gap_number is a plain string
    or null (JSON has no distinct "GAP-NNN" type) -- callers that need
    the "GAP-" prefix add it themselves, same as everywhere else in this
    project's JSON output (e.g. Finding.detector has no GAP- prefix
    either)."""
    payload = {
        "baseline_detectors": len(results),
        "still_present": sum(1 for r in results if r.status == "still_present"),
        "not_detected": sum(1 for r in results if r.status == "not_detected"),
        "not_verifiable": sum(1 for r in results if r.status == "not_verifiable"),
        "results": [asdict(r) for r in results],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


_CSV_FIELDNAMES = [*(f.name for f in fields(Finding)), "gap_number", "failure_stage"]


def to_csv(findings: list[Finding]) -> str:
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
    this one format's write path."""
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=_CSV_FIELDNAMES, lineterminator="\n")
    writer.writeheader()
    for f in findings:
        writer.writerow(_enrich(f))
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
        message = f.message.replace("|", "\\|").replace("\n", " ")
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
            f"<td>{html.escape(f.message)}</td>"
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


def _sarif_rule_id(detector: str, message: str) -> str:
    """A single detector can legitimately have more than one distinct
    static message -- e.g. bulk_collect.py attaches one of three fixed
    strings (_TYPE_DECL_MESSAGE / _BULK_COLLECT_MESSAGE / _FORALL_MESSAGE)
    depending on which sub-pattern matched, all under detector=
    "bulk_collect". terminal_report.py's own explanation section already
    accounts for this by grouping on (detector, message), not detector
    alone (see its explanation_counts dict) -- SARIF rules follow the same
    grouping here, via a message hash appended to the id, so a rule's
    fullDescription always accurately describes every result filed under
    it. Stable across runs (content-derived, not insertion-order-derived),
    which matters for GitHub code scanning's cross-run issue tracking by
    ruleId."""
    digest = hashlib.sha1(message.encode()).hexdigest()[:8]
    return f"{detector}/{digest}"


def _sarif_rule(detector: str, message: str) -> dict:
    gap = gap_by_detector(detector)
    # Deliberately not "first sentence of `message`" for shortDescription:
    # these messages are free-form prose about Oracle/ora2pg internals,
    # full of abbreviations and literal '...' (e.g. "TYPE ... IS TABLE OF"),
    # so splitting on '.' truncates mid-thought as often as not. The
    # detector name itself, lightly reformatted, is short but always
    # correct; fullDescription carries the real explanation, which is
    # exact for this rule since _sarif_rule_id() splits rules per distinct
    # message rather than per detector.
    rule: dict = {
        "id": _sarif_rule_id(detector, message),
        "name": detector,
        "shortDescription": {"text": detector.replace("_", " ").capitalize()},
        "fullDescription": {"text": message},
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


def _sarif_location(f: Finding) -> dict:
    physical_location: dict = {"artifactLocation": {"uri": f.source_file}}
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


def to_sarif(findings: list[Finding], tool_version: str = "unknown") -> str:
    """SARIF 2.1.0 (https://sarifweb.azurewebsites.net/), for GitHub/GitLab
    code scanning integrations. One rule per distinct (detector, message)
    pair actually present among `findings` (not all detectors/messages
    this project ships) -- see _sarif_rule_id()'s docstring for why it's
    that pair, not detector alone."""
    rules_by_id: dict[str, dict] = {}
    for f in findings:
        rule_id = _sarif_rule_id(f.detector, f.message)
        if rule_id not in rules_by_id:
            rules_by_id[rule_id] = _sarif_rule(f.detector, f.message)

    results = [
        {
            "ruleId": _sarif_rule_id(f.detector, f.message),
            "level": _SARIF_LEVEL.get(f.severity, "warning"),
            "message": {"text": f.message},
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
