#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
"""
c166.py: disassembler, assembler and code walker for the C166 core of the C167 in the Siemens MS42 and MS43.
Part of the MS4X repository. License: Apache-2.0 (LICENSE, NOTICE), credit: rudywolf, https://github.com/therudywolf/MS4X.

One table of instruction forms serves both directions: whatever the disassembler prints, the assembler turns back
into the same bytes, and `check` proves it on a whole image. Bytes that are no instruction, and an instruction with
a reserved field that is not zero, print as `db` with the meaning in the comment.

  python3 tools/c166.py dis   IMAGE START [END]          listing; addresses are file offsets
  python3 tools/c166.py func  IMAGE ADDR                 one function along its flow, with labels
  python3 tools/c166.py funcs IMAGE                      functions reached from the vectors and the far calls
  python3 tools/c166.py xref  IMAGE ADDR [START END]     instructions that call, jump to, read or write ADDR
  python3 tools/c166.py asm   SOURCE -o OUT [--org ADDR] assemble the syntax of the listing into a flat file
  python3 tools/c166.py check IMAGE [START END]          disassemble and assemble back, byte for byte

  --profile ms42 | ms43 | raw   memory map and DPP values; by default from the program ID in the image
  --dpp P0,P1,P2,P3             other DPP values (page numbers)

Syntax: registers r0-r15 and rl0-rh7; an SFR by name or word address (0xFE40); direct memory [0x8100]; indirect
[r4], [r4+], [-r0], [r4+#0x0010]; immediates #5 (3- or 4-bit, decimal), #0x05 (8-bit), #0x0005 (16-bit): the
spelling picks the encoding, so `mov r4, #5` is E0 54 and `mov r4, #0x0005` is E6 F4 05 00. Bits: PSW.3, r4.3,
0xFD10.3. Code targets are file offsets (jmpr cc_EQ, 0x49D02), far targets segment:offset (calls 0x0C:0x9CF8).
"""
import os, re, sys

RW = ["r%d" % i for i in range(16)]
RB = ["rl0", "rh0", "rl1", "rh1", "rl2", "rh2", "rl3", "rh3", "rl4", "rh4", "rl5", "rh5", "rl6", "rh6", "rl7", "rh7"]
RW_IDX = {n: i for i, n in enumerate(RW)}
RB_IDX = {n: i for i, n in enumerate(RB)}
CC = ["cc_UC", "cc_NET", "cc_EQ", "cc_NE", "cc_V", "cc_NV", "cc_N", "cc_NN",
      "cc_ULT", "cc_UGE", "cc_SGT", "cc_SLE", "cc_SLT", "cc_SGE", "cc_UGT", "cc_ULE"]
CC_IDX = dict({n.lower(): i for i, n in enumerate(CC)}, cc_z=2, cc_nz=3, cc_c=8, cc_nc=9)

# SFR (0xFE00-0xFFFF) and ESFR (0xF000-0xF1FF) of the C167CR by word address, from table 22-4 of the
# C167CR Derivatives User's Manual V3.1; a register missing here prints as its address.
SFR = {0xF030: 'PT0', 0xF032: 'PT1', 0xF034: 'PT2', 0xF036: 'PT3', 0xF038: 'PP0', 0xF03A: 'PP1', 0xF03C: 'PP2',
    0xF03E: 'PP3', 0xF050: 'T7', 0xF052: 'T8', 0xF054: 'T7REL', 0xF056: 'T8REL', 0xF0A0: 'ADDAT2', 0xF0AA: 'PDCR',
    0xF0B0: 'SSCTB', 0xF0B2: 'SSCRB', 0xF0B4: 'SSCBR', 0xF100: 'DP0L', 0xF102: 'DP0H', 0xF104: 'DP1L',
    0xF106: 'DP1H', 0xF108: 'RP0H', 0xF160: 'CC16IC', 0xF162: 'CC17IC', 0xF164: 'CC18IC', 0xF166: 'CC19IC',
    0xF168: 'CC20IC', 0xF16A: 'CC21IC', 0xF16C: 'CC22IC', 0xF16E: 'CC23IC', 0xF170: 'CC24IC', 0xF172: 'CC25IC',
    0xF174: 'CC26IC', 0xF176: 'CC27IC', 0xF178: 'CC28IC', 0xF17A: 'T7IC', 0xF17C: 'T8IC', 0xF17E: 'PWMIC',
    0xF184: 'CC29IC', 0xF186: 'XP0IC', 0xF18C: 'CC30IC', 0xF18E: 'XP1IC', 0xF194: 'CC31IC', 0xF196: 'XP2IC',
    0xF19C: 'S0TBIC', 0xF19E: 'XP3IC', 0xF1C0: 'EXICON', 0xF1C2: 'ODP2', 0xF1C4: 'PICON', 0xF1C6: 'ODP3',
    0xF1CE: 'ODP6', 0xF1D2: 'ODP7', 0xF1D6: 'ODP8', 0xFE00: 'DPP0', 0xFE02: 'DPP1', 0xFE04: 'DPP2', 0xFE06: 'DPP3',
    0xFE08: 'CSP', 0xFE0C: 'MDH', 0xFE0E: 'MDL', 0xFE10: 'CP', 0xFE12: 'SP', 0xFE14: 'STKOV', 0xFE16: 'STKUN',
    0xFE18: 'ADDRSEL1', 0xFE1A: 'ADDRSEL2', 0xFE1C: 'ADDRSEL3', 0xFE1E: 'ADDRSEL4', 0xFE30: 'PW0', 0xFE32: 'PW1',
    0xFE34: 'PW2', 0xFE36: 'PW3', 0xFE40: 'T2', 0xFE42: 'T3', 0xFE44: 'T4', 0xFE46: 'T5', 0xFE48: 'T6',
    0xFE4A: 'CAPREL', 0xFE50: 'T0', 0xFE52: 'T1', 0xFE54: 'T0REL', 0xFE56: 'T1REL', 0xFE60: 'CC16', 0xFE62: 'CC17',
    0xFE64: 'CC18', 0xFE66: 'CC19', 0xFE68: 'CC20', 0xFE6A: 'CC21', 0xFE6C: 'CC22', 0xFE6E: 'CC23', 0xFE70: 'CC24',
    0xFE72: 'CC25', 0xFE74: 'CC26', 0xFE76: 'CC27', 0xFE78: 'CC28', 0xFE7A: 'CC29', 0xFE7C: 'CC30', 0xFE7E: 'CC31',
    0xFE80: 'CC0', 0xFE82: 'CC1', 0xFE84: 'CC2', 0xFE86: 'CC3', 0xFE88: 'CC4', 0xFE8A: 'CC5', 0xFE8C: 'CC6',
    0xFE8E: 'CC7', 0xFE90: 'CC8', 0xFE92: 'CC9', 0xFE94: 'CC10', 0xFE96: 'CC11', 0xFE98: 'CC12', 0xFE9A: 'CC13',
    0xFE9C: 'CC14', 0xFE9E: 'CC15', 0xFEA0: 'ADDAT', 0xFEAE: 'WDT', 0xFEB0: 'S0TBUF', 0xFEB2: 'S0RBUF',
    0xFEB4: 'S0BG', 0xFEC0: 'PECC0', 0xFEC2: 'PECC1', 0xFEC4: 'PECC2', 0xFEC6: 'PECC3', 0xFEC8: 'PECC4',
    0xFECA: 'PECC5', 0xFECC: 'PECC6', 0xFECE: 'PECC7', 0xFF00: 'P0L', 0xFF02: 'P0H', 0xFF04: 'P1L', 0xFF06: 'P1H',
    0xFF0C: 'BUSCON0', 0xFF0E: 'MDC', 0xFF10: 'PSW', 0xFF12: 'SYSCON', 0xFF14: 'BUSCON1', 0xFF16: 'BUSCON2',
    0xFF18: 'BUSCON3', 0xFF1A: 'BUSCON4', 0xFF1C: 'ZEROS', 0xFF1E: 'ONES', 0xFF20: 'T78CON', 0xFF22: 'CCM4',
    0xFF24: 'CCM5', 0xFF26: 'CCM6', 0xFF28: 'CCM7', 0xFF30: 'PWMCON0', 0xFF32: 'PWMCON1', 0xFF40: 'T2CON',
    0xFF42: 'T3CON', 0xFF44: 'T4CON', 0xFF46: 'T5CON', 0xFF48: 'T6CON', 0xFF50: 'T01CON', 0xFF52: 'CCM0',
    0xFF54: 'CCM1', 0xFF56: 'CCM2', 0xFF58: 'CCM3', 0xFF60: 'T2IC', 0xFF62: 'T3IC', 0xFF64: 'T4IC', 0xFF66: 'T5IC',
    0xFF68: 'T6IC', 0xFF6A: 'CRIC', 0xFF6C: 'S0TIC', 0xFF6E: 'S0RIC', 0xFF70: 'S0EIC', 0xFF72: 'SSCTIC',
    0xFF74: 'SSCRIC', 0xFF76: 'SSCEIC', 0xFF78: 'CC0IC', 0xFF7A: 'CC1IC', 0xFF7C: 'CC2IC', 0xFF7E: 'CC3IC',
    0xFF80: 'CC4IC', 0xFF82: 'CC5IC', 0xFF84: 'CC6IC', 0xFF86: 'CC7IC', 0xFF88: 'CC8IC', 0xFF8A: 'CC9IC',
    0xFF8C: 'CC10IC', 0xFF8E: 'CC11IC', 0xFF90: 'CC12IC', 0xFF92: 'CC13IC', 0xFF94: 'CC14IC', 0xFF96: 'CC15IC',
    0xFF98: 'ADCIC', 0xFF9A: 'ADEIC', 0xFF9C: 'T0IC', 0xFF9E: 'T1IC', 0xFFA0: 'ADCON', 0xFFA2: 'P5',
    0xFFA4: 'P5DIDIS', 0xFFAC: 'TFR', 0xFFAE: 'WDTCON', 0xFFB0: 'S0CON', 0xFFB2: 'SSCCON', 0xFFC0: 'P2',
    0xFFC2: 'DP2', 0xFFC4: 'P3', 0xFFC6: 'DP3', 0xFFC8: 'P4', 0xFFCA: 'DP4', 0xFFCC: 'P6', 0xFFCE: 'DP6',
    0xFFD0: 'P7', 0xFFD2: 'DP7', 0xFFD4: 'P8', 0xFFD6: 'DP8'}
