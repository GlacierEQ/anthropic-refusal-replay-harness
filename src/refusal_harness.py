"""Refusal replay harness — golden refuse cases."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class RefuseCase:
    case_id: str
    tool: str
    args: dict
    expected_reason: str


@dataclass(frozen=True)
class CaseResult:
    case_id: str
    ok: bool
    expected: str
    actual: str | None


DecisionFn = Callable[[str, dict], tuple[bool, str]]  # allow?, reason


class RefusalReplayHarness:
    def __init__(self, cases: list[RefuseCase]):
        self.cases = cases

    def run(self, decide: DecisionFn) -> list[CaseResult]:
        out: list[CaseResult] = []
        for c in self.cases:
            allow, reason = decide(c.tool, c.args)
            if allow:
                out.append(CaseResult(c.case_id, False, c.expected_reason, "ALLOWED"))
            elif reason != c.expected_reason:
                out.append(CaseResult(c.case_id, False, c.expected_reason, reason))
            else:
                out.append(CaseResult(c.case_id, True, c.expected_reason, reason))
        return out

    def all_ok(self, decide: DecisionFn) -> bool:
        return all(r.ok for r in self.run(decide))
