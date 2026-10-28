#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
"""
Tests of tools/c166emu.py. Part of the MS4X repository. License: Apache-2.0 (LICENSE, NOTICE),
credit: rudywolf, https://github.com/therudywolf/MS4X.

  python3 tests/test_c166emu.py
  MS4X_IMAGES=<dir with ms42/ and ms43/> python3 tests/test_c166emu.py

Without images: every group of instructions against the operation and the flags of the Infineon Instruction Set
Manual for the C166 Family V2.0 (the expected values are worked out from its descriptions), the condition codes of
its table 5, addressing through DPP, EXTP, EXTS and EXTR, the stack. With the stock images of ms4x-net: the program's
own CRC routine, run by the emulator over every image of 0110C6 and 430069, gives what an independent CRC gives and
the sums stored in the images (all but one, whose stored calibration sum does not match its content), and the
functions reached in the code run without an error of the emulator.
"""
import hashlib, os, sys, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import c166                                                             # noqa: E402
import c166emu                                                          # noqa: E402

IMAGES = os.environ.get("MS4X_IMAGES")
ORG = 0x60000                                                           # MS42 profile: file = physical address


def run(src, regs=None, mem=None, psw=0, org=ORG, extra=None):
    """Assembles src at org (and extra {address: source}), runs it as a near function ending in RET."""
    img = bytearray(b"\xff" * 0x80000)
    img[0x48008:0x4800E] = b"0110C6"
    for at, text in [(org, src + "\nret")] + list((extra or {}).items()):
        for a, b in c166.assemble("org 0x%X\n%s" % (at, text)).items():
            img[a:a + len(b)] = b
    emu = c166emu.Emu(bytes(img))
    emu.psw = psw
    for n, v in (regs or {}).items():
        emu.r[n] = v
    for a, v in (mem or {}).items():
        emu.wr16(a, v)
    emu.call(org, near=True)
    return emu


def fl(emu):
    """The flags as letters, for example 'ZC'."""
    return "".join(n for n, b in (("E", 16), ("Z", 8), ("V", 4), ("C", 2), ("N", 1)) if emu.psw & b)


