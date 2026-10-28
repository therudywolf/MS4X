# 01. C166 tools: disassembler, assembler, code walker

[`tools/c166.py`](../../tools/c166.py) reads and writes the code of the C167 in the Siemens MS42 (program 0110C6) and MS43 (program 430069). One table of instruction forms serves both directions: whatever the disassembler prints, the assembler turns back into the same bytes. Python 3, no other packages.

## Commands

| Command | What it does |
|---|---|
| `python3 tools/c166.py dis IMAGE START [END]` | Listing: file offset, bytes, instruction, comment |
| `python3 tools/c166.py func IMAGE ADDR` | One function along its flow, with labels; calls are not followed |
| `python3 tools/c166.py funcs IMAGE` | Functions reached from the vectors and the far calls, with the number of callers |
| `python3 tools/c166.py xref IMAGE ADDR [START END]` | Instructions that call or jump to `ADDR`, address it as data, as a register or a bit, or load it as a 16-bit constant |
| `python3 tools/c166.py asm SOURCE -o OUT [--org ADDR]` | Assembles a source in the syntax of the listing into a flat file |
| `python3 tools/c166.py check IMAGE [START END]` | Disassembles and assembles back; reports every instruction that does not give the same bytes |

`--profile ms42 | ms43 | raw` selects the memory map; by default it comes from the program ID in the image (`0110C6` at 0x48008, `430069` at 0x6FFBA). `--dpp P0,P1,P2,P3` sets other DPP values.

## Syntax

| Operand | Written as | Example |
|---|---|---|
| Word and byte register | `r0`-`r15`, `rl0`-`rh7` | `mov r4, r5` |
| Special function register | name from the register table of the C167CR user's manual (`PSW`, `DPP0`, `T2`, `ADCON`, under EXTR `DP0L`, `XP0IC`...) or word address | `mov T2, #0x0000`, `mov 0xFE40, #0x0000` |
| Direct memory | `[address]` | `movb rl4, [0x8100]` |
| Indirect | `[r4]`, `[r4+]`, `[-r0]`, `[r4+#0x0010]` | `mov r4, [r5+#0x0010]` |
| Immediate | `#5` decimal: the 3- or 4-bit form; `#0x05`: 8 bits; `#0x0005`: 16 bits | `mov r4, #5` is `E0 54`, `mov r4, #0x0005` is `E6 F4 05 00` |
| Bit | `word.bit`: `PSW.3`, `r4.3`, `0xFD10.3` | `jb PSW.3, 0x49D10` |
| Condition | `cc_UC`, `cc_EQ`, `cc_NE`, `cc_ULT`, `cc_UGE` and the rest; `cc_Z`, `cc_NZ`, `cc_C`, `cc_NC` are accepted | `jmpr cc_NE, 0x49D02` |
| Code target | file offset of the target | `calla cc_UC, 0x4A000` |
| Far target | `segment:offset` | `calls 0x0C:0x9CF8` |

The spelling of an immediate picks the encoding, so a listing assembles back exactly. A source may use labels (`name:`), `org ADDR`, `db` and `dw`, and lines copied from a listing (address and bytes at the start are read, then the text).

## What the listing shows

From the stock MS43 430069:

```
1DCC2  DA 0C 38 5B  calls 0x0C:0x5B38                 ; file 0x45B38
1DCE4  F3 F8 89 80  movb rl4, [0x8089]                ; ext RAM 0x40089
1DCE8  D7 40 10 00  extp #0x010, #1                   ; next 1
1DCEC  F7 F8 E8 1C  movb [0x1CE8], rl4                ; ext RAM 0x41CE8
```

- The address is the file offset, the same as in a hex editor and in an XDF.
- A data address is shown physically, through the DPP of the profile or through the page or segment of a preceding `EXTP` / `EXTS`, with what is there: a file offset in the flash, external RAM, XRAM (0xE000-0xE7FF), IRAM (0xF600-0xFDFF), a register by name, or a part of the CAN module: `CAN object 1 data 0` is 0xEF17, byte 0 of message object 1.
- After `EXTR`, `EXTPR` and `EXTSR` the registers and bits of the next instructions are the extended SFR (0xF000-0xF1FF) and print with those addresses.
- A far call shows the file offset of its target.
- Bytes that are no instruction print as `db`. When a reserved field of a known instruction is not zero, the comment says so.

## Memory maps

| | MS42 0110C6 | MS43 430069 |
|---|---|---|
| Flash in the file | file offset = physical address | the flash shows at 0x00000 and 0x80000: file offset = physical address & 0x7FFFF |
| Code | segments 0-7 (for example 0x61234 is `06:1234`) | segment 0 (start-up) and segments 9-0x0F: `calls 0x0C:0x9CF8` goes to file 0x49CF8 |
| DPP0, DPP1, DPP2, DPP3 after start-up | 0x12 (0x48000), 0x14 (0x50000), 0x13 (0x4C000), 0x03 | 0x1C (0x70000, calibration), 0x3B (0xEC000 = file 0x6C000), 0x10 (external RAM 0x40000-0x43FFF), 0x03 |
| Calibration | 0x48000-0x4FFFF | 0x70000-0x7FFFF |

DPP3 = 3 is the system page of the C167: XRAM, the CAN module, IRAM and the SFRs. The listing uses the start-up DPP values; a function that loads other values (on the MS43 some table functions change DPP0) is read with the start-up ones, so check such places by hand.

## How it is checked

`python3 tests/test_c166.py`; GitHub Actions runs it on every pull request with the stock images.

- Every first byte with every second byte and several tails, in both EXTR states (more than 600,000 cases), disassembles to a text that assembles back to the same bytes. 236 first bytes are instructions; 20 are not used by the C167: 0x3B, 0x44, 0x45, 0x83, 0x85, 0x8B, 0x8C, 0x93, 0x95, 0xA3, 0xB3, 0xC1, 0xC3, 0xC7, 0xD3, 0xE3, 0xE5, 0xF5, 0xF8, 0xF9.
- More than a hundred encodings, one or more per layout of the Infineon *Instruction Set Manual for the C166 Family* V2.0 (2001), in both directions; every layout of the tool was compared with that manual. The register names come from table 22-4 of the *C167CR Derivatives User's Manual* V3.1 (2000).
- The 16 stock images of 0110C6 and the 18 of 430069 from the [ms4x-net](https://github.com/ms4x-net) repositories, listed with their SHA-256 in [`tests/ms4x_images.txt`](../../tests/ms4x_images.txt) and downloaded for the run, not stored here. Every byte of them disassembles and assembles back. The code reached from the vectors and the far calls (MS42: 471 functions, about 66,000 instructions; MS43: 650 functions, about 73,000 instructions) decodes without a gap.
- The bytes of `BFLDL` and `BFLDH` differ: `0A QQ mask data` and `1A QQ data mask`, the syntax is `bitoff, #mask, #data` for both. Read so, the data byte lies inside the mask in every `BFLDL` and `BFLDH` of the stock code.
- In the stock code a byte instruction with an 8-bit constant keeps the sign extension in its unused byte: `CMPB RL0, #-9` is stored as `47 F0 F7 FF`. The processor reads only the low byte; the tool shows `#0xFFF7` and keeps the stored byte.

## Limits

- The data address of `[r4]` and other indirect operands is not known without running the code.
- `xref` is a linear pass: tables between the functions decode too, so check each hit in its function.
- The walk follows direct jumps and calls; tasks called through pointer tables are found through the far calls of a linear pass, which counts a target only when its own flow meets no gap.
- The emulator is the next step.
