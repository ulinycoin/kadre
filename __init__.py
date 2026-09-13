"""Точка входа для `hermes plugins install ulinycoin/kadre`."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_PLUGIN = Path(__file__).resolve().parent / "plugins" / "image_gen" / "nanogpt-cyber"
if str(_PLUGIN) not in sys.path:
    sys.path.insert(0, str(_PLUGIN))
_SPEC = importlib.util.spec_from_file_location("kadre_nanogpt_cyber", _PLUGIN / "__init__.py")
if _SPEC is None or _SPEC.loader is None:
    raise ImportError(f"Kadre plugin not found: {_PLUGIN}")
_MOD = importlib.util.module_from_spec(_SPEC)
sys.modules["kadre_nanogpt_cyber"] = _MOD
_SPEC.loader.exec_module(_MOD)

register = _MOD.register
NanoGptCyberProvider = _MOD.NanoGptCyberProvider