class TestArithmetic(unittest.TestCase):
    def test_add(self):
        e = run("add r1, r2", {1: 0x7FFF, 2: 1})
        self.assertEqual((e.r[1], fl(e)), (0x8000, "VN"))                  # signed overflow
        e = run("add r1, r2", {1: 0xFFFF, 2: 1})
        self.assertEqual((e.r[1], fl(e)), (0, "ZC"))
        e = run("add r1, r2", {1: 1, 2: 0x8000})
        self.assertEqual((e.r[1], fl(e)), (0x8001, "EN"))                  # E: op2 is the lowest negative number
        e = run("addb rl1, rh1", {1: 0x80FF})
        self.assertEqual((e.r[1], fl(e)), (0x807F, "EVC"))

    def test_addc_and_subc_chain_zero(self):
        e = run("addc r1, r2", {1: 0xFFFF, 2: 0}, psw=0x0A)                # C = 1, Z = 1 before
        self.assertEqual((e.r[1], fl(e)), (0, "ZC"))
        e = run("addc r1, r2", {1: 0xFFFF, 2: 0}, psw=0x02)                # Z = 0 before: Z stays 0
        self.assertEqual((e.r[1], fl(e)), (0, "C"))
        e = run("subc r1, r2", {1: 0, 2: 0}, psw=0x02)                     # 0 - 0 - 1
        self.assertEqual((e.r[1], fl(e)), (0xFFFF, "CN"))

    def test_sub_cmp_neg(self):
        e = run("sub r1, r2", {1: 0, 2: 1})
        self.assertEqual((e.r[1], fl(e)), (0xFFFF, "CN"))                  # C: borrow
        e = run("sub r1, r2", {1: 0x8000, 2: 1})
        self.assertEqual((e.r[1], fl(e)), (0x7FFF, "V"))                   # V: underflow
        e = run("cmp r1, r2", {1: 5, 2: 5})
        self.assertEqual((e.r[1], fl(e)), (5, "Z"))
        e = run("neg r1", {1: 0x8000})
        self.assertEqual((e.r[1], fl(e)), (0x8000, "EVCN"))
        e = run("neg r1", {1: 0})
        self.assertEqual((e.r[1], fl(e)), (0, "Z"))
        e = run("cpl r1", {1: 0x8000})
        self.assertEqual((e.r[1], fl(e)), (0x7FFF, "E"))

    def test_compare_and_step(self):
        e = run("cmpi1 r1, #5", {1: 5})
        self.assertEqual((e.r[1], fl(e)), (6, "Z"))
        e = run("cmpd2 r1, #0x0007", {1: 5})
        self.assertEqual((e.r[1], fl(e)), (3, "CN"))

    def test_logic(self):
        e = run("and r1, r2", {1: 0xF0F0, 2: 0x8000}, psw=0x06)
        self.assertEqual((e.r[1], fl(e)), (0x8000, "EN"))                  # V, C cleared
        e = run("xorb rl1, #0xFF", {1: 0x00FF})
        self.assertEqual((e.r[1], fl(e)), (0, "Z"))
        e = run("or r1, #0x0000", {1: 0})
        self.assertEqual(fl(e), "Z")

    def test_multiply_divide(self):
        e = run("mul r1, r2", {1: 0x8000, 2: 0x8000})
        self.assertEqual((e.rd16(0xFE0C), e.rd16(0xFE0E), fl(e)), (0x4000, 0x0000, "V"))
        e = run("mulu r1, r2", {1: 0xFFFF, 2: 0xFFFF})
        self.assertEqual((e.rd16(0xFE0C), e.rd16(0xFE0E), fl(e)), (0xFFFE, 0x0001, "VN"))
        e = run("mov [0xFE0E], r1\ndiv r2", {1: 0xFFF9, 2: 2})                   # -7 / 2
        self.assertEqual((e.rd16(0xFE0E), e.rd16(0xFE0C), fl(e)), (0xFFFD, 0xFFFF, "N"))
        e = run("mov [0xFE0E], r1\ndivu r2", {1: 7, 2: 2})
        self.assertEqual((e.rd16(0xFE0E), e.rd16(0xFE0C)), (3, 1))
        e = run("mov [0xFE0E], r1\ndivu r2", {1: 7, 2: 0})
        self.assertEqual(fl(e), "V")                                       # divide by zero
        e = run("mov [0xFE0C], r1\nmov [0xFE0E], r2\ndivl r3", {1: 1, 2: 0, 3: 2})    # 65536 / 2 is no signed word
        self.assertEqual(fl(e), "VN")
        e = run("mov [0xFE0C], r1\nmov [0xFE0E], r2\ndivlu r3", {1: 1, 2: 0, 3: 2})
        self.assertEqual((e.rd16(0xFE0E), fl(e)), (0x8000, "N"))
        self.assertTrue(e.rd16(0xFF0E) & 0x10)                             # MDC.MDRIU

    def test_prior(self):
        for v, n in ((1, 15), (0x8000, 0), (0x0F00, 4)):
            self.assertEqual(run("prior r1, r2", {2: v}).r[1], n)
        e = run("prior r1, r2", {1: 9, 2: 0})
        self.assertEqual((e.r[1], fl(e)), (0, "Z"))


class TestShifts(unittest.TestCase):
    def test_shift_and_rotate(self):
        e = run("shl r1, #4", {1: 0x1234})
        self.assertEqual((e.r[1], fl(e)), (0x2340, "C"))                   # C: last MSB shifted out
        e = run("shr r1, #2", {1: 0x0007})
        self.assertEqual((e.r[1], fl(e)), (0x0001, "VC"))                  # V: a 1 shifted out of C before
        e = run("ashr r1, #15", {1: 0x8000})
        self.assertEqual((e.r[1], fl(e)), (0xFFFF, "N"))
        e = run("rol r1, #1", {1: 0x8001})
        self.assertEqual((e.r[1], fl(e)), (0x0003, "C"))
        e = run("ror r1, #1", {1: 0x0001})
        self.assertEqual((e.r[1], fl(e)), (0x8000, "CN"))
        e = run("shl r1, r2", {1: 0x0001, 2: 0x0010}, psw=0x02)            # count from the low 4 bits: 0
        self.assertEqual((e.r[1], fl(e)), (0x0001, ""))


