import csv
import io
import json
from dataclasses import asdict, fields

from .models import Finding


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
