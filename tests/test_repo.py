#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
"""
Repository rules of MS4X by rudywolf. License: Apache-2.0 (LICENSE, NOTICE).

  python3 tests/test_repo.py
  python3 -m unittest discover -s tests -v

What must hold before anything else is added: no firmware images or dumps in the tree, nothing that
looks like a BMW / Alpina VIN in the text files, the documents in docs/en and docs/ru come in pairs,
the licence files are the official texts and NOTICE carries the credit, every script has an SPDX line,
relative links in the Markdown files point to files that exist.
"""
import os, re, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CREDIT = "rudywolf, https://github.com/therudywolf/MS4X"
VIN_LIKE = re.compile(r"\bW(?:BA|BS|BX|BY|AP)[A-HJ-NPR-Z0-9]{14}\b")    # BMW, BMW M, BMW SAV / i, Alpina
FIRMWARE_EXT = {".bin", ".hex", ".ori", ".mod", ".img", ".eep", ".s19", ".srec", ".a2l", ".ols", ".kp"}
DUMP_SIZES = {0x8000, 0x40000, 0x80000}                                   # partial 32K, 256K, full 512K
ASSET_EXT = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".webp"}


def tree():
    for d, dirs, files in os.walk(ROOT):
        dirs[:] = [x for x in dirs if x not in (".git", "__pycache__")]
        for n in sorted(files):
            yield os.path.join(d, n)


def read(*p):
    with open(os.path.join(ROOT, *p), encoding="utf-8") as f:
        return f.read()


def text_of(path):
    """File text, or None for a binary file (NUL bytes or not UTF-8)."""
    with open(path, "rb") as f:
        b = f.read()
    if b"\0" in b:
        return None
    try:
        return b.decode("utf-8")
    except UnicodeDecodeError:
        return None


def rel(path):
    return os.path.relpath(path, ROOT)


class TestRepository(unittest.TestCase):
    def test_no_firmware_images(self):
        # no dumps and no firmware in any form; binary files only as pictures in assets/
        for p in tree():
            ext = os.path.splitext(p)[1].lower()
            with self.subTest(file=rel(p)):
                self.assertNotIn(ext, FIRMWARE_EXT)
                self.assertNotIn(os.path.getsize(p), DUMP_SIZES)
                if text_of(p) is None:
                    self.assertTrue(rel(p).startswith("assets" + os.sep) and ext in ASSET_EXT, rel(p))

    def test_nothing_like_a_vin(self):
        for p in tree():
            t = text_of(p)
            if t is not None:
                with self.subTest(file=rel(p)):
                    self.assertIsNone(VIN_LIKE.search(t))

    def test_documents_in_pairs(self):
        en, ru = (sorted(os.listdir(os.path.join(ROOT, "docs", lang))) for lang in ("en", "ru"))
        self.assertEqual(en, ru)

    def test_licence_and_credit(self):
        # code: Apache-2.0 with the credit in NOTICE; documents and data: CC BY-SA 4.0 (NOTICE)
        self.assertTrue(read("LICENSE").lstrip().startswith("Apache License"))
        self.assertIn("Version 2.0, January 2004", read("LICENSE"))
        self.assertIn("Attribution-ShareAlike 4.0 International Public License", read("LICENSE-docs"))
        self.assertIn(CREDIT, read("NOTICE"))
        self.assertIn("https://github.com/therudywolf/MS4X", read("CITATION.cff"))
        for p in tree():
            if p.endswith(".py"):
                with self.subTest(file=rel(p)):
                    self.assertIn("SPDX-License-Identifier: Apache-2.0", read(p))

    def test_relative_links(self):
        link = re.compile(r'\]\(([^)\s]+)\)|(?:src|srcset|href)="([^"]+)"')
        for p in tree():
            if not p.endswith(".md"):
                continue
            for m in link.finditer(read(p)):
                target = (m.group(1) or m.group(2)).split("#")[0]
                if not target or re.match(r"[a-z]+:", target):          # anchors, http(s), mailto
                    continue
                with self.subTest(file=rel(p), link=target):
                    self.assertTrue(os.path.exists(os.path.normpath(os.path.join(os.path.dirname(p), target))))


if __name__ == "__main__":
    unittest.main()
