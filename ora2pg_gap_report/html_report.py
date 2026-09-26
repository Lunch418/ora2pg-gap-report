"""The --format html report: one self-contained page, organised around the
question a migration plan starts from -- when will each gap bite?

Its layout follows the failure stages in the order a migration meets them
(conversion, schema load, run time, silently), then lists every gap once:
its title, why it happens, what to do, and every place it was found. The
explanation used to be repeated in each row of one long table, which made
a 389-finding report 700 KB of the same paragraphs.

Everything is inline -- no script, no stylesheet, no font or image from
anywhere else -- because the report is made to be opened in a closed
network. The filters are plain radio buttons and CSS (:has()); a browser
without :has() shows everything, which is still the whole report."""

from __future__ import annotations

import dataclasses
import html
import re
from collections import Counter
from collections.abc import Callable
from importlib import metadata
from typing import IO

from . import i18n, messages
from .effort_estimator import estimate_hours, summarize_by_severity
from .gap_registry import gap_by_detector
from .models import Finding

Write = Callable[[str], object]

# The order a migration meets the stages in. None collects what has no
# stage: cost-estimation gaps and the dbms_utl_calls classifier.
STAGES: tuple[str | None, ...] = ("conversion", "deployment", "runtime", "semantic", None)
_SEVERITIES = ("high", "medium", "low")
_SOURCE_NAME = {"oracle": "Oracle", "mysql": "MySQL/MariaDB", "mssql": "SQL Server"}
_TOP_OBJECTS = 10

