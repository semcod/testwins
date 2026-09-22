from __future__ import annotations
from dataclasses import dataclass, asdict, field
from typing import Any
from .util import digest

@dataclass
class Finding:
    rule: str
    title: str
    message: str
    selectors: list[str]
    rects: list[dict]
    severity: str = "normal"
    confidence: float = 0.9
    candidate: bool = False
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict: return asdict(self)


def identity(project: str, stage: str, finding: dict) -> str:
    # No browser, viewport, coordinates, screenshot hash or volatile text in the key.
    # Stage is operator-owned route/journey id + step id, preserving application state.
    import re
    stage=re.sub(r"--scroll-[0-9]+$","--initial",stage)
    return "tw-" + digest({"v":1,"project":project,"stage":stage,
                            "rule":finding["rule"],"selectors":sorted(set(finding["selectors"]))})[:32]
