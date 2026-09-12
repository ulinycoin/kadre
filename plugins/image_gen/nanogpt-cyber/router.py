"""Маршрутизация CyberRealistic XL / Pony v9 по итогам живых тестов NanoGPT."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

ModelId = Literal["cyberrealistic-xl", "cyberrealistic-pony-v9"]
Intent = Literal["look", "act", "pose_change", "i2i_fix", "age"]

ACT_TERMS = (
    "sex", "cowgirl", "missionary", "doggy", "blowjob", "bj", "anal",
    "pissing", "peeing", "urine", "cum", "semen", "facial", "bukkake",
    "ejaculation", "cunnilingus", "licking pussy", "penis", "vaginal",
    "минет", "анал", "наездниц", "секс", "половой", "сперм", "конч",
    "писсинг", "моч", "куни", "вылиз", "эякул", "член", "вагин",
    "оральн", "проникновен",
)

LOOK_TERMS = (
    "harley", "lara", "croft", "cleopatra", "catwoman", "witch",
    "wonder woman", "amazon", "vampire", "barbie", "холли", "харли",
    "лара", "клеопатр", "ведьм", "амазон", "вампир", "барби",
    "аксессуар", "кобур", "бита", "чокер", "тиара", "корона",
)

BARBIE_TERMS = ("barbie", "барби", "fashion doll", "кукл")
AGE50_TERMS = (
    "50+", "52", "55", "50 year", "50-year", "mature", "milf",
    "50 лет", "пятьдесят", "возрастн",
)
POSE_CHANGE_TERMS = (
    "sitting", "seated", "squat", "cowgirl", "doggy", "kneeling",
    "look back", "lean", "сидит", "сидяч", "корточ", "наездн",
    "раком", "стоит", "поза",
)
I2I_FIX_TERMS = (
    "убери", "докрути", "убери пистолет", "сосок", "remove",
    "fix", "same pose", "та же поза", "тот же кадр",
)


@dataclass
class Route:
    model: ModelId
    intent: Intent
    reason: str
    i2i_ok: bool
    strength: float | None
    warnings: list[str] = field(default_factory=list)


def _has(text: str, terms: tuple[str, ...]) -> bool:
    return any(term in text for term in terms)


def route(
    request: str,
    *,
    has_reference: bool = False,
    model_override: str | None = None,
) -> Route:
    text = (request or "").strip().lower()
    warnings: list[str] = []

    is_act = _has(text, ACT_TERMS)
    is_look = _has(text, LOOK_TERMS)
    is_barbie = _has(text, BARBIE_TERMS)
    is_age50 = _has(text, AGE50_TERMS)
    is_pose_change = _has(text, POSE_CHANGE_TERMS)
    is_fix = _has(text, I2I_FIX_TERMS)

    if model_override in ("cyberrealistic-xl", "cyberrealistic-pony-v9"):
        intent: Intent = "act" if is_act else "look"
        strength = _strength(has_reference, is_act, is_pose_change, is_fix)
        if has_reference and is_pose_change and not is_fix:
            warnings.append(
                "i2i с референса почти не меняет позу. Для новой позы — txt2img без картинки."
            )
        return Route(
            model=model_override,
            intent=intent,
            reason="модель задана явно",
            i2i_ok=has_reference and not (is_pose_change and not is_fix),
            strength=strength,
            warnings=warnings,
        )

    if is_barbie and not is_act:
        return Route(
            model="cyberrealistic-pony-v9",
            intent="look",
            reason="Барби/кукла: XL уводит кожу в силикон, Pony держит живое тело",
            i2i_ok=has_reference,
            strength=0.4 if has_reference else None,
        )

    if is_age50 and not is_act:
        return Route(
            model="cyberrealistic-xl",
            intent="age",
            reason="50+: XL держит возраст на лице и теле, Pony омолаживает",
            i2i_ok=has_reference,
            strength=0.38 if has_reference else None,
        )

    if has_reference and is_fix and not is_act:
        return Route(
            model="cyberrealistic-xl",
            intent="i2i_fix",
            reason="правка того же кадра: i2i через generations+imageDataUrl, strength 0.28–0.40",
            i2i_ok=True,
            strength=0.34,
            warnings=["input_references на /api/v1/images молча игнорируется — только imageDataUrl"],
        )

    if has_reference and is_pose_change:
        warnings.append(
            "Референс залипает в исходной позе даже на strength 0.75. "
            "Генерирую txt2img: лицо уедет, поза будет новой."
        )
        model: ModelId = "cyberrealistic-pony-v9" if is_act else "cyberrealistic-xl"
        return Route(
            model=model,
            intent="pose_change",
            reason="смена позы с референса не работает как i2i",
            i2i_ok=False,
            strength=None,
            warnings=warnings,
        )

    if is_act and has_reference:
        warnings.append(
            "Акт + референс внешности: i2i сохранит лицо и сотрёт акт, "
            "txt2img даст акт и сотрёт лицо. Беру Pony txt2img — приоритет сцены."
        )
        return Route(
            model="cyberrealistic-pony-v9",
            intent="act",
            reason="явный акт: Pony рисует действие, XL держит портрет и выкидывает акт",
            i2i_ok=False,
            strength=None,
            warnings=warnings,
        )

    if is_act:
        return Route(
            model="cyberrealistic-pony-v9",
            intent="act",
            reason="явный акт (секс/cum/писсинг/куни): Pony, теги действия в начале промпта",
            i2i_ok=False,
            strength=None,
        )

    if is_look or is_age50:
        return Route(
            model="cyberrealistic-xl",
            intent="look",
            reason="узнаваемый образ и аксессуары: XL (Лара, Харли, Клеопатра, кошка, ведьма)",
            i2i_ok=has_reference,
            strength=0.4 if has_reference else None,
        )

    return Route(
        model="cyberrealistic-xl",
        intent="look",
        reason="нет явного акта — XL как портретный дефолт",
        i2i_ok=has_reference,
        strength=0.4 if has_reference else None,
    )


def _strength(
    has_reference: bool,
    is_act: bool,
    is_pose_change: bool,
    is_fix: bool,
) -> float | None:
    if not has_reference:
        return None
    if is_fix:
        return 0.34
    if is_pose_change or is_act:
        return None
    return 0.4
