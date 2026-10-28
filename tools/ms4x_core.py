#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
"""
ms4x_core.py: what is in an MS42 0110C6 or MS43 430069 image, read before anything is written to it.
Part of the MS4X repository. License: Apache-2.0 (LICENSE, NOTICE), credit: rudywolf, https://github.com/therudywolf/MS4X.

  python3 tools/ms4x_core.py info IMAGE [--patchlist XDF ...] [--stock IMAGE] [--json]

info only reads. It prints:
  - the program (0110C6 or 430069) and the labels of its program and calibration parts;
  - both checksums computed by the program's own CRC routine (c166emu.py), next to the stored ones;
  - on the 430069 also the two 32-bit sums its background task keeps (SUM32), next to the stored ones;
  - whether the program part (the blocks of the program checksum) is the stock one;
  - the free area of the stock program, where patches put their code, and what occupies it;
  - with --patchlist: every patch of a TunerPro patchlist (XDFPATCH) as applied, not applied, partly applied or
    changed otherwise, and the patches of the list that share bytes;
  - with --stock: the ranges from 0x10000 on (calibration left out) where the image differs from a stock image
    of the same program, and which patch of the list explains each.

The patch bytes come from the XDF the user gives; this repository holds no copy of any patchlist.
"""
import hashlib, json, os, sys
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import c166                                                             # noqa: E402
import c166emu                                                          # noqa: E402

# Facts of the stock programs: SHA-256 over the blocks of the program checksum (the same in all 16 images of 0110C6
# and all 18 of 430069 of ms4x-net), the labels, the free area of the stock program.
PROGRAMS = {
    "ms42": dict(program_sha="cee8f0250a6f746e23f6c6ba7e74721d3fd2f41bdf7a54a0bd306917bd75042f", labels=(("program", 0x5002E, 50), ("calibration", 0x48000, 8)),
                 free=(0x60C44, 0x70000)),
    "ms43": dict(program_sha="bb63da0e7ee2baf25aad453800c4431c4132657f7758981ff9df9721918199ed", labels=(("program", 0x6FFB2, 46), ("calibration", 0x70000, 8)),
                 free=(0x4A8CC, 0x50000)),
}


# The two 32-bit sums of the 430069 besides its CRC-16s: a background task (code 0x5FBE0-0x5FD58, summing helper 0x5FD7C)
# adds the 16-bit words of two ranges to a seed and compares with the stored word; a mismatch sets bit 0xFD7E.8 and
# registers fault 8 (calls 0x61192), the calibration one only unless the byte 0x70E07 is 0xA5. Per sum: where the
# stored value is, where the seed is, where the two [start, end) far-pointer pairs are (all in the image itself).
SUM32 = {"ms43": ((0x6FDAE, 0x6FDB2, 0x6FDBE), (0x72FFC, 0x6FDB8, 0x6FDCE))}


def u32(img, at):
    return int.from_bytes(img[at:at + 4], "little")


def sums32(img, prof):
    """[(stored at, stored, computed, [(start, end), ...])] of the 32-bit sums the program keeps, if it keeps any."""
    out = []
    for stored_at, seed_at, ptr_at in SUM32.get(prof.key, ()):
        ranges = [(prof.file_of(u32(img, ptr_at + 8 * k), len(img)), prof.file_of(u32(img, ptr_at + 8 * k + 4), len(img)))
                  for k in range(2)]
        s = u32(img, seed_at)
        for a, z in ranges:
            s += sum(int.from_bytes(img[i:i + 2], "little") for i in range(a, z, 2))
        out.append((stored_at, u32(img, stored_at), s & 0xFFFFFFFF, ranges))
    return out


def blocks(img, prof, desc):
    """File ranges [start, end] of a checksum descriptor (sum word, block count, then 32-bit start / end pairs)."""
    out = []
    for i in range(img[desc + 2]):
        lo = int.from_bytes(img[desc + 4 + 8 * i:desc + 8 + 8 * i], "little")
        hi = int.from_bytes(img[desc + 8 + 8 * i:desc + 12 + 8 * i], "little")
        a, b = prof.file_of(lo, len(img)), prof.file_of(hi, len(img))
        if a is None or b is None or b < a:
            raise ValueError("descriptor 0x%05X: block %d is outside the image" % (desc, i))
        out.append((a, b))
    return out


def program_sha(img, prof):
    desc = c166emu.CRC[prof.key][1][1][0]
    return hashlib.sha256(b"".join(img[a:b + 1] for a, b in blocks(img, prof, desc))).hexdigest()


def label(img, at, n):
    s = img[at:at + n]
    return "".join(chr(c) if 32 <= c < 127 else "." for c in s)


def runs(img, lo, hi, empty=0xFF):
    """Ranges [start, end) in [lo, hi) whose bytes are not `empty`."""
    out, a = [], None
    for i in range(lo, hi):
        used = img[i] != empty
        if used and a is None:
            a = i
        elif not used and a is not None:
            out.append((a, i))
            a = None
    if a is not None:
        out.append((a, hi))
    return out


