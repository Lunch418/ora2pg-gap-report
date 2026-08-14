import json
from dataclasses import asdict

from .models import Finding


def to_json(findings: list[Finding]) -> str:
    return json.dumps([asdict(f) for f in findings], ensure_ascii=False, indent=2)


def to_markdown(findings: list[Finding]) -> str:
    if not findings:
        return "Проблемных конструкций не найдено.\n"

    lines = [
        "| Объект | Строка | Серьёзность | Фрагмент | Комментарий |",
        "|---|---|---|---|---|",
    ]
    for f in findings:
        snippet = f.snippet.replace("|", "\\|")
        message = f.message.replace("|", "\\|").replace("\n", " ")
        lines.append(
            f"| `{f.object_name}` | {f.line} | {f.severity} | `{snippet}` | {message} |"
        )
    return "\n".join(lines) + "\n"
