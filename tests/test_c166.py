#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
"""
Tests of tools/c166.py. Part of the MS4X repository. License: Apache-2.0 (LICENSE, NOTICE),
credit: rudywolf, https://github.com/therudywolf/MS4X.

  python3 tests/test_c166.py
  MS4X_IMAGES=<dir with ms42/ and ms43/> python3 tests/test_c166.py

Without images: the instruction table (every first byte with every second byte and several tails, through the
text and back), the encodings of the instruction set manual, the assembler, the memory profiles. With the stock
images of ms4x-net (tests/ms4x_images.txt; CI downloads them, they are never stored here): every image of
0110C6 and 430069 disassembles and assembles back byte for byte, and the code reached from the vectors and the
far calls decodes without a gap.
"""
import hashlib, os, sys, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import c166                                                             # noqa: E402

IMAGES = os.environ.get("MS4X_IMAGES")
AT = 0x49D00                                                            # file offset the encodings are made at

# (text, bytes at AT): one or more lines per layout of the Instruction Set Manual for the C166 Family V2.0 (2001)
REFERENCE = [
    ("add r1, r2", "0012"), ("addb rl1, rh1", "0123"), ("add r4, [0x8100]", "02F40081"),
    ("add [0x8100], r4", "04F40081"), ("add r4, #0x1234", "06F43412"), ("addb rl4, #0x05", "07F80500"),
    ("add r4, #3", "0843"), ("add r4, [r2]", "084A"), ("add r4, [r2+]", "084E"), ("subcb rl0, [r3+]", "390F"),
    ("cmp r4, r5", "4045"), ("cmpb rl0, #0xFFF7", "47F0F7FF"), ("or DPP0, #0x0001", "76000100"),
    ("mov r4, #5", "E054"), ("mov r4, #0x0005", "E6F40500"), ("movb rl4, #5", "E158"), ("movb rl4, #0x05", "E7F80500"),
    ("mov r4, r5", "F045"), ("movb rl0, rh7", "F10F"), ("mov r4, [0x8100]", "F2F40081"), ("movb [0x8100], rl4", "F7F80081"),
    ("mov PSW, #0x0800", "E6880008"), ("mov [0xFE12], ZEROS", "F68E12FE"), ("mov [0xFE40], r4", "F6F440FE"),
    ("mov T2, #0x0000", "E6200000"),
    ("mov r4, [r5]", "A845"), ("mov [r5], r4", "B845"), ("mov [-r0], r4", "8840"), ("mov r4, [r5+]", "9845"),
    ("mov [r4], [r5]", "C845"), ("mov [r4+], [r5]", "D845"), ("mov [r4], [r5+]", "E845"), ("movb [r1], [r0+]", "E910"),
    ("mov r4, [r5+#0x0010]", "D4451000"), ("mov [r5+#0x0010], r4", "C4451000"), ("movb rl4, [r5+#0x0010]", "F4851000"),
    ("movb [r5+#0x0010], rl4", "E4851000"), ("mov [r4], [0x8100]", "84040081"), ("mov [0x8100], [r4]", "94040081"),
    ("movbz r4, rl5", "C0A4"), ("movbs r4, rl5", "D0A4"), ("movbz r4, [0x8100]", "C2F40081"),
    ("movbz [0x8100], rl5", "C5FA0081"), ("neg r4", "8140"), ("cpl r4", "9140"), ("negb rl4", "A180"),
    ("cplb rh0", "B110"), ("mul r4, r5", "0B45"), ("mulu r4, r5", "1B45"), ("prior r9, r4", "2B94"), ("div r4", "4B44"),
    ("divlu r4", "7B44"), ("shl r4, #3", "5C34"), ("shl r4, r5", "4C45"), ("ashr r4, #15", "BCF4"), ("rol r1, r2", "0C12"),
    ("cmpi1 r4, #3", "8034"), ("cmpd2 r4, #3", "B034"), ("cmpi1 r4, #0x1234", "86F43412"),
    ("cmpi1 r4, [0x8100]", "82F40081"), ("bset PSW.3", "3F88"), ("bclr r4.15", "FEF4"), ("bset 0xFD02.0", "0F01"),
    ("bfldl PSW, #0x0F, #0x01", "0A880F01"), ("bfldh CCM6, #0x0F, #0x00", "1A93000F"),
    ("bmov 0xFD02.3, r4.5", "4AF40153"), ("band PSW.1, 0xFD10.15", "6A0888F1"),
    ("jb PSW.3, 0x49D10", "8A880630"), ("jnbs r4.0, 0x49CF0", "BAF4F600"),
    ("jmpr cc_EQ, 0x49D10", "2D07"), ("jmpr cc_UC, 0x49D00", "0DFF"), ("jmpa cc_UC, 0x49D10", "EA00109D"),
    ("jmpa cc_ULE, 0x40000", "EAF00000"), ("calla cc_UC, 0x4A000", "CA0000A0"), ("calls 0x0C:0x9CF8", "DA0CF89C"),
    ("jmps 0x0E:0xEE04", "FA0E04EE"), ("callr 0x49CF0", "BBF7"), ("calli cc_UC, [r4]", "AB04"),
    ("jmpi cc_NE, [r4]", "9C34"), ("pcall r4, 0x49E00", "E2F4009E"), ("trap #0x10", "9B20"),
    ("ret", "CB00"), ("rets", "DB00"), ("reti", "FB88"), ("nop", "CC00"), ("retp r4", "EBF4"), ("push r4", "ECF4"),
    ("pop PSW", "FC88"), ("scxt DPP0, #0x0012", "C6001200"), ("scxt CP, [0x8100]", "D6080081"),
    ("diswdt", "A55AA5A5"), ("einit", "B54AB5B5"), ("srvwdt", "A758A7A7"), ("srst", "B748B7B7"),
    ("idle", "87788787"), ("pwrdn", "97689797"), ("atomic #2", "D110"), ("extr #1", "D180"),
    ("exts #0x0C, #1", "D7000C00"), ("extp #0x012, #2", "D7501200"), ("extsr #0x0C, #1", "D7800C00"),
    ("extpr #0x3FF, #4", "D7F0FF03"), ("exts r4, #1", "DC04"), ("extp r4, #2", "DC54"), ("extpr r1, #1", "DCC1"),
]
UNDEFINED = [0x3B, 0x44, 0x45, 0x83, 0x85, 0x8B, 0x8C, 0x93, 0x95, 0xA3, 0xB3, 0xC1, 0xC3, 0xC7, 0xD3, 0xE3, 0xE5,
             0xF5, 0xF8, 0xF9]