_CSS = """
:root {
  --paper: #f4f6f8; --surface: #ffffff; --ink: #18202b; --muted: #5b6675;
  --rule: #d9dee5; --soft: #eef1f5; --focus: #245b8f;
  --high: #b42318; --medium: #a15c07; --low: #1d5fb0;
  --conversion: #6d3fc0; --deployment: #b42318; --runtime: #c2410c;
  --semantic: #0f766e; --none: #6b7280;
  --sans: system-ui, -apple-system, "Segoe UI", Roboto, Ubuntu, Cantarell, "Noto Sans", sans-serif;
  --mono: ui-monospace, "Cascadia Code", "JetBrains Mono", "SF Mono", Menlo, Consolas, monospace;
  color-scheme: light dark;
}
@media (prefers-color-scheme: dark) {
  :root {
    --paper: #12161c; --surface: #1a2029; --ink: #e6eaf0; --muted: #9aa5b4;
    --rule: #2c3440; --soft: #222a35; --focus: #7fb0e6;
    --high: #f97066; --medium: #f5b049; --low: #7cb4f5;
    --conversion: #b49cf5; --deployment: #f97066; --runtime: #fb8c4a;
    --semantic: #4fd1c0; --none: #9aa5b4;
  }
}
* { box-sizing: border-box; }
html { background: var(--paper); }
body { margin: 0; color: var(--ink); background: var(--paper); font: 15px/1.55 var(--sans); }
.page { max-width: 72rem; margin: 0 auto; padding: 2.5rem 1.5rem 4rem; }
code, .mono { font-family: var(--mono); font-size: 0.92em; }
h1 { font-size: 2.1rem; line-height: 1.2; letter-spacing: -0.015em; margin: 0 0 0.75rem; font-weight: 650; max-width: 30em; }
h2 { font-size: 1.25rem; margin: 3rem 0 1rem; font-weight: 650; }
h3 { font-size: 0.95rem; margin: 1.25rem 0 0.35rem; color: var(--muted); font-weight: 600; }
.lede { margin: 0; color: var(--muted); max-width: 44em; }
.lede strong { color: var(--ink); font-weight: 600; }

.rail { list-style: none; margin: 2rem 0 0; padding: 0; display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 0; }
.rail li { position: relative; padding: 1.1rem 1.25rem 1.25rem 0; }
.rail li + li { padding-left: 1.25rem; border-left: 1px solid var(--rule); }
.rail .stage-name { font-weight: 600; display: flex; align-items: center; gap: 0.5rem; }
.rail .stage-name::before { content: ""; width: 0.7rem; height: 0.7rem; border-radius: 50%;
                            background: var(--stage); flex: none; }
.rail .stage-count { display: block; font-size: 2.6rem; line-height: 1.1; font-weight: 700;
                     margin: 0.5rem 0 0.1rem; font-variant-numeric: tabular-nums; color: var(--stage); }
.rail .stage-gaps { color: var(--muted); font-size: 0.88rem; }
.rail .stage-desc { display: block; color: var(--muted); font-size: 0.88rem; margin-top: 0.35rem; }
.rail .track { height: 4px; background: var(--soft); margin-top: 0.9rem; border-radius: 2px; overflow: hidden; }
.rail .track span { display: block; height: 100%; background: var(--stage); }
.rail li.empty { opacity: 0.45; }
.rail li.empty .stage-count { color: var(--muted); }
.aside-stage { margin: 0.75rem 0 0; color: var(--muted); font-size: 0.9rem; }

.strip { display: grid; grid-template-columns: minmax(0, 3fr) minmax(0, 2fr); gap: 2.5rem;
         margin-top: 2rem; padding-top: 1.5rem; border-top: 1px solid var(--rule); }
.sevbar { display: flex; height: 10px; border-radius: 5px; overflow: hidden; background: var(--soft); margin: 0.6rem 0; }
.sevbar span { display: block; height: 100%; }
.legend { display: flex; flex-wrap: wrap; gap: 0.25rem 1.25rem; font-size: 0.9rem; color: var(--muted); }
.legend b { color: var(--ink); font-variant-numeric: tabular-nums; }
.dot { display: inline-block; width: 0.6rem; height: 0.6rem; border-radius: 50%; margin-right: 0.35rem; vertical-align: 0.05em; }
.effort-range { font-size: 1.6rem; font-weight: 650; font-variant-numeric: tabular-nums; margin: 0.2rem 0; }
.caveat { color: var(--muted); font-size: 0.88rem; margin: 0; }
.label { color: var(--muted); font-size: 0.9rem; }

.filters { display: flex; flex-wrap: wrap; gap: 0.75rem 2.5rem; margin: 0 0 1.25rem; }
.filters fieldset { border: 0; padding: 0; margin: 0; display: flex; flex-wrap: wrap; align-items: center; gap: 0.4rem; }
.filters legend { float: left; margin-right: 0.5rem; color: var(--muted); font-size: 0.9rem; }
.filters input { position: absolute; opacity: 0; pointer-events: none; }
.filters label { cursor: pointer; padding: 0.25rem 0.75rem; border-radius: 999px; border: 1px solid var(--rule);
                 background: var(--surface); font-size: 0.88rem; }
.filters label .n { color: var(--muted); margin-left: 0.3rem; font-variant-numeric: tabular-nums; }
.filters input:checked + label { background: var(--ink); color: var(--surface); border-color: var(--ink); }
.filters input:checked + label .n { color: inherit; opacity: 0.75; }
.filters input:focus-visible + label { outline: 2px solid var(--focus); outline-offset: 2px; }

.gaps { border-top: 1px solid var(--rule); }
.gap { border-bottom: 1px solid var(--rule); border-left: 4px solid var(--stage); background: var(--surface); }
.gap > summary { list-style: none; cursor: pointer; display: grid; align-items: baseline;
                 grid-template-columns: 5.2rem minmax(0, 1fr) auto auto;
                 grid-template-areas: "num title meta badge"; gap: 0.25rem 1rem; padding: 0.9rem 1.1rem; }
.gap-num { grid-area: num; } .gap-title { grid-area: title; overflow-wrap: anywhere; }
.gap-meta { grid-area: meta; } .gap > summary .badge { grid-area: badge; justify-self: end; }
.gap > summary::-webkit-details-marker { display: none; }
.gap > summary:hover { background: var(--soft); }
.gap > summary:focus-visible { outline: 2px solid var(--focus); outline-offset: -2px; }
.gap-num { font-family: var(--mono); font-size: 0.85rem; color: var(--muted); }
.gap-title { font-weight: 600; }
.gap-title code { font-weight: 600; }
.gap-meta { color: var(--muted); font-size: 0.88rem; white-space: nowrap; font-variant-numeric: tabular-nums; }
.gap-body { padding: 0 1.1rem 1.25rem calc(5.2rem + 2.1rem); }
.gap-body p { margin: 0; max-width: 46em; }
.gap-stage { color: var(--stage); font-weight: 600; }
.badge { font-size: 0.78rem; font-weight: 650; padding: 0.1rem 0.5rem; border-radius: 4px; color: #fff; white-space: nowrap; }
.sev-high { background: var(--high); } .sev-medium { background: var(--medium); } .sev-low { background: var(--low); }
@media (prefers-color-scheme: dark) { .badge { color: #12161c; } }

table.where { width: 100%; border-collapse: collapse; font-size: 0.88rem; margin-top: 0.4rem; }
table.where th { text-align: left; font-weight: 600; color: var(--muted); padding: 0.35rem 0.6rem 0.35rem 0;
                 border-bottom: 1px solid var(--rule); }
table.where td { padding: 0.35rem 0.6rem 0.35rem 0; border-bottom: 1px solid var(--soft); vertical-align: top; }
table.where td.num { text-align: right; font-variant-numeric: tabular-nums; color: var(--muted); }
table.where td.file { color: var(--muted); word-break: break-all; }
table.where td.snippet { word-break: break-word; }

.objects { list-style: none; padding: 0; margin: 0; columns: 2; column-gap: 2.5rem; }
.objects li { break-inside: avoid; display: flex; justify-content: space-between; gap: 1rem;
              padding: 0.4rem 0; border-bottom: 1px solid var(--rule); }
.objects .n { color: var(--muted); font-variant-numeric: tabular-nums; }

.empty-state { margin-top: 2.5rem; padding: 1.5rem 1.75rem; border-left: 4px solid var(--semantic); background: var(--surface); }
.empty-state h2 { margin: 0 0 0.4rem; }
.empty-state p { margin: 0; max-width: 46em; }
footer { margin-top: 3.5rem; color: var(--muted); font-size: 0.85rem; }

.st-conversion { --stage: var(--conversion); } .st-deployment { --stage: var(--deployment); }
.st-runtime { --stage: var(--runtime); } .st-semantic { --stage: var(--semantic); } .st-none { --stage: var(--none); }

__FILTER_RULES__

@media (max-width: 760px) {
  .page { padding: 1.5rem 1rem 3rem; }
  h1 { font-size: 1.6rem; }
  .rail { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .rail li:nth-child(3) { border-left: 0; padding-left: 0; }
  .strip { grid-template-columns: 1fr; gap: 1.5rem; }
  .gap > summary { grid-template-columns: minmax(0, 1fr) auto;
                   grid-template-areas: "num badge" "title title" "meta meta"; }
  .gap-meta { white-space: normal; }
  .gap-body { padding-left: 1.1rem; }
  .objects { columns: 1; }
}
@media print {
  html, body { background: #fff; }
  .filters { display: none; }
  .gap { break-inside: avoid-page; }
  details::details-content { content-visibility: visible; display: block; }
}
@media (prefers-reduced-motion: reduce) { * { transition: none !important; } }
"""


