#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
"""
c166emu.py: emulator of the C166 core of the C167 for the code of the Siemens MS42 and MS43, on the decoder of c166.py.
Part of the MS4X repository. License: Apache-2.0 (LICENSE, NOTICE), credit: rudywolf, https://github.com/therudywolf/MS4X.

Runs code of an image instruction by instruction: every instruction of the C167 with the operation and the flags of the
Infineon Instruction Set Manual for the C166 Family V2.0, the general registers in internal RAM at CP, the registers
that code relies on (DPP0-DPP3, CSP, CP, SP, PSW, MDH, MDL, MDC, ZEROS, ONES, SYSCON), EXTP / EXTS / EXTR, the system
stack. The flash is read from the image and never written; RAM starts as zeros. No interrupts and no peripherals: a
peripheral register reads back what was written to it.

  python3 tools/c166emu.py call IMAGE ADDR [r12=0xF758 ...] [--near] [--steps N] [--trace]
  python3 tools/c166emu.py crc  IMAGE      both checksums computed by the program's own CRC routine

As a library:
  emu = Emu(img)                            # profile from the program ID, as in c166.py
  emu.r[12] = 0xF758                        # general registers (the bank at CP)
  emu.wr16(0xF756, 0x3643)                  # memory by physical address
  emu.call(0x75D8E)                         # a far function (CALLS ... RETS); near=True for CALLA / CALLR ... RET
"""
import os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import c166                                                             # noqa: E402

N, C, V, Z, E = 1, 2, 4, 8, 16                                          # PSW bits
SYS = 0xC000                                                            # system page: XRAM, CAN, ESFR, IRAM, SFR
RET_IP = 0xFFFE                                                         # return address that ends call()
RET_CSP = 0xFF
BYTE_OPS = {"addb", "addcb", "subb", "subcb", "cmpb", "andb", "orb", "xorb", "movb", "negb", "cplb"}


class Stop(Exception):
    """The emulator met something it cannot run (or was told to stop)."""


class _Regs:
    def __init__(self, emu):
        self.emu = emu

    def __getitem__(self, n):
        return self.emu.gpr(n)

    def __setitem__(self, n, v):
        self.emu.set_gpr(n, v)