class TestMoves(unittest.TestCase):
    def test_mov_flags(self):
        e = run("mov r1, #0x8000", psw=0x06)
        self.assertEqual((e.r[1], fl(e)), (0x8000, "EVCN"))                # V and C not affected
        e = run("mov r1, #0")
        self.assertEqual(fl(e), "Z")
        e = run("movbz r1, rl2", {2: 0x0080})
        self.assertEqual((e.r[1], fl(e)), (0x0080, ""))
        e = run("movbs r1, rl2", {2: 0x0080})
        self.assertEqual((e.r[1], fl(e)), (0xFF80, "N"))

    def test_indirect(self):
        e = run("mov [-r2], r1\nmov [-r2], r1\nmov r3, [r2+]", {1: 0xBEEF, 2: 0xF604})
        self.assertEqual((e.r[2], e.r[3], e.rd16(0xF600), e.rd16(0xF602)), (0xF602, 0xBEEF, 0xBEEF, 0xBEEF))
        e = run("mov [r2+], [r3]", {2: 0xF600, 3: 0xF610}, mem={0xF610: 0x4321})
        self.assertEqual((e.r[2], e.rd16(0xF600)), (0xF602, 0x4321))
        e = run("mov r3, [r2+#0x0004]\nmovb rl4, [r2]", {2: 0xF600}, mem={0xF604: 0x1234, 0xF600: 0x00AA})
        self.assertEqual((e.r[3], e.r[4] & 0xFF), (0x1234, 0xAA))
        e = run("add r1, [r2+]", {1: 1, 2: 0xF600}, mem={0xF600: 2})
        self.assertEqual((e.r[1], e.r[2]), (3, 0xF602))

    def test_dpp_and_ext(self):
        e = run("mov r1, [0x800A]\nextp #0x012, #1\nmov r2, [0x800A]\nmov r4, [0x800A]\nexts #0x06, #1\nmov r3, [0x1000]",
                extra={0x61000: "dw 0xBEEF"})
        self.assertEqual(e.r[1], 0xFFFF)                                   # DPP2 = 0x13: flash 0x4C00A
        self.assertEqual(e.r[2], 0x3031)                                   # page 0x12: 0x4800A, "10" of "0110C6"
        self.assertEqual(e.r[4], 0xFFFF)                                   # the prefix covered one instruction
        self.assertEqual(e.r[3], 0xBEEF)                                   # segment 6: 0x61000
        e = run("extr #1\nmov 0xF0A0, #0x1234\nmov 0xFEA0, #0x5678")
        self.assertEqual((e.rd16(0xF0A0), e.rd16(0xFEA0)), (0x1234, 0x5678))

    def test_registers_and_cp(self):
        e = run("mov r4, [0xFF1C]\nmov r5, [0xFF1E]\nmov MDL, #0x1234\nmov r6, [0xFE0E]")
        self.assertEqual((e.r[4], e.r[5], e.r[6]), (0, 0xFFFF, 0x1234))
        e = run("mov r1, #0x0011\nscxt CP, #0xFB00\nmov r1, #0x0022\npop CP", {})
        self.assertEqual((e.cp, e.r[1], e.rd16(0xFB02)), (0xFC00, 0x0011, 0x0022))


