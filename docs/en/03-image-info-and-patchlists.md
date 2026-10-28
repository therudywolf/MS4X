# 03. What is in an image, and the community patchlists

[`tools/ms4x_core.py`](../../tools/ms4x_core.py) `info` reads an MS42 0110C6 or MS43 430069 image before anything is written to it. It changes nothing.

```
python3 tools/ms4x_core.py info IMAGE [--patchlist PATCHLIST.xdf ...] [--stock STOCK.bin] [--json]
```

## What it reports

From the stock MS43 430069:

```
program        Siemens MS43 430069, 524288 bytes
labels         program 432900104300696577355117--11143053690111143053, calibration C769Y548
program part   stock (SHA-256 of the program checksum blocks bb63da0e7ee2baf2...)
checksum       0x73FE0 stored 0xD37E, the program's own routine gives 0xD37E
checksum       0x6FDE0 stored 0x727E, the program's own routine gives 0x727E
sum32          0x6FDAE stored 0xB3DAAD17, the seed plus the words of 0x50000-0x53BF7, 0x6E876-0x6E877 gives 0xB3DAAD17
sum32          0x72FFC stored 0xA61EB8D5, the seed plus the words of 0x712C6-0x71315, 0x7EB94-0x7EE15 gives 0xA61EB8D5
free area      0x4A8CC-0x4FFFF: empty
```

- **Program and labels.** The program by its label, the label of the program part (MS42 0x5002E, MS43 0x6FFB2) and the first characters of the calibration (MS42 0x48000, MS43 0x70000).
- **Program part.** SHA-256 over the blocks of the program checksum, the bytes the ECU itself checks. It is the same in all 16 stock images of 0110C6 and in all 18 of 430069 of ms4x-net, so "stock" here means: not one byte of the checked program changed.
- **Checksums.** Both sums computed by the program's own CRC routine in the emulator (document 02), next to the stored ones. A sum that differs has to be fixed before flashing (most flashers do it).
- **The two 32-bit sums of the 430069.** Besides the CRC-16s the MS43 keeps two additive sums (see Findings below): one over the program, stored at 0x6FDAE, one over two pieces of the calibration, stored at 0x72FFC. `info` computes both from the descriptors in the image and shows them next to the stored ones. Whether your flasher recomputes them is worth checking here: the ECU does, in the background.
- **Free area.** The part of the program the stock code leaves empty and the patches use for their code: MS42 0x60C44-0x6FFFF, MS43 0x4A8CC-0x4FFFF, both outside the program checksum. Every used range is listed with the patch whose bytes are there.
- **`--patchlist`.** Every patch of a TunerPro patchlist (`XDFPATCH` entries) is shown as:

| State | Meaning |
|---|---|
| applied | every entry holds the bytes the patch writes |
| not applied | every entry holds its base data |
| not applied, expects another patch first | an entry is still empty (0xFF) while its base data are the bytes of another patch |
| partly applied | some entries hold the patch, the others their base data |
| changed otherwise | an entry holds neither: another patch or other code is there |

  A patch that writes stock bytes back, for example one that removes an older patch, shows as applied on a stock image. Patches of the list that share bytes are listed too.
- **`--stock`.** The ranges from 0x10000 on, calibration left out, where the image differs from a stock image of the same program, each with the patch entry whose bytes are there or the stored checksum it is.

The patch bytes come from the patchlist file you give; this repository holds no copy of any patchlist.

## A dump called stock may not be

A dump read from a car and kept as the original can already carry patches. With the patchlist and a stock image `info` shows which ones, entry by entry, and whatever is left over. Check the program part before building anything on a dump.

## Patches that share bytes

In the community patchlists MS42 v1.7.1 and MS43 v2.9.2 these pairs share bytes:

| Program | Patches | Shared |
|---|---|---|
| 0110C6 | Custom CAN - OLM Boost Gauge and M Cluster LED Support | 0x60D4A-0x60D53: the first expects the second applied |
| 0110C6 | M3 and M5 Cluster LED Mod Default Values | data 0x4F860-0x4F87D: alternatives |
| 430069 | Remove Deprecated Launch Control and Launch Control & Rolling Anti Lag | 0x58C14-0x58C83 |
| 430069 | Remove Deprecated Launch Control and DS2 Logging Feature Enhancement | 0x4AACA-0x4AAF5 |
| 430069 | Remove Deprecated Launch Control and LC & RAL Default Values | data 0x71316-0x7131A |
| 430069 | MAF Sensor Hack 2048kg/h and 4096kg/h | 0x3B4C3, 0x3B4E7: alternatives |

## Findings in the factory programs

Facts found on the way that anyone who edits these images should know; none of them is about any particular layer.

- **The 430069 keeps two 32-bit sums besides its CRC-16s.** A background task (code 0x5FBE0–0x5FD58, summing helper 0x5FD7C) adds the 16-bit words of two ranges to a seed, two passes per sum, and compares the result with the stored word. The descriptors sit in the image at 0x6FDAE–0x6FDDD: the stored program sum (0x6FDAE), the seeds (0x6FDB2, 0x6FDB8, both 0xA5A5A5A5), then two [start, end) far-pointer pairs per sum: the program sum over 0x50000–0x53BF7 and 0x6E876–0x6E877, the calibration sum over 0x712C6–0x71315 and 0x7EB94–0x7EE15, stored at 0x72FFC. A mismatch sets bit 0xFD7E.8 and registers fault 8 (`calls 0x0E:0x1192`); for the calibration sum the byte 0x70E07 = 0xA5 bypasses the check (stock: 1); that byte is the `lc_swi_cal_mon_cks` entry of the community patch Checksum Bypass, whose other three entries bypass the CRC-16 checks. All 18 stock images of ms4x-net match both sums; `info` shows them.
- **MS43 RAM that looks free is not.** The initialisation loop at 0x33300 fills 0x8976–0x8A75 and 0x8AE4–0x8BE3 (256 copies each of the bytes at 0x8970 and 0x8ADE) on every start. Whoever looks for free RAM for own cells must scan the whole code for writers, not for readers of a cell.
- **One stock image does not hold together.** `Siemens_MS43_MS430069_E39_M54B25_EU4_LHD.bin` of ms4x-net stores a calibration CRC that its content does not give (document 02).