class Emu:
    def __init__(self, img, prof=None, cp=0xFC00, sp=0xFA00):
        self.img = img
        self.prof = prof or c166.detect(img)
        self.sysmem = bytearray(0x4000)                                 # 0xC000-0xFFFF
        self.win = [(lo, hi, bytearray(hi - lo)) for lo, hi, _ in self.prof.ram]
        self.dpp = list(self.prof.dpp)
        self.cp, self.sp, self.psw, self.csp, self.ip = cp, sp, 0, 0, 0
        self.ext = None                                                 # (kind, value, count) of EXTP / EXTS / EXTR
        self.steps = 0
        self.code = {}                                                  # file offset -> Insn
        self.hooks = {}                                                 # file offset -> f(emu); True skips the instruction
        self.trace = None                                               # a list to collect (file offset, text)
        self.writes = None                                              # a list to collect (phys, size, value, file offset)
        self.cur = None
        self.r = _Regs(self)

    # ------------------------------------------------------------------ memory by physical address
    def _sfr_rd(self, p):
        w = p & ~1
        if w in (0xFF1C,):
            return 0
        if w == 0xFF1E:
            return 0xFF
        v = {0xFE10: self.cp, 0xFE12: self.sp, 0xFF10: self.psw, 0xFE08: self.csp}.get(w)
        if v is None and 0xFE00 <= w <= 0xFE06:
            v = self.dpp[(w - 0xFE00) >> 1]
        if v is None:
            return self.sysmem[p - SYS]
        return (v >> 8) & 0xFF if p & 1 else v & 0xFF

    def _sfr_wr(self, p, b):
        w = p & ~1
        if w in (0xFF1C, 0xFF1E, 0xFE08):                               # ZEROS, ONES, CSP: read only
            return
        hi = p & 1
        if w == 0xFE10:
            self.cp = (self.cp & (0x00FF if hi else 0xFF00)) | (b << 8 if hi else b)
        elif w == 0xFE12:
            self.sp = (self.sp & (0x00FF if hi else 0xFF00)) | (b << 8 if hi else b)
        elif w == 0xFF10:
            self.psw = (self.psw & (0x00FF if hi else 0xFF00)) | (b << 8 if hi else b)
        elif 0xFE00 <= w <= 0xFE06:
            i = (w - 0xFE00) >> 1
            self.dpp[i] = ((self.dpp[i] & (0x00FF if hi else 0xFF00)) | (b << 8 if hi else b)) & 0x3FF
        else:
            self.sysmem[p - SYS] = b

    def rd8(self, p):
        if SYS <= p <= 0xFFFF:
            if p >= 0xFE00:
                return self._sfr_rd(p)
            return self.sysmem[p - SYS]
        for lo, hi, m in self.win:
            if lo <= p < hi:
                return m[p - lo]
        f = self.prof.file_of(p, len(self.img))
        if f is None:
            raise Stop("read outside the memory map: 0x%06X" % p)
        return self.img[f]

    def wr8(self, p, b):
        b &= 0xFF
        if self.writes is not None:
            self.writes.append((p, 1, b, self.cur))
        if SYS <= p <= 0xFFFF:
            if p >= 0xFE00:
                self._sfr_wr(p, b)
            else:
                self.sysmem[p - SYS] = b
            return
        for lo, hi, m in self.win:
            if lo <= p < hi:
                m[p - lo] = b
                return
        raise Stop("write outside RAM: 0x%06X" % p)

    def rd16(self, p):
        if p & 1:
            raise Stop("word read at an odd address 0x%06X" % p)
        return self.rd8(p) | self.rd8(p + 1) << 8

    def wr16(self, p, v):
        if p & 1:
            raise Stop("word write at an odd address 0x%06X" % p)
        self.wr8(p, v & 0xFF)
        self.wr8(p + 1, (v >> 8) & 0xFF)

    # ------------------------------------------------------------------ registers
    def gpr(self, n):
        a = self.cp + 2 * n - SYS
        return self.sysmem[a] | self.sysmem[a + 1] << 8

    def set_gpr(self, n, v):
        a = self.cp + 2 * n - SYS
        self.sysmem[a] = v & 0xFF
        self.sysmem[a + 1] = (v >> 8) & 0xFF

    def gprb(self, n):
        return self.sysmem[self.cp + n - SYS]

    def set_gprb(self, n, v):
        self.sysmem[self.cp + n - SYS] = v & 0xFF

    @property
    def syscon(self):
        return self.rd16(0xFF12)

    # ------------------------------------------------------------------ addressing
    def data_phys(self, a):
        """Physical address of a 16-bit data address: DPP, or the page / segment of an EXTP / EXTS prefix."""
        x = self.ext
        if x and x[0] in ("extp", "extpr"):
            return x[1] << 14 | (a & 0x3FFF)
        if x and x[0] in ("exts", "extsr"):
            return x[1] << 16 | a
        return self.dpp[a >> 14] << 14 | (a & 0x3FFF)

    def _extr(self):
        return bool(self.ext) and self.ext[0] in ("extr", "extpr", "extsr")

    def reg_phys(self, r):
        return (0xF000 if self._extr() else 0xFE00) + 2 * r

    def bit_word(self, q):
        """('g', n) for a general register, else ('m', physical word address)."""
        if q >= 0xF0:
            return "g", q & 15
        if q >= 0x80:
            return "m", (0xF100 if self._extr() else 0xFF00) + 2 * (q - 0x80)
        return "m", 0xFD00 + 2 * q

    def get_bit(self, q, b):
        k, x = self.bit_word(q)
        return ((self.gpr(x) if k == "g" else self.rd16(x)) >> b) & 1

    def set_bit(self, q, b, v):
        k, x = self.bit_word(q)
        w = self.gpr(x) if k == "g" else self.rd16(x)
        w = (w | 1 << b) if v else (w & ~(1 << b))
        self.set_gpr(x, w) if k == "g" else self.wr16(x, w)

    def get(self, o, size):
        """Value of an operand (side effects of [Rw+] and [-Rw] included)."""
        t = o[0]
        if t == "r":
            return self.gpr(o[1])
        if t == "rb":
            return self.gprb(o[1])
        if t == "reg":
            r = o[1]
            if r >= 0xF0:
                return self.gprb(r & 15) if size == 1 else self.gpr(r & 15)
            p = self.reg_phys(r)
            return self.rd8(p) if size == 1 else self.rd16(p)
        if t == "imm":
            return o[1] & (0xFF if size == 1 else 0xFFFF)
        if t == "mem":
            p = self.data_phys(o[1])
        elif t == "ind":
            p = self.data_phys(self.gpr(o[1]))
        elif t == "inc":
            a = self.gpr(o[1])
            p = self.data_phys(a)
            v = self.rd8(p) if size == 1 else self.rd16(p)
            self.set_gpr(o[1], a + size)
            return v
        elif t == "dec":
            a = (self.gpr(o[1]) - size) & 0xFFFF
            self.set_gpr(o[1], a)
            p = self.data_phys(a)
        elif t == "idx":
            p = self.data_phys((self.gpr(o[1]) + o[2]) & 0xFFFF)
        else:
            raise Stop("no value for operand %r" % (o,))
        return self.rd8(p) if size == 1 else self.rd16(p)

    def put(self, o, size, v):
        t = o[0]
        v &= 0xFF if size == 1 else 0xFFFF
        if t == "r":
            self.set_gpr(o[1], v)
            return
        if t == "rb":
            self.set_gprb(o[1], v)
            return
        if t == "reg":
            r = o[1]
            if r >= 0xF0:
                self.set_gprb(r & 15, v) if size == 1 else self.set_gpr(r & 15, v)
                return
            p = self.reg_phys(r)
        elif t == "mem":
            p = self.data_phys(o[1])
        elif t == "ind":
            p = self.data_phys(self.gpr(o[1]))
        elif t == "inc":
            a = self.gpr(o[1])
            p = self.data_phys(a)
            self.wr8(p, v) if size == 1 else self.wr16(p, v)
            self.set_gpr(o[1], a + size)
            return
        elif t == "dec":
            a = (self.gpr(o[1]) - size) & 0xFFFF
            self.set_gpr(o[1], a)
            p = self.data_phys(a)
        elif t == "idx":
            p = self.data_phys((self.gpr(o[1]) + o[2]) & 0xFFFF)
        else:
            raise Stop("cannot write operand %r" % (o,))
        self.wr8(p, v) if size == 1 else self.wr16(p, v)

    # ------------------------------------------------------------------ flags and stack
    def flags(self, **kw):
        for name, bit in (("N", N), ("C", C), ("V", V), ("Z", Z), ("E", E)):
            if name in kw:
                self.psw = (self.psw | bit) if kw[name] else (self.psw & ~bit)

    def f(self, bit):
        return 1 if self.psw & bit else 0

    def cond(self, c):
        n, cy, v, z, e = self.f(N), self.f(C), self.f(V), self.f(Z), self.f(E)
        return (True, not z and not e, z, not z, v, not v, n, not n, cy, not cy,
                not (z or (n ^ v)), z or (n ^ v), n ^ v, not (n ^ v), not (z or cy), z or cy)[c]

    def push(self, v):
        self.sp = (self.sp - 2) & 0xFFFF
        self.wr16(self.sp, v)

    def pop(self):
        v = self.rd16(self.sp)
        self.sp = (self.sp + 2) & 0xFFFF
        return v

    def ezn(self, v, size):
        msb = 0x80 if size == 1 else 0x8000
        self.flags(E=v == msb, Z=v == 0, N=v & msb)

    # ------------------------------------------------------------------ execution
    def phys_of_file(self, f):
        """Physical address code at file offset f runs at: MS43 runs the flash above 0xFFFF at 0x80000 + f."""
        return f | 0x80000 if self.prof.mirror and f >= 0x10000 else f

    def fetch(self):
        f = self.prof.file_of(self.csp << 16 | self.ip, len(self.img))
        if f is None:
            raise Stop("code outside the flash: %02X:%04X" % (self.csp, self.ip))
        ins = self.code.get(f)
        if ins is None:
            ins = self.code[f] = c166.decode(self.img, f)
        return f, ins

    def step(self):
        f, ins = self.fetch()
        self.cur = f
        h = self.hooks.get(f)
        if h and h(self):                                               # the hook did the instruction itself
            return
        if self.trace is not None:
            self.trace.append((f, c166.insn_text(ins, self._extr())))
        nxt = (self.ip + ins.size) & 0xFFFF
        self.ip = nxt
        covered = self.ext                                              # EXTP / EXTS / EXTR still running
        self.exec(ins, nxt)
        if covered is not None and not ins.ext:
            k, v, n = covered
            self.ext = (k, v, n - 1) if n > 1 else None
        self.steps += 1

    def exec(self, ins, nxt):
        mn, o = ins.mn, ins.ops
        if mn == "db":
            raise Stop("no instruction at 0x%05X" % ins.off)
        size = 1 if mn in BYTE_OPS else 2
        if mn in ("movbz", "movbs"):
            v = self.get(o[1], 1)
            w = (v | 0xFF00) if (mn == "movbs" and v & 0x80) else v
            self.put(o[0], 2, w)
            self.flags(E=0, Z=v == 0, N=(mn == "movbs" and v & 0x80))
            return
        base = mn[:-1] if size == 1 else mn
        if base in ("add", "addc", "sub", "subc", "cmp"):
            a, b = self.get(o[0], size), self.get(o[1], size)
            cin = self.f(C) if base in ("addc", "subc") else 0
            bits = 8 * size
            mask, msb = (1 << bits) - 1, 1 << (bits - 1)
            if base.startswith("add"):
                r = a + b + cin
                cy, ov = r > mask, (~(a ^ b) & (a ^ r) & msb) != 0
            else:
                r = a - b - cin
                cy, ov = r < 0, ((a ^ b) & (a ^ r) & msb) != 0
            r &= mask
            z = r == 0 and (self.f(Z) if base in ("addc", "subc") else True)
            self.flags(E=b == msb, Z=z, V=ov, C=cy, N=r & msb)
            if base != "cmp":
                self.put(o[0], size, r)
            return
        if base in ("and", "or", "xor"):
            a, b = self.get(o[0], size), self.get(o[1], size)
            r = a & b if base == "and" else (a | b if base == "or" else a ^ b)
            msb = 0x80 if size == 1 else 0x8000
            self.flags(E=b == msb, Z=r == 0, V=0, C=0, N=r & msb)
            self.put(o[0], size, r)
            return
        if base in ("mov",):
            v = self.get(o[1], size)
            self.ezn(v, size)
            self.put(o[0], size, v)
            return
        if base in ("cmpi1", "cmpi2", "cmpd1", "cmpd2"):
            a, b = self.get(o[0], 2), self.get(o[1], 2)
            r = a - b
            self.flags(E=b == 0x8000, Z=(r & 0xFFFF) == 0, V=((a ^ b) & (a ^ r) & 0x8000) != 0, C=r < 0, N=r & 0x8000)
            d = {"cmpi1": 1, "cmpi2": 2, "cmpd1": -1, "cmpd2": -2}[base]
            self.put(o[0], 2, a + d)
            return
        if base in ("neg", "cpl"):
            a = self.get(o[0], size)
            msb, mask = (0x80, 0xFF) if size == 1 else (0x8000, 0xFFFF)
            if base == "neg":
                r = (-a) & mask
                self.flags(E=a == msb, Z=r == 0, V=a == msb, C=a != 0, N=r & msb)
            else:
                r = ~a & mask
                self.flags(E=a == msb, Z=r == 0, V=0, C=0, N=r & msb)
            self.put(o[0], size, r)
            return
        if mn in ("mul", "mulu"):
            a, b = self.gpr(o[0][1]), self.gpr(o[1][1])
            if mn == "mul":
                a, b = a - 0x10000 if a & 0x8000 else a, b - 0x10000 if b & 0x8000 else b
                r = a * b
                ov = not -0x8000 <= r <= 0x7FFF
            else:
                r = a * b
                ov = r > 0xFFFF
            r &= 0xFFFFFFFF
            self.wr16(0xFE0C, r >> 16)
            self.wr16(0xFE0E, r & 0xFFFF)
            self.wr16(0xFF0E, self.rd16(0xFF0E) | 0x10)                 # MDC.MDRIU
            self.flags(E=0, Z=r == 0, V=ov, C=0, N=r & 0x80000000)
            return
        if mn in ("div", "divu", "divl", "divlu"):
            d = self.gpr(o[0][1])
            if mn in ("div", "divu"):
                x = self.rd16(0xFE0E)
                xs = x - 0x10000 if mn == "div" and x & 0x8000 else x
            else:
                x = self.rd16(0xFE0C) << 16 | self.rd16(0xFE0E)
                xs = x - 0x100000000 if mn == "divl" and x & 0x80000000 else x
            ds = d - 0x10000 if mn in ("div", "divl") and d & 0x8000 else d
            self.wr16(0xFF0E, self.rd16(0xFF0E) | 0x10)
            if ds == 0:
                self.flags(E=0, Z=0, V=1, C=0, N=0)
                return
            q = abs(xs) // abs(ds) * (1 if (xs < 0) == (ds < 0) else -1)
            rem = xs - q * ds
            if mn in ("div", "divl"):
                ov = not -0x8000 <= q <= 0x7FFF
            else:
                ov = q > 0xFFFF
            q &= 0xFFFF
            self.wr16(0xFE0E, q)
            self.wr16(0xFE0C, rem & 0xFFFF)
            self.flags(E=0, Z=q == 0, V=ov, C=0, N=q & 0x8000)
            return
        if mn == "prior":
            v = self.gpr(o[1][1])
            n = 0
            t = v
            while v and not t & 0x8000 and n != 15:
                t = (t << 1) & 0xFFFF
                n += 1
            self.set_gpr(o[0][1], n)
            self.flags(E=0, Z=v == 0, V=0, C=0, N=0)
            return
        if mn in ("shl", "shr", "ashr", "rol", "ror"):
            v = self.gpr(o[0][1])
            cnt = (o[1][1] if o[1][0] == "imm" else self.gpr(o[1][1])) & 15
            cy = ov = 0
            for _ in range(cnt):
                if mn == "shl":
                    cy, v = v >> 15 & 1, (v << 1) & 0xFFFF
                elif mn == "rol":
                    cy = v >> 15 & 1
                    v = ((v << 1) | cy) & 0xFFFF
                else:
                    ov |= cy
                    cy = v & 1
                    if mn == "shr":
                        v >>= 1
                    elif mn == "ashr":
                        v = (v >> 1) | (v & 0x8000)
                    else:
                        v = (v >> 1) | (cy << 15)
            self.set_gpr(o[0][1], v)
            self.flags(E=0, Z=v == 0, V=ov if mn in ("shr", "ashr", "ror") else 0, C=cy, N=v & 0x8000)
            return
        if mn in ("bset", "bclr"):
            q, b = o[0][1], o[0][2]
            old = self.get_bit(q, b)
            self.set_bit(q, b, mn == "bset")
            self.flags(E=0, Z=not old, V=0, C=0, N=old)
            return
        if mn in ("bmov", "bmovn", "band", "bor", "bxor", "bcmp"):
            (_, zq, zb), (_, qq, qb) = o[0], o[1]
            src, dst = self.get_bit(qq, qb), self.get_bit(zq, zb)
            if mn in ("bmov", "bmovn"):
                self.set_bit(zq, zb, src if mn == "bmov" else 1 - src)
                self.flags(E=0, Z=not src, V=0, C=0, N=src)
                return
            if mn != "bcmp":
                self.set_bit(zq, zb, {"band": dst & src, "bor": dst | src, "bxor": dst ^ src}[mn])
            self.flags(E=0, Z=not (dst | src), V=dst | src, C=dst & src, N=dst ^ src)
            return
        if mn in ("bfldl", "bfldh"):
            q, mask, data = o[0][1], o[1][1], o[2][1]
            k, x = self.bit_word(q)
            w = self.gpr(x) if k == "g" else self.rd16(x)
            sh = 0 if mn == "bfldl" else 8
            w = (w & ~(mask << sh)) | (data << sh)
            w &= 0xFFFF
            self.set_gpr(x, w) if k == "g" else self.wr16(x, w)
            self.flags(E=0, Z=w == 0, V=0, C=0, N=w & 0x8000)
            return
        if mn in ("jb", "jnb", "jbc", "jnbs"):
            q, b = o[0][1], o[0][2]
            v = self.get_bit(q, b)
            take = v if mn in ("jb", "jbc") else not v
            if mn == "jbc" and v:
                self.set_bit(q, b, 0)
            if mn == "jnbs" and not v:
                self.set_bit(q, b, 1)
            if mn in ("jbc", "jnbs"):
                self.flags(E=0, Z=not v, V=0, C=0, N=v)
            if take:
                self.ip = o[1][1] & 0xFFFF
            return
        if mn in ("jmpr", "jmpa"):
            if self.cond(o[0][1]):
                self.ip = o[1][1] & 0xFFFF
            return
        if mn == "jmpi":
            if self.cond(o[0][1]):
                self.ip = self.gpr(o[1][1])
            return
        if mn == "jmps":
            self.csp, self.ip = o[0][1], o[0][2]
            return
        if mn in ("calla", "calli"):
            if self.cond(o[0][1]):
                self.push(nxt)
                self.ip = (o[1][1] & 0xFFFF) if mn == "calla" else self.gpr(o[1][1])
            return
        if mn == "callr":
            self.push(nxt)
            self.ip = o[0][1] & 0xFFFF
            return
        if mn == "calls":
            self.push(self.csp)
            self.push(nxt)
            self.csp, self.ip = o[0][1], o[0][2]
            return
        if mn == "pcall":
            v = self.get(o[0], 2)
            self.push(v)
            self.push(nxt)
            self.ezn(v, 2)
            self.ip = o[1][1] & 0xFFFF
            return
        if mn == "ret":
            self.ip = self.pop()
            return
        if mn == "rets":
            self.ip = self.pop()
            self.csp = self.pop() & 0xFF
            return
        if mn == "retp":
            self.ip = self.pop()
            v = self.pop()
            self.put(o[0], 2, v)
            self.ezn(v, 2)
            return
        if mn == "reti":
            self.ip = self.pop()
            if not self.syscon & 0x0800:
                self.csp = self.pop() & 0xFF
            self.psw = self.pop()
            return
        if mn == "trap":
            self.push(self.psw)
            if not self.syscon & 0x0800:
                self.push(self.csp)
                self.csp = 0
            self.push(nxt)
            self.ip = o[0][1] * 4
            return
        if mn == "push":
            v = self.get(o[0], 2)
            self.push(v)
            self.ezn(v, 2)
            return
        if mn == "pop":
            v = self.pop()
            self.put(o[0], 2, v)
            self.ezn(v, 2)
            return
        if mn == "scxt":
            v = self.get(o[1], 2)
            self.push(self.get(o[0], 2))
            self.put(o[0], 2, v)
            return
        if ins.ext:
            k, v, n = ins.ext
            if isinstance(v, tuple):                                    # EXTP / EXTS by register
                v = self.gpr(v[1]) & (0x3FF if k in ("extp", "extpr") else 0xFF)
            self.ext = (k, v, n) if k != "atomic" else None
            return
        if mn in ("nop", "diswdt", "einit", "srvwdt"):
            return
        raise Stop("%s at 0x%05X: the processor stops or resets here" % (mn, ins.off))

    # ------------------------------------------------------------------ running
    def run(self, max_steps=5000000, until=None):
        """Steps until (csp, ip) == until, or raises Stop."""
        for _ in range(max_steps):
            if until is not None and (self.csp, self.ip) == until:
                return
            self.step()
        raise Stop("no end after %d instructions" % max_steps)

    def call(self, target, near=False, max_steps=5000000):
        """Runs the function at a file offset (or (segment, offset)) until it returns; returns the instructions run."""
        seg, ip = target if isinstance(target, tuple) else divmod(self.phys_of_file(target), 0x10000)
        start = self.steps
        if near:
            self.push(RET_IP)
            self.csp, self.ip = seg, ip
            self.run(max_steps, (seg, RET_IP))
        else:
            self.push(RET_CSP)
            self.push(RET_IP)
            self.csp, self.ip = seg, ip
            self.run(max_steps, (RET_CSP, RET_IP))
        return self.steps - start