class TestBits(unittest.TestCase):
    def test_set_clear_move(self):
        e = run("bset 0xFD02.3")
        self.assertEqual((e.rd16(0xFD02), fl(e)), (8, "Z"))                # N, Z from the previous state
        e = run("bclr 0xFD02.3", mem={0xFD02: 8})
        self.assertEqual((e.rd16(0xFD02), fl(e)), (0, "N"))
        e = run("bmov r1.15, r2.0", {2: 1})
        self.assertEqual((e.r[1], fl(e)), (0x8000, "N"))
        e = run("bmovn r1.15, r2.0", {2: 1})
        self.assertEqual((e.r[1], fl(e)), (0, "N"))

    def test_logic_on_bits(self):
        e = run("band r1.0, r2.0", {1: 1, 2: 1})
        self.assertEqual((e.r[1], fl(e)), (1, "VC"))                       # Z NOR, V OR, C AND, N XOR
        e = run("bor r1.0, r2.0", {1: 0, 2: 1})
        self.assertEqual((e.r[1], fl(e)), (1, "VN"))
        e = run("bxor r1.0, r2.0", {1: 1, 2: 1})
        self.assertEqual((e.r[1], fl(e)), (0, "VC"))
        e = run("bcmp r1.0, r2.0", {1: 0, 2: 0})
        self.assertEqual((e.r[1], fl(e)), (0, "Z"))

    def test_bit_fields(self):
        e = run("bfldl 0xFD10, #0x0F, #0x05\nbfldh 0xFD10, #0xF0, #0x50", mem={0xFD10: 0x1234})
        self.assertEqual(e.rd16(0xFD10), 0x5235)
        e = run("bfldl 0xFD10, #0x0F, #0xF5", mem={0xFD10: 0x1234})        # the data is ORed as it is
        self.assertEqual(e.rd16(0xFD10), 0x12F5)
        self.assertEqual(c166.assemble_one("bfldh 0xFD10, #0xF0, #0x50", 0), bytes.fromhex("1A0850F0"))

    def test_bit_jumps(self):
        e = run("mov r1, #2\njbc 0xFD02.0, taken\nmov r1, #1\ntaken:", mem={0xFD02: 1})
        self.assertEqual((e.r[1], e.rd16(0xFD02), fl(e)), (2, 0, "N"))      # taken, bit cleared
        e = run("mov r1, #2\njnbs 0xFD02.0, taken\nmov r1, #1\ntaken:", mem={0xFD02: 0})
        self.assertEqual((e.r[1], e.rd16(0xFD02), fl(e)), (2, 1, "Z"))      # taken, bit set
        e = run("mov r1, #2\njb 0xFD02.0, taken\nmov r1, #1\ntaken:", mem={0xFD02: 0})
        self.assertEqual(e.r[1], 1)                                          # not taken