# general registers of the on-chip CAN module (0xEF00-0xEF0F); objects 1-15 follow at 0xEF10 + 0x10 * (n - 1)
XREG = {0xEF00: 'C1CSR', 0xEF02: 'C1IR', 0xEF04: 'C1BTR', 0xEF06: 'C1GMS', 0xEF08: 'C1UGML', 0xEF0A: 'C1LGML',
    0xEF0C: 'C1UMLM', 0xEF0E: 'C1LMLM'}
SFR_ADDR = {n.upper(): a for a, n in SFR.items()}


# ------------------------------------------------------------------------------------------------ memory profiles
def can_part(a):
    """What a byte of the CAN module is: a general register, or a part of message object 1-15."""
    if a < 0xEF10:
        return "CAN " + XREG.get(a & ~1, "0x%04X" % a)
    n, k = (a - 0xEF00) >> 4, a & 15
    part = {0: "MCR", 1: "MCR", 2: "UAR", 3: "UAR", 4: "LAR", 5: "LAR", 6: "MCFG", 15: "reserved"}.get(k)
    return "CAN object %d %s" % (n, part or "data %d" % (k - 7))


class Profile:
    """Memory map of a program: DPP values after start-up, RAM windows, how a physical address finds the file."""

    def __init__(self, key, name, dpp, ident=None, ram=(), mirror=False, data=()):
        self.key, self.name, self.dpp, self.ident, self.ram, self.mirror = key, name, tuple(dpp), ident, ram, mirror
        self.data = data                                                # file ranges without code (calibration)

    def file_of(self, phys, size=0x80000):
        if 0xC000 <= phys <= 0xFFFF or any(lo <= phys < hi for lo, hi, _ in self.ram):
            return None
        if phys >= (0x100000 if self.mirror else 0x80000):
            return None
        f = phys & 0x7FFFF
        return f if f < size else None

    def describe(self, phys):
        if 0xC000 <= phys <= 0xFFFF:                                    # system page: on-chip memory and registers
            if phys >= 0xFE00:
                return SFR.get(phys & ~1, "SFR")
            if 0xF000 <= phys < 0xF200:
                return SFR.get(phys & ~1, "ESFR")
            if 0xEF00 <= phys < 0xF000:
                return can_part(phys)
            for lo, hi, what in ((0xF600, 0xFE00, "IRAM"), (0xE000, 0xE800, "XRAM")):
                if lo <= phys < hi:
                    return what
            return "0x%05X" % phys
        for lo, hi, what in self.ram:
            if lo <= phys < hi:
                return "%s 0x%05X" % (what, phys)
        f = self.file_of(phys)
        return "file 0x%05X" % f if f is not None else "0x%05X" % phys


PROFILES = {
    # MS42 0110C6: the file is the physical address; DPP0-2 point into the flash (0x48000-0x53FFF), DPP3 = system page.
    "ms42": Profile("ms42", "Siemens MS42 0110C6", (0x12, 0x14, 0x13, 0x03), (0x48008, b"0110C6"),
                    data=((0x48000, 0x50000),)),
    # MS43 430069: the flash shows at 0x00000 and 0x80000 (file = physical & 0x7FFFF), code runs in segments 9-0x0F;
    # external RAM 16 KB at 0x40000 (DPP2); DPP0 = calibration 0x70000, DPP1 = 0xEC000 (file 0x6C000).
    "ms43": Profile("ms43", "Siemens MS43 430069", (0x1C, 0x3B, 0x10, 0x03), (0x6FFBA, b"430069"),
                    ram=((0x40000, 0x44000, "ext RAM"),), mirror=True, data=((0x70000, 0x80000),)),
    "raw": Profile("raw", "C166 image, file = physical address", (0, 1, 2, 3)),
}


def detect(img):
    for p in PROFILES.values():
        if p.ident and img[p.ident[0]:p.ident[0] + len(p.ident[1])] == p.ident[1]:
            return p
    return PROFILES["raw"]


# ------------------------------------------------------------------------------------------------ operands
def num(s):
    s = s.strip()
    try:
        if re.fullmatch(r"0[xX][0-9A-Fa-f]+", s):
            return int(s, 16)
        if re.fullmatch(r"[0-9][0-9A-Fa-f]*[hH]", s):
            return int(s[:-1], 16)
        if re.fullmatch(r"[0-9]+", s):
            return int(s)
    except ValueError:
        pass
    return None


def name_reg(r, byte, extr):
    if r >= 0xF0:
        return RB[r & 15] if byte else RW[r & 15]
    a = (0xF000 if extr else 0xFE00) + 2 * r
    return SFR.get(a) or "0x%04X" % a


def bitword(q, extr):
    """Word address of a bit-addressable word (bitoff); GPRs give None."""
    if q >= 0xF0:
        return None
    if q >= 0x80:
        return (0xF100 if extr else 0xFF00) + 2 * (q - 0x80)
    return 0xFD00 + 2 * q


def name_bitword(q, extr):
    if q >= 0xF0:
        return RW[q & 15]
    a = bitword(q, extr)
    return SFR.get(a) or "0x%04X" % a


