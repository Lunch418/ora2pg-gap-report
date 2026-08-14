from dataclasses import dataclass


@dataclass(frozen=True)
class Finding:
    detector: str
    severity: str  # "low" | "medium" | "high"
    object_name: str
    line: int
    snippet: str
    message: str
