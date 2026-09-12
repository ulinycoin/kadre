"""Hermes image_gen provider: NanoGPT CyberRealistic XL / Pony v9."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from .nanogpt import generate as nanogpt_generate
    from .plan import make_plan
except ImportError:
    from nanogpt import generate as nanogpt_generate
    from plan import make_plan

try:
    from agent.image_gen_provider import (
        DEFAULT_ASPECT_RATIO,
        ImageGenProvider,
        error_response,
        normalize_reference_images,
        resolve_aspect_ratio,
        save_b64_image,
        success_response,
    )

    _HERMES = True
except ImportError:  # CLI / тесты без Hermes
    _HERMES = False
    ImageGenProvider = object  # type: ignore[misc,assignment]
    DEFAULT_ASPECT_RATIO = "portrait"
    resolve_aspect_ratio = lambda v: v or "portrait"  # noqa: E731
    normalize_reference_images = lambda v: v  # noqa: E731

    def error_response(**kwargs):  # type: ignore[no-redef]
        return {"success": False, **kwargs}

    def success_response(**kwargs):  # type: ignore[no-redef]
        return {"success": True, **kwargs}

    def save_b64_image(b64_data, *, prefix="image", extension="jpg"):  # type: ignore[no-redef]
        out = Path(os.environ.get("KADRE_OUT", ".kadre-out"))
        out.mkdir(parents=True, exist_ok=True)
        path = out / f"{prefix}.{extension}"
        import base64

        path.write_bytes(base64.b64decode(b64_data))
        return path


class NanoGptCyberProvider(ImageGenProvider):
    @property
    def name(self) -> str:
        return "nanogpt-cyber"

    @property
    def display_name(self) -> str:
        return "NanoGPT CyberRealistic"

    def is_available(self) -> bool:
        return bool(os.environ.get("NANOGPT_API_KEY") or os.environ.get("NANO_GPT_API_KEY"))

    def list_models(self) -> List[Dict[str, Any]]:
        return [
            {
                "id": "auto",
                "display": "Auto (XL / Pony по запросу)",
                "speed": "~8s",
                "strengths": "маршрутизация по тестам",
                "price": "$0.0051",
            },
            {
                "id": "cyberrealistic-xl",
                "display": "CyberRealistic XL",
                "speed": "~8s",
                "strengths": "лицо, возраст 50+, аксессуары, портрет",
                "price": "$0.0051",
            },
            {
                "id": "cyberrealistic-pony-v9",
                "display": "CyberRealistic Pony v9.0",
                "speed": "~8s",
                "strengths": "акт, cum, поза, живая кожа",
                "price": "$0.0051",
            },
        ]

    def default_model(self) -> Optional[str]:
        return "auto"

    def get_setup_schema(self) -> Dict[str, Any]:
        return {
            "name": "NanoGPT CyberRealistic",
            "badge": "paid",
            "tag": "XL + Pony v9 через NanoGPT, авто-маршрут по запросу",
            "env_vars": [
                {
                    "key": "NANOGPT_API_KEY",
                    "prompt": "NanoGPT API key",
                    "url": "https://nano-gpt.com",
                }
            ],
        }

    def capabilities(self) -> Dict[str, Any]:
        return {"modalities": ["text", "image"], "max_reference_images": 1}

    def generate(
        self,
        prompt: str,
        aspect_ratio: str = DEFAULT_ASPECT_RATIO,
        *,
        image_url: Optional[str] = None,
        reference_image_urls: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        text = (prompt or "").strip()
        aspect = resolve_aspect_ratio(aspect_ratio)
        if aspect not in ("landscape", "square", "portrait"):
            aspect = "portrait"
        low = text.lower()
        if aspect == "landscape" and not any(w in low for w in ("landscape", "горизонт", "wide", "16:9")):
            aspect = "portrait"
        if not text:
            return error_response(
                error="пустой запрос",
                error_type="invalid_argument",
                provider=self.name,
                aspect_ratio=aspect,
            )

        refs = []
        if image_url:
            refs.append(image_url)
        refs.extend(normalize_reference_images(reference_image_urls) or [])
        ref = refs[0] if refs else None

        override = kwargs.get("model")
        if override in (None, "", "auto"):
            override = None

        plan = make_plan(
            text,
            has_reference=bool(ref),
            model_override=override,
            aspect_ratio=aspect,
        )
        try:
            result = nanogpt_generate(
                model=plan.model,
                prompt=plan.prompt,
                negative_prompt=plan.negative_prompt,
                resolution=plan.resolution,
                guidance_scale=plan.guidance_scale,
                steps=plan.steps,
                reference=ref if plan.use_i2i else None,
                strength=plan.strength,
            )
        except Exception as exc:
            return error_response(
                error=str(exc),
                error_type=type(exc).__name__,
                provider=self.name,
                model=plan.model,
                prompt=plan.prompt,
                aspect_ratio=aspect,
            )

        path = save_b64_image(result["b64"], prefix="nanogpt-cyber", extension="jpg")
        extra = {
            "reason": plan.reason,
            "warnings": plan.warnings,
            "rewritten_prompt": plan.prompt,
            "negative_prompt": plan.negative_prompt,
            "cost": result.get("cost"),
            "balance": result.get("balance"),
            "used_i2i": plan.use_i2i,
            "strength": plan.strength,
        }
        return success_response(
            image=str(path),
            model=plan.model,
            prompt=plan.prompt,
            aspect_ratio=aspect,
            provider=self.name,
            modality="image" if plan.use_i2i else "text",
            extra=extra,
        )


def register(ctx) -> None:
    if not _HERMES:
        return
    ctx.register_image_gen_provider(NanoGptCyberProvider())