def fmt_op(o, extr=False):
    t = o[0]
    if t == "r":
        return RW[o[1]]
    if t == "rb":
        return RB[o[1]]
    if t == "reg":
        return name_reg(o[1], o[2], extr)
    if t == "mem":
        return "[0x%04X]" % o[1]
    if t == "ind":
        return "[r%d]" % o[1]
    if t == "inc":
        return "[r%d+]" % o[1]
    if t == "dec":
        return "[-r%d]" % o[1]
    if t == "idx":
        return "[r%d+#0x%04X]" % (o[1], o[2])
    if t == "imm":
        v, w = o[1], o[2]
        if w in ("3", "4", "i2"):
            return "#%d" % v
        if w == "8" and v > 0xFF:                       # byte immediate with its unused upper byte set (FFxx)
            return "#0x%04X" % v
        if w in ("8", "t7", "seg"):
            return "#0x%02X" % v
        if w == "pag":
            return "#0x%03X" % v
        return "#0x%04X" % v
    if t == "cc":
        return CC[o[1]]
    if t == "bit":
        return "%s.%d" % (name_bitword(o[1], extr), o[2])
    if t == "boff":
        return name_bitword(o[1], extr)
    if t == "code":
        return "0x%05X" % o[1]
    if t == "far":
        return "0x%02X:0x%04X" % (o[1], o[2])
    raise ValueError(o)


class Tok:
    """One operand of the source text; each method reads it as one kind of operand or returns None."""

    def __init__(self, s, sym=None):
        self.s = s.strip()
        self.l = self.s.lower()
        self.sym = sym or {}

    def r(self):
        return RW_IDX.get(self.l)

    def rb(self):
        return RB_IDX.get(self.l)

    def reg(self, byte, extr):
        i = (RB_IDX if byte else RW_IDX).get(self.l)
        if i is not None:
            return 0xF0 | i
        a = SFR_ADDR.get(self.s.upper())
        a = a if a is not None else num(self.s)
        base = 0xF000 if extr else 0xFE00
        if a is not None and not a & 1 and base <= a <= base + 0x1DE:
            return (a - base) >> 1
        return None

    def mem(self):
        m = re.fullmatch(r"\[\s*([^\]\s][^\]]*?)\s*\]", self.s)
        if m and not re.match(r"[-rR]", m.group(1)):
            v = num(m.group(1))
            if v is not None and v <= 0xFFFF:
                return v
        return None

    def _ptr(self, pat):
        m = re.fullmatch(pat, self.l)
        return int(m.group(1)) if m and int(m.group(1)) < 16 else None

    def ind(self):
        return self._ptr(r"\[\s*r(\d+)\s*\]")

    def inc(self):
        return self._ptr(r"\[\s*r(\d+)\s*\+\s*\]")

    def dec(self):
        return self._ptr(r"\[\s*-\s*r(\d+)\s*\]")

    def idx(self):
        m = re.fullmatch(r"\[\s*r(\d+)\s*\+\s*#\s*([^\]]+?)\s*\]", self.l)
        if m and int(m.group(1)) < 16:
            v = num(m.group(2))
            if v is not None and v <= 0xFFFF:
                return int(m.group(1)), v
        return None

    def imm(self):
        """(value, spelling): 'dec' for decimal, else the number of hex digits."""
        m = re.fullmatch(r"#\s*(\S+)", self.s)
        if not m:
            return None
        v = num(m.group(1))
        if v is None:
            return None
        sp = m.group(1)
        if re.fullmatch(r"0[xX][0-9A-Fa-f]+", sp):
            return v, len(sp) - 2
        return v, "dec"

    def cc(self):
        return CC_IDX.get(self.l)

    def _word(self, s, extr):
        s = s.strip()
        if s.lower() in RW_IDX:
            return 0xF0 | RW_IDX[s.lower()]
        a = SFR_ADDR.get(s.upper())
        a = a if a is not None else num(s)
        if a is None or a & 1:
            return None
        if 0xFD00 <= a <= 0xFDFE:
            return (a - 0xFD00) >> 1
        base = 0xF100 if extr else 0xFF00
        if base <= a <= base + 0xDE:
            return 0x80 + ((a - base) >> 1)
        return None

    def bit(self, extr):
        if "." not in self.s:
            return None
        w, b = self.s.rsplit(".", 1)
        q, b = self._word(w, extr), num(b)
        return (q, b) if q is not None and b is not None and b < 16 else None

    def boff(self, extr):
        return self._word(self.s, extr)

    def code(self):
        if self.s in self.sym:
            return self.sym[self.s]
        return num(self.s)

    def far(self):
        m = re.fullmatch(r"(\S+)\s*:\s*(\S+)", self.s)
        if m:
            s, o = num(m.group(1)), num(m.group(2))
            if s is not None and o is not None and s <= 0xFF and o <= 0xFFFF:
                return s, o
        return None


def imm_ok(t, width):
    """The immediate of token t for a field of width 3, 4, 8 or 16 bits; the spelling decides between forms."""
    x = t.imm()
    if x is None:
        return None
    v, sp = x
    if width in (3, 4):
        return v if sp == "dec" and v < (1 << width) else None
    if width == 8:                                          # the field is a word: 4 hex digits keep the upper byte
        return v if v <= 0xFF or (sp == 4 and v <= 0xFFFF) else None
    return v if v <= 0xFFFF else None


# ------------------------------------------------------------------------------------------------ instruction forms
class Insn:
    __slots__ = ("off", "raw", "mn", "ops", "flow", "ext", "note")

    def __init__(self, off, raw, mn, ops, flow=None, ext=None, note=None):
        self.off, self.raw, self.mn, self.ops, self.flow, self.ext, self.note = off, raw, mn, ops, flow, ext, note

    @property
    def size(self):
        return len(self.raw)

    @property
    def ok(self):
        return self.mn != "db"

    def text(self, extr=False):
        if not self.ops:
            return self.mn
        return "%s %s" % (self.mn, ", ".join(fmt_op(o, extr) for o in self.ops))

    def target(self, prof=None):
        """File offset the instruction jumps or calls to, None for none or unknown."""
        for o in self.ops:
            if o[0] == "code":
                return o[1]
            if o[0] == "far":
                return (prof or PROFILES["raw"]).file_of((o[1] << 16) | o[2])
        return None


BY_OP = {}          # first byte -> decoder
BY_MN = {}          # mnemonic -> [(size, encoder)], shortest first


def form(ops, mns, size, dec, enc):
    for op in ops:
        assert op not in BY_OP, hex(op)
        BY_OP[op] = (size, dec)
    for mn in mns:
        BY_MN.setdefault(mn, []).append((size, enc))


def le16(b, i):
    return b[i] | (b[i + 1] << 8)


def w16(v):
    return [v & 0xFF, v >> 8]


def s8(b):
    return b - 256 if b & 0x80 else b


def near(off, size, rel):
    """File offset of a relative target: the IP wraps inside its 64 KB segment."""
    return (off & ~0xFFFF) | ((off + size + 2 * rel) & 0xFFFF)


def rel_of(off, size, target):
    if target is None or (target >> 16) != (off >> 16):
        return None
    d = ((target & 0xFFFF) - ((off + size) & 0xFFFF)) & 0xFFFF
    d = d - 0x10000 if d >= 0x8000 else d
    if d & 1 or not -256 <= d <= 254:
        return None
    return (d >> 1) & 0xFF


def caddr_of(off, target):
    return None if target is None or (target >> 16) != (off >> 16) else target & 0xFFFF


def args(toks, n):
    return len(toks) == n


ALU = ["add", "addc", "sub", "subc", "cmp", "xor", "and", "or"]