def image(head):
    buf = bytearray(0x50000)
    buf[AT:AT + len(head)] = head
    return bytes(buf)


class TestTable(unittest.TestCase):
    def test_every_first_and_second_byte(self):
        # whatever decodes, valid or db, prints a text that assembles back to the same bytes, in both EXTR states;
        # the tail op, op completes the fixed patterns of DISWDT, EINIT, IDLE, PWRDN, SRVWDT and SRST
        valid = set()
        for op in range(256):
            for b1 in range(256):
                for tail in (b"\x00\x00", b"\x34\x12", b"\xff\xff", b"\x02\x80", bytes([op, op])):
                    ins = c166.decode(image(bytes([op, b1]) + tail), AT)
                    if ins.ok:
                        valid.add(op)
                    for extr in (False, True):
                        txt = c166.insn_text(ins, extr)
                        self.assertEqual(c166.assemble_one(txt, AT, extr), ins.raw, (txt, extr))
        self.assertEqual(sorted(set(range(256)) - valid), UNDEFINED)
        self.assertEqual(c166.UNDEFINED, UNDEFINED)

    def test_reference_encodings(self):
        for text, hexa in REFERENCE:
            with self.subTest(text=text):
                raw = bytes.fromhex(hexa)
                self.assertEqual(c166.assemble_one(text, AT).hex().upper(), hexa)
                ins = c166.decode(image(raw), AT)
                self.assertEqual((c166.insn_text(ins), ins.size), (text, len(raw)))

    def test_spelling_picks_the_form(self):
        self.assertEqual(c166.assemble_one("addb rl4, #5", AT).hex(), "0985")
        self.assertEqual(c166.assemble_one("addb rl4, #0x05", AT).hex(), "07f80500")
        self.assertEqual(c166.assemble_one("cmpi1 r4, #0x0003", AT).hex(), "86f40300")
        self.assertEqual(c166.assemble_one("mov r4, #200", AT).hex(), "e6f4c800")    # no 4-bit form fits

    def test_reserved_bits_are_kept(self):
        # a reserved field that is not zero gives db with a note, never a different instruction
        for hexa in ("8141", "8A880631", "EA01109D", "D701000C", "D7100C01", "4B45", "9B21", "CB01", "82E40081"):
            ins = c166.decode(image(bytes.fromhex(hexa)), AT)
            self.assertEqual(ins.mn, "db", hexa)
            self.assertEqual(c166.assemble_one(c166.insn_text(ins), AT), ins.raw)


class TestAssembler(unittest.TestCase):
    def test_labels_org_and_listing_lines(self):
        src = """
                org 0x49D00
        start:  mov r4, #5          ; E0 54
                jmpr cc_UC, later
                nop
        later:  rets
        49E00  CA 00 00 9D  calla cc_UC, start
        """
        out = c166.assemble(src)
        self.assertEqual({a: b.hex() for a, b in out.items()},
                         {0x49D00: "e054", 0x49D02: "0d01", 0x49D04: "cc00", 0x49D06: "db00", 0x49E00: "ca00009d"})

    def test_extr_range(self):
        with self.assertRaises(c166.AsmError):
            c166.assemble_one("mov 0xF0A0, #0x0001", AT)                 # an ESFR outside EXTR
        out = c166.assemble("org 0x49D00\nextr #1\nmov 0xF0A0, #0x0001\nmov 0xFEA0, #0x0001\n")
        self.assertEqual([b.hex() for a, b in sorted(out.items())], ["d180", "e6500100", "e6500100"])
        with self.assertRaises(c166.AsmError):
            c166.assemble("org 0x49D00\nextr #1\nnop\nmov 0xF0A0, #0x0001\n")

    def test_errors(self):
        for bad in ("jmpr cc_UC, 0x4A100", "jmpa cc_UC, 0x59D00", "mov r4, #0x10000", "movb rl4, r4", "frob r1",
                    "mov r4", "add r4, [r4]"):
            with self.subTest(text=bad), self.assertRaises(c166.AsmError):
                c166.assemble_one(bad, AT)


