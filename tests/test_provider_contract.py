#!/usr/bin/env python3
"""Контракт провайдера: регистрация не глотает ошибки, цена — замер, а не смета."""

from __future__ import annotations

import base64
import os
import sys
import tempfile
import unittest
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[1] / "plugins" / "image_gen" / "nanogpt-cyber"
sys.path.insert(0, str(PLUGIN))

import __init__ as provider_mod  # noqa: E402
from plan import COST_ESTIMATE_USD, make_plan  # noqa: E402

LOGGER = "hermes.plugin.kadre"
PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAgAAAAIAQMAAAD+wSzIAAAABlBMVEX///+/v7+jQ3Y5AAAADUlEQVQI12P4"
    "AIX8EAgALgAD/aNpbtEAAAAASUVORK5CYII="
)


class _Ctx:
    def __init__(self, *, fail_section: bool = False, fail_skill: bool = False):
        self.fail_section = fail_section
        self.fail_skill = fail_skill
        self.provider = None
        self.skill_name = None
        self.skill_path = None

    def register_image_gen_provider(self, provider):
        self.provider = provider

    def register_system_prompt_section(self, *args, **kwargs):
        if self.fail_section:
            raise RuntimeError("boom-section")

    def register_skill(self, name, path, *args, **kwargs):
        self.skill_name = name
        self.skill_path = path
        if self.fail_skill:
            raise RuntimeError("boom-skill")


class RegistrationTests(unittest.TestCase):
    def test_provider_always_registered(self):
        ctx = _Ctx(fail_section=True, fail_skill=True)
        with self.assertLogs(LOGGER, level="WARNING"):
            provider_mod.register(ctx)
        self.assertIsNotNone(ctx.provider)

    def test_registration_failures_are_logged_not_swallowed(self):
        ctx = _Ctx(fail_section=True, fail_skill=True)
        with self.assertLogs(LOGGER, level="WARNING") as logs:
            provider_mod.register(ctx)
        text = " ".join(logs.output)
        self.assertIn("boom-section", text)
        self.assertIn("boom-skill", text)

    def test_successful_registration_is_quiet(self):
        ctx = _Ctx()
        with self.assertNoLogs(LOGGER, level="WARNING"):
            provider_mod.register(ctx)
        self.assertIsNotNone(ctx.provider)

    def test_skill_path_points_to_skill_md_file(self):
        """Hermes ждёт Path с .exists() и описанием «путь до SKILL.md», а не строку папки."""
        ctx = _Ctx()
        provider_mod.register(ctx)
        self.assertEqual(ctx.skill_name, "kadre")
        self.assertTrue(hasattr(ctx.skill_path, "exists"), "нужен Path, а не str")
        self.assertTrue(str(ctx.skill_path).endswith("SKILL.md"), str(ctx.skill_path))
        self.assertTrue(Path(str(ctx.skill_path)).is_file())


class CostReportingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["KADRE_CACHE"] = self.tmp.name
        os.environ["KADRE_OUT"] = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()
        os.environ.pop("KADRE_CACHE", None)
        os.environ.pop("KADRE_OUT", None)

    def test_measure_of_frame_is_the_estimate(self):
        self.assertAlmostEqual(COST_ESTIMATE_USD, 0.0022, places=4)
        self.assertAlmostEqual(make_plan("портрет").cost_usd, COST_ESTIMATE_USD, places=6)

    def test_list_models_shows_measured_price(self):
        prices = {m["price"] for m in provider_mod.NanoGptCyberProvider().list_models()}
        self.assertEqual(prices, {f"${COST_ESTIMATE_USD:.4f}"})

    def test_response_carries_estimate_next_to_api_cost(self):
        calls = []

        def fake_generate(**kwargs):
            calls.append(kwargs)
            return {"b64": PNG_B64, "cost": 0.0051, "balance": 1.0}

        provider = provider_mod.NanoGptCyberProvider()
        original = provider_mod.nanogpt_generate
        provider_mod.nanogpt_generate = fake_generate
        try:
            out = provider.generate("женщина 52 года, полный рост, кадр 8 из 9")
        finally:
            provider_mod.nanogpt_generate = original

        self.assertTrue(out["success"], out)
        self.assertEqual(len(calls), 1)
        self.assertAlmostEqual(out["cost"], 0.0051, places=6)
        self.assertAlmostEqual(out["cost_estimate_usd"], COST_ESTIMATE_USD, places=6)


if __name__ == "__main__":
    unittest.main()
