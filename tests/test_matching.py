#!/usr/bin/env python3
"""Матчинг терминов: границы слов, а не подстрока; возраст берётся из запроса."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[1] / "plugins" / "image_gen" / "nanogpt-cyber"
sys.path.insert(0, str(PLUGIN))

from plan import make_plan  # noqa: E402
from router import route  # noqa: E402

BENIGN = (
    "analysis of the pose",
    "document the walk in the park",
    "circumstance lighting test",
    "subject standing in studio",
    "canal street portrait",
    "prefix the file name",
    "анализ позы на фото",
    "кончик ленты, макро",
)


class WordBoundaryTests(unittest.TestCase):
    def test_benign_requests_are_not_act(self):
        for text in BENIGN:
            with self.subTest(text=text):
                r = route(text)
                self.assertEqual(r.model, "cyberrealistic-xl")
                self.assertEqual(r.intent, "look")

    def test_benign_prompts_get_no_act_tags(self):
        for text in BENIGN:
            with self.subTest(text=text):
                p = make_plan(text)
                low = p.prompt.lower()
                for tag in ("anal sex", "penis in anus", "(cum", "semen", "facial:",
                            "penis in mouth", "cowgirl sex", "pissing"):
                    self.assertNotIn(tag, low)

    def test_word_act_terms_still_fire(self):
        cases = {
            "anal sex, rear view": "cyberrealistic-pony-v9",
            "cum on her face, close up": "cyberrealistic-pony-v9",
            "blowjob portrait, studio": "cyberrealistic-pony-v9",
            "минет, сперма на лице": "cyberrealistic-pony-v9",
            "писсинг в ванной": "cyberrealistic-pony-v9",
            "наездница, половой акт": "cyberrealistic-pony-v9",
            "куни, крупный план": "cyberrealistic-pony-v9",
        }
        for text, model in cases.items():
            with self.subTest(text=text):
                self.assertEqual(route(text).model, model)

    def test_act_tags_still_front_loaded(self):
        p = make_plan("минет со спермой на лице")
        self.assertIn("(cum", p.prompt)

    def test_cyrillic_stem_terms_still_fire(self):
        for text in ("вылизывает киску", "эякуляция на живот", "вагина крупным планом"):
            with self.subTest(text=text):
                self.assertEqual(route(text).model, "cyberrealistic-pony-v9")


class AgeTests(unittest.TestCase):
    def test_bare_number_is_not_age50(self):
        for text in ("объектив 55mm, портрет в студии", "кадр 1024x1408, студия"):
            with self.subTest(text=text):
                self.assertEqual(route(text).intent, "look")
                self.assertNotIn("52 year old", make_plan(text).prompt)

    def test_explicit_age_is_used(self):
        p = make_plan("женщина 55 лет, полный рост")
        self.assertEqual(route("женщина 55 лет, полный рост").intent, "age")
        self.assertIn("55", p.prompt)
        self.assertNotIn("52 year old", p.prompt)

    def test_age_branch_without_number_does_not_invent_52(self):
        p = make_plan("mature woman, полный рост")
        self.assertEqual(route("mature woman, полный рост").intent, "age")
        self.assertNotIn("52 year old", p.prompt)

    def test_unknown_age_is_never_below_floor(self):
        p = make_plan("женщина 19 лет, портрет")
        self.assertNotIn("19 year old", p.prompt)


if __name__ == "__main__":
    unittest.main()
