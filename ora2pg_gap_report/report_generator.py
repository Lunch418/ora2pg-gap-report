import json
from dataclasses import asdict

from .models import Finding


def to_json(findings: list[Finding]) -> str:
    return json.dumps([asdict(f) for f in findings], ensure_ascii=False, indent=2)


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
