from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal


@dataclass(frozen=True)
class Observation:
    """A point-in-time observation with enough provenance to audit it."""

    entity_id: str
    metric: str
    value: float | int | str | None
    unit: str
    period_start: str | None
    period_end: str | None
    filed_at: str | None
    effective_at: str
    source: str
    source_locator: str
    raw_ref: str
    quality_status: Literal["valid", "missing", "suspicious"] = "valid"
    formula: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Evidence:
    evidence_id: str
    title: str
    source: str
    locator: str
    as_of: str
    excerpt: str
    supports: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["supports"] = list(self.supports)
        return data


@dataclass(frozen=True)
class Claim:
    claim_id: str
    text: str
    claim_type: str
    evidence_ids: tuple[str, ...] = ()
    formula_refs: tuple[str, ...] = ()
    confidence: float = 0.0
    caveats: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["evidence_ids"] = list(self.evidence_ids)
        data["formula_refs"] = list(self.formula_refs)
        data["caveats"] = list(self.caveats)
        return data


@dataclass
class DataManifest:
    run_id: str
    mode: str
    ticker: str
    as_of: str
    sources: list[dict[str, Any]] = field(default_factory=list)
    checks: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def as_jsonable(value: Any) -> Any:
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if isinstance(value, dict):
        return {str(k): as_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [as_jsonable(v) for v in value]
    return value