class TestProfiles(unittest.TestCase):
    def test_detect_and_map(self):
        img = bytearray(0x80000)
        img[0x6FFBA:0x6FFC0] = b"430069"
        ms43 = c166.detect(bytes(img))
        self.assertEqual(ms43.key, "ms43")
        self.assertEqual(ms43.file_of(0xCAB00), 0x4AB00)
        self.assertEqual(ms43.file_of(0x70010), 0x70010)
        self.assertIsNone(ms43.file_of(0x40010))
        self.assertEqual(ms43.describe(0x40100), "ext RAM 0x40100")
        self.assertEqual(c166.phys_of(0x8100, ms43), 0x40100)                # DPP2 = 0x10
        self.assertEqual(c166.phys_of(0x0010, ms43), 0x70010)                # DPP0 = 0x1C
        ms42 = c166.PROFILES["ms42"]
        self.assertEqual(ms42.file_of(0x61234), 0x61234)
        self.assertEqual(ms42.describe(0xFF10), "PSW")
        self.assertEqual(ms42.describe(0xE0FF), "XRAM")
        self.assertEqual(c166.phys_of(0x1234, ms42, page=0x12), 0x49234)    # EXTP #0x12
        self.assertEqual(c166.phys_of(0x1234, ms42, seg=0x06), 0x61234)     # EXTS #0x06
        img = bytearray(0x80000)
        img[0x48008:0x4800E] = b"0110C6"
        self.assertEqual(c166.detect(bytes(img)).key, "ms42")
        self.assertEqual(c166.detect(bytes(0x1000)).key, "raw")

    def test_ext_prefix_applies_to_its_range(self):
        code = bytes.fromhex("D7500100" "F2F43412" "F2F43412")             # extp #0x001, #2 and two loads
        lines = c166.dis(image(code), AT, AT + len(code), c166.PROFILES["raw"])
        self.assertIn("next 2", lines[0])
        self.assertIn("file 0x05234", lines[1])                              # page 1: 0x4000 + 0x1234
        self.assertIn("file 0x05234", lines[2])


def listed():
    out = []
    with open(os.path.join(ROOT, "tests", "ms4x_images.txt"), encoding="utf-8") as f:
        for line in f:
            if line.strip() and not line.startswith("#"):
                h, ref = line.split()
                repo, path = ref.split("@", 1)
                out.append((h, repo, os.path.basename(path)))
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
        cls.walked = {}
        for repo, imgs in cls.img.items():
            prof = c166.detect(imgs[0])
            cls.walked[repo] = c166.walk(imgs[0], c166.vectors(imgs[0], prof) + c166.far_calls(imgs[0], prof), prof,
                                         follow_calls=True)

    def test_all_listed_and_detected(self):
        self.assertEqual({k: len(v) for k, v in self.img.items()}, {"ms42": 16, "ms43": 18})
        for repo, imgs in self.img.items():
            for b in imgs:
                self.assertEqual(c166.detect(b).key, repo)

    def test_round_trip(self):
        # the first image of each family whole, the others where they differ from it (calibration)
        for repo, imgs in self.img.items():
            n, bad = c166.check(imgs[0], 0, len(imgs[0]))
            self.assertGreater(n, 150000)
            self.assertEqual(bad, [], repo)
            for b in imgs[1:]:
                diff = [i for i in range(0, len(b), 16) if b[i:i + 16] != imgs[0][i:i + 16]]
                lo = 0
                while lo < len(diff):
                    hi = lo
                    while hi + 1 < len(diff) and diff[hi + 1] - diff[hi] <= 64:
                        hi += 1
                    self.assertEqual(c166.check(b, max(0, diff[lo] - 16), min(len(b), diff[hi] + 32))[1], [], repo)
                    lo = hi + 1

    def test_code_reached_without_gaps(self):
        for repo in self.img:
            seen, labels, xrefs, errors = self.walked[repo]
            self.assertEqual(errors, [], repo)
            self.assertGreater(len(seen), 60000, repo)
            self.assertGreater(sum(1 for v in labels.values() if v.startswith("sub_")), 400, repo)

    def test_bit_field_masks(self):
        # BFLDL keeps the mask in byte 3, BFLDH in byte 4: read so, the data lies inside the mask in the stock code
        for repo in self.img:
            n = ok = 0
            for ins in self.walked[repo][0].values():
                if ins.mn in ("bfldl", "bfldh"):
                    n += 1
                    ok += ins.ops[2][1] & ~ins.ops[1][1] == 0
            self.assertGreater(n, 300, repo)
            self.assertGreaterEqual(ok / n, 0.99, repo)


if __name__ == "__main__":
    unittest.main()