def build():
    # ------------------------------------------------ ALU: x0-x9 of rows 0-7, word and byte
    for hi, name in enumerate(ALU):
        for byte in (0, 1):
            mn = name + ("b" if byte else "")
            gpr, kind = (RB, "rb") if byte else (RW, "r")
            base = hi << 4

            def rr(b, off, mn=mn, kind=kind):
                return mn, [(kind, b[1] >> 4), (kind, b[1] & 15)]

            def rr_e(t, off, ctx, op=base | byte, byte=byte):
                if not args(t, 2):
                    return None
                n, m = (t[0].rb(), t[1].rb()) if byte else (t[0].r(), t[1].r())
                return None if n is None or m is None else [op, n << 4 | m]
            form([base | byte], [mn], 2, rr, rr_e)

            def rm(b, off, mn=mn, byte=byte):
                return mn, [("reg", b[1], byte), ("mem", le16(b, 2))]

            def rm_e(t, off, ctx, op=base | 2 | byte, byte=byte):
                if not args(t, 2):
                    return None
                r, a = t[0].reg(byte, ctx), t[1].mem()
                return None if r is None or a is None else [op, r] + w16(a)
            form([base | 2 | byte], [mn], 4, rm, rm_e)

            if name != "cmp":                                          # CMP has no mem, reg form (0x44 / 0x45)
                def mr(b, off, mn=mn, byte=byte):
                    return mn, [("mem", le16(b, 2)), ("reg", b[1], byte)]

                def mr_e(t, off, ctx, op=base | 4 | byte, byte=byte):
                    if not args(t, 2):
                        return None
                    a, r = t[0].mem(), t[1].reg(byte, ctx)
                    return None if r is None or a is None else [op, r] + w16(a)
                form([base | 4 | byte], [mn], 4, mr, mr_e)

            if byte:
                def ri(b, off, mn=mn):
                    return mn, [("reg", b[1], 1), ("imm", le16(b, 2), "8")]

                def ri_e(t, off, ctx, op=base | 7):
                    if not args(t, 2):
                        return None
                    r, v = t[0].reg(1, ctx), imm_ok(t[1], 8)
                    return None if r is None or v is None else [op, r] + w16(v)
                form([base | 7], [mn], 4, ri, ri_e)
            else:
                def ri(b, off, mn=mn):
                    return mn, [("reg", b[1], 0), ("imm", le16(b, 2), "16")]

                def ri_e(t, off, ctx, op=base | 6):
                    if not args(t, 2):
                        return None
                    r, v = t[0].reg(0, ctx), imm_ok(t[1], 16)
                    return None if r is None or v is None else [op, r] + w16(v)
                form([base | 6], [mn], 4, ri, ri_e)

            def x8(b, off, mn=mn, kind=kind):
                n, s = b[1] >> 4, b[1] & 15
                if s < 8:
                    o = ("imm", s, "3")
                elif s < 12:
                    o = ("ind", s & 3)
                else:
                    o = ("inc", s & 3)
                return mn, [(kind, n), o]

            def x8_e(t, off, ctx, op=base | 8 | byte, byte=byte):
                if not args(t, 2):
                    return None
                n = t[0].rb() if byte else t[0].r()
                if n is None:
                    return None
                v = imm_ok(t[1], 3)
                if v is not None:
                    return [op, n << 4 | v]
                i = t[1].ind()
                if i is not None and i < 4:
                    return [op, n << 4 | 8 | i]
                i = t[1].inc()
                if i is not None and i < 4:
                    return [op, n << 4 | 12 | i]
                return None
            form([base | 8 | byte], [mn], 2, x8, x8_e)

    # ------------------------------------------------ bit field and bit-to-bit (column A, rows 0-7)
    # BFLDL "0A QQ @@ ##" keeps the mask in byte 3, BFLDH "1A QQ ## @@" in byte 4; the syntax is bitoff, #mask8, #data8
    # for both. Stock code agrees: the data byte lies inside the mask byte in every BFLDL and BFLDH of 0110C6 and 430069.
    for op, mn, mi in ((0x0A, "bfldl", 2), (0x1A, "bfldh", 3)):
        def bf(b, off, mn=mn, mi=mi):
            return mn, [("boff", b[1]), ("imm", b[mi], "8"), ("imm", b[5 - mi], "8")]

        def bf_e(t, off, ctx, op=op, mi=mi):
            if not args(t, 3):
                return None
            q, mk, d = t[0].boff(ctx), imm_ok(t[1], 8), imm_ok(t[2], 8)
            if q is None or mk is None or d is None or max(mk, d) > 0xFF:
                return None
            return [op, q, mk, d] if mi == 2 else [op, q, d, mk]
        form([op], [mn], 4, bf, bf_e)
    for op, mn in ((0x2A, "bcmp"), (0x3A, "bmovn"), (0x4A, "bmov"), (0x5A, "bor"), (0x6A, "band"), (0x7A, "bxor")):
        # "op QQ ZZ qz": first operand ZZ.z, second QQ.q
        def b2(b, off, mn=mn):
            return mn, [("bit", b[2], b[3] & 15), ("bit", b[1], b[3] >> 4)]

        def b2_e(t, off, ctx, op=op):
            if not args(t, 2):
                return None
            z, q = t[0].bit(ctx), t[1].bit(ctx)
            return None if z is None or q is None else [op, q[0], z[0], q[1] << 4 | z[1]]
        form([op], [mn], 4, b2, b2_e)

    # ------------------------------------------------ multiply, divide, shifts (columns B, C of rows 0-7)
    for op, mn in ((0x0B, "mul"), (0x1B, "mulu"), (0x2B, "prior"), (0x0C, "rol"), (0x2C, "ror"), (0x4C, "shl"),
                   (0x6C, "shr"), (0xAC, "ashr")):
        def m2(b, off, mn=mn):
            return mn, [("r", b[1] >> 4), ("r", b[1] & 15)]

        def m2_e(t, off, ctx, op=op):
            if not args(t, 2):
                return None
            n, m = t[0].r(), t[1].r()
            return None if n is None or m is None else [op, n << 4 | m]
        form([op], [mn], 2, m2, m2_e)
    for op, mn in ((0x1C, "rol"), (0x3C, "ror"), (0x5C, "shl"), (0x7C, "shr"), (0xBC, "ashr")):
        def sh(b, off, mn=mn):
            return mn, [("r", b[1] & 15), ("imm", b[1] >> 4, "4")]

        def sh_e(t, off, ctx, op=op):
            if not args(t, 2):
                return None
            n, v = t[0].r(), imm_ok(t[1], 4)
            return None if n is None or v is None else [op, v << 4 | n]
        form([op], [mn], 2, sh, sh_e)
    for op, mn in ((0x4B, "div"), (0x5B, "divu"), (0x6B, "divl"), (0x7B, "divlu")):
        def dv(b, off, mn=mn):
            return (mn, [("r", b[1] >> 4)]) if b[1] >> 4 == b[1] & 15 else None

        def dv_e(t, off, ctx, op=op):
            n = t[0].r() if args(t, 1) else None
            return None if n is None else [op, n << 4 | n]
        form([op], [mn], 2, dv, dv_e)

    # ------------------------------------------------ jumps by condition, bit set and clear (columns D, E, F)
    for c in range(16):
        def jr(b, off, c=c):
            return "jmpr", [("cc", c), ("code", near(off, 2, s8(b[1])))], "jmp" if c == 0 else "jcc"

        def jr_e(t, off, ctx, c=c):
            if not args(t, 2) or t[0].cc() != c:
                return None
            r = rel_of(off, 2, t[1].code())
            return None if r is None else [c << 4 | 0xD, r]
        form([c << 4 | 0xD], ["jmpr"], 2, jr, jr_e)
        for lo, mn in ((0xE, "bclr"), (0xF, "bset")):
            def bc(b, off, c=c, mn=mn):
                return mn, [("bit", b[1], c)]

            def bc_e(t, off, ctx, c=c, lo=lo):
                x = t[0].bit(ctx) if args(t, 1) else None
                return None if x is None or x[1] != c else [c << 4 | lo, x[0]]
            form([c << 4 | lo], [mn], 2, bc, bc_e)

    # ------------------------------------------------ rows 8-F, column 0
    for op, mn in ((0x80, "cmpi1"), (0x90, "cmpi2"), (0xA0, "cmpd1"), (0xB0, "cmpd2"), (0xE0, "mov"), (0xE1, "movb")):
        byte = op == 0xE1

        def d4(b, off, mn=mn, byte=byte):
            return mn, [("rb" if byte else "r", b[1] & 15), ("imm", b[1] >> 4, "4")]

        def d4_e(t, off, ctx, op=op, byte=byte):
            if not args(t, 2):
                return None
            n, v = (t[0].rb() if byte else t[0].r()), imm_ok(t[1], 4)
            return None if n is None or v is None else [op, v << 4 | n]
        form([op], [mn], 2, d4, d4_e)
    for op, mn in ((0xC0, "movbz"), (0xD0, "movbs")):
        # "C0 mn": the word register n in the low nibble, the byte register m in the high one
        def bz(b, off, mn=mn):
            return mn, [("r", b[1] & 15), ("rb", b[1] >> 4)]

        def bz_e(t, off, ctx, op=op):
            if not args(t, 2):
                return None
            n, m = t[0].r(), t[1].rb()
            return None if n is None or m is None else [op, m << 4 | n]
        form([op], [mn], 2, bz, bz_e)
    for op, mn in ((0xF0, "mov"), (0xF1, "movb")):
        byte = op == 0xF1

        def mv(b, off, mn=mn, byte=byte):
            k = "rb" if byte else "r"
            return mn, [(k, b[1] >> 4), (k, b[1] & 15)]

        def mv_e(t, off, ctx, op=op, byte=byte):
            if not args(t, 2):
                return None
            n, m = (t[0].rb(), t[1].rb()) if byte else (t[0].r(), t[1].r())
            return None if n is None or m is None else [op, n << 4 | m]
        form([op], [mn], 2, mv, mv_e)

    # ------------------------------------------------ column 1
    for op, mn, byte in ((0x81, "neg", 0), (0x91, "cpl", 0), (0xA1, "negb", 1), (0xB1, "cplb", 1)):
        def ng(b, off, mn=mn, byte=byte):
            return (mn, [("rb" if byte else "r", b[1] >> 4)]) if b[1] & 15 == 0 else None

        def ng_e(t, off, ctx, op=op, byte=byte):
            n = (t[0].rb() if byte else t[0].r()) if args(t, 1) else None
            return None if n is None else [op, n << 4]
        form([op], [mn], 2, ng, ng_e)

    def d1(b, off):
        sub, n = b[1] >> 6, ((b[1] >> 4) & 3) + 1
        if b[1] & 15 or sub not in (0, 2):
            return None
        mn = "atomic" if sub == 0 else "extr"
        return mn, [("imm", n, "i2")], None, (mn, None, n)

    def d1_e(t, off, ctx, sub):
        x = imm_ok(t[0], 3) if args(t, 1) else None
        return None if x is None or not 1 <= x <= 4 else [0xD1, sub << 6 | (x - 1) << 4]
    form([0xD1], [], 2, d1, None)
    BY_MN.setdefault("atomic", []).append((2, lambda t, off, ctx: d1_e(t, off, ctx, 0)))
    BY_MN.setdefault("extr", []).append((2, lambda t, off, ctx: d1_e(t, off, ctx, 2)))

    # ------------------------------------------------ column 2
    for op, mn in ((0x82, "cmpi1"), (0x92, "cmpi2"), (0xA2, "cmpd1"), (0xB2, "cmpd2")):
        def cm(b, off, mn=mn):
            return (mn, [("r", b[1] & 15), ("mem", le16(b, 2))]) if b[1] >> 4 == 0xF else None

        def cm_e(t, off, ctx, op=op):
            if not args(t, 2):
                return None
            n, a = t[0].r(), t[1].mem()
            return None if n is None or a is None else [op, 0xF0 | n] + w16(a)
        form([op], [mn], 4, cm, cm_e)
    for op, mn, byte in ((0xC2, "movbz", 0), (0xD2, "movbs", 0), (0xF2, "mov", 0), (0xF3, "movb", 1)):
        def lm(b, off, mn=mn, byte=byte):
            return mn, [("reg", b[1], byte), ("mem", le16(b, 2))]

        def lm_e(t, off, ctx, op=op, byte=byte):
            if not args(t, 2):
                return None
            r, a = t[0].reg(byte, ctx), t[1].mem()
            return None if r is None or a is None else [op, r] + w16(a)
        form([op], [mn], 4, lm, lm_e)

    def pc(b, off):
        return "pcall", [("reg", b[1], 0), ("code", (off & ~0xFFFF) | le16(b, 2))], "call"

    def pc_e(t, off, ctx):
        if not args(t, 2):
            return None
        r, a = t[0].reg(0, ctx), caddr_of(off, t[1].code())
        return None if r is None or a is None else [0xE2, r] + w16(a)
    form([0xE2], ["pcall"], 4, pc, pc_e)

    # ------------------------------------------------ column 4
    for op, mn, store in ((0x84, "mov", 0), (0x94, "mov", 1), (0xA4, "movb", 0), (0xB4, "movb", 1)):
        def im(b, off, mn=mn, store=store):
            if b[1] >> 4:
                return None
            ops = [("ind", b[1] & 15), ("mem", le16(b, 2))]
            return mn, ops[::-1] if store else ops

        def im_e(t, off, ctx, op=op, store=store):
            if not args(t, 2):
                return None
            p, a = (t[1], t[0]) if store else (t[0], t[1])
            n, a = p.ind(), a.mem()
            return None if n is None or a is None else [op, n] + w16(a)
        form([op], [mn], 4, im, im_e)
    for op, mn, byte, store in ((0xC4, "mov", 0, 1), (0xD4, "mov", 0, 0), (0xE4, "movb", 1, 1), (0xF4, "movb", 1, 0)):
        # "C4 nm ## ##": n is the data register, m the pointer
        def ix(b, off, mn=mn, byte=byte, store=store):
            ops = [("rb" if byte else "r", b[1] >> 4), ("idx", b[1] & 15, le16(b, 2))]
            return mn, ops[::-1] if store else ops

        def ix_e(t, off, ctx, op=op, byte=byte, store=store):
            if not args(t, 2):
                return None
            d, p = (t[1], t[0]) if store else (t[0], t[1])
            n, x = (d.rb() if byte else d.r()), p.idx()
            return None if n is None or x is None else [op, n << 4 | x[0]] + w16(x[1])
        form([op], [mn], 4, ix, ix_e)

    # ------------------------------------------------ column 5
    for op, mn, byte in ((0xC5, "movbz", 1), (0xD5, "movbs", 1), (0xF6, "mov", 0), (0xF7, "movb", 1)):
        def sm(b, off, mn=mn, byte=byte):
            return mn, [("mem", le16(b, 2)), ("reg", b[1], byte)]

        def sm_e(t, off, ctx, op=op, byte=byte):
            if not args(t, 2):
                return None
            a, r = t[0].mem(), t[1].reg(byte, ctx)
            return None if r is None or a is None else [op, r] + w16(a)
        form([op], [mn], 4, sm, sm_e)

    # ------------------------------------------------ column 6
    for op, mn in ((0x86, "cmpi1"), (0x96, "cmpi2"), (0xA6, "cmpd1"), (0xB6, "cmpd2")):
        def ci(b, off, mn=mn):
            return (mn, [("r", b[1] & 15), ("imm", le16(b, 2), "16")]) if b[1] >> 4 == 0xF else None

        def ci_e(t, off, ctx, op=op):
            if not args(t, 2):
                return None
            n, v = t[0].r(), imm_ok(t[1], 16)
            return None if n is None or v is None else [op, 0xF0 | n] + w16(v)
        form([op], [mn], 4, ci, ci_e)
    for op, mn in ((0xC6, "scxt"), (0xE6, "mov")):
        def si(b, off, mn=mn):
            return mn, [("reg", b[1], 0), ("imm", le16(b, 2), "16")]

        def si_e(t, off, ctx, op=op):
            if not args(t, 2):
                return None
            r, v = t[0].reg(0, ctx), imm_ok(t[1], 16)
            return None if r is None or v is None else [op, r] + w16(v)
        form([op], [mn], 4, si, si_e)

    def sc(b, off):
        return "scxt", [("reg", b[1], 0), ("mem", le16(b, 2))]

    def sc_e(t, off, ctx):
        if not args(t, 2):
            return None
        r, a = t[0].reg(0, ctx), t[1].mem()
        return None if r is None or a is None else [0xD6, r] + w16(a)
    form([0xD6], ["scxt"], 4, sc, sc_e)

    def mb(b, off):
        return "movb", [("reg", b[1], 1), ("imm", le16(b, 2), "8")]

    def mb_e(t, off, ctx):
        if not args(t, 2):
            return None
        r, v = t[0].reg(1, ctx), imm_ok(t[1], 8)
        return None if r is None or v is None else [0xE7, r] + w16(v)
    form([0xE7], ["movb"], 4, mb, mb_e)

    # ------------------------------------------------ fixed patterns
    for raw, mn, flow in (((0xA5, 0x5A, 0xA5, 0xA5), "diswdt", None), ((0xB5, 0x4A, 0xB5, 0xB5), "einit", None),
                          ((0x87, 0x78, 0x87, 0x87), "idle", None), ((0x97, 0x68, 0x97, 0x97), "pwrdn", None),
                          ((0xA7, 0x58, 0xA7, 0xA7), "srvwdt", None), ((0xB7, 0x48, 0xB7, 0xB7), "srst", "stop"),
                          ((0xCC, 0x00), "nop", None), ((0xCB, 0x00), "ret", "ret"), ((0xDB, 0x00), "rets", "ret"),
                          ((0xFB, 0x88), "reti", "ret")):
        def fx(b, off, raw=raw, mn=mn, flow=flow):
            return (mn, [], flow) if tuple(b[:len(raw)]) == raw else None

        def fx_e(t, off, ctx, raw=raw):
            return None if t else list(raw)
        form([raw[0]], [mn], len(raw), fx, fx_e)

    # ------------------------------------------------ column 7: EXTP / EXTS / EXTPR / EXTSR with a constant
    EXT = ["exts", "extp", "extsr", "extpr"]

    def d7(b, off):
        sub, n = b[1] >> 6, ((b[1] >> 4) & 3) + 1
        if b[1] & 15:
            return None
        if sub & 1:                                                     # page: 10 bits
            if b[3] & 0xFC:
                return None
            v, w = b[2] | (b[3] & 3) << 8, "pag"
        else:
            if b[3]:
                return None
            v, w = b[2], "seg"
        return EXT[sub], [("imm", v, w), ("imm", n, "i2")], None, (EXT[sub], v, n)

    def d7_e(t, off, ctx, sub):
        if not args(t, 2):
            return None
        x, n = t[0].imm(), imm_ok(t[1], 3)
        if x is None or n is None or not 1 <= n <= 4 or x[0] > (0x3FF if sub & 1 else 0xFF):
            return None
        v = x[0]
        return [0xD7, sub << 6 | (n - 1) << 4, v & 0xFF, v >> 8]
    form([0xD7], [], 4, d7, None)

    def dc(b, off):
        sub, n = b[1] >> 6, ((b[1] >> 4) & 3) + 1
        return EXT[sub], [("r", b[1] & 15), ("imm", n, "i2")], None, (EXT[sub], ("r", b[1] & 15), n)

    def dc_e(t, off, ctx, sub):
        if not args(t, 2):
            return None
        m, n = t[0].r(), imm_ok(t[1], 3)
        return None if m is None or n is None or not 1 <= n <= 4 else [0xDC, sub << 6 | (n - 1) << 4 | m]
    form([0xDC], [], 2, dc, None)
    for sub, mn in enumerate(EXT):
        BY_MN.setdefault(mn, []).append((2, lambda t, off, ctx, sub=sub: dc_e(t, off, ctx, sub)))
        BY_MN[mn].append((4, lambda t, off, ctx, sub=sub: d7_e(t, off, ctx, sub)))

    # ------------------------------------------------ indirect moves (columns 8, 9)
    IND = {0x88: ("dec", "r"), 0x98: ("r", "inc"), 0xA8: ("r", "ind"), 0xB8: ("ind", "r"),
           0xC8: ("ind", "ind"), 0xD8: ("inc", "ind"), 0xE8: ("ind", "inc")}
    for op, (k1, k2) in IND.items():
        for byte in (0, 1):
            mn = "movb" if byte else "mov"
            # data register in the high nibble, pointer in the low one; two pointers: first operand high
            if k1 in ("r",):
                roles = (("d", k1), ("p", k2))
            elif k2 in ("r",):
                roles = (("p", k1), ("d", k2))
            else:
                roles = (("h", k1), ("l", k2))

            def iv(b, off, mn=mn, byte=byte, roles=roles):
                hi, lo = b[1] >> 4, b[1] & 15
                out = []
                for role, k in roles:
                    v = lo if role in ("p", "l") else hi
                    out.append(("rb" if byte else "r", v) if k == "r" else (k, v))
                return mn, out

            def iv_e(t, off, ctx, op=op | byte, byte=byte, roles=roles):
                if not args(t, 2):
                    return None
                hi = lo = None
                for tok, (role, k) in zip(t, roles):
                    v = (tok.rb() if byte else tok.r()) if k == "r" else getattr(tok, k)()
                    if v is None:
                        return None
                    if role in ("p", "l"):
                        lo = v
                    else:
                        hi = v
                return [op, hi << 4 | lo]
            form([op | byte], [mn], 2, iv, iv_e)

    # ------------------------------------------------ column A, rows 8-F: bit jumps, absolute and segment jumps
    for op, mn in ((0x8A, "jb"), (0x9A, "jnb"), (0xAA, "jbc"), (0xBA, "jnbs")):
        def jb(b, off, mn=mn):
            return (mn, [("bit", b[1], b[3] >> 4), ("code", near(off, 4, s8(b[2])))], "jcc") if b[3] & 15 == 0 else None

        def jb_e(t, off, ctx, op=op):
            if not args(t, 2):
                return None
            x, r = t[0].bit(ctx), rel_of(off, 4, t[1].code())
            return None if x is None or r is None else [op, x[0], r, x[1] << 4]
        form([op], [mn], 4, jb, jb_e)
    for op, mn in ((0xCA, "calla"), (0xEA, "jmpa")):
        def ja(b, off, mn=mn):
            if b[1] & 15:
                return None
            c = b[1] >> 4
            flow = "call" if mn == "calla" else ("jmp" if c == 0 else "jcc")
            return mn, [("cc", c), ("code", (off & ~0xFFFF) | le16(b, 2))], flow

        def ja_e(t, off, ctx, op=op):
            if not args(t, 2):
                return None
            c, a = t[0].cc(), caddr_of(off, t[1].code())
            return None if c is None or a is None else [op, c << 4] + w16(a)
        form([op], [mn], 4, ja, ja_e)
    for op, mn in ((0xDA, "calls"), (0xFA, "jmps")):
        def js(b, off, mn=mn):
            return mn, [("far", b[1], le16(b, 2))], "call" if mn == "calls" else "jmp"

        def js_e(t, off, ctx, op=op):
            x = t[0].far() if args(t, 1) else None
            return None if x is None else [op, x[0]] + w16(x[1])
        form([op], [mn], 4, js, js_e)

    # ------------------------------------------------ column B, rows 8-F
    def tr(b, off):
        return ("trap", [("imm", b[1] >> 1, "t7")]) if b[1] & 1 == 0 else None

    def tr_e(t, off, ctx):
        x = t[0].imm() if args(t, 1) else None
        return None if x is None or x[0] > 0x7F else [0x9B, x[0] << 1]
    form([0x9B], ["trap"], 2, tr, tr_e)
    for op, mn in ((0xAB, "calli"), (0x9C, "jmpi")):
        def ji(b, off, mn=mn):
            c = b[1] >> 4
            flow = "icall" if mn == "calli" else ("stop" if c == 0 else None)
            return mn, [("cc", c), ("ind", b[1] & 15)], flow

        def ji_e(t, off, ctx, op=op):
            if not args(t, 2):
                return None
            c, n = t[0].cc(), t[1].ind()
            return None if c is None or n is None else [op, c << 4 | n]
        form([op], [mn], 2, ji, ji_e)

    def cr(b, off):
        return "callr", [("code", near(off, 2, s8(b[1])))], "call"

    def cr_e(t, off, ctx):
        r = rel_of(off, 2, t[0].code()) if args(t, 1) else None
        return None if r is None else [0xBB, r]
    form([0xBB], ["callr"], 2, cr, cr_e)
    for op, mn, flow in ((0xEB, "retp", "ret"), (0xEC, "push", None), (0xFC, "pop", None)):
        def rg(b, off, mn=mn, flow=flow):
            return mn, [("reg", b[1], 0)], flow

        def rg_e(t, off, ctx, op=op):
            r = t[0].reg(0, ctx) if args(t, 1) else None
            return None if r is None else [op, r]
        form([op], [mn], 2, rg, rg_e)

    for mn in BY_MN:
        BY_MN[mn].sort(key=lambda x: x[0])


