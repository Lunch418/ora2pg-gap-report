from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Finding:
    """One flagged construct in one scanned file.

    `message_id` is a key into messages.MESSAGES, not the prose itself.
    A finding is produced once per occurrence -- a large migration scans
    hundreds of thousands of them -- and the explanation attached to each
    is a 400-600 character paragraph that is identical for every finding
    the same detector produces. Carrying the id and resolving it at render
    time keeps that paragraph in exactly one place, and makes the message
    text editable without silently breaking the Russian-text-as-key lookup
    that used to join a message to its translation (see messages.py).

    slots=True for the same reason: at 80,000 findings the per-instance
    __dict__ is the single largest thing this program allocates.
    """

    detector: str
    severity: str  # "low" | "medium" | "high"
    object_name: str
    line: int
    snippet: str
    message_id: str
    source_file: str = ""
