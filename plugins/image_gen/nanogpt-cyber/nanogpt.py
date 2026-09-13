"""Клиент NanoGPT: txt2img и рабочий i2i (generations + imageDataUrl).

Референс уходит третьей стороне целиком, поэтому он проходит проверку: только
https на публичный хост (без локалки и метадата-эндпоинтов, включая редиректы),
только настоящая картинка по magic-байтам и только до лимита размера. Иначе
агент (или текст со страницы) мог отправить наружу произвольный локальный файл.
"""

from __future__ import annotations

import base64
import ipaddress
import json
import os
import socket
import stat
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

API_IMAGES = "https://nano-gpt.com/api/v1/images"
API_GENERATIONS = "https://nano-gpt.com/api/v1/images/generations"

MAX_REFERENCE_BYTES = 12 * 1024 * 1024
REFERENCE_TIMEOUT_SEC = 30
_READ_CHUNK = 64 * 1024

_BLOCKED_HOST_NAMES = frozenset({"localhost", "metadata", "metadata.google.internal", "instance-data"})
_BLOCKED_HOST_SUFFIXES = (".localhost", ".local", ".internal", ".home.arpa")
_MAGIC_MIME = (
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"GIF87a", "image/gif"),
    (b"GIF89a", "image/gif"),
)


class ReferencePolicyError(ValueError):
    """Референс не прошёл проверку: схема, хост, размер или формат."""


def api_key() -> str:
    return (os.environ.get("NANOGPT_API_KEY") or os.environ.get("NANO_GPT_API_KEY") or "").strip()


def _headers(key: str) -> dict[str, str]:
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {key}",
        "x-api-key": key,
    }


def _sniff_mime(raw: bytes) -> str | None:
    """MIME по содержимому, а не по расширению или заголовку ответа."""
    for magic, mime in _MAGIC_MIME:
        if raw.startswith(magic):
            return mime
    if raw[:4] == b"RIFF" and raw[8:12] == b"WEBP":
        return "image/webp"
    return None


def _is_public_ip(value: str) -> bool:
    try:
        ip = ipaddress.ip_address(value)
    except ValueError:
        return False
    return not (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def _host_is_blocked(host: str) -> bool:
    host = (host or "").strip("[]").strip().lower().rstrip(".")
    if not host or host in _BLOCKED_HOST_NAMES or host.endswith(_BLOCKED_HOST_SUFFIXES):
        return True
    if _is_ip_literal(host):
        return not _is_public_ip(host)
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as exc:
        raise ReferencePolicyError(f"референс-URL не резолвится: {host}") from exc
    if not infos:
        raise ReferencePolicyError(f"референс-URL не резолвится: {host}")
    return any(not _is_public_ip(str(info[4][0])) for info in infos)


def _is_ip_literal(host: str) -> bool:
    try:
        ipaddress.ip_address(host)
    except ValueError:
        return False
    return True


def validate_reference_url(url: str) -> str:
    """Разрешить только https на публичный хост. Возвращает URL как есть."""
    parsed = urllib.parse.urlparse(url or "")
    if parsed.scheme != "https":
        raise ReferencePolicyError("референс по URL — только https")
    if not parsed.hostname:
        raise ReferencePolicyError("в референс-URL нет хоста")
    if _host_is_blocked(parsed.hostname):
        raise ReferencePolicyError(f"референс-URL ведёт внутрь сети: {parsed.hostname}")
    return url


class _SafeRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Каждый хоп редиректа проверяется теми же правилами: 302 тоже ведёт внутрь."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D102
        validate_reference_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_OPENER = urllib.request.build_opener(_SafeRedirectHandler())


def _fetch_url_bytes(url: str) -> bytes:
    """Тянет https-референс. Проверку хоста делает вызывающий (validate_reference_url)."""
    request = urllib.request.Request(url, method="GET")
    chunks: list[bytes] = []
    total = 0
    with _OPENER.open(request, timeout=REFERENCE_TIMEOUT_SEC) as response:
        while True:
            chunk = response.read(_READ_CHUNK)
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_REFERENCE_BYTES:
                raise ReferencePolicyError(f"референс больше {MAX_REFERENCE_BYTES} байт")
            chunks.append(chunk)
    return b"".join(chunks)


def _read_file_bytes(path: Path) -> bytes:
    try:
        info = path.stat()
    except OSError as exc:
        raise ReferencePolicyError(f"референс-файл недоступен: {path}") from exc
    if not stat.S_ISREG(info.st_mode):
        raise ReferencePolicyError(f"референс — не обычный файл: {path}")
    if info.st_size > MAX_REFERENCE_BYTES:
        raise ReferencePolicyError(f"референс-файл больше {MAX_REFERENCE_BYTES} байт")
    try:
        return path.read_bytes()
    except OSError as exc:
        raise ReferencePolicyError(f"референс-файл не читается: {path}") from exc


def _decoded_size(payload: str) -> int:
    return max(0, len(payload.strip()) * 3 // 4)


def _to_data_url(ref: str) -> str:
    """Референс → data-url. Всё, что не https-картинка в лимите, отклоняется."""
    if ref.startswith("data:"):
        head, _, payload = ref.partition(",")
        if not head.lower().startswith("data:image/") or "base64" not in head.lower():
            raise ReferencePolicyError("референс data-url должен быть image/*;base64")
        if _decoded_size(payload) > MAX_REFERENCE_BYTES:
            raise ReferencePolicyError(f"референс больше {MAX_REFERENCE_BYTES} байт")
        if _sniff_mime(base64.b64decode(payload, validate=False) or b"") is None:
            raise ReferencePolicyError("data-url не содержит картинку")
        return ref

    parsed = urllib.parse.urlparse(ref)
    if parsed.scheme in ("http", "https"):
        raw = _fetch_url_bytes(validate_reference_url(ref))
    elif parsed.scheme:
        raise ReferencePolicyError(f"схема референса не поддерживается: {parsed.scheme}")
    else:
        raw = _read_file_bytes(Path(ref).expanduser())

    if len(raw) > MAX_REFERENCE_BYTES:
        raise ReferencePolicyError(f"референс больше {MAX_REFERENCE_BYTES} байт")
    mime = _sniff_mime(raw)
    if mime is None:
        raise ReferencePolicyError("референс не картинка (jpeg/png/webp/gif)")
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
