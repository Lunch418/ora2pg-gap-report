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
from pathlib import PurePath
import re
from collections import Counter
from collections.abc import Callable
from importlib import metadata
from typing import IO, TYPE_CHECKING

from . import i18n, messages
from .effort_estimator import estimate_hours, summarize_by_severity
from .gap_registry import gap_by_detector
from .models import Finding
from .prepare import prepare_command
from .recipes import recipe_for, recipe_url

if TYPE_CHECKING:
    from .load_check import LoadCheckResult

Write = Callable[[str], object]

# The order a migration meets the stages in. None collects what has no
# stage: cost-estimation gaps and the dbms_utl_calls classifier.
STAGES: tuple[str | None, ...] = ("conversion", "deployment", "runtime", "semantic", None)
_SEVERITIES = ("high", "medium", "low")
_SOURCE_NAME = {"oracle": "Oracle", "mysql": "MySQL/MariaDB", "mssql": "SQL Server"}
_TOP_OBJECTS = 10

_CSS = """
:root {
  --paper: #faf9f5; --surface: #ffffff; --ink: #1f1e1c; --muted: #6e6b63;
  --rule: #e6e3da; --soft: #f0eee6; --accent: #c96442; --focus: #c96442;
  --high: #b8322a; --medium: #a8680f; --low: #3f7f3a;
  --conversion: #6a5cc7; --deployment: #b8322a; --runtime: #a8680f;
  --semantic: #2b7f74; --none: #8a877f;
  --sans: system-ui, -apple-system, "Segoe UI", Roboto, Ubuntu, Cantarell, "Noto Sans", sans-serif;
  --serif: "Iowan Old Style", "Palatino Linotype", Palatino, "Book Antiqua", Georgia, "Noto Serif", serif;
  --mono: ui-monospace, "Cascadia Code", "JetBrains Mono", "SF Mono", Menlo, Consolas, monospace;
  --radius: 14px;
  color-scheme: light dark;
}
@media (prefers-color-scheme: dark) {
  :root {
    --paper: #1f1e1d; --surface: #262624; --ink: #eceae4; --muted: #a3a097;
    --rule: #3a3935; --soft: #2d2c29; --accent: #d97757; --focus: #d97757;
    --high: #ff6b80; --medium: #ebb85e; --low: #6cc67e;
    --conversion: #b1b9f9; --deployment: #ff6b80; --runtime: #ebb85e;
    --semantic: #5fc4b4; --none: #8f8b82;
  }
}
* { box-sizing: border-box; }
html { background: var(--paper); }
body { margin: 0; color: var(--ink); background: var(--paper); font: 15px/1.6 var(--sans); }
.page { max-width: 72rem; margin: 0 auto; padding: 2.5rem 1.5rem 4rem; }
code, .mono { font-family: var(--mono); font-size: 0.9em; }
.brand { margin: 0 0 1.5rem; font-family: var(--mono); font-size: 0.85rem; color: var(--muted); }
.brand .mark { color: var(--accent); font-weight: 700; margin-right: 0.4rem; }
.brand .ver { margin-left: 0.5rem; }
h1 { font-family: var(--serif); font-size: 2.6rem; line-height: 1.15; letter-spacing: -0.01em;
     margin: 0 0 0.75rem; font-weight: 500; max-width: 26em; }
h2 { font-family: var(--serif); font-size: 1.6rem; margin: 3.25rem 0 1rem; font-weight: 500; letter-spacing: -0.005em; }
h3 { font-size: 0.8rem; margin: 1.4rem 0 0.35rem; color: var(--muted); font-weight: 600; letter-spacing: 0.02em; }
.lede { margin: 0; color: var(--muted); max-width: 44em; }
.loadcard { margin: 1.75rem 0 0; padding: 1.1rem 1.25rem 1.2rem; background: var(--surface);
            border: 1px solid var(--rule); border-left: 4px solid var(--verdict); border-radius: var(--radius); }
.loadcard.ok { --verdict: var(--low); } .loadcard.bad { --verdict: var(--high); }
.loadcard .verdict { margin: 0; font-family: var(--serif); font-size: 1.35rem; color: var(--verdict); }
.loadcard .where-to { margin: 0.2rem 0 0; color: var(--muted); font-size: 0.9rem; }
.loadcard .cats { display: flex; flex-wrap: wrap; gap: 0.4rem 1.1rem; margin: 0.8rem 0 0; padding: 0; list-style: none;
                  font-size: 0.9rem; }
.loadcard .cats b { font-variant-numeric: tabular-nums; }
.loadcard table.where { margin-top: 0.9rem; }
.loadcard td.msg { font-family: var(--mono); font-size: 0.82rem; }
.loadcard a, .fix a { color: var(--accent); text-underline-offset: 2px; }
.loadcard details { margin-top: 0.9rem; }
.loadcard details > summary { cursor: pointer; color: var(--accent); font-size: 0.9rem; font-weight: 600; }
.loadcard details > summary:focus-visible { outline: 2px solid var(--focus); outline-offset: 3px; border-radius: 4px; }
.lede strong { color: var(--ink); font-weight: 600; }

.rail { list-style: none; margin: 2rem 0 0; padding: 0; display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 0;
        background: var(--surface); border: 1px solid var(--rule); border-radius: var(--radius); overflow: hidden; }
.rail li { position: relative; padding: 1.25rem 1.4rem 1.4rem; }
.rail li + li { border-left: 1px solid var(--rule); }
.rail .stage-name { font-weight: 600; display: flex; align-items: center; gap: 0.5rem; font-size: 0.92rem; }
.rail .stage-name::before { content: ""; width: 0.6rem; height: 0.6rem; border-radius: 50%;
                            background: var(--stage); flex: none; }
.rail .stage-count { display: block; font-family: var(--serif); font-size: 3.2rem; line-height: 1.05; font-weight: 500;
                     margin: 0.55rem 0 0.15rem; font-variant-numeric: lining-nums tabular-nums; color: var(--stage); }
.rail .stage-gaps { color: var(--ink); font-size: 0.88rem; }
.rail .stage-desc { display: block; color: var(--muted); font-size: 0.88rem; margin-top: 0.3rem; }
.rail .track { height: 3px; background: var(--soft); margin-top: 1rem; border-radius: 2px; overflow: hidden; }
.rail .track span { display: block; height: 100%; background: var(--stage); border-radius: 2px; }
.rail li.empty .stage-name, .rail li.empty .stage-gaps, .rail li.empty .stage-desc { opacity: 0.55; }
.rail li.empty .stage-count { color: var(--rule); }
.aside-stage { margin: 0.9rem 0 0; color: var(--muted); font-size: 0.9rem; }

.strip { display: grid; grid-template-columns: minmax(0, 3fr) minmax(0, 2fr); gap: 2.5rem; margin-top: 2.25rem; }
.sevbar { display: flex; gap: 3px; height: 8px; margin: 0.7rem 0; }
.sevbar span { display: block; height: 100%; border-radius: 4px; }
.legend { display: flex; flex-wrap: wrap; gap: 0.25rem 1.25rem; font-size: 0.9rem; color: var(--muted); }
.legend b { color: var(--ink); font-variant-numeric: tabular-nums; }
.dot { display: inline-block; width: 0.55rem; height: 0.55rem; border-radius: 50%; margin-right: 0.4rem; vertical-align: 0.05em; }
.effort-range { font-family: var(--serif); font-size: 2rem; font-weight: 500; font-variant-numeric: lining-nums tabular-nums;
                margin: 0.1rem 0 0.2rem; }
.caveat { color: var(--muted); font-size: 0.86rem; margin: 0; }
.label { color: var(--muted); font-size: 0.9rem; }

.filters { display: flex; flex-wrap: wrap; gap: 0.75rem 2.5rem; margin: 0 0 1.25rem; }
.filters fieldset { border: 0; padding: 0; margin: 0; display: flex; flex-wrap: wrap; align-items: center; gap: 0.4rem; }
.filters legend { float: left; margin-right: 0.5rem; color: var(--muted); font-size: 0.9rem; }
.filters input { position: absolute; opacity: 0; pointer-events: none; }
.filters label { cursor: pointer; padding: 0.28rem 0.8rem; border-radius: 999px; border: 1px solid var(--rule);
                 background: var(--surface); font-size: 0.88rem; transition: background 0.15s, border-color 0.15s; }
.filters label:hover { border-color: var(--muted); }
.filters label .n { color: var(--muted); margin-left: 0.35rem; font-variant-numeric: tabular-nums; }
.filters input:checked + label { background: var(--ink); color: var(--paper); border-color: var(--ink); }
.filters input:checked + label .n { color: inherit; opacity: 0.7; }
.filters input:focus-visible + label { outline: 2px solid var(--focus); outline-offset: 2px; }

.gaps { background: var(--surface); border: 1px solid var(--rule); border-radius: var(--radius); overflow: hidden; }
.gap { position: relative; border-top: 1px solid var(--rule); }
.gap:first-child { border-top: 0; }
.gap::before { content: ""; position: absolute; left: 0; top: 0; bottom: 0; width: 3px; background: var(--stage); }
.gap > summary { list-style: none; cursor: pointer; display: grid; align-items: baseline;
                 grid-template-columns: 5.2rem minmax(0, 1fr) auto auto;
                 grid-template-areas: "num title meta badge"; gap: 0.25rem 1rem; padding: 1rem 1.25rem 1rem 1.4rem;
                 transition: background 0.15s; }
.gap-num { grid-area: num; } .gap-title { grid-area: title; overflow-wrap: anywhere; }
.gap-meta { grid-area: meta; } .gap > summary .badge { grid-area: badge; justify-self: end; }
.gap > summary::-webkit-details-marker { display: none; }
.gap > summary:hover, .gap[open] > summary { background: var(--soft); }
.gap > summary:focus-visible { outline: 2px solid var(--focus); outline-offset: -2px; }
.gap-num { font-family: var(--mono); font-size: 0.82rem; color: var(--muted); }
.gap-title { font-weight: 600; }
.gap-title code { font-weight: 600; }
.gap-meta { color: var(--muted); font-size: 0.86rem; white-space: nowrap; font-variant-numeric: tabular-nums; }
.gap-body { padding: 0.25rem 1.25rem 1.5rem calc(5.2rem + 2.4rem); }
.gap[open] .gap-body { background: var(--soft); }
.gap-body p { margin: 0; max-width: 46em; }
.gap-stage { color: var(--stage); font-weight: 600; margin-top: 0.25rem !important; }
.fix { margin: 1rem 0 0.25rem; padding: 0.75rem 1rem 0.85rem; max-width: 50em; background: var(--surface);
       border: 1px solid var(--rule); border-radius: 10px; }
.fix h3 { margin-top: 0; color: var(--accent); }
.fix .recipe { margin-top: 0.5rem; }
.fix .handled { margin: 0 0 0.5rem; color: var(--low); font-weight: 600; }
.fix a { color: var(--accent); }
.badge { font-size: 0.76rem; font-weight: 650; padding: 0.12rem 0.55rem; border-radius: 999px; white-space: nowrap;
         color: var(--sev); background: color-mix(in srgb, var(--sev) 13%, transparent); }
.sev-high { --sev: var(--high); } .sev-medium { --sev: var(--medium); } .sev-low { --sev: var(--low); }
.dot.sev-high, .sevbar .sev-high { background: var(--high); } .dot.sev-medium, .sevbar .sev-medium { background: var(--medium); }
.dot.sev-low, .sevbar .sev-low { background: var(--low); }

table.where { width: 100%; border-collapse: collapse; font-size: 0.86rem; margin-top: 0.4rem;
              background: var(--surface); border: 1px solid var(--rule); border-radius: 10px;
              border-spacing: 0; border-collapse: separate; overflow: hidden; }
table.where th { text-align: left; font-weight: 600; color: var(--muted); padding: 0.5rem 0.75rem;
                 border-bottom: 1px solid var(--rule); font-size: 0.8rem; }
table.where td { padding: 0.4rem 0.75rem; border-top: 1px solid var(--soft); vertical-align: top; }
table.where tr:first-child td { border-top: 0; }
table.where td.num { text-align: right; font-variant-numeric: tabular-nums; color: var(--muted); }
table.where td.file { color: var(--muted); word-break: break-all; }
table.where td.snippet { word-break: break-word; color: var(--accent); }

.objects { list-style: none; padding: 0; margin: 0; columns: 2; column-gap: 2.5rem; }
.objects li { break-inside: avoid; display: flex; justify-content: space-between; gap: 1rem;
              padding: 0.45rem 0; border-bottom: 1px solid var(--rule); }
.objects .n { color: var(--muted); font-variant-numeric: tabular-nums; }

.empty-state { margin-top: 2.5rem; padding: 1.5rem 1.75rem; border: 1px solid var(--rule); border-radius: var(--radius);
               background: var(--surface); position: relative; overflow: hidden; }
.empty-state::before { content: ""; position: absolute; left: 0; top: 0; bottom: 0; width: 3px; background: var(--semantic); }
.empty-state h2 { margin: 0 0 0.4rem; }
.empty-state p { margin: 0; max-width: 46em; }
footer { margin-top: 3.5rem; padding-top: 1.25rem; border-top: 1px solid var(--rule); color: var(--muted); font-size: 0.85rem; }
footer .mark { color: var(--accent); font-weight: 700; margin-right: 0.4rem; font-family: var(--mono); }

.st-conversion { --stage: var(--conversion); } .st-deployment { --stage: var(--deployment); }
.st-runtime { --stage: var(--runtime); } .st-semantic { --stage: var(--semantic); } .st-none { --stage: var(--none); }

__FILTER_RULES__

@media (max-width: 760px) {
  .page { padding: 1.5rem 1rem 3rem; }
  h1 { font-size: 1.6rem; }
  .rail { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .rail li:nth-child(3) { border-left: 0; }
  .rail li:nth-child(n+3) { border-top: 1px solid var(--rule); }
  .strip { grid-template-columns: 1fr; gap: 1.5rem; }
  .gap > summary { grid-template-columns: minmax(0, 1fr) auto;
                   grid-template-areas: "num badge" "title title" "meta meta"; }
  .gap-meta { white-space: normal; }
  .gap-body { padding-left: 1.4rem; }
  table.where { display: block; overflow-x: auto; }
  .objects { columns: 1; }
}
@media print {
  html, body { background: #fff; }
  .rail, .gaps { border-radius: 0; }
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


def source_dialect(findings: list[Finding]) -> str:
    """The dialect most of the findings' gaps belong to ("oracle" when
    nothing says otherwise)."""
    dialects = Counter(
        (gap.dialect if (gap := gap_by_detector(f.detector)) is not None else "oracle") for f in findings
    )
    return dialects.most_common(1)[0][0] if dialects else "oracle"


def source_name(findings: list[Finding]) -> str:
    """How the reports name the source database."""
    return _SOURCE_NAME.get(source_dialect(findings), "Oracle")


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


def write_html(
    findings: list[Finding],
    stream: IO[str],
    lang: str = "ru",
    load: "LoadCheckResult | None" = None,
    handled: dict[str, str] | None = None,
) -> None:
    """Write the report for `findings` to `stream`. With `load` (from
    --migrate --load-check), a card near the top says whether the converted
    output loaded into PostgreSQL, and lists what did not, each error
    linked to its gap further down the page. `handled` (from --migrate,
    see migrate.handled_by_migrate) notes in a gap's card that the run
    already took care of it."""
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
<title>{html.escape(heading)} - ora2pg-gap-report</title>
<style>{_CSS.replace("__FILTER_RULES__", _filter_rules(severities_present, stages_present))}</style>
</head>
<body>
<main class="page">
<p class="brand"><span class="mark">*</span>ora2pg-gap-report<span class="ver">{html.escape(_version())}</span></p>
<h1>{html.escape(heading)}</h1>
""")

    if not findings:
        if load is not None:
            _write_load_card(w, lang, load, set())
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
    if load is not None:
        _write_load_card(w, lang, load, {g.detector for g in gaps})

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
            f'{i18n.count(lang, "finding", per_stage["none"])} - {i18n.t(lang, "stage_none_desc")}.</p>\n'
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
    w(f'<p class="effort-range">{i18n.t(lang, "report_effort_range", lo=i18n.hours(lang, lo), hi=i18n.hours(lang, hi))}</p>\n')
    w(f'<p class="caveat">{html.escape(i18n.t(lang, "report_effort_caveat"))}</p>\n</div>\n</div>\n')

    # The gaps, each once.
    w(f'<h2>{i18n.t(lang, "report_gaps_heading")}</h2>\n')
    _write_filters(w, lang, severities_present, stages_present, gaps)
    w('<div class="gaps">\n')
    for gap in gaps:
        _write_gap(w, lang, gap, (handled or {}).get(gap.detector))
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


