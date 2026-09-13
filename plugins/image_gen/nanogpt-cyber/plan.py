"""План кадра для агента: модель, промпт, i2i, возраст, предупреждения."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

try:
    from .prompts import (
        DEFAULT_AGE,
        aspect_to_resolution,
        build_prompts,
        model_display,
        normalize_age,
        requested_age,
    )
    from .router import Route, route
except ImportError:
    from prompts import (
        DEFAULT_AGE,
        aspect_to_resolution,
        build_prompts,
        model_display,
        normalize_age,
        requested_age,
    )
    from router import Route, route

# Замер 2026-09-13 по дельтам баланса: 29 кадров = $0.0646 → ≈ $0.0022 за кадр.
# Прежние $0.0051 — смета планировщика, а не списание; агенту её показывать нельзя.
COST_ESTIMATE_USD = 0.0022


@dataclass
class Plan:
    model: str
    model_name: str
    prompt: str
    negative_prompt: str
    resolution: str
    use_i2i: bool
    strength: float | None
    reason: str
    warnings: list[str]
    guidance_scale: float
    steps: int
    cost_usd: float = COST_ESTIMATE_USD
    age: int = DEFAULT_AGE

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def make_plan(
    request: str,
    *,
    has_reference: bool = False,
    model_override: str | None = None,
    aspect_ratio: str = "portrait",
    age: int | None = None,
) -> Plan:
    decided: Route = route(
        request,
        has_reference=has_reference,
        model_override=model_override,
    )
    prompt, negative = build_prompts(request, decided, age=age)
    cfg = 6.0 if decided.model.endswith("pony-v9") else 5.5
    resolved_age = normalize_age(age if age is not None else requested_age(request))
    return Plan(
        model=decided.model,
        model_name=model_display(decided.model),
        prompt=prompt,
        negative_prompt=negative,
        resolution=aspect_to_resolution(aspect_ratio),
        use_i2i=bool(has_reference and decided.i2i_ok),
        strength=decided.strength if (has_reference and decided.i2i_ok) else None,
        reason=decided.reason,
        warnings=list(decided.warnings),
        guidance_scale=cfg,
        steps=30,
        age=resolved_age,
    )
