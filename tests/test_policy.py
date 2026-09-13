#!/usr/bin/env python3
"""Политика: запросы с несовершеннолетними не должны уходить в NanoGPT."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[1] / "plugins" / "image_gen" / "nanogpt-cyber"
sys.path.insert(0, str(PLUGIN))

from policy import underage_violation  # noqa: E402

REJECT = (
    "16yo schoolgirl, cum on face",
    "girl 17 years old, portrait",
    "девочка 15 лет, портрет",
    "несовершеннолетняя модель, студия",
    "подросток в кадре, портрет",
    "школьница в форме, портрет",
    "ребёнок на фоне, студия",
    "loli style portrait",
    "underage model, studio",
    "младше 21, портрет",
)

ALLOW = (
    "25 year old woman, studio",
    "женщина 52 года, полный рост",
    "харли квинн склад бита",
    "18yo adult woman, studio",
    "21 year old adult woman",
    "mature milf portrait, 50+",
    "объектив 55mm, портрет",
    "кадр 1024x1408, студия",
    "harley quinn, 16 candles scene",
)

# Осознанно консервативно: проверка идёт по словам, а не по смыслу — фраза с отрицанием
# («дети на фоне не нужны») тоже отклоняется. Ложный отказ дешевле пропущенного запроса.
REJECT_NEGATIONS = ("дети на заднем плане нет", "no children in frame, studio")


class UnderagePolicyTests(unittest.TestCase):
    def test_rejects_minor_markers(self):
        for text in REJECT:
            with self.subTest(text=text):
                self.assertTrue(underage_violation(text))

    def test_allows_adults(self):
        for text in ALLOW:
            with self.subTest(text=text):
                self.assertFalse(underage_violation(text))

    def test_negations_are_refused_conservatively(self):
        for text in REJECT_NEGATIONS:
            with self.subTest(text=text):
                self.assertTrue(underage_violation(text))


class PolicyWiringTests(unittest.TestCase):
    """Запрет должен срабатывать до выхода в сеть, а не только в негативе промпта."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["KADRE_CACHE"] = self.tmp.name
        os.environ["KADRE_OUT"] = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()
        os.environ.pop("KADRE_CACHE", None)
        os.environ.pop("KADRE_OUT", None)

    def test_provider_refuses_without_calling_api(self):
        import __init__ as provider_mod

        calls = []

        def fake_generate(**kwargs):
            calls.append(kwargs)
            return {"b64": "", "cost": 0, "balance": 0}

        provider = provider_mod.NanoGptCyberProvider()
        original = provider_mod.nanogpt_generate
        provider_mod.nanogpt_generate = fake_generate
        try:
            out = provider.generate("16yo schoolgirl, cum on face")
        finally:
            provider_mod.nanogpt_generate = original

        self.assertFalse(out["success"])
        self.assertEqual(calls, [])
        self.assertIn("policy", str(out.get("error_type", "")).lower())

    def test_provider_still_generates_for_adults(self):
        import __init__ as provider_mod

        calls = []

        def fake_generate(**kwargs):
            calls.append(kwargs)
            return {"b64": TINY_JPEG_B64, "cost": 0.0051, "balance": 1.0}

        provider = provider_mod.NanoGptCyberProvider()
        original = provider_mod.nanogpt_generate
        provider_mod.nanogpt_generate = fake_generate
        try:
            out = provider.generate("женщина 52 года, полный рост в студии, кадр 7 из 9")
        finally:
            provider_mod.nanogpt_generate = original

        self.assertTrue(out["success"], out)
        self.assertEqual(len(calls), 1)


TINY_JPEG_B64 = (
    "/9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0a"
    "HBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/wAALCAABAAEBAREA/8QAFAABAAAAAAAA"
    "AAAAAAAAAAAACf/EABQQAQAAAAAAAAAAAAAAAAAAAAD/2gAIAQEAAD8AKp//2Q=="
)

if __name__ == "__main__":
    unittest.main()