_LOAD_ROWS_SHOWN = 40


def _write_load_card(w: Write, lang: str, load: "LoadCheckResult", gaps_on_page: set[str]) -> None:
    from .load_check import CATEGORIES, FAILING_CATEGORIES

    failing = [e for e in load.errors if e.category in FAILING_CATEGORIES]
    server = html.escape(load.target + (f" ({load.server_version})" if load.server_version else ""))
    statements = i18n.count(lang, "statement", load.statements)
    if not failing and load.incomplete:
        verdict = i18n.t(lang, "report_load_incomplete", files=i18n.count(lang, "file", len(load.skipped_files)))
        w(f'<section class="loadcard bad"><p class="verdict">{html.escape(verdict)}</p>\n')
    elif not failing:
        w(f'<section class="loadcard ok"><p class="verdict">{i18n.t(lang, "report_load_ok", statements=statements)}</p>\n')
    else:
        statements_of = i18n.count(lang, "statement_of", load.statements)
        verdict = i18n.t(lang, "report_load_bad", errors=i18n.count(lang, "error", len(failing)), statements=statements_of)
        w(f'<section class="loadcard bad"><p class="verdict">{verdict}</p>\n')
    w(f'<p class="where-to">{i18n.t(lang, "report_load_server", server=server)}</p>\n')
    counts = Counter(e.category for e in load.errors)
    if counts:
        w('<ul class="cats">')
        for category in CATEGORIES:
            if counts.get(category):
                w(f"<li>{i18n.t(lang, f'load_check_cat_{category}')} <b>{counts[category]}</b></li>")
        w("</ul>\n")
        # The missing-object errors by the object they miss: many errors,
        # few objects -- the ones to bring in or fix first.
        missing: Counter[str] = Counter()
        spelled: dict[str, str] = {}
        for e in load.errors:
            if e.missing:
                key = e.missing.lower().rsplit(".", 1)[-1]
                missing[key] += 1
                if len(e.missing) > len(spelled.get(key, "")):
                    spelled[key] = e.missing
        if missing:
            top = ", ".join(f"<code>{html.escape(spelled[k])}</code> {n}" for k, n in missing.most_common(5))
            w(f'<p class="where-to">{i18n.t(lang, "report_load_missing", n=len(missing), top=top)}</p>\n')
        w(f'<details><summary>{i18n.t(lang, "report_load_show", n=len(load.errors))}</summary>\n')
        w(
            f'<table class="where"><thead><tr><th>{i18n.t(lang, "report_col_file")}</th>'
            f'<th>{i18n.t(lang, "report_col_line")}</th><th>GAP</th><th>SQLSTATE</th>'
            f'<th>{i18n.t(lang, "report_load_col_message")}</th></tr></thead>\n<tbody>\n'
        )
        for e in load.errors[:_LOAD_ROWS_SHOWN]:
            if e.gap_number is not None or e.detector is not None:
                label = f"GAP-{e.gap_number}" if e.gap_number is not None else html.escape(e.detector or "")
                gap = (
                    f'<a href="#{html.escape(e.detector or "")}">{label}</a>'
                    if e.detector in gaps_on_page
                    else label
                )
            else:
                gap = html.escape(i18n.t(lang, f"load_check_cat_{e.category}"))
            w(
                f'<tr><td class="file">{html.escape(PurePath(e.file).name)}</td><td class="num">{e.line}</td>'
                f"<td>{gap}</td><td class=\"mono\">{e.sqlstate}</td><td class=\"msg\">{html.escape(e.message)}</td></tr>\n"
            )
        w("</tbody></table>\n")
        if len(load.errors) > _LOAD_ROWS_SHOWN:
            w(f'<p class="where-to">{i18n.t(lang, "report_load_more", n=len(load.errors) - _LOAD_ROWS_SHOWN)}</p>\n')
        w("</details>\n")
    w("</section>\n")


