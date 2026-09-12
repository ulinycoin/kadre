"""Клиент NanoGPT: txt2img и рабочий i2i (generations + imageDataUrl)."""

from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

API_IMAGES = "https://nano-gpt.com/api/v1/images"
API_GENERATIONS = "https://nano-gpt.com/api/v1/images/generations"


def api_key() -> str:
    return (os.environ.get("NANOGPT_API_KEY") or os.environ.get("NANO_GPT_API_KEY") or "").strip()


def _headers(key: str) -> dict[str, str]:
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {key}",
        "x-api-key": key,
    }


def _to_data_url(ref: str) -> str:
    if ref.startswith("data:image/"):
        return ref
    parsed = urlparse(ref)
    if parsed.scheme in ("http", "https"):
        req = urllib.request.Request(ref, method="GET")
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = r.read()
            ctype = r.headers.get("Content-Type", "image/jpeg").split(";")[0]
        return f"data:{ctype};base64,{base64.b64encode(raw).decode()}"
    path = Path(ref).expanduser()
    raw = path.read_bytes()
    suffix = path.suffix.lower()
    mime = {".png": "image/png", ".webp": "image/webp", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}.get(
        suffix, "image/jpeg"
    )
    return f"data:{mime};base64,{base64.b64encode(raw).decode()}"


def generate(
    *,
    model: str,
    prompt: str,
    negative_prompt: str,
    resolution: str,
    seed: int | None = None,
    guidance_scale: float = 5.5,
    steps: int = 30,
    reference: str | None = None,
    strength: float | None = None,
) -> dict[str, Any]:
    key = api_key()
    if not key:
        raise RuntimeError("Нет NANOGPT_API_KEY. Ключ: https://nano-gpt.com")

    payload: dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "negative_prompt": negative_prompt,
        "n": 1,
        "guidance_scale": guidance_scale,
        "num_inference_steps": steps,
        "response_format": "b64_json",
    }
    if seed is not None:
        payload["seed"] = seed

    if reference:
        payload["size"] = resolution
        payload["imageDataUrl"] = _to_data_url(reference)
        payload["strength"] = 0.34 if strength is None else strength
        url = API_GENERATIONS
    else:
        payload["resolution"] = resolution
        url = API_IMAGES

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        method="POST",
        headers=_headers(key),
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            body = json.loads(r.read())
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:800]
        raise RuntimeError(f"NanoGPT HTTP {e.code}: {detail}") from e

    b64 = body["data"][0]["b64_json"]
    return {
        "b64": b64,
        "bytes": base64.b64decode(b64),
        "cost": body.get("cost"),
        "balance": body.get("remainingBalance"),
        "endpoint": url,
    }