# ------------------------------------------------------------------------------------------------ patchlists
def _int(s):
    return int(s, 16) if s.lower().startswith("0x") else int(s)


def read_patchlist(path):
    """Patches of a TunerPro XDF: [{title, entries: [{name, at, patch, base}]}]; addresses are file offsets."""
    root = ET.parse(path).getroot()
    off, sub = 0, False
    bo = root.find("XDFHEADER/BASEOFFSET")
    if bo is not None:
        off, sub = _int(bo.get("offset", "0")), bo.get("subtract", "0") == "1"
    out = []
    for p in root.iter("XDFPATCH"):
        title = (p.findtext("title") or "").strip() or p.get("uniqueid", "?")
        entries = []
        for e in p.iter("XDFPATCHENTRY"):
            at = _int(e.get("address", "0"))
            at = at - off if sub else at + off
            patch = bytes.fromhex(e.get("patchdata", ""))
            base = bytes.fromhex(e.get("basedata", "")) if e.get("basedata") else None
            n = _int(e.get("datasize", "0")) or len(patch)
            entries.append(dict(name=e.get("name", ""), at=at, size=n, patch=patch[:n], base=base[:n] if base else None))
        out.append(dict(title=title, entries=entries))
    return out


def patch_state(img, patch):
    """'applied', 'not applied', 'partly applied' or 'changed otherwise', with the entries that decide it."""
    states = []
    for e in patch["entries"]:
        cur = img[e["at"]:e["at"] + e["size"]]
        if len(cur) < e["size"]:
            states.append("outside")
        elif cur == e["patch"]:
            states.append("patch")
        elif e["base"] is None or cur == e["base"]:
            states.append("base")
        elif set(cur) == {0xFF}:
            states.append("empty")                                      # base data of another patch, place still free
        else:
            states.append("other")
    if "outside" in states:
        return "outside the image", states
    if all(s == "patch" for s in states):
        return "applied", states
    if "other" in states:
        return "changed otherwise", states
    if all(s in ("base", "empty") for s in states):
        return "not applied" if "empty" not in states else "not applied, expects another patch first", states
    return "partly applied", states


def overlaps(patches):
    """Pairs of patches whose entries share bytes: [(title a, title b, [(start, end)])]."""
    spans = [(p["title"], e["at"], e["at"] + e["size"]) for p in patches for e in p["entries"]]
    out = {}
    for i, (ta, a0, a1) in enumerate(spans):
        for tb, b0, b1 in spans[i + 1:]:
            if ta != tb and a0 < b1 and b0 < a1:
                out.setdefault(tuple(sorted((ta, tb))), []).append((max(a0, b0), min(a1, b1)))
    return [(a, b, r) for (a, b), r in sorted(out.items())]


def explain(lo, hi, patches, img, prof=None):
    """What covers bytes of [lo, hi): the entries of patches whose bytes are there, the stored checksums."""
    out = []
    for p in patches:
        for e in p["entries"]:
            a, b = e["at"], e["at"] + e["size"]
            if a < hi and lo < b and img[a:b] == e["patch"]:
                out.append("%s (%s)" % (p["title"], e["name"]) if len(p["entries"]) > 1 else p["title"])
    if prof is not None and prof.key in c166emu.CRC:
        for desc, _ in c166emu.CRC[prof.key][1]:
            if desc < hi and lo < desc + 2:
                out.append("stored checksum 0x%05X" % desc)
    return out


def merge(ranges, gap=16):
    """Ranges [start, end) with gaps of up to `gap` bytes joined."""
    out = []
    for a, b in ranges:
        if out and a - out[-1][1] <= gap:
            out[-1] = (out[-1][0], b)
        else:
            out.append((a, b))
    return out


def diff_ranges(img, stock, skip, start=0x10000, gap=16):
    out, a, last = [], None, None
    for i in range(start, min(len(img), len(stock))):
        if any(lo <= i < hi for lo, hi in skip) or img[i] == stock[i]:
            continue
        if a is not None and i - last <= gap:
            last = i
            continue
        if a is not None:
            out.append((a, last + 1))
        a = last = i
    if a is not None:
        out.append((a, last + 1))
    return out


