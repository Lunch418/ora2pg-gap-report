import re

from ..models import Finding
from ..plsql_lex import line_at, mask_strings_and_comments, qualified_name_pattern

_TRIGGER_START_RE = re.compile(
    qualified_name_pattern(
        r"CREATE\s+(?:OR\s+REPLACE\s+)?(?:EDITIONABLE\s+|NONEDITIONABLE\s+)?TRIGGER"
    ),
    re.IGNORECASE,
)
_COMPOUND_RE = re.compile(r"\bCOMPOUND\s+TRIGGER\b", re.IGNORECASE)


def find_compound_triggers(source: str) -> list[Finding]:
    """Detect CREATE [OR REPLACE] TRIGGER ... COMPOUND TRIGGER declarations.

    Bounds each trigger by the next CREATE TRIGGER statement (or end of
    file) rather than full block matching — Oracle does not support nested
    trigger declarations, so this is exact, not an approximation.
    """
    clean = mask_strings_and_comments(source)
    matches = list(_TRIGGER_START_RE.finditer(clean))

    findings: list[Finding] = []
    for idx, match in enumerate(matches):
        boundary = matches[idx + 1].start() if idx + 1 < len(matches) else len(clean)
        span = clean[match.end() : boundary]

        compound_match = _COMPOUND_RE.search(span)
        if not compound_match:
            continue

        absolute_pos = match.end() + compound_match.start()
        line_no = line_at(clean, absolute_pos)

        findings.append(
            Finding(
                detector="compound_triggers",
                severity="high",
                object_name=match.group(1).upper(),
                line=line_no,
                snippet=compound_match.group(0).strip(),
                message_id="compound_triggers",
            )
        )

    return findings