def stage_of(detector: str) -> str | None:
    """The failure stage a detector's gap is registered with, or None."""
    gap = gap_by_detector(detector)
    return gap.failure_stage if gap is not None else None


def stage_key(stage: str | None) -> str:
    """A stage as a word that names it in CSS classes and i18n keys."""
    return stage or "none"


def severity_rank(severity: str) -> int:
    return _SEVERITIES.index(severity) if severity in _SEVERITIES else len(_SEVERITIES)


@dataclasses.dataclass(frozen=True)
class GapGroup:
    """Every finding of one detector, with what the reports show about it."""

    detector: str
    findings: list[Finding]
    stage: str | None
    severity: str  # the most severe of its findings

    @property
    def objects(self) -> int:
        return len({(f.source_file, f.object_name) for f in self.findings})


def group_by_gap(findings: list[Finding]) -> list[GapGroup]:
    """The findings grouped by detector, in the order both reports list
    gaps: by the stage a migration reaches first, then severity, then the
    number of findings, largest first."""
    by_detector: dict[str, list[Finding]] = {}
    for f in findings:
        by_detector.setdefault(f.detector, []).append(f)
    groups = [
        GapGroup(d, group, stage_of(d), min((f.severity for f in group), key=severity_rank))
        for d, group in by_detector.items()
    ]
    return sorted(
        groups,
        key=lambda g: (STAGES.index(g.stage), severity_rank(g.severity), -len(g.findings), g.detector),
    )


def source_name(findings: list[Finding]) -> str:
    """How the reports name the source database: the dialect most of the
    findings' gaps belong to."""
    dialects = Counter(
        (gap.dialect if (gap := gap_by_detector(f.detector)) is not None else "oracle") for f in findings
    )
    dialect = dialects.most_common(1)[0][0] if dialects else "oracle"
    return _SOURCE_NAME.get(dialect, "Oracle")


def _filter_rules(severities: list[str], stages: list[str]) -> str:
    """One CSS rule per filter option: while that radio is checked, gaps
    that do not match it are hidden."""
    rules = [
        f'body:has(#sev-{s}:checked) .gap:not([data-sev="{s}"]) {{ display: none; }}' for s in severities
    ] + [
        f'body:has(#stage-{s}:checked) .gap:not([data-stage="{s}"]) {{ display: none; }}' for s in stages
    ]
    return "\n".join(rules)


