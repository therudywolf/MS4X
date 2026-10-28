#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
"""
Tests of tools/ms4x_core.py. Part of the MS4X repository. License: Apache-2.0 (LICENSE, NOTICE),
credit: rudywolf, https://github.com/therudywolf/MS4X.

  python3 tests/test_ms4x_core.py
  MS4X_IMAGES=<dir with ms42/ and ms43/> python3 tests/test_ms4x_core.py

Without images: the patchlist reader (TunerPro XDFPATCH, BASEOFFSET), the states of a patch, the patches that share
bytes. With the stock images of ms4x-net: every image is the stock program with an empty free area; a patchlist made
here from the bytes of the image (no community patchlist is stored or downloaded) is found not applied on the stock
image and applied on a copy, and the differences against stock are put down to its entries.
"""
import hashlib, json, os, subprocess, sys, tempfile, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import c166                                                             # noqa: E402
import ms4x_core                                                        # noqa: E402

IMAGES = os.environ.get("MS4X_IMAGES")


def xdf(patches, offset=0, subtract=False):
    """A TunerPro XDF with patches [(title, [(name, address, patch hex, base hex or None)])]."""
    out = ['<XDFFORMAT version="1.70">', "  <XDFHEADER>",
           '    <BASEOFFSET offset="%d" subtract="%d" />' % (offset, 1 if subtract else 0), "  </XDFHEADER>"]
    for i, (title, entries) in enumerate(patches):
        out.append('  <XDFPATCH uniqueid="0x%X">' % (i + 1))
        out.append("    <title>%s</title>" % title)
        for name, at, patch, base in entries:
            b = ' basedata="%s"' % base if base is not None else ""
            out.append('    <XDFPATCHENTRY name="%s" address="0x%X" datasize="0x%X" patchdata="%s"%s />'
                       % (name, at, len(patch) // 2, patch, b))
        out.append("  </XDFPATCH>")
    out.append("</XDFFORMAT>")
    return "\n".join(out)


def write(text):
    f = tempfile.NamedTemporaryFile("w", suffix=".xdf", delete=False, encoding="utf-8")
    f.write(text)
    f.close()
    return f.name


class TestPatchlist(unittest.TestCase):
    def test_reader_and_base_offset(self):
        p = write(xdf([("A", [("one", 0x1010, "AABB", "0000"), ("two", 0x1020, "CC", None)])], offset=0x1000, subtract=True))
        try:
            (a,) = ms4x_core.read_patchlist(p)
        finally:
            os.unlink(p)
        self.assertEqual(a["title"], "A")
        self.assertEqual([(e["at"], e["size"], e["patch"], e["base"]) for e in a["entries"]],
                         [(0x10, 2, b"\xaa\xbb", b"\x00\x00"), (0x20, 1, b"\xcc", None)])

    def test_states(self):
        img = bytearray(0x100)
        img[0x20:0x24] = b"\x11\x22\x33\x44"
        img[0x40:0x48] = b"\xff" * 8
        patch = lambda *e: dict(title="t", entries=[dict(name="e%d" % i, at=a, size=len(p), patch=p, base=b)
                                                    for i, (a, p, b) in enumerate(e)])
        state = lambda *e: ms4x_core.patch_state(bytes(img), patch(*e))[0]
        self.assertEqual(state((0x20, b"\x11\x22", b"\x00\x00")), "applied")
        self.assertEqual(state((0x20, b"\x99\x99", b"\x11\x22")), "not applied")
        self.assertEqual(state((0x20, b"\x11\x22", b"\x00\x00"), (0x22, b"\x99", b"\x33")), "partly applied")
        self.assertEqual(state((0x20, b"\x99\x99", b"\x55\x55")), "changed otherwise")
        self.assertEqual(state((0x40, b"\x01\x02", b"\x03\x04")), "not applied, expects another patch first")
        self.assertEqual(state((0xFF, b"\x01\x02", None)), "outside the image")
        self.assertEqual(state((0x20, b"\x99", None)), "not applied")                 # no base data: not its bytes

    def test_shared_bytes(self):
        a = dict(title="A", entries=[dict(name="x", at=0x10, size=8, patch=b"", base=None)])
        b = dict(title="B", entries=[dict(name="y", at=0x14, size=8, patch=b"", base=None)])
        c = dict(title="C", entries=[dict(name="z", at=0x40, size=2, patch=b"", base=None)])
        self.assertEqual(ms4x_core.overlaps([a, b, c]), [("A", "B", [(0x14, 0x18)])])

    def test_ranges(self):
        img = b"\xff" * 4 + b"\x01\x02" + b"\xff" * 3 + b"\x03" + b"\xff" * 40 + b"\x04"
        self.assertEqual(ms4x_core.runs(img, 0, len(img)), [(4, 6), (9, 10), (50, 51)])
        self.assertEqual(ms4x_core.merge([(4, 6), (9, 10), (50, 51)]), [(4, 10), (50, 51)])


def listed():
    out = []
    with open(os.path.join(ROOT, "tests", "ms4x_images.txt"), encoding="utf-8") as f:
        for line in f:
            if line.strip() and not line.startswith("#"):
                h, ref = line.split()
                out.append((h, ref.split("@", 1)[0], os.path.basename(ref)))
    return out


@unittest.skipUnless(IMAGES and os.path.isdir(IMAGES), "MS4X_IMAGES not set: the stock images of ms4x-net are not here")
class TestImages(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.img = {}
        for h, repo, name in listed():
            with open(os.path.join(IMAGES, repo, name), "rb") as f:
                b = f.read()
            assert hashlib.sha256(b).hexdigest() == h, name
            cls.img.setdefault(repo, []).append(b)

    def test_every_stock_image(self):
        for repo, imgs in self.img.items():
            for k, b in enumerate(imgs):
                r = ms4x_core.info(b, crc=k == 0)                          # the CRC itself is tested in test_c166emu
                self.assertTrue(r["program_part"]["stock"], (repo, k))
                self.assertEqual(r["free_area"]["used"], [], (repo, k))
                if k == 0:
                    self.assertTrue(all(c["stored"] == c["computed"] for c in r["checksums"]), repo)
                self.assertEqual(len(r["sums32"]), 2 if repo == "ms43" else 0, repo)
                for c in r["sums32"]:                                      # every 430069 image keeps both 32-bit sums right
                    self.assertEqual(c["stored"], c["computed"], (repo, k, hex(c["at"])))

    def test_patchlist_made_from_the_image(self):
        for repo, imgs in self.img.items():
            b = imgs[0]
            prof = c166.detect(b)
            free = ms4x_core.PROGRAMS[prof.key]["free"][0]
            prog = ms4x_core.blocks(b, prof, 0x50306 if repo == "ms42" else 0x6FDE0)[1]
            code = prog[0] + 0x100                                         # bytes inside the program checksum
            p_free, p_code = "CC00DB00", bytes(x ^ 0x5A for x in b[code:code + 4]).hex().upper()
            path = write(xdf([("Free code", [("slot", free, p_free, "FFFFFFFF")]),
                              ("Code hook", [("hook", code, p_code, b[code:code + 4].hex().upper())])]))
            try:
                r = ms4x_core.info(b, [path], crc=False)
                self.assertEqual([p["state"] for p in r["patches"]], ["not applied", "not applied"], repo)
                m = bytearray(b)
                m[free:free + 4] = bytes.fromhex(p_free)
                m[code:code + 4] = bytes.fromhex(p_code)
                r = ms4x_core.info(bytes(m), [path], stock=b, crc=False)
                self.assertEqual([p["state"] for p in r["patches"]], ["applied", "applied"], repo)
                self.assertFalse(r["program_part"]["stock"], repo)
                self.assertEqual([(u["start"], u["end"], u["by"]) for u in r["free_area"]["used"]],
                                 [(free, free + 4, ["Free code"])], repo)
                self.assertEqual({(d["start"], tuple(d["by"])) for d in r["against_stock"]},
                                 {(code, ("Code hook",)), (free, ("Free code",))}, repo)
            finally:
                os.unlink(path)

    def test_command_line_json(self):
        b = self.img["ms42"][0]
        with tempfile.TemporaryDirectory() as t:
            p = os.path.join(t, "image")
            with open(p, "wb") as f:
                f.write(b)
            out = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "ms4x_core.py"), "info", p, "--json"],
                                 capture_output=True, text=True)
        self.assertEqual(out.returncode, 0, out.stderr)
        r = json.loads(out.stdout)
        self.assertEqual((r["program"], r["program_part"]["stock"]), ("Siemens MS42 0110C6", True))


if __name__ == "__main__":
    unittest.main()