class TestFlow(unittest.TestCase):
    def test_conditions_of_table_5(self):
        e = c166emu.Emu(bytes(0x80000), c166.PROFILES["ms42"])
        for psw in range(32):
            e.psw = psw
            n, c, v, z, x = (psw >> 0) & 1, (psw >> 1) & 1, (psw >> 2) & 1, (psw >> 3) & 1, (psw >> 4) & 1
            want = {0: 1, 1: (z | x) == 0, 2: z, 3: not z, 4: v, 5: not v, 6: n, 7: not n, 8: c, 9: not c,
                    0xA: (z | (n ^ v)) == 0, 0xB: (z | (n ^ v)) == 1, 0xC: n ^ v, 0xD: not (n ^ v),
                    0xE: (z | c) == 0, 0xF: (z | c) == 1}
            for cc, w in want.items():
                self.assertEqual(bool(e.cond(cc)), bool(w), (psw, cc))

    def test_calls_and_returns(self):
        extra = {0x61000: "add r1, #1\nret", 0x70000: "add r1, #0x0010\nrets"}
        e = run("calla cc_UC, 0x61000\ncallr 0x60010\ncalls 0x07:0x0000\njmpr cc_UC, 0x60014\n"
                "org 0x60010\nadd r1, #2\nret\norg 0x60014\nmov r2, #0x0000", {1: 0}, extra=extra)
        self.assertEqual((e.r[1], e.sp), (0x13, 0xFA00))
        e = run("mov r3, #0x1000\ncalli cc_UC, [r3]", {1: 0}, extra={0x61000: "mov r1, #7\nret"})
        self.assertEqual(e.r[1], 7)
        e = run("pcall r5, 0x61000", {5: 0x8000}, extra={0x61000: "retp r6"})
        self.assertEqual((e.r[6], fl(e), e.sp), (0x8000, "EN", 0xFA00))

    def test_trap_and_reti(self):
        e = run("trap #0x10", {1: 0}, psw=0x0001, extra={0x0040: "mov r1, #5\nmov PSW, #0x0000\nreti"})
        self.assertEqual((e.r[1], e.psw, e.sp), (5, 0x0001, 0xFA00))

    def test_stack_flags(self):
        e = run("push r1\npop r2", {1: 0})
        self.assertEqual((e.r[2], fl(e)), (0, "Z"))

    def test_stops(self):
        for src, why in (("mov r1, [0x8001]", "odd"), ("mov [0x8000], r1", "outside RAM"), ("db 0x3B, 0x00", "no instruction"),
                         ("srst", "stops")):
            with self.subTest(src=src), self.assertRaises(c166emu.Stop) as cm:
                run(src)
            self.assertIn(why, str(cm.exception))


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
        cls.img, cls.names = {}, {}
        for h, repo, name in listed():
            with open(os.path.join(IMAGES, repo, name), "rb") as f:
                b = f.read()
            assert hashlib.sha256(b).hexdigest() == h, name
            cls.img.setdefault(repo, []).append(b)
            cls.names.setdefault(repo, []).append(name)

    def test_checksums_by_the_programs_own_routine(self):
        # the program's own CRC routine run by the emulator gives what an independent CRC-16 (polynomial 0xA001, as
        # reflected) gives over the same blocks; the program part is the same in every image of a family, so its
        # CRC runs once and the calibration CRC in every image
        table = []
        for i in range(256):
            c = i
            for _ in range(8):
                c = (c >> 1) ^ 0xA001 if c & 1 else c >> 1
            table.append(c)
        differ = set()
        for repo, imgs in self.img.items():
            for k, b in enumerate(imgs):
                prof = c166.detect(b)
                routine, descs = c166emu.CRC[prof.key]
                for desc, how in descs[:1] if k else descs:
                    _, stored, got, _ = c166emu.program_crc(b, prof, only=desc)[0]
                    crc = c166emu.crc_init(b, prof, how)
                    for i in range(b[desc + 2]):
                        lo = int.from_bytes(b[desc + 4 + 8 * i:desc + 8 + 8 * i], "little")
                        hi = int.from_bytes(b[desc + 8 + 8 * i:desc + 12 + 8 * i], "little")
                        for x in b[prof.file_of(lo):prof.file_of(hi) + 1]:
                            crc = (crc >> 8) ^ table[(crc ^ x) & 0xFF]
                    self.assertEqual(got, crc, "%s %s descriptor 0x%05X" % (repo, self.names[repo][k], desc))
                    if got != stored:
                        differ.add((self.names[repo][k], desc))
        # one image of ms4x-net stores a calibration sum that its content does not give (C138, stored 5ADF)
        self.assertEqual(differ, {("Siemens_MS43_MS430069_E39_M54B25_EU4_LHD.bin", 0x73FE0)})

    def test_functions_run_without_emulator_errors(self):
        # every function reached in the code, with RAM at zero: it returns or stops on something the emulator
        # reports (a step limit, memory outside the map); a Python error would be a fault of the emulator
        for repo, imgs in self.img.items():
            b = imgs[0]
            prof = c166.detect(b)
            seen, labels, xrefs, errors = c166.walk(b, c166.vectors(b, prof) + c166.far_calls(b, prof), prof,
                                                    follow_calls=True)
            subs = sorted(t for t, n in labels.items() if n.startswith("sub_"))
            returned = 0
            for t in subs:
                far = any(seen[s].mn == "calls" for s in xrefs.get(t, ()))
                emu = c166emu.Emu(b, prof)
                try:
                    emu.call(t, near=not far, max_steps=3000)
                    returned += 1
                except c166emu.Stop:
                    pass
            self.assertGreater(returned / len(subs), 0.5, repo)


if __name__ == "__main__":
    unittest.main()