def _title_html(detector: str, lang: str) -> str:
    """The detector's one-line title, escaped, with its `code` spans set in
    the monospace face."""
    escaped = html.escape(messages.title(detector, lang))
    return re.sub(r"`([^`]+)`", r"<code>\1</code>", escaped)


def _version() -> str:
    try:
        return metadata.version("ora2pg-gap-report")
    except metadata.PackageNotFoundError:
        return ""


def write_html(findings: list[Finding], stream: IO[str], lang: str = "ru") -> None:
    """Write the report for `findings` to `stream`."""
    w = stream.write
    gaps = group_by_gap(findings)
    counts = summarize_by_severity(findings)
    severities_present = [s for s in _SEVERITIES if counts.get(s)]
    stages_present = [stage_key(s) for s in STAGES if any(g.stage == s for g in gaps)]

    files = {f.source_file for f in findings if f.source_file}
    objects = {(f.source_file, f.object_name) for f in findings}
    html_lang = "en" if lang == "en" else "ru"
    heading = i18n.t(lang, "report_heading", source=source_name(findings))

    w(f"""<!doctype html>
<html lang="{html_lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(heading)} — ora2pg-gap-report</title>
<style>{_CSS.replace("__FILTER_RULES__", _filter_rules(severities_present, stages_present))}</style>
</head>
<body>
<main class="page">
<h1>{html.escape(heading)}</h1>
""")

    if not findings:
        w(f"""<section class="empty-state">
<h2>{i18n.t(lang, "report_empty_title")}</h2>
<p>{i18n.t(lang, "report_empty_text")}</p>
</section>
""")
        _write_footer(w, lang)
        return

    scanned = i18n.t(
        lang, "report_scanned",
        files=i18n.count(lang, "file", len(files)) if files else "—",
        objects=i18n.count(lang, "object", len(objects)),
    )
    found = i18n.t(
        lang, "report_found",
        findings=f"<strong>{i18n.count(lang, 'finding', len(findings))}</strong>",
        gaps=i18n.count(lang, "gap", len(gaps)),
    )
    w(f'<p class="lede">{scanned} {found}</p>\n')

    # The rail: the four stages in the order a migration reaches them.
    per_stage = Counter(stage_key(g.stage) for g in gaps for _ in g.findings)
    gaps_per_stage = Counter(stage_key(g.stage) for g in gaps)
    peak = max(per_stage.values())
    w(f'<ol class="rail" aria-label="{i18n.t(lang, "report_rail_label")}">\n')
    for stage in STAGES[:-1]:
        key = stage_key(stage)
        n = per_stage.get(key, 0)
        share = round(100 * n / peak) if peak else 0
        w(
            f'<li class="st-{key}{"" if n else " empty"}">'
            f'<span class="stage-name">{i18n.t(lang, f"stage_{key}_name")}</span>'
            f'<span class="stage-count">{n}</span>'
            f'<span class="stage-gaps">{i18n.count(lang, "gap", gaps_per_stage.get(key, 0))}</span>'
            f'<span class="stage-desc">{i18n.t(lang, f"stage_{key}_desc")}</span>'
            f'<div class="track"><span style="width:{share}%"></span></div>'
            "</li>\n"
        )
    w("</ol>\n")
    if per_stage.get("none"):
        w(
            f'<p class="aside-stage">{i18n.t(lang, "stage_none_name")}: '
            f'{i18n.count(lang, "finding", per_stage["none"])} — {i18n.t(lang, "stage_none_desc")}.</p>\n'
        )

    # Severity split and effort, side by side.
    total = len(findings)
    lo, hi = estimate_hours(findings)
    w('<div class="strip">\n<div>\n<span class="label">' + i18n.t(lang, "report_filter_severity") + "</span>\n")
    w('<div class="sevbar">')
    for s in severities_present:
        w(f'<span class="sev-{s}" style="width:{100 * counts[s] / total:.2f}%"></span>')
    w('</div>\n<div class="legend">')
    for s in severities_present:
        w(f'<span><span class="dot sev-{s}"></span>{s} <b>{counts[s]}</b></span>')
    w("</div>\n</div>\n<div>\n")
    w(f'<span class="label">{i18n.t(lang, "report_effort_label")}</span>\n')
    w(f'<p class="effort-range">{i18n.t(lang, "report_effort_range", lo=lo, hi=hi)}</p>\n')
    w(f'<p class="caveat">{html.escape(i18n.t(lang, "report_effort_caveat"))}</p>\n</div>\n</div>\n')

    # The gaps, each once.
    w(f'<h2>{i18n.t(lang, "report_gaps_heading")}</h2>\n')
    _write_filters(w, lang, severities_present, stages_present, gaps)
    w('<div class="gaps">\n')
    for gap in gaps:
        _write_gap(w, lang, gap)
    w("</div>\n")

    # The objects with the most findings.
    per_object = Counter((f.object_name, f.source_file) for f in findings)
    if len(per_object) > 1:
        w(f'<h2>{i18n.t(lang, "report_top_objects")}</h2>\n<ol class="objects">\n')
        for (obj, _src), n in per_object.most_common(_TOP_OBJECTS):
            w(f'<li><span class="mono">{html.escape(obj)}</span><span class="n">{n}</span></li>\n')
        w("</ol>\n")

    _write_footer(w, lang)


