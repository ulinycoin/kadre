"""Сборка промптов CyberRealistic XL / Pony по рецептам с тестов."""

from __future__ import annotations

import re

try:
    from .router import ModelId, Route, matches
except ImportError:
    from router import ModelId, Route, matches

ADULT_XL = (
    "photorealistic 25 year old adult woman, 25yo, adult face, mature adult features, "
)
ADULT_PONY = "1girl, 25 year old adult woman, adult, 25yo, "
ADULT_NEG = (
    "child, teen, underage, loli, school, baby face, barely legal, young girl, "
)
ANATOMY_NEG = (
    "extra people, extra legs, extra feet, extra fingers, extra arms, fused bodies, "
)
JUNK_NEG = "watermark, text, logo, signature, username, blurry"

MIN_AGE = 21
DEFAULT_AGE = 25
AGE50_FALLBACK = "mature adult woman, 50+"

# Возраст — только число рядом с возрастным словом и без склейки с другой цифрой,
# иначе «55mm» и «1024x1408» читались бы как возраст.
_AGE_RE = re.compile(
    r"(?<![\d])(\d{1,2})\s*(?:y/?o\b|years?\s*old|год(?:а|ов)?\b|лет\b)(?![\w])",
    re.IGNORECASE,
)

ACT_FRONT = {
    "cum": "(cum:1.45), (semen:1.4), (facial:1.35), ",
    "сперм": "(cum:1.45), (semen:1.4), (facial:1.35), ",
    "piss": "(pissing:1.5), (female peeing:1.4), (urine stream:1.4), ",
    "писс": "(pissing:1.5), (female peeing:1.4), (urine stream:1.4), ",
    "cowgirl": "cowgirl sex, woman riding man, girl on top, (penis in pussy:1.35), ",
    "наездн": "cowgirl sex, woman riding man, girl on top, (penis in pussy:1.35), ",
    "blowjob": "blowjob, oral, penis in mouth, looking at camera, ",
    "минет": "blowjob, oral, penis in mouth, looking at camera, ",
    "anal": "(anal sex:1.4), penis in anus, rear view, ",
    "анал": "(anal sex:1.4), penis in anus, rear view, ",
    "cunnilingus": "(cunnilingus:1.5), male licking pussy, man's head between thighs, ",
    "вылиз": "(cunnilingus:1.5), male licking pussy, man's head between thighs, ",
    "куни": "(cunnilingus:1.5), male licking pussy, man's head between thighs, ",
}


def requested_age(text: str) -> int | None:
    """Возраст, явно названный в запросе («55 лет», «52 года», «30yo»)."""
    m = _AGE_RE.search(text or "")
    return int(m.group(1)) if m else None


def normalize_age(age: int | None) -> int:
    """Жёсткий пол 21+; без числа — дефолт 25 (совпадает с CLI --age)."""
    if age is None:
        return DEFAULT_AGE
    return max(MIN_AGE, int(age))


def build_prompts(request: str, route: Route) -> tuple[str, str]:
    raw = (request or "").strip()
    low = raw.lower()
    front = "".join(tag for key, tag in ACT_FRONT.items() if matches(low, key))

    if route.model == "cyberrealistic-pony-v9":
        prompt = _pony(raw, front, route)
    else:
        prompt = _xl(raw, front, route)
    return prompt, _negative(low)


def _xl(raw: str, front: str, route: Route) -> str:
    if route.intent == "age":
        age = requested_age(raw)
        if age is None:
            head = f"photorealistic {AGE50_FALLBACK}, "
            tail = AGE50_FALLBACK
        else:
            years = normalize_age(age)
            head = f"photorealistic {years} year old mature adult woman, {years}yo, "
            tail = f"{years} years old adult"
        return f"{front}{head}{raw}, looking at camera, 85mm, cinematic light, {tail}"
    return (
        f"{front}{ADULT_XL}{raw}, looking at camera, 85mm, cinematic light, "
        "professional photography, 25 years old adult"
    )


def _pony(raw: str, front: str, route: Route) -> str:
    scores = "score_9, score_8_up, score_7_up, source_photo, realistic, "
    return f"{scores}{front}{ADULT_PONY}{raw}, looking at viewer, professional photography"


def _negative(low: str) -> str:
    extra = ""
    if matches(low, "стоя") or matches(low, "stand"):
        extra += "sitting, squatting, "
    if matches(low, "наездн") or matches(low, "cowgirl"):
        extra += "standing, "
    if matches(low, "анал") or matches(low, "anal"):
        extra += "vaginal penetration, "
    return ADULT_NEG + ANATOMY_NEG + extra + JUNK_NEG


def aspect_to_resolution(aspect: str) -> str:
    return {
        "portrait": "768x1024",
        "square": "1024x1024",
        "landscape": "1024x768",
    }.get(aspect, "768x1024")


def model_display(model: ModelId) -> str:
    if model == "cyberrealistic-xl":
        return "CyberRealistic XL"
    return "CyberRealistic Pony v9.0"