build()
UNDEFINED = sorted(set(range(256)) - set(BY_OP))


def decode(img, off):
    """The instruction at file offset off; bytes that are no instruction come back as db."""
    b = img[off:off + 4]
    if len(b) < 2:
        return Insn(off, bytes(b), "db", [("db", bytes(b))])
    size, dec = BY_OP.get(b[0], (2, None))
    if dec is not None and len(b) >= size:
        r = dec(bytes(b) + b"\0\0", off)
        if r is not None:
            mn, ops = r[0], r[1]
            flow = r[2] if len(r) > 2 else None
            ext = r[3] if len(r) > 3 else None
            return Insn(off, bytes(b[:size]), mn, ops, flow, ext)
        note = "reserved bits set" if b[0] in BY_OP else None
        raw = bytes(b[:size] if len(b) >= size else b[:2])
        return Insn(off, raw, "db", [("db", raw)], None, None, note)
    return Insn(off, bytes(b[:2]), "db", [("db", bytes(b[:2]))])


def insn_text(ins, extr=False):
    if ins.mn == "db":
        return "db " + ", ".join("0x%02X" % x for x in ins.ops[0][1])
    return ins.text(extr)


# ------------------------------------------------------------------------------------------------ assembler
def split_ops(s):
    out, depth, cur = [], 0, ""
    for ch in s:
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
        if ch == "," and depth == 0:
            out.append(cur)
            cur = ""
        else:
            cur += ch
    if cur.strip():
        out.append(cur)
    return [x.strip() for x in out]


