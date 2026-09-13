#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "plugins" / "image_gen" / "nanogpt-cyber"))

import once  # noqa: E402
from once import Shot, lookup, normalize_core, remember, resolve_request, similar, wants_new_take  # noqa: E402


class OnceLogicTests(unittest.TestCase):
    def test_strips_agent_retry_fluff(self):
        a = normalize_core("харли квинн склад бита")
        b = normalize_core("харли квинн склад бита, better anatomy, try again, исправь пальцы")
        self.assertEqual(a, b)

    def test_short_force_is_new_take(self):
        self.assertTrue(wants_new_take("ещё"))
        self.assertTrue(wants_new_take("перегенерируй"))
        self.assertTrue(wants_new_take("другой вариант"))
        self.assertFalse(wants_new_take("харли квинн, склад, бита"))

    def test_long_retry_prompt_is_not_force(self):
        self.assertFalse(
            wants_new_take("харли квинн склад бита better hands try again another variant")
        )

    def test_similar_cores(self):
        self.assertTrue(similar("харли квинн склад бита", "харли квинн склад бита чокер"))
        self.assertFalse(similar("харли квинн", "клеопатра дворец золото"))


class OnceCacheTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["KADRE_CACHE"] = self.tmp.name
        self.jpg = Path(self.tmp.name) / "frame.jpg"
        self.jpg.write_bytes(b"jpeg")

    def tearDown(self):
        self.tmp.cleanup()
        os.environ.pop("KADRE_CACHE", None)

    def _store(self, request: str = "харли квинн склад бита") -> Shot:
        core = normalize_core(request)
        shot = Shot(
            path=str(self.jpg),
            core=core,
            fingerprint=once.fingerprint(core, None, "portrait", "auto"),
            request=request,
            model="cyberrealistic-xl",
            ts=time.time(),
            reason="тест",
            notes=[],
        )
        remember(shot)
        return shot

    def test_exact_retry_hits_cache(self):
        self._store()
        hit = lookup("харли квинн склад бита")
        self.assertIsNotNone(hit)
        self.assertEqual(hit.path, str(self.jpg))

    def test_agent_paraphrase_hits_cache(self):
        self._store()
        hit = lookup("харли квинн склад бита, better anatomy, try pony")
        self.assertIsNotNone(hit)

    def test_force_bypasses_cache(self):
        self._store()
        self.assertIsNone(lookup("ещё"))
        self.assertIsNone(lookup("перегенерируй"))

    def test_force_resolves_to_last_request(self):
        self._store("клеопатра в золоте")
        self.assertEqual(resolve_request("ещё"), "клеопатра в золоте")

    def test_different_scene_misses(self):
        self._store()
        self.assertIsNone(lookup("клеопатра в золоте, дворец"))

    def test_provider_returns_cached_without_api(self):
        self._store()
        from __init__ import NanoGptCyberProvider

        out = NanoGptCyberProvider().generate("харли квинн склад бита better hands")
        self.assertTrue(out["success"])
        self.assertTrue(out["cached"])
        self.assertTrue(out["final"])
        self.assertFalse(out["regenerate"])
        self.assertEqual(out["cost"], 0)
        self.assertEqual(out["image"], str(self.jpg))
        self.assertIn("не дергали", " ".join(out["notes"]))


if __name__ == "__main__":
    unittest.main()
