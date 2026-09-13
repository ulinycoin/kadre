#!/usr/bin/env python3
"""Возраст персоны: параметр кадра + жёсткий пол 21+, guard в хвосте промпта."""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins" / "image_gen" / "nanogpt-cyber"
sys.path.insert(0, str(PLUGIN))

from plan import make_plan  # noqa: E402
from prompts import DEFAULT_AGE, MIN_AGE, normalize_age  # noqa: E402


class AgeControlTests(unittest.TestCase):
    def test_age_param_used_in_default_branch(self):
        p = make_plan("портрет в студии", age=32)
        self.assertEqual(p.age, 32)
        self.assertIn("32 year old adult woman", p.prompt)

    def test_age_param_is_clamped_to_floor(self):
        p = make_plan("портрет в студии", age=15)
        self.assertEqual(p.age, MIN_AGE)
        self.assertIn("21 year old", p.prompt)
        self.assertNotIn("15 year old", p.prompt)

    def test_age_param_wins_over_request_text(self):
        p = make_plan("женщина 55 лет, полный рост", age=40)
        self.assertIn("40 year old", p.prompt)
        self.assertNotIn("55 year old", p.prompt)

    def test_age_branch_without_age_is_neutral(self):
        p = make_plan("mature woman, полный рост")
        self.assertEqual(p.age, DEFAULT_AGE)
        self.assertIn("50+", p.prompt)
        self.assertNotIn("52 year old", p.prompt)

    def test_normalize_age_floor(self):
        self.assertEqual(normalize_age(None), DEFAULT_AGE)
        self.assertEqual(normalize_age(15), MIN_AGE)
        self.assertEqual(normalize_age(21), 21)
        self.assertEqual(normalize_age("58"), 58)
        self.assertEqual(normalize_age("мусор"), DEFAULT_AGE)

    def test_negative_bans_under21(self):
        p = make_plan("портрет в студии")
        self.assertIn("under 21", p.negative_prompt)

    def test_adult_guard_survives_in_prompt_tail(self):
        look = make_plan("портрет в студии", age=30)
        pony = make_plan("минет, сперма на лице", age=30)
        self.assertEqual(pony.model, "cyberrealistic-pony-v9")
        self.assertIn("30 years old adult", look.prompt[-120:])
        self.assertIn("30 years old adult", pony.prompt[-120:])


class AgeCliTests(unittest.TestCase):
    def _plan(self, *args: str) -> dict:
        out = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "kadre.py"), "plan", *args],
            capture_output=True,
            text=True,
            cwd=ROOT,
            timeout=60,
        )
        self.assertEqual(out.returncode, 0, out.stderr)
        return json.loads(out.stdout)

    def test_cli_age_flag_reaches_plan(self):
        data = self._plan("портрет в студии", "--age", "33")
        self.assertEqual(data["age"], 33)
        self.assertIn("33 year old", data["prompt"])

    def test_cli_age_flag_is_clamped(self):
        data = self._plan("портрет в студии", "--age", "16")
        self.assertEqual(data["age"], MIN_AGE)


if __name__ == "__main__":
    unittest.main()