def _write_gap(w: Write, lang: str, group_: GapGroup, handled: str | None = None) -> None:
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
    # What to do first: it is what the reader acts on, and the explanation
    # under it is there for when the fix needs justifying.
    hint = messages.remediation_hint(detector, lang)
    recipe = recipe_for(detector)
    command = prepare_command(detector) if handled != "checklist_migrate_prepared" else None
    if hint or recipe is not None or command is not None or handled:
        w(f'<div class="fix"><h3>{i18n.t(lang, "report_gap_fix")}</h3>\n')
        if handled:
            w(f'<p class="handled"><code>--migrate</code>: {html.escape(i18n.t(lang, handled))}</p>\n')
        if hint:
            w(f"<p>{html.escape(hint)}</p>\n")
        if command is not None:
            w(f'<p class="recipe">{i18n.t(lang, "report_gap_prepare")}: <code>{html.escape(command)}</code></p>\n')
        if recipe is not None:
            w(
                f'<p class="recipe">{i18n.t(lang, "report_gap_recipe")}: '
                f'<a href="{html.escape(recipe_url(recipe, lang))}">{html.escape(recipe.title(lang))}</a></p>\n'
            )
        w("</div>\n")
    w(f'<h3>{i18n.t(lang, "report_gap_why")}</h3>\n')
    for message_id in dict.fromkeys(f.message_id for f in group):
        w(f"<p>{html.escape(messages.text(message_id, lang))}</p>\n")
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
    w(
        '<footer><span class="mark">*</span>'
        f'{html.escape(i18n.t(lang, "report_footer", version=version).replace("  ", " "))}</footer>\n'
    )
    w("</main>\n</body>\n</html>\n")
