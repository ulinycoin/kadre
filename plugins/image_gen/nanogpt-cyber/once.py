"""Один платный вызов NanoGPT на запрос.

Hermes по умолчанию батчит до 4 image_generate и после кадра сам
запускает vision-QA / «ещё вариант». Этот слой сериализует вызовы
и отдаёт уже готовый файл, пока человек явно не попросит новый дубль.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import threading
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

try:
    import fcntl
except ImportError:  # Windows — межпроцессный замок недоступен
    fcntl = None  # type: ignore[assignment]

_lock = threading.Lock()
_index_mutex = threading.Lock()

CACHE_TTL_SEC = 15 * 60
SIMILARITY = 0.55

FORCE_RE = re.compile(
    r"(ещё|еще|перегенер\w*|заново|снова|retry|regenerate|another|again|redo|"
    r"другой\s+вариант|новый\s+кадр|ещё\s+один|еще\s+один|force)",
    re.IGNORECASE,
)

RETRY_FLUFF_RE = re.compile(
    r"\b("
    r"better|another|again|retry|variant|option|seed|anatomy|hands|fingers|"
    r"more\s+realistic|try\s+(again|xl|pony|once)|fix(ed|ing)?"
    r"|лучше|получше|попробуй|вариант|анатом\w*|пальц\w*|качеств\w*"
    r"|чётче|четче|переделай|исправь|перегенер\w*|заново|снова"
    r"|ещё\s+раз|еще\s+раз|другой\s+ракурс"
    r")\b",
    re.IGNORECASE,
)

AGENT_INSTRUCTION = (
    "Кадр готов и финальный. Не вызывай image_generate повторно, "
    "не делай варианты, не гоняй vision-QA. Покажи файл человеку. "
    "Новый вызов — только если он явно сказал «ещё» или «перегенерируй»."
)


@dataclass
class Shot:
    path: str
    core: str
    fingerprint: str
    request: str
    model: str
    ts: float
    reason: str = ""
    notes: list[str] | None = None

    def alive(self) -> bool:
        return bool(self.path) and Path(self.path).is_file()


def cache_dir() -> Path:
    override = os.environ.get("KADRE_CACHE")
    if override:
        d = Path(override)
    else:
        home = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes"))
        d = home / "cache" / "kadre"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _index_path() -> Path:
    return cache_dir() / "shots.json"


def _read_index(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"shots": [], "last": None}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"shots": [], "last": None}
    if not isinstance(data, dict):
        return {"shots": [], "last": None}
    data.setdefault("shots", [])
    data.setdefault("last", None)
    return data


def load_index() -> dict[str, Any]:
    return _read_index(_index_path())


def _write_atomic(path: Path, payload: str) -> None:
    """Временный файл + os.replace: обрыв записи не портит рабочий индекс."""
    tmp = path.with_name(f"{path.name}.tmp{os.getpid()}")
    try:
        tmp.write_text(payload, encoding="utf-8")
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass


@contextmanager
def _index_guard(path: Path):
    """Потоковый и межпроцессный замок: CLI и gateway пишут один и тот же индекс."""
    handle = None
    with _index_mutex:
        try:
            if fcntl is not None:
                handle = open(path.with_name(path.name + ".lock"), "a+")
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        except OSError:
            handle = None
        try:
            yield
        finally:
            if handle is not None:
                if fcntl is not None:
                    try:
                        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
                    except OSError:
                        pass
                handle.close()


def _update_index(mutate) -> dict[str, Any]:
    path = _index_path()
    with _index_guard(path):
        data = mutate(_read_index(path))
        _write_atomic(path, json.dumps(data, ensure_ascii=False, indent=2))
        return data


def save_index(data: dict[str, Any]) -> None:
    """Полная перезапись индекса (атомарно, под замком)."""
    _update_index(lambda _current: data)


def normalize_core(text: str) -> str:
    t = (text or "").strip().lower()
    t = RETRY_FLUFF_RE.sub(" ", t)
    t = re.sub(r"[^\wа-яё]+", " ", t, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", t).strip()


def wants_new_take(text: str) -> bool:
    """Короткая явная просьба человека сделать другой дубль."""
    t = (text or "").strip()
    if not t or not FORCE_RE.search(t):
        return False
    core = normalize_core(t)
    return len(t) <= 96 and len(core.split()) <= 3


def fingerprint(core: str, ref: str | None, aspect: str, model: str | None) -> str:
    raw = "|".join([core, ref or "", aspect or "portrait", model or "auto"])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def similar(a: str, b: str) -> bool:
    if not a or not b:
        return False
    if a == b:
        return True
    shorter, longer = (a, b) if len(a) <= len(b) else (b, a)
    if shorter in longer and len(shorter) >= 8:
        return True
    ta, tb = set(a.split()), set(b.split())
    if not ta or not tb:
        return False
    return len(ta & tb) / len(ta | tb) >= SIMILARITY


def _shot_from(raw: Any) -> Shot | None:
    if not isinstance(raw, dict):
        return None
    try:
        shot = Shot(
            path=str(raw.get("path") or ""),
            core=str(raw.get("core") or ""),
            fingerprint=str(raw.get("fingerprint") or ""),
            request=str(raw.get("request") or ""),
            model=str(raw.get("model") or ""),
            ts=float(raw.get("ts") or 0),
            reason=str(raw.get("reason") or ""),
            notes=list(raw.get("notes") or []),
        )
    except (TypeError, ValueError):
        return None
    return shot if shot.alive() else None


def remember(shot: Shot) -> None:
    now = time.time()

    def mutate(data: dict[str, Any]) -> dict[str, Any]:
        shots = []
        for raw in data.get("shots") or []:
            old = _shot_from(raw)
            if old and now - old.ts <= CACHE_TTL_SEC:
                shots.append(asdict(old))
        shots.append(asdict(shot))
        data["shots"] = shots[-40:]
        data["last"] = asdict(shot)
        return data

    _update_index(mutate)


def _looks_like_retry(text: str) -> bool:
    """Парафраз ретрая от агента («better anatomy, try again»), а не новый заказ."""
    return bool(RETRY_FLUFF_RE.search(text or ""))


def lookup(
    request: str,
    *,
    ref: str | None = None,
    aspect: str = "portrait",
    model: str | None = None,
) -> Shot | None:
    """Вернуть уже готовый кадр, если это ретрай агента, не новый заказ."""
    if wants_new_take(request):
        return None

    core = normalize_core(request)
    data = load_index()
    now = time.time()
    key = fingerprint(core, ref, aspect, model)

    for raw in reversed(data.get("shots") or []):
        shot = _shot_from(raw)
        if not shot or now - shot.ts > CACHE_TTL_SEC:
            continue
        if shot.fingerprint == key:
            return shot

    # Нечёткое совпадение — только для ретрая: иначе новый похожий заказ молча
    # получит старый файл с cost=0 и не будет сгенерирован вовсе.
    if not _looks_like_retry(request):
        return None

    last = _shot_from(data.get("last"))
    if last and now - last.ts <= CACHE_TTL_SEC:
        if not core:
            return last
        if similar(core, last.core):
            return last
    return None


def resolve_request(request: str) -> str:
    """«ещё» без сцены — взять текст прошлого заказа, чтобы план не разъехался."""
    text = (request or "").strip()
    if not wants_new_take(text):
        return text
    if len(normalize_core(text).split()) > 3:
        return text
    last = _shot_from(load_index().get("last"))
    return last.request if last and last.request else text


def guarded(fn, **kwargs):
    """Сериализовать параллельный батч Hermes (max_parallel_requests=4)."""
    with _lock:
        return fn(**kwargs)