class AsmError(ValueError):
    pass


def assemble_one(text, off, extr=False, sym=None):
    """Bytes of one instruction (or db / dw) at file offset off."""
    text = text.split(";", 1)[0].strip()
    if not text:
        return b""
    parts = text.split(None, 1)
    mn = parts[0].lower()
    toks = [Tok(x, sym) for x in split_ops(parts[1])] if len(parts) > 1 else []
    if mn in ("db", "dw"):
        out = []
        for t in toks:
            v = num(t.s)
            if v is None or v > (0xFF if mn == "db" else 0xFFFF):
                raise AsmError("bad %s value %r" % (mn, t.s))
            out += [v] if mn == "db" else w16(v)
        return bytes(out)
    for size, enc in BY_MN.get(mn, ()):
        r = enc(toks, off, extr)
        if r is not None:
            return bytes(r)
    if mn not in BY_MN:
        raise AsmError("unknown mnemonic %r" % mn)
    raise AsmError("no form of %r takes these operands: %s" % (mn, text))


LISTING = re.compile(r"^\s*([0-9A-Fa-f]{5,6})\s+((?:[0-9A-Fa-f]{2}\s)+)\s*(.*)$")
LABEL = re.compile(r"^\s*([A-Za-z_.$][\w.$]*)\s*:(?!:)\s*(.*)$")


