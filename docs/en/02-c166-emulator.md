# 02. C166 emulator

[`tools/c166emu.py`](../../tools/c166emu.py) runs the code of an MS42 or MS43 image instruction by instruction, on the decoder of [`c166.py`](01-c166-tools.md). Python 3, no other packages.

## What it emulates

- Every instruction of the C167 with the operation and the flags E, Z, V, C, N of the Infineon *Instruction Set Manual for the C166 Family* V2.0. Among them: `ADDC` and `SUBC` keep Z only when it was set before; V of `SHR`, `ASHR` and `ROR` is the rounding flag of the bits shifted out; `MUL`, `DIV` and their kin set V and MDC.MDRIU; `PRIOR`; the flags of the bit instructions from the previous bit states; `BFLDL` / `BFLDH` OR the data in as it is; `JBC` and `JNBS` change the bit they test.
- The general registers live in internal RAM at CP, so `SCXT CP` switches the bank. The system stack runs at SP; `CALLS` and `RETS` push and pop CSP; `TRAP` and `RETI` follow SYSCON.SGTDIS.
- The registers code relies on: DPP0-DPP3 (a value written takes effect), CSP (read only), CP, SP, PSW, MDH, MDL, MDC, ZEROS, ONES, SYSCON. `EXTP`, `EXTS`, `EXTPR` and `EXTSR` with a constant or a register, `EXTR` for the extended SFR.
- Memory: the flash comes from the image through the profile of `c166.py` and is never written. The system page 0xC000-0xFFFF (XRAM, CAN, ESFR, IRAM, SFR) and the RAM windows of the profile (the external RAM of the MS43) start at zero.
- Not emulated: interrupts, the peripherals (a peripheral register reads back what was written to it), timing, the watchdog.

The emulator stops with the exception `Stop` and says why: bytes that are no instruction, a word at an odd address, a write to the flash, a read outside the memory map, `SRST`, `IDLE` or `PWRDN`, the step limit.

## Use

| Command | What it does |
|---|---|
| `python3 tools/c166emu.py call IMAGE ADDR [r12=0xF758] [0xF756=0x3643] [--near] [--steps N] [--trace]` | Runs the function at a file offset (a far one by default, `--near` for one called by `CALLA` / `CALLR`) with the registers and memory words given; prints the registers, and the last instructions with `--trace` |
| `python3 tools/c166emu.py crc IMAGE` | Both checksums of the program computed by its own CRC routine, next to the stored ones |

As a library:

```python
from c166emu import Emu
emu = Emu(img)                 # profile from the program ID
emu.r[12] = 0xF760             # general registers
emu.wr16(0xF756, 0x3643)       # memory by physical address
emu.call(0x75D8E)              # a far function; near=True for CALLA / CALLR
emu.hooks[0x1234A] = f         # f(emu) before the instruction at a file offset; True skips it
```

## How it is checked

`python3 tests/test_c166emu.py`; GitHub Actions runs it on every pull request with the stock images.

- Every group of instructions against the operation and the flags of the manual, the 16 condition codes of its table 5, the addressing through DPP, EXTP, EXTS and EXTR, the stack, `TRAP` and `RETI`.
- **The programs' own CRC routine.** Both programs check their flash in a background task: a CRC-16 routine (0110C6: `calls 07:5D8E`, 430069: `calls 0E:3642`; r12 points to a far pointer, r13 to the CRC, r14 holds the byte count) is fed the blocks of two descriptors (sum, block count, blocks): MS42 0x4FEE0 (calibration) and 0x50306 (program), MS43 0x73FE0 and 0x6FDE0. The task starts each CRC with two ASCII bytes of an identification string: the MS42 reads them at 0x4800C and 0x50032 (`C6` of `0110C6` gives 0x3643, `00` gives 0x3030), the MS43 through the far pointers at 0x6ED5A and 0x6ED42. Run by the emulator over the 34 stock images of ms4x-net, the routine gives what an independent CRC-16 (polynomial 0xA001, reflected) gives, more than four million instructions of compiled code for the program CRC of the MS43 alone, and the sums stored in the images.
- One stock image does not hold together: `Siemens_MS43_MS430069_E39_M54B25_EU4_LHD.bin` of ms4x-net stores the calibration sum 0x5ADF, while its content gives 0xC138, both by the program's routine and by the independent CRC.
- Every function reached in the code (document 01), run with RAM at zero, returns or stops on something the emulator reports, never on an error of the emulator itself. With RAM at zero 415 of the 471 functions of the MS42 return and 497 of the 650 of the MS43; the others wait for hardware or follow a pointer that is still zero.
- Speed: about 400,000 instructions a second.

## Limits

- No interrupts and no peripherals: code that waits for a timer, the ADC or a CAN flag runs to the step limit; set the register it waits for, or replace the call with a hook.
- The DPP values start at the start-up values of the profile; code that loads others is followed, code that relies on values set elsewhere needs them set first.
