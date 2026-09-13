#!/usr/bin/env python3
"""Референс кадра: что отдаём наружу и сколько читаем.

Референс уходит на сторонний API целиком, поэтому локальный файл должен быть
настоящей картинкой ограниченного размера, а URL — только https на публичный
хост (никакой локалки, метадата-эндпоинтов и редиректов внутрь).
"""

from __future__ import annotations

import base64
import io
import os
import socket
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

PLUGIN = Path(__file__).resolve().parents[1] / "plugins" / "image_gen" / "nanogpt-cyber"
sys.path.insert(0, str(PLUGIN))

import nanogpt  # noqa: E402

PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAgAAAAIAQMAAAD+wSzIAAAABlBMVEX///+/v7+jQ3Y5AAAADUlEQVQI12P4"
    "AIX8EAgALgAD/aNpbtEAAAAASUVORK5CYII="
)


def _png_bytes() -> bytes:
    return base64.b64decode(PNG_B64)


class UrlPolicyTests(unittest.TestCase):
    BLOCKED = (
        "http://example.com/a.jpg",
        "https://127.0.0.1/a.jpg",
        "https://[::1]/a.jpg",
        "https://localhost/a.jpg",
        "https://169.254.169.254/latest/meta-data/",
        "https://10.0.0.5/a.jpg",
        "https://192.168.1.10/a.jpg",
        "https://metadata.google.internal/a.jpg",
        "file:///etc/passwd",
        "ftp://example.com/a.jpg",
    )

    def test_blocked_urls_never_fetched(self):
        fetch = mock.Mock(side_effect=AssertionError("сеть дёрнули до проверки"))
        with mock.patch.object(nanogpt, "_fetch_url_bytes", fetch):
            for url in self.BLOCKED:
                with self.subTest(url=url):
                    with self.assertRaises(ValueError):
                        nanogpt._to_data_url(url)
        self.assertEqual(fetch.call_count, 0)

    def test_hostname_resolving_to_private_is_rejected(self):
        private = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))]
        with mock.patch.object(socket, "getaddrinfo", return_value=private):
            with self.assertRaises(ValueError):
                nanogpt._to_data_url("https://looks-public.example/a.jpg")

    def test_public_https_is_allowed(self):
        public = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))]
        with mock.patch.object(socket, "getaddrinfo", return_value=public):
            with mock.patch.object(nanogpt, "_fetch_url_bytes", return_value=_png_bytes()):
                out = nanogpt._to_data_url("https://cdn.example/a.png")
        self.assertTrue(out.startswith("data:image/png;base64,"))

    def test_redirect_into_private_is_rejected(self):
        with self.assertRaises(ValueError):
            nanogpt.validate_reference_url("https://127.0.0.1/internal.jpg")


class FilePolicyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_real_image_is_allowed(self):
        path = self.dir / "frame.png"
        path.write_bytes(_png_bytes())
        out = nanogpt._to_data_url(str(path))
        self.assertTrue(out.startswith("data:image/png;base64,"))

    def test_text_file_with_image_extension_is_rejected(self):
        path = self.dir / "fake.jpg"
        path.write_text("BEGIN PRIVATE KEY", encoding="utf-8")
        with self.assertRaises(ValueError):
            nanogpt._to_data_url(str(path))

    def test_secret_file_with_image_extension_is_rejected(self):
        path = self.dir / "id_rsa.png"
        path.write_text("-----BEGIN OPENSSH PRIVATE KEY-----\n", encoding="utf-8")
        with self.assertRaises(ValueError):
            nanogpt._to_data_url(str(path))

    def test_directory_and_device_are_rejected(self):
        for target in (str(self.dir), "/dev/null"):
            with self.subTest(target=target):
                with self.assertRaises(ValueError):
                    nanogpt._to_data_url(target)

    def test_missing_file_is_rejected(self):
        with self.assertRaises(ValueError):
            nanogpt._to_data_url(str(self.dir / "nope.png"))

    def test_oversized_file_is_rejected_before_reading(self):
        path = self.dir / "big.png"
        path.write_bytes(_png_bytes() * 64)
        with mock.patch.object(nanogpt, "MAX_REFERENCE_BYTES", 512):
            with self.assertRaises(ValueError):
                nanogpt._to_data_url(str(path))

    def test_oversized_download_is_rejected(self):
        public = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))]
        with mock.patch.object(socket, "getaddrinfo", return_value=public):
            with mock.patch.object(nanogpt, "MAX_REFERENCE_BYTES", 512):
                with mock.patch.object(nanogpt, "_fetch_url_bytes", return_value=_png_bytes() * 64):
                    with self.assertRaises(ValueError):
                        nanogpt._to_data_url("https://cdn.example/huge.png")


class DataUrlTests(unittest.TestCase):
    def test_data_image_passthrough(self):
        ref = f"data:image/png;base64,{PNG_B64}"
        self.assertEqual(nanogpt._to_data_url(ref), ref)

    def test_oversized_data_url_is_rejected(self):
        ref = f"data:image/png;base64,{PNG_B64 * 64}"
        with mock.patch.object(nanogpt, "MAX_REFERENCE_BYTES", 512):
            with self.assertRaises(ValueError):
                nanogpt._to_data_url(ref)

    def test_non_image_data_url_is_rejected(self):
        with self.assertRaises(ValueError):
            nanogpt._to_data_url("data:text/plain;base64,SGVsbG8=")


class GeneratorWiringTests(unittest.TestCase):
    def test_generate_refuses_blocked_reference(self):
        with mock.patch.object(nanogpt, "api_key", return_value="test-key"):
            with mock.patch.object(
                nanogpt, "_fetch_url_bytes", side_effect=AssertionError("сеть дёрнули")
            ):
                with self.assertRaises(ValueError):
                    nanogpt.generate(
                        model="cyberrealistic-xl",
                        prompt="portrait",
                        negative_prompt="child",
                        resolution="768x1024",
                        reference="https://127.0.0.1/secret.png",
                    )


if __name__ == "__main__":
    unittest.main()