def _write_filters(w: Write, lang: str, severities: list[str], stages: list[str], gaps: list[GapGroup]) -> None:
    sev_gaps = Counter(g.severity for g in gaps)
    stage_gaps = Counter(stage_key(g.stage) for g in gaps)
    w('<div class="filters">\n')
    groups: tuple[tuple[str, str, list[str], Counter[str], Callable[[str], str]], ...] = (
        ("sev", "report_filter_severity", severities, sev_gaps, lambda s: s),
        ("stage", "report_filter_stage", stages, stage_gaps, lambda s: i18n.t(lang, f"stage_{s}_name")),
    )
    for group, legend, options, n_of, label_of in groups:
        if len(options) < 2:
            continue
        w(f"<fieldset><legend>{i18n.t(lang, legend)}</legend>")
        w(
            f'<input type="radio" name="{group}" id="{group}-all" checked>'
            f'<label for="{group}-all">{i18n.t(lang, "report_filter_all")}</label>'
        )
        for opt in options:
            w(
                f'<input type="radio" name="{group}" id="{group}-{opt}">'
                f'<label for="{group}-{opt}">{html.escape(label_of(opt))}<span class="n">{n_of[opt]}</span></label>'
            )
        w("</fieldset>\n")
    w("</div>\n")


def _write_gap(w: Write, lang: str, group_: GapGroup) -> None:
    detector, group, severity = group_.detector, group_.findings, group_.severity
    gap = gap_by_detector(detector)
    key = stage_key(group_.stage)
    number = f"GAP-{gap.number}" if gap is not None else "—"
    w(
        f'<details class="gap st-{key}" data-sev="{html.escape(severity)}" data-stage="{key}" '
        f'id="{html.escape(detector)}">\n<summary>'
        f'<span class="gap-num">{number}</span>'
        f'<span class="gap-title">{_title_html(detector, lang)}</span>'
        f'<span class="gap-meta">{i18n.count(lang, "finding", len(group))}, '
        f'{i18n.count(lang, "object", group_.objects)}</span>'
        f'<span class="badge sev-{html.escape(severity)}">{html.escape(severity)}</span>'
        "</summary>\n<div class=\"gap-body\">\n"
    )
    w(
        f'<p class="gap-stage">{i18n.t(lang, f"stage_{key}_name")}: {i18n.t(lang, f"stage_{key}_desc")}</p>\n'
    )
    w(f'<h3>{i18n.t(lang, "report_gap_why")}</h3>\n')
    for message_id in dict.fromkeys(f.message_id for f in group):
        w(f"<p>{html.escape(messages.text(message_id, lang))}</p>\n")
    hint = messages.remediation_hint(detector, lang)
    if hint:
        w(f'<h3>{i18n.t(lang, "report_gap_fix")}</h3>\n<p>{html.escape(hint)}</p>\n')
    w(
        f'<h3>{i18n.t(lang, "report_gap_where")}</h3>\n<table class="where"><thead><tr>'
        f'<th>{i18n.t(lang, "report_col_file")}</th><th>{i18n.t(lang, "report_col_line")}</th>'
        f'<th>{i18n.t(lang, "report_col_object")}</th><th>{i18n.t(lang, "report_col_snippet")}</th>'
        "</tr></thead>\n<tbody>\n"
    )
    for f in sorted(group, key=lambda f: (f.source_file, f.line)):
        w(
            f'<tr><td class="file">{html.escape(f.source_file) or "—"}</td>'
            f'<td class="num">{f.line or "—"}</td>'
            f'<td class="mono">{html.escape(f.object_name)}</td>'
            f'<td class="mono snippet">{html.escape(f.snippet)}</td></tr>\n'
        )
    w("</tbody></table>\n</div>\n</details>\n")


def _write_footer(w: Write, lang: str) -> None:
    version = _version()
    w(f'<footer>{html.escape(i18n.t(lang, "report_footer", version=version).replace("  ", " "))}</footer>\n')
    w("</main>\n</body>\n</html>\n")