# ------------------------------------------------------------------------------------------------ info
def info(img, patchlists=(), stock=None, crc=True):
    prof = c166.detect(img)
    if prof.key not in PROGRAMS:
        raise SystemExit("not an image of 0110C6 or 430069 (no program label found)")
    known = PROGRAMS[prof.key]
    out = dict(program=prof.name, size=len(img),
               labels={k: label(img, at, n) for k, at, n in known["labels"]})
    sha = program_sha(img, prof)
    out["program_part"] = dict(sha256=sha, stock=sha == known["program_sha"])
    if crc:
        out["checksums"] = [dict(descriptor=d, stored=s, computed=c) for d, s, c, _ in c166emu.program_crc(img, prof)]
    out["sums32"] = [dict(at=a, stored=s, computed=c, ranges=[dict(start=x, end=y) for x, y in r]) for a, s, c, r in sums32(img, prof)]
    patches = [p for path in patchlists for p in read_patchlist(path)]
    if patches:
        out["patches"] = []
        for p in patches:
            st, states = patch_state(img, p)
            out["patches"].append(dict(title=p["title"], state=st,
                                       entries=[dict(name=e["name"], at=e["at"], size=e["size"], state=s)
                                                for e, s in zip(p["entries"], states)]))
        out["overlaps"] = [dict(a=a, b=b, ranges=r) for a, b, r in overlaps(patches)]
    lo, hi = known["free"]
    out["free_area"] = dict(start=lo, end=hi, bytes_used=sum(b - a for a, b in runs(img, lo, hi)),
                            used=[dict(start=a, end=b, by=explain(a, b, patches, img, prof))
                                  for a, b in merge(runs(img, lo, hi))])
    if stock is not None:
        sprof = c166.detect(stock)
        if sprof.key != prof.key or program_sha(stock, sprof) != known["program_sha"]:
            raise SystemExit("--stock: not a stock image of the same program")
        out["against_stock"] = [dict(start=a, end=b, by=explain(a, b, patches, img, prof))
                                for a, b in diff_ranges(img, stock, prof.data)]
    return out


def show(r):
    w = print
    w("program        %s, %d bytes" % (r["program"], r["size"]))
    w("labels         " + ", ".join("%s %s" % (k, v) for k, v in r["labels"].items()))
    pp = r["program_part"]
    w("program part   %s (SHA-256 of the program checksum blocks %s...)"
      % ("stock" if pp["stock"] else "NOT the stock program", pp["sha256"][:16]))
    for c in r.get("checksums", ()):
        ok = c["stored"] == c["computed"]
        w("checksum       0x%05X stored 0x%04X, the program's own routine gives 0x%04X%s"
          % (c["descriptor"], c["stored"], c["computed"], "" if ok else "  DIFFERENT: fix it before flashing"))
    for c in r.get("sums32", ()):
        ok = c["stored"] == c["computed"]
        w("sum32          0x%05X stored 0x%08X, the seed plus the words of %s gives 0x%08X%s"
          % (c["at"], c["stored"], ", ".join("0x%05X-0x%05X" % (x["start"], x["end"] - 1) for x in c["ranges"]), c["computed"],
             "" if ok else "  DIFFERENT: fix it before flashing"))
    fa = r["free_area"]
    w("free area      0x%05X-0x%05X: %s"
      % (fa["start"], fa["end"] - 1, "empty" if not fa["used"] else
         "%d bytes used" % fa["bytes_used"]))
    for u in fa["used"]:
        w("  0x%05X-0x%05X  %s" % (u["start"], u["end"] - 1, ", ".join(u["by"]) or "not from the patchlist given"))
    if "patches" in r:
        w("patches        %d in the list (applied = the bytes it writes are there; a patch that writes stock bytes back"
          % len(r["patches"]))
        w("               shows as applied on a stock image):")
        for p in r["patches"]:
            w("  %-40s %s" % (p["state"], p["title"]))
            if p["state"] in ("partly applied", "changed otherwise"):
                for e in p["entries"]:
                    w("      0x%05X +%-4d %-8s %s" % (e["at"], e["size"], e["state"], e["name"]))
        for o in r["overlaps"]:
            w("  shared bytes: %s / %s at %s" % (o["a"], o["b"], ", ".join("0x%05X-0x%05X" % (a, b - 1) for a, b in o["ranges"][:4])))
    if "against_stock" in r:
        w("against stock  %d ranges differ outside the calibration%s" % (len(r["against_stock"]), ":" if r["against_stock"] else ""))
        for d in r["against_stock"]:
            w("  0x%05X-0x%05X  %s" % (d["start"], d["end"] - 1, ", ".join(d["by"]) or "not from the patchlist given"))


def main(argv):
    if not argv or argv[0] in ("-h", "--help") or argv[0] != "info" or len(argv) < 2:
        print(__doc__)
        return 0 if argv and argv[0] in ("-h", "--help") else 2
    rest = argv[1:]
    patchlists, stock, as_json = [], None, "--json" in rest
    i = 0
    args = []
    while i < len(rest):
        if rest[i] == "--patchlist":
            patchlists.append(rest[i + 1])
            i += 2
        elif rest[i] == "--stock":
            with open(rest[i + 1], "rb") as f:
                stock = f.read()
            i += 2
        elif rest[i] == "--json":
            i += 1
        else:
            args.append(rest[i])
            i += 1
    with open(args[0], "rb") as f:
        img = f.read()
    r = info(img, patchlists, stock)
    if as_json:
        print(json.dumps(r, indent=1))
    else:
        show(r)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
