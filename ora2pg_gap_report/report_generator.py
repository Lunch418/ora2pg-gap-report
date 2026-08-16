import csv
import hashlib
import io
import json
from dataclasses import asdict, fields

from .gap_registry import gap_by_detector, research_doc_url
from .models import Finding

SARIF_SCHEMA_URI = "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json"
_TOOL_INFORMATION_URI = "https://github.com/Lunch418/ora2pg-gap-report"

_SARIF_LEVEL = {"high": "error", "medium": "warning", "low": "note"}


def to_json(findings: list[Finding]) -> str:
    return json.dumps([asdict(f) for f in findings], ensure_ascii=False, indent=2)


_CSV_FIELDNAMES = [f.name for f in fields(Finding)]


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
        writer.writerow(asdict(f))
    return buffer.getvalue()


def to_markdown(findings: list[Finding]) -> str:
    if not findings:
        return "Проблемных конструкций не найдено.\n"

    lines = [
        "| Файл | Объект | Строка | Серьёзность | Фрагмент | Комментарий |",
        "|---|---|---|---|---|---|",
    ]
    for f in findings:
        source_file = f.source_file.replace("|", "\\|")
        object_name = f.object_name.replace("|", "\\|")
        snippet = f.snippet.replace("|", "\\|")
        message = f.message.replace("|", "\\|").replace("\n", " ")
        lines.append(
            f"| {source_file} | `{object_name}` | {f.line} | {f.severity} "
            f"| `{snippet}` | {message} |"
        )
    return "\n".join(lines) + "\n"


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
