#!/usr/bin/env python3
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "plugins" / "image_gen" / "nanogpt-cyber"))

from plan import make_plan  # noqa: E402
from router import route  # noqa: E402


class RouterTests(unittest.TestCase):
    def test_harley_look_xl(self):
        r = route("Харли Квинн, обнажёнка, бита, чокер")
        self.assertEqual(r.model, "cyberrealistic-xl")
        self.assertEqual(r.intent, "look")

    def test_cleopatra_look_xl(self):
        r = route("клеопатра в золоте, дворец")
        self.assertEqual(r.model, "cyberrealistic-xl")

    def test_barbie_pony(self):
        r = route("кукла барби стиль, розовый дом")
        self.assertEqual(r.model, "cyberrealistic-pony-v9")

    def test_act_pony(self):
        r = route("клеопатра, поза наездницы, половой акт")
        self.assertEqual(r.model, "cyberrealistic-pony-v9")
        self.assertEqual(r.intent, "act")

    def test_age50_xl(self):
        r = route("женщина 52 года, полный рост")
        self.assertEqual(r.model, "cyberrealistic-xl")
        self.assertEqual(r.intent, "age")

    def test_pose_change_drops_i2i(self):
        r = route("сидячая поза, ноги врозь", has_reference=True)
        self.assertFalse(r.i2i_ok)
        self.assertTrue(r.warnings)

    def test_i2i_fix_keeps_low_strength(self):
        r = route("докрути, убери пистолет, тот же кадр", has_reference=True)
        self.assertEqual(r.intent, "i2i_fix")
        self.assertTrue(r.i2i_ok)
        self.assertLess(r.strength or 1, 0.45)

    def test_act_plus_ref_is_txt2img(self):
        r = route("раб вылизывает сперму с вагины", has_reference=True)
        self.assertEqual(r.model, "cyberrealistic-pony-v9")
        self.assertFalse(r.i2i_ok)

    def test_override(self):
        r = route("наездница", model_override="cyberrealistic-xl")
        self.assertEqual(r.model, "cyberrealistic-xl")


class PlanTests(unittest.TestCase):
    def test_front_loads_cum(self):
        p = make_plan("минет со спермой на лице")
        self.assertTrue(p.prompt.lower().startswith("score_9") or "(cum" in p.prompt)
        self.assertIn("semen", p.prompt)

    def test_negative_snake_ready(self):
        p = make_plan("Харли с битой")
        self.assertIn("child", p.negative_prompt)
        self.assertEqual(p.resolution, "768x1024")

    def test_pose_change_plan_skips_i2i(self):
        p = make_plan("сидит на полу", has_reference=True)
        self.assertFalse(p.use_i2i)


if __name__ == "__main__":
    unittest.main()