# ------------------------------------------------------------------------------------------------ checksums
# The CRC-16 routine of each program (r12 -> far pointer to the next byte, r13 -> CRC, r14 = byte count; a background
# task feeds it the blocks of a descriptor: sum word, block count, then [start, end] as 32-bit words, end included)
# and its descriptors. The task starts each CRC with two ASCII bytes of an identification string: MS42 reads them at
# a fixed place (code 0x1C320 and 0x1C226), MS43 through a far pointer (code 0x6356C and 0x6345C).
CRC = {"ms42": (0x75D8E, ((0x4FEE0, ("at", 0x4800C)), (0x50306, ("at", 0x50032)))),
       "ms43": (0x63642, ((0x73FE0, ("ptr", 0x6ED5A)), (0x6FDE0, ("ptr", 0x6ED42))))}


def crc_init(img, prof, how):
    kind, at = how
    if kind == "ptr":
        at = prof.file_of(int.from_bytes(img[at:at + 4], "little"), len(img))
    return img[at] | img[at + 1] << 8


def program_crc(img, prof=None, only=None):
    """Runs the program's own CRC routine over the blocks of its descriptors (or of the one at `only`).
    Returns [(descriptor, stored sum, computed sum, instructions run)]."""
    prof = prof or c166.detect(img)
    if prof.key not in CRC:
        raise Stop("no CRC routine known for %s" % prof.name)
    routine, descs = CRC[prof.key]
    out = []
    for desc, how in descs:
        if only is not None and desc != only:
            continue
        emu = Emu(img, prof)
        stored = img[desc] | img[desc + 1] << 8
        emu.wr16(0xF756, crc_init(img, prof, how))
        for i in range(img[desc + 2]):
            lo = int.from_bytes(img[desc + 4 + 8 * i:desc + 8 + 8 * i], "little")
            hi = int.from_bytes(img[desc + 8 + 8 * i:desc + 12 + 8 * i], "little")
            emu.wr16(0xF760, lo & 0xFFFF)
            emu.wr16(0xF762, lo >> 16)
            left = hi - lo + 1
            while left:
                k = min(left, 0x7FF0)
                emu.r[12], emu.r[13], emu.r[14] = 0xF760, 0xF756, k
                emu.call(routine)
                left -= k
        out.append((desc, stored, emu.rd16(0xF756), emu.steps))
    return out