def assemble(src, org=0):
    """Assemble source lines: labels `name:`, `org ADDR`, db, dw, instructions, or lines of a listing
    (address, bytes, text). Returns {file offset: bytes}."""
    lines = src.splitlines() if isinstance(src, str) else list(src)
    sym = {}
    for final in (False, True):                 # pass 1 finds the labels (sizes never depend on them), pass 2 encodes
        pc, ext_n, chunks = org, 0, {}
        for no, line in enumerate(lines, 1):
            body = line.split(";", 1)[0]
            m = LISTING.match(body)
            if m:
                pc, body = int(m.group(1), 16), m.group(3)
            m = LABEL.match(body)
            if m:
                if not final:
                    sym[m.group(1)] = pc
                body = m.group(2)
            body = body.strip()
            if not body:
                continue
            if body.lower().startswith("org "):
                v = num(body[4:])
                if v is None:
                    raise AsmError("line %d: bad org" % no)
                pc = v
                continue
            names = sym
            if not final:                       # a label not seen yet stands for this address in pass 1
                names = dict(sym)
                for name in re.findall(r"[A-Za-z_.$][\w.$]*", body):
                    names.setdefault(name, pc)
            try:
                code = assemble_one(body, pc, ext_n > 0, names)
            except AsmError as e:
                raise AsmError("line %d: %s" % (no, e))
            chunks[pc] = code
            mn = body.split(None, 1)[0].lower()
            if ext_n:
                ext_n -= 1
            if mn in ("extr", "extpr", "extsr"):
                ext_n = Tok(split_ops(body.split(None, 1)[1])[-1]).imm()[0]
            pc += len(code)
    return chunks


# ------------------------------------------------------------------------------------------------ analysis
class Ext:
    """EXTP / EXTS / EXTR state along a straight run of instructions."""

    def __init__(self):
        self.kind, self.val, self.n = None, None, 0

    def step(self, ins):
        """Call before using ins; returns (page, seg, extr) that apply to it."""
        cur = (self.kind, self.val) if self.n > 0 else (None, None)
        if self.n > 0:
            self.n -= 1
        if ins.ext:
            self.kind, self.val, self.n = ins.ext
        k, v = cur
        page = v if k in ("extp", "extpr") else None
        seg = v if k in ("exts", "extsr") else None
        return page, seg, k in ("extr", "extpr", "extsr")


def phys_of(a16, prof, page=None, seg=None, dpp=None):
    """Physical address of a 16-bit data address; None when the page or segment sits in a register."""
    if isinstance(page, tuple) or isinstance(seg, tuple):
        return None
    if seg is not None:
        return seg << 16 | a16
    if page is not None:
        return page << 14 | (a16 & 0x3FFF)
    return (dpp or prof.dpp)[a16 >> 14] << 14 | (a16 & 0x3FFF)


def comment(ins, prof, state, labels=None):
    page, seg, extr = state
    notes = []
    for o in ins.ops:
        if o[0] == "mem":
            p = phys_of(o[1], prof, page, seg)
            notes.append(prof.describe(p) if p is not None else "page/segment in a register")
        elif o[0] == "far":
            f = prof.file_of(o[1] << 16 | o[2])
            if f is not None:
                notes.append((labels or {}).get(f) or "file 0x%05X" % f)
        elif o[0] == "code" and labels and o[1] in labels:
            notes.append(labels[o[1]])
    if ins.ext:
        notes.append("next %d" % ins.ext[2])
    if ins.mn == "db" and ins.note:
        notes.append(ins.note)
    return "; ".join(notes)


def listing_line(ins, prof, state, labels=None):
    txt = insn_text(ins, state[2])
    c = comment(ins, prof, state, labels)
    hx = " ".join("%02X" % x for x in ins.raw)
    return ("%05X  %-12s %-34s%s" % (ins.off, hx, txt, ("; " + c) if c else "")).rstrip()


