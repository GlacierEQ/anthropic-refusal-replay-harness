"""Refusal replay harness — taxonomy-bound golden cases and drift detection."""
from __future__ import annotations

import copy
import hashlib
import json
import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Mapping


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _validate_args(args: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(args, Mapping):
        raise TypeError("args")
    materialized = copy.deepcopy(dict(args))
    # json round-trip is deliberate: unsupported and non-finite evidence fails closed.
    try:
        encoded = _canonical(materialized)
        decoded = json.loads(encoded)
    except (TypeError, ValueError) as exc:
        raise ValueError("ARGS_NOT_CANONICAL_JSON") from exc
    if not isinstance(decoded, dict):
        raise ValueError("ARGS_NOT_OBJECT")
    return decoded


class ReasonCategory(str, Enum):
    POLICY_RED_LINE = "POLICY_RED_LINE"
    CAPABILITY_SCOPE = "CAPABILITY_SCOPE"
    CONTEXT_INSUFFICIENT = "CONTEXT_INSUFFICIENT"
    ARGUMENT_SAFETY = "ARGUMENT_SAFETY"
    AUTHORITY = "AUTHORITY"
    UNKNOWN = "UNKNOWN"


class DiffKind(str, Enum):
    UNCHANGED = "UNCHANGED"
    REFUSAL_LOST = "REFUSAL_LOST"
    REFUSAL_GAINED = "REFUSAL_GAINED"
    REASON_CHANGED = "REASON_CHANGED"
    CATEGORY_CHANGED = "CATEGORY_CHANGED"
    BOTH_ALLOWED = "BOTH_ALLOWED"


@dataclass(frozen=True)
class ReasonTaxonomy:
    version: str = "v1"
    mapping: Mapping[str, ReasonCategory] = field(
        default_factory=lambda: {
            "RED_LINE": ReasonCategory.POLICY_RED_LINE,
            "NOT_IN_POLICY": ReasonCategory.CAPABILITY_SCOPE,
            "MISSING_CONTEXT": ReasonCategory.CONTEXT_INSUFFICIENT,
            "UNSAFE_ARGUMENT": ReasonCategory.ARGUMENT_SAFETY,
            "AUTHORITY_REQUIRED": ReasonCategory.AUTHORITY,
        }
    )

    def __post_init__(self) -> None:
        if not isinstance(self.version, str) or not self.version.strip():
            raise ValueError("taxonomy_version")
        for code, category in self.mapping.items():
            if not isinstance(code, str) or not code.strip():
                raise ValueError("reason_code")
            if not isinstance(category, ReasonCategory):
                raise TypeError("reason_category")

    def classify(self, reason: str | None) -> ReasonCategory:
        if reason is None:
            return ReasonCategory.UNKNOWN
        return self.mapping.get(reason, ReasonCategory.UNKNOWN)

    def fingerprint(self) -> str:
        return _digest(
            {
                "version": self.version,
                "mapping": {key: self.mapping[key].value for key in sorted(self.mapping)},
            }
        )


@dataclass(frozen=True)
class RefuseCase:
    case_id: str
    tool: str
    args: dict[str, Any]
    expected_reason: str
    expected_category: ReasonCategory | None = None
    mutation_stable: bool = False

    def __post_init__(self) -> None:
        for name, value in (("case_id", self.case_id), ("tool", self.tool), ("expected_reason", self.expected_reason)):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(name)
        object.__setattr__(self, "args", _validate_args(self.args))
        if self.expected_category is not None and not isinstance(self.expected_category, ReasonCategory):
            raise TypeError("expected_category")


@dataclass(frozen=True)
class CaseResult:
    case_id: str
    ok: bool
    expected: str
    actual: str | None
    expected_category: ReasonCategory
    actual_category: ReasonCategory
    allowed: bool


@dataclass(frozen=True)
class MutationResult:
    case_id: str
    mutation_id: str
    ok: bool
    actual: str | None
    actual_category: ReasonCategory
    args_digest: str


@dataclass(frozen=True)
class VersionCaseDiff:
    case_id: str
    kind: DiffKind
    old_allowed: bool
    new_allowed: bool
    old_reason: str | None
    new_reason: str | None
    old_category: ReasonCategory
    new_category: ReasonCategory


@dataclass(frozen=True)
class VersionDiffReport:
    old_version: str
    new_version: str
    taxonomy_version: str
    diffs: tuple[VersionCaseDiff, ...]
    fingerprint: str

    @property
    def equivalent(self) -> bool:
        return all(diff.kind is DiffKind.UNCHANGED for diff in self.diffs)

    @property
    def refusal_regression(self) -> bool:
        return any(diff.kind is DiffKind.REFUSAL_LOST for diff in self.diffs)


DecisionFn = Callable[[str, dict[str, Any]], tuple[bool, str]]


def deterministic_arg_mutations(args: Mapping[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    """Generate a bounded deterministic mutation corpus for mutation-stable refusals."""
    base = _validate_args(args)
    candidates: list[tuple[str, dict[str, Any]]] = []

    extra = copy.deepcopy(base)
    extra["__fuzz_extra__"] = True
    candidates.append(("extra-field", extra))

    nested = copy.deepcopy(base)
    nested["__fuzz_nested__"] = {"enabled": True, "payload": "mutation"}
    candidates.append(("nested-noise", nested))

    if base:
        first_key = sorted(base)[0]
        dropped = copy.deepcopy(base)
        dropped.pop(first_key, None)
        candidates.append((f"drop-{first_key}", dropped))

        value = base[first_key]
        changed = copy.deepcopy(base)
        if isinstance(value, str):
            changed[first_key] = value + "\u0000mutation"
            candidates.append((f"string-boundary-{first_key}", changed))
        elif isinstance(value, bool):
            changed[first_key] = not value
            candidates.append((f"boolean-flip-{first_key}", changed))
        elif isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value)):
            changed[first_key] = -value if value != 0 else 1
            candidates.append((f"numeric-boundary-{first_key}", changed))

    # Deduplicate structurally identical candidates while preserving deterministic order.
    out: list[tuple[str, dict[str, Any]]] = []
    seen: set[str] = set()
    for mutation_id, candidate in candidates:
        encoded = _canonical(candidate)
        if encoded in seen:
            continue
        seen.add(encoded)
        out.append((mutation_id, candidate))
    return out


class RefusalReplayHarness:
    def __init__(self, cases: list[RefuseCase], taxonomy: ReasonTaxonomy | None = None):
        if not cases:
            raise ValueError("cases")
        ids = [case.case_id for case in cases]
        if len(ids) != len(set(ids)):
            raise ValueError("DUPLICATE_CASE_ID")
        self.cases = list(cases)
        self.taxonomy = taxonomy or ReasonTaxonomy()

    def _expected_category(self, case: RefuseCase) -> ReasonCategory:
        return case.expected_category or self.taxonomy.classify(case.expected_reason)

    def _observe(self, decide: DecisionFn, case: RefuseCase, args: dict[str, Any] | None = None) -> tuple[bool, str | None, ReasonCategory]:
        decision_args = copy.deepcopy(case.args if args is None else args)
        allow, reason = decide(case.tool, decision_args)
        if not isinstance(allow, bool):
            raise TypeError("decision_allow")
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("decision_reason")
        actual = "ALLOWED" if allow else reason
        category = ReasonCategory.UNKNOWN if allow else self.taxonomy.classify(reason)
        return allow, actual, category

    def run(self, decide: DecisionFn) -> list[CaseResult]:
        out: list[CaseResult] = []
        for case in self.cases:
            expected_category = self._expected_category(case)
            allow, actual, actual_category = self._observe(decide, case)
            ok = (
                not allow
                and actual == case.expected_reason
                and actual_category is expected_category
                and expected_category is not ReasonCategory.UNKNOWN
            )
            out.append(
                CaseResult(
                    case_id=case.case_id,
                    ok=ok,
                    expected=case.expected_reason,
                    actual=actual,
                    expected_category=expected_category,
                    actual_category=actual_category,
                    allowed=allow,
                )
            )
        return out

    def all_ok(self, decide: DecisionFn) -> bool:
        return all(result.ok for result in self.run(decide))

    def run_mutation_fuzz(self, decide: DecisionFn) -> list[MutationResult]:
        out: list[MutationResult] = []
        for case in self.cases:
            if not case.mutation_stable:
                continue
            expected_category = self._expected_category(case)
            for mutation_id, args in deterministic_arg_mutations(case.args):
                allow, actual, actual_category = self._observe(decide, case, args)
                ok = (
                    not allow
                    and actual == case.expected_reason
                    and actual_category is expected_category
                    and expected_category is not ReasonCategory.UNKNOWN
                )
                out.append(
                    MutationResult(
                        case_id=case.case_id,
                        mutation_id=mutation_id,
                        ok=ok,
                        actual=actual,
                        actual_category=actual_category,
                        args_digest=_digest(args),
                    )
                )
        return out

    def mutation_fuzz_ok(self, decide: DecisionFn) -> bool:
        results = self.run_mutation_fuzz(decide)
        return bool(results) and all(result.ok for result in results)

    def compare_versions(
        self,
        old_version: str,
        old_decide: DecisionFn,
        new_version: str,
        new_decide: DecisionFn,
    ) -> VersionDiffReport:
        if not old_version.strip() or not new_version.strip():
            raise ValueError("version")
        diffs: list[VersionCaseDiff] = []
        for case in self.cases:
            old_allowed, old_reason, old_category = self._observe(old_decide, case)
            new_allowed, new_reason, new_category = self._observe(new_decide, case)
            if old_allowed and new_allowed:
                kind = DiffKind.BOTH_ALLOWED
            elif not old_allowed and new_allowed:
                kind = DiffKind.REFUSAL_LOST
            elif old_allowed and not new_allowed:
                kind = DiffKind.REFUSAL_GAINED
            elif old_category is not new_category:
                kind = DiffKind.CATEGORY_CHANGED
            elif old_reason != new_reason:
                kind = DiffKind.REASON_CHANGED
            else:
                kind = DiffKind.UNCHANGED
            diffs.append(
                VersionCaseDiff(
                    case_id=case.case_id,
                    kind=kind,
                    old_allowed=old_allowed,
                    new_allowed=new_allowed,
                    old_reason=old_reason,
                    new_reason=new_reason,
                    old_category=old_category,
                    new_category=new_category,
                )
            )

        body = {
            "old_version": old_version,
            "new_version": new_version,
            "taxonomy_version": self.taxonomy.version,
            "taxonomy_fingerprint": self.taxonomy.fingerprint(),
            "diffs": [
                {
                    "case_id": diff.case_id,
                    "kind": diff.kind.value,
                    "old_allowed": diff.old_allowed,
                    "new_allowed": diff.new_allowed,
                    "old_reason": diff.old_reason,
                    "new_reason": diff.new_reason,
                    "old_category": diff.old_category.value,
                    "new_category": diff.new_category.value,
                }
                for diff in diffs
            ],
        }
        return VersionDiffReport(
            old_version=old_version,
            new_version=new_version,
            taxonomy_version=self.taxonomy.version,
            diffs=tuple(diffs),
            fingerprint=_digest(body),
        )
