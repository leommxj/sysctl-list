from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class DocRecord:
    name: str
    namespace: str
    aliases: list[str]
    doc_path: str
    heading: str
    body: str
    prefix: str
    kind: str
    line_start: int | None = None
    line_end: int | None = None

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class SourceRecord:
    name: str
    namespace: str
    aliases: list[str]
    source_path: str
    api: str
    table: str
    path_segments: list[str]
    data_symbol: str = ""
    handler_symbol: str = ""
    trail: list[str] = field(default_factory=list)

    def to_json(self) -> dict[str, Any]:
        return asdict(self)
