"""План кадра для агента: модель, промпт, i2i, предупреждения."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

try:
    from .prompts import aspect_to_resolution, build_prompts, model_display
    from .router import Route, route
except ImportError:
    from prompts import aspect_to_resolution, build_prompts, model_display
    from router import Route, route


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
    cost_usd: float = 0.0051

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def make_plan(
    request: str,
    *,
    has_reference: bool = False,
    model_override: str | None = None,
    aspect_ratio: str = "portrait",
) -> Plan:
    decided: Route = route(
        request,
        has_reference=has_reference,
        model_override=model_override,
    )
    prompt, negative = build_prompts(request, decided)
    cfg = 6.0 if decided.model.endswith("pony-v9") else 5.5
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
    )