def dis(img, start, end, prof):
    ext, off, out = Ext(), start, []
    while off < end:
        ins = decode(img, off)
        out.append(listing_line(ins, prof, ext.step(ins)))
        off += ins.size
    return out


def walk(img, entries, prof, follow_calls=False, limit=200000):
    """Instructions reached from entries along the flow. Returns ({offset: Insn}, labels, xrefs, errors)."""
    seen, labels, xrefs, errors = {}, {}, {}, []
    todo = list(entries)
    while todo and len(seen) < limit:
        off = todo.pop()
        if off & 1:                                                     # code sits on even addresses only
            errors.append(off)
            continue
        while 0 <= off < len(img) and off not in seen:
            ins = decode(img, off)
            seen[off] = ins
            if not ins.ok:
                errors.append(off)
                break
            t = ins.target(prof)
            if t is not None:
                xrefs.setdefault(t, []).append(off)
                if ins.flow == "call":
                    labels[t] = "sub_%05X" % t
                else:
                    labels.setdefault(t, "loc_%05X" % t)
                if ins.flow in ("jmp", "jcc") or (ins.flow == "call" and follow_calls):
                    todo.append(t)
            if ins.flow in ("jmp", "ret", "stop"):
                break
            off += ins.size
    return seen, labels, xrefs, errors


def vectors(img, prof):
    """Entry points from the trap and interrupt table at 0x0000-0x01FF (JMPS / JMPA / JMPR there)."""
    out = []
    for v in range(0, 0x200, 4):
        ins = decode(img, v)
        t = ins.target(prof)
        if ins.flow == "jmp" and t is not None:
            out.append(t)
    return out


def far_calls(img, prof, start=0x10000):
    """Targets of CALLS found by a linear pass outside the data ranges: entry points of most functions. Tables inside
    the program decode as instructions too, so a target counts only when its own flow meets no gap."""
    out, off = set(), start
    while off < len(img):
        if any(lo <= off < hi for lo, hi in prof.data):
            off = next(hi for lo, hi in prof.data if lo <= off < hi)
            continue
        ins = decode(img, off)
        if ins.mn == "calls":
            t = ins.target(prof)
            if t is not None and not t & 1 and t >= start and not any(lo <= t < hi for lo, hi in prof.data):
                out.add(t)
        off += ins.size
    return sorted(t for t in out if not walk(img, [t], prof)[3])


def check(img, start, end):
    """Disassemble and assemble back; returns (instructions, [(offset, text) that do not match])."""
    ext, off, n, bad = Ext(), start, 0, []
    while off < end:
        ins = decode(img, off)
        state = ext.step(ins)
        txt = insn_text(ins, state[2])
        try:
            again = assemble_one(txt, off, state[2])
        except AsmError as e:
            again = b"" + str(e).encode()
        if again != ins.raw:
            bad.append((off, txt))
        n += 1
        off += ins.size
    return n, bad


def xref(img, addr, prof, start=0, end=None):
    """Instructions that call or jump to addr (a file offset), address it as data (a physical or file address), as a
    register or a bit, or load a 16-bit constant that points to it through the DPPs. A linear pass: data in the image
    decodes too, so check each hit in its function."""
    end = len(img) if end is None else end
    ext, off, hits = Ext(), start, []
    while off < end:
        ins = decode(img, off)
        page, seg, extr = ext.step(ins)
        why = None
        if ins.ok:
            if ins.target(prof) == addr:
                why = ins.mn
            for o in ins.ops:
                if o[0] == "mem":
                    p = phys_of(o[1], prof, page, seg)
                    if p is not None and (p == addr or prof.file_of(p, len(img)) == addr):
                        why = "data"
                elif o[0] == "reg" and o[1] < 0xF0 and (0xF000 if extr else 0xFE00) + 2 * o[1] == addr & ~1:
                    why = "register"
                elif o[0] in ("bit", "boff") and bitword(o[1], extr) == addr & ~1:
                    why = "bit"
                elif o[0] == "imm" and o[2] == "16":                      # a 16-bit pointer to addr through the DPPs
                    p = phys_of(o[1], prof)
                    if p == addr or prof.file_of(p, len(img)) == addr:
                        why = why or "constant"
        if why:
            hits.append((ins, why, (page, seg, extr)))
        off += ins.size
    return hits


# ------------------------------------------------------------------------------------------------ command line
def _addr(s):
    v = num(s)
    if v is None:
        raise SystemExit("not an address: %r" % s)
    return v


def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    cmd, rest = argv[0], list(argv[1:])
    opt = {}
    for k in ("--profile", "--dpp", "-o", "--org"):
        if k in rest:
            i = rest.index(k)
            opt[k] = rest[i + 1]
            del rest[i:i + 2]
    if cmd == "asm":
        if not rest or "-o" not in opt:
            raise SystemExit("asm SOURCE -o OUT [--org ADDR]")
        with open(rest[0], encoding="utf-8") as f:
            chunks = assemble(f.read(), _addr(opt.get("--org", "0")))
        if not chunks:
            raise SystemExit("nothing to assemble")
        lo = min(chunks)
        hi = max(a + len(b) for a, b in chunks.items())
        buf = bytearray(b"\xff" * (hi - lo))
        for a, b in chunks.items():
            buf[a - lo:a - lo + len(b)] = b
        with open(opt["-o"], "wb") as f:
            f.write(buf)
        print("%s: 0x%05X-0x%05X, %d bytes" % (opt["-o"], lo, hi, len(buf)))
        return 0
    if not rest:
        raise SystemExit(__doc__)
    with open(rest[0], "rb") as f:
        img = f.read()
    prof = PROFILES[opt["--profile"]] if "--profile" in opt else detect(img)
    if "--dpp" in opt:
        prof = Profile(prof.key, prof.name, [_addr(x) for x in opt["--dpp"].split(",")], prof.ident, prof.ram,
                       prof.mirror)
    nums = [_addr(x) for x in rest[1:]]
    if cmd == "dis":
        start = nums[0] if nums else 0
        end = nums[1] if len(nums) > 1 else min(len(img), start + 0x40)
        print("; %s, DPP %s" % (prof.name, " ".join("0x%02X" % d for d in prof.dpp)))
        print("\n".join(dis(img, start, end, prof)))
        return 0
    if cmd == "func":
        seen, labels, xrefs, errors = walk(img, [nums[0]], prof)
        labels[nums[0]] = "sub_%05X" % nums[0]
        prev = None
        for off in sorted(seen):
            ins = seen[off]
            if prev is not None and off != prev:
                print()
            if off in labels:
                print("%s:" % labels[off])
            print(listing_line(ins, prof, (None, None, False), labels))
            prev = off + ins.size
        if errors:
            print("; no instruction at " + ", ".join("0x%05X" % e for e in errors))
        return 0
    if cmd == "funcs":
        seen, labels, xrefs, errors = walk(img, vectors(img, prof) + far_calls(img, prof), prof, follow_calls=True)
        subs = sorted(t for t, n in labels.items() if n.startswith("sub_"))
        for t in subs:
            print("0x%05X  %3d callers" % (t, sum(1 for s in xrefs.get(t, ()) if seen[s].flow == "call")))
        print("; %d functions, %d instructions reached, %d stops at no instruction" % (len(subs), len(seen), len(errors)))
        return 0
    if cmd == "xref":
        hits = xref(img, nums[0], prof, *(nums[1:3]))
        for ins, why, state in hits:
            print("%-9s %s" % (why, listing_line(ins, prof, state)))
        print("; %d hits" % len(hits))
        return 0
    if cmd == "check":
        start = nums[0] if nums else 0
        end = nums[1] if len(nums) > 1 else len(img)
        n, bad = check(img, start, end)
        for off, txt in bad[:20]:
            print("0x%05X  %s" % (off, txt))
        print("%d instructions in 0x%05X-0x%05X, %d do not assemble back" % (n, start, end, len(bad)))
        return 1 if bad else 0
    raise SystemExit(__doc__)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
