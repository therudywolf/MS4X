# Documents (EN)

Documents come in pairs with [`docs/ru`](../ru/README.md): the same file names, the same facts.

| Document | What it covers |
|---|---|
| [01 C166 tools](01-c166-tools.md) | Disassembler, assembler and code walker: commands, syntax, memory maps of 0110C6 and 430069, how it is checked |
| [02 C166 emulator](02-c166-emulator.md) | What it runs and what not, use, the programs' own CRC routine as the check, one stock image whose calibration sum does not match |
| [03 What is in an image, and the community patchlists](03-image-info-and-patchlists.md) | `ms4x_core.py info`: program, checksums, stock or not, free area, patches of your patchlist, differences against stock; patches that share bytes; the two 32-bit sums of the 430069; findings in the factory programs |
| [04 A safe code layer for the MS42: the rule and the boundary](04-ms42-core-boundary.md) | Guideline for own code in the free area: the rule it has to meet, what has to stay out, how to prove it on the emulator |