def _num(s):
    v = c166.num(s)
    if v is None:
        raise SystemExit("not a number: %r" % s)
    return v


def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    cmd, rest = argv[0], list(argv[1:])
    with open(rest[0], "rb") as f:
        img = f.read()
    if cmd == "crc":
        bad = 0
        for desc, stored, got, n in program_crc(img):
            print("descriptor 0x%05X: stored 0x%04X, computed by the program's own routine 0x%04X (%d instructions)%s"
                  % (desc, stored, got, n, "" if stored == got else "  DIFFERENT"))
            bad += stored != got
        return 1 if bad else 0
    if cmd == "call":
        emu = Emu(img)
        steps, near, trace = 5000000, "--near" in rest, "--trace" in rest
        if "--steps" in rest:
            steps = _num(rest[rest.index("--steps") + 1])
        for a in rest[2:]:
            if "=" in a:
                k, v = a.split("=", 1)
                if k.lower().startswith("r") and k[1:].isdigit():
                    emu.r[int(k[1:])] = _num(v)
                else:
                    emu.wr16(_num(k), _num(v))
        if trace:
            emu.trace = []
        try:
            n = emu.call(_num(rest[1]), near=near, max_steps=steps)
            print("returned after %d instructions" % n)
        except Stop as e:
            print("stopped: %s (after %d instructions)" % (e, emu.steps))
        if trace:
            for f, t in emu.trace[-200:]:
                print("%05X  %s" % (f, t))
        print("r0-r15: " + " ".join("%04X" % emu.r[i] for i in range(16)))
        print("PSW %04X  MDH %04X  MDL %04X  SP %04X" % (emu.psw, emu.rd16(0xFE0C), emu.rd16(0xFE0E), emu.sp))
        return 0
    raise SystemExit(__doc__)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
