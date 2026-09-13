"""Hermes image_gen provider: NanoGPT CyberRealistic XL / Pony v9."""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from .nanogpt import generate as nanogpt_generate
    from .once import (
        AGENT_INSTRUCTION,
        Shot,
        fingerprint,
        guarded,
        lookup,
        normalize_core,
        remember,
        resolve_request,
    )
    from .plan import COST_ESTIMATE_USD, make_plan
    from .policy import underage_violation
except ImportError:
    from nanogpt import generate as nanogpt_generate
    from once import (
        AGENT_INSTRUCTION,
        Shot,
        fingerprint,
        guarded,
        lookup,
        normalize_core,
        remember,
        resolve_request,
    )
    from plan import COST_ESTIMATE_USD, make_plan
    from policy import underage_violation

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
        payload = {
            "success": True,
            "image": kwargs.get("image"),
            "model": kwargs.get("model"),
            "prompt": kwargs.get("prompt"),
            "aspect_ratio": kwargs.get("aspect_ratio"),
            "modality": kwargs.get("modality", "text"),
            "provider": kwargs.get("provider"),
        }
        extra = kwargs.get("extra") or {}
        for key, value in extra.items():
            payload.setdefault(key, value)
        return payload

    def save_b64_image(b64_data, *, prefix="image", extension="jpg"):  # type: ignore[no-redef]
        out = Path(os.environ.get("KADRE_OUT", ".kadre-out"))
        out.mkdir(parents=True, exist_ok=True)
        path = out / f"{prefix}.{extension}"
        import base64

        path.write_bytes(base64.b64decode(b64_data))
        return path


LOGGER_NAME = "hermes.plugin.kadre"
logger = logging.getLogger(LOGGER_NAME)

KADRE_SYSTEM = """Kadre / image_generate — одноразовый кадр.
- Один вызов image_generate на один запрос человека.
- Не делай варианты, не вызывай инструмент пачкой, не гоняй vision-QA.
- success=true значит кадр финальный. Покажи путь и модель. Стоп.
- Повтор — только если человек явно написал «ещё» или «перегенерируй».
- Модель XL/Pony и промпт выбирает nanogpt-cyber сам. Не подменяй «на всякий случай».
"""


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
        price = f"${COST_ESTIMATE_USD:.4f}"
        return [
            {
                "id": "auto",
                "display": "Auto (XL / Pony по запросу)",
                "speed": "~8s",
                "strengths": "маршрутизация по тестам",
                "price": price,
            },
            {
                "id": "cyberrealistic-xl",
                "display": "CyberRealistic XL",
                "speed": "~8s",
                "strengths": "лицо, возраст 50+, аксессуары, портрет",
                "price": price,
            },
            {
                "id": "cyberrealistic-pony-v9",
                "display": "CyberRealistic Pony v9.0",
                "speed": "~8s",
                "strengths": "акт, cum, поза, живая кожа",
                "price": price,
            },
        ]

    def default_model(self) -> Optional[str]:
        return "auto"

    def get_setup_schema(self) -> Dict[str, Any]:
        return {
            "name": "NanoGPT CyberRealistic",
            "badge": "paid",
            "tag": "XL + Pony v9 через NanoGPT, один кадр на запрос",
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
        return guarded(
            self._generate_locked,
            prompt=prompt,
            aspect_ratio=aspect_ratio,
            image_url=image_url,
            reference_image_urls=reference_image_urls,
            **kwargs,
        )

    def _generate_locked(
        self,
        prompt: str,
        aspect_ratio: str = DEFAULT_ASPECT_RATIO,
        *,
        image_url: Optional[str] = None,
        reference_image_urls: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        del kwargs  # n / upscale / лишние поля Hermes — игнор, всегда один кадр
        raw = (prompt or "").strip()
        aspect = resolve_aspect_ratio(aspect_ratio)
        if aspect not in ("landscape", "square", "portrait"):
            aspect = "portrait"
        low = raw.lower()
        if aspect == "landscape" and not any(w in low for w in ("landscape", "горизонт", "wide", "16:9")):
            aspect = "portrait"

        if underage_violation(raw):
            return error_response(
                error="запрос отклонён политикой: упоминание несовершеннолетних",
                error_type="policy_violation",
                provider=self.name,
                prompt=raw,
                aspect_ratio=aspect,
            )

        text = resolve_request(raw)
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

        cached = lookup(raw, ref=ref, aspect=aspect, model="auto")
        if cached:
            return self._finish(
                image=cached.path,
                model=cached.model,
                user_prompt=raw,
                aspect=aspect,
                plan_reason=cached.reason,
                notes=list(cached.notes or []) + ["повторный вызов агента — тот же кадр, NanoGPT не дергали"],
                used_i2i=False,
                strength=None,
                cached=True,
            )

        plan = make_plan(
            text,
            has_reference=bool(ref),
            model_override=None,
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
                prompt=raw,
                aspect_ratio=aspect,
            )

        path = save_b64_image(result["b64"], prefix="nanogpt-cyber", extension="jpg")
        core = normalize_core(text)
        remember(
            Shot(
                path=str(path),
                core=core,
                fingerprint=fingerprint(core, ref, aspect, "auto"),
                request=text,
                model=plan.model,
                ts=time.time(),
                reason=plan.reason,
                notes=list(plan.warnings),
            )
        )
        return self._finish(
            image=str(path),
            model=plan.model,
            user_prompt=raw,
            aspect=aspect,
            plan_reason=plan.reason,
            notes=list(plan.warnings),
            used_i2i=plan.use_i2i,
            strength=plan.strength,
            cached=False,
            cost=result.get("cost"),
            balance=result.get("balance"),
        )

    def _finish(
        self,
        *,
        image: str,
        model: str,
        user_prompt: str,
        aspect: str,
        plan_reason: str,
        notes: list[str],
        used_i2i: bool,
        strength: float | None,
        cached: bool,
        cost: Any = None,
        balance: Any = None,
    ) -> Dict[str, Any]:
        extra = {
            "final": True,
            "regenerate": False,
            "cached": cached,
            "agent_instruction": AGENT_INSTRUCTION,
            "reason": plan_reason,
            "notes": notes,
            "cost": 0 if cached else cost,
            "cost_estimate_usd": COST_ESTIMATE_USD,
            "balance": balance,
            "used_i2i": used_i2i,
            "strength": strength,
        }
        return success_response(
            image=image,
            model=model,
            prompt=user_prompt,
            aspect_ratio=aspect,
            provider=self.name,
            modality="image" if used_i2i else "text",
            extra=extra,
        )


def register(ctx) -> None:
    if not _HERMES:
        return
    ctx.register_image_gen_provider(NanoGptCyberProvider())
    try:
        ctx.register_system_prompt_section(
            "kadre.one-shot",
            KADRE_SYSTEM,
            position="after_memory",
            max_chars=900,
        )
    except Exception as exc:
        # Молчание тут = агент снова начнёт батчить кадры и платить дважды.
        logger.warning("kadre: секция промпта не зарегистрирована: %s", exc)
    skill = Path(__file__).resolve().parent / "skill"
    if not skill.is_dir():
        skill = Path(__file__).resolve().parents[3] / "skills" / "kadre"
    if skill.is_dir():
        try:
            ctx.register_skill("kadre", str(skill))
        except Exception as exc:
            logger.warning("kadre: скилл не зарегистрирован (%s): %s", skill, exc)
