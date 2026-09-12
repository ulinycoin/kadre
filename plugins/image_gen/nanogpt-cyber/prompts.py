"""Сборка промптов CyberRealistic XL / Pony по рецептам с тестов."""

from __future__ import annotations

try:
    from .router import ModelId, Route
except ImportError:
    from router import ModelId, Route

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


def build_prompts(request: str, route: Route) -> tuple[str, str]:
    raw = (request or "").strip()
    low = raw.lower()
    front = "".join(tag for key, tag in ACT_FRONT.items() if key in low)

    if route.model == "cyberrealistic-pony-v9":
        prompt = _pony(raw, front, route)
    else:
        prompt = _xl(raw, front, route)
    return prompt, _negative(low, route)


def _xl(raw: str, front: str, route: Route) -> str:
    if route.intent == "age":
        return (
            f"{front}photorealistic 52 year old mature adult woman, 52yo, {raw}, "
            "looking at camera, 85mm, cinematic light, 52 years old adult"
        )
    return (
        f"{front}{ADULT_XL}{raw}, looking at camera, 85mm, cinematic light, "
        "professional photography, 25 years old adult"
    )


def _pony(raw: str, front: str, route: Route) -> str:
    scores = "score_9, score_8_up, score_7_up, source_photo, realistic, "
    return f"{scores}{front}{ADULT_PONY}{raw}, looking at viewer, professional photography"


def _negative(low: str, route: Route) -> str:
    extra = ""
    if "стоя" in low or "stand" in low:
        extra += "sitting, squatting, "
    if "наездн" in low or "cowgirl" in low:
        extra += "standing, "
    if "анал" in low or "anal" in low:
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
