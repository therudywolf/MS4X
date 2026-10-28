# Changelog

Newest first. Each entry: date and title, then **EN** and **RU** with the same facts. Older entries are not rewritten: what turned out wrong is corrected in a newer entry.

## 2026-10-30 (3): paused

**EN**

- New material is paused: there has been next to no demand or response, and this is unpaid work. What is here stays and is kept correct; error reports are answered. README and CONTRIBUTING say so.
- `SECURITY.md`: how to report a dangerous error privately. Small tidy-ups in document 01, the examples and `CITATION.cff`.

**RU**

- Новое наполнение на паузе: запроса и отклика почти нет, а это неоплачиваемая работа. То, что здесь есть, остаётся и поддерживается в верном виде; на сообщения об ошибках отвечаю. Это сказано в README и CONTRIBUTING.
- `SECURITY.md`: как лично сообщить об опасной ошибке. Мелкие правки в документе 01, примерах и `CITATION.cff`.

## 2026-10-30 (2): the two 32-bit sums of the 430069, findings

**EN**

- `ms4x_core.py info` computes the two 32-bit sums the MS43 keeps besides its CRC-16s (program sum stored at 0x6FDAE, calibration sum at 0x72FFC), from the descriptors in the image, and shows them next to the stored ones; the test checks them on all 18 stock images. Document 03: how the background task computes and checks them (code 0x5FBE0–0x5FD58, fault 8, the bypass byte 0x70E07), and a "Findings" section: these sums, the MS43 RAM the initialisation loop at 0x33300 fills, the stock image whose calibration CRC does not match.

**RU**

- `ms4x_core.py info` считает две 32-битные суммы, которые MS43 держит кроме CRC-16 (сумма программы в 0x6FDAE, сумма калибровки в 0x72FFC), по дескрипторам из образа и показывает рядом с записанными; тест проверяет их на всех 18 заводских образах. Документ 03: как фоновая задача их считает и проверяет (код 0x5FBE0–0x5FD58, ошибка 8, байт обхода 0x70E07), и раздел «Находки»: эти суммы, RAM MS43, которую заполняет цикл инициализации 0x33300, заводской образ с несходящейся CRC калибровки.

## 2026-10-30: reverse is public, the product is not

**EN**

- Material about the author's own code that was published briefly on 29.10 is withdrawn. The repository is the reverse of the factory programs, the tools and the checkers; what the author builds on them is paid work (README, Custom work). Document 04 keeps the rule a safe layer has to meet, what has to stay out and how to prove it.

**RU**

- Материал о собственном коде автора, ненадолго опубликованный 29.10, отозван. Репозиторий — реверс заводских программ, инструменты и проверялки; то, что автор строит на них, — платная работа (README, «Работа на заказ»). Документ 04 оставляет правило, которому должен отвечать безопасный слой, что за бортом и как доказать.

## 2026-10-29 (3): what is in an image, and the community patchlists

**EN**

- `tools/ms4x_core.py info` reads an image of 0110C6 or 430069 and changes nothing (document 03): the program and its labels, both checksums by the program's own CRC routine, whether the program part (the blocks the ECU checks) is the stock one, what occupies the free area of the stock program; with `--patchlist` every patch of a TunerPro patchlist as applied, not applied, partly applied or changed otherwise, and the patches that share bytes; with `--stock` the differences against a stock image, each put down to a patch entry or a stored checksum. `--json` for other tools.
- The patch bytes come from the patchlist the user gives; no patchlist is stored or downloaded here.
- Document 03: the states, the pairs of patches of MS42 v1.7.1 and MS43 v2.9.2 that share bytes.
- Tests: the reader, the states and the shared bytes; on the 34 stock images every one is the stock program with an empty free area, and a patchlist made from the bytes of the image is found as it should be.

**RU**

- `tools/ms4x_core.py info` читает образ 0110C6 или 430069 и ничего не меняет (документ 03): программа и её метки, обе суммы собственной подпрограммой CRC программы, заводская ли программная часть (блоки, которые проверяет блок), что занимает свободную область заводской программы; с `--patchlist` каждый патч патчлиста TunerPro как applied, not applied, partly applied или changed otherwise и патчи, которые делят байты; с `--stock` отличия от заводского образа, каждое названо записью патча или записанной суммой. `--json` для других инструментов.
- Байты патчей берутся из патчлиста пользователя; здесь патчлисты не хранятся и не скачиваются.
- Документ 03: состояния, пары патчей MS42 v1.7.1 и MS43 v2.9.2, которые делят байты.
- Тесты: чтение, состояния и общие байты; на 34 заводских образах каждый — заводская программа с пустой свободной областью, а патчлист, собранный из байт самого образа, находится как должен.

## 2026-10-29 (2): C166 emulator

**EN**

- `tools/c166emu.py`: emulator of the C167 on the decoder of `c166.py` (document 02). Every instruction with the operation and the flags of the Infineon instruction set manual, the general registers in internal RAM at CP, the system stack, DPP / EXTP / EXTS / EXTR, the registers code relies on; the flash read only, no interrupts or peripherals. Commands `call` and `crc`.
- Checked: every group of instructions against the manual, the 16 condition codes; the programs' own CRC routine (0110C6 `calls 07:5D8E`, 430069 `calls 0E:3642`), run by the emulator over all 34 stock images, gives what an independent CRC-16 gives and the sums stored in the images; every function reached in the code runs without an error of the emulator (with RAM at zero 415 of 471 return in the MS42, 497 of 650 in the MS43).
- Found: the stock image `Siemens_MS43_MS430069_E39_M54B25_EU4_LHD.bin` of ms4x-net stores the calibration sum 0x5ADF, its content gives 0xC138. The CRC starts from two ASCII bytes of an identification string that the program loads (0110C6: 0x4800C and 0x50032; 430069: through the pointers at 0x6ED5A and 0x6ED42).
- README, documents index, CI runs the emulator tests with the images.

**RU**

- `tools/c166emu.py`: эмулятор C167 на декодере `c166.py` (документ 02). Каждая команда с действием и флагами из руководства Infineon по набору команд, регистры общего назначения во внутренней RAM по CP, системный стек, DPP / EXTP / EXTS / EXTR, регистры, на которые опирается код; флеш только для чтения, без прерываний и периферии. Команды `call` и `crc`.
- Проверено: каждая группа команд против руководства, 16 кодов условий; собственная подпрограмма CRC программ (0110C6 `calls 07:5D8E`, 430069 `calls 0E:3642`), исполненная эмулятором на всех 34 заводских образах, даёт то же, что независимый CRC-16, и суммы, записанные в образах; каждая функция, достижимая в коде, работает без ошибки эмулятора (с нулевой RAM возвращаются 415 из 471 в MS42 и 497 из 650 в MS43).
- Найдено: в заводском образе `Siemens_MS43_MS430069_E39_M54B25_EU4_LHD.bin` из ms4x-net записана калибровочная сумма 0x5ADF, содержимое даёт 0xC138. CRC начинается с двух байт ASCII из строки опознания, которые грузит программа (0110C6: 0x4800C и 0x50032; 430069: через указатели в 0x6ED5A и 0x6ED42).
- README, оглавление документов, CI запускает тесты эмулятора с образами.

## 2026-10-29: C166 tools

**EN**

- `tools/c166.py`: disassembler, assembler and code walker for the C167 of the MS42 0110C6 and MS43 430069 (document 01). One table of instruction forms for both directions; commands `dis`, `func`, `funcs`, `xref`, `asm`, `check`; memory profiles of both programs, detected by the program ID; data addresses resolved through the DPP and the EXTP / EXTS prefixes, the extended SFR after EXTR; register names of the C167CR user's manual, parts of the CAN module by message object.
- Checked: every first byte with every second byte, more than 600,000 cases, through the text and back; more than a hundred encodings of the Infineon instruction set manual, every layout compared with it (the order of mask and data differs between `BFLDL` and `BFLDH`); the 16 + 18 stock images of ms4x-net disassemble and assemble back byte for byte, and the code reached from the vectors and the far calls (MS42: 471 functions, MS43: 650) decodes without a gap. GitHub Actions downloads the images for every run (`tests/ms4x_images.txt`, pinned commits and SHA-256); they are not stored here.
- README: status, layout; documents index.

**RU**

- `tools/c166.py`: дизассемблер, ассемблер и обход кода для C167 в MS42 0110C6 и MS43 430069 (документ 01). Одна таблица форм команд в обе стороны; команды `dis`, `func`, `funcs`, `xref`, `asm`, `check`; профили памяти обеих программ, определяются по метке программы; адреса данных считаются через DPP и префиксы EXTP / EXTS, после EXTR — расширенные SFR; имена регистров из руководства C167CR, части модуля CAN по объектам сообщений.
- Проверено: каждый первый байт с каждым вторым, больше 600 000 случаев, через текст и обратно; больше сотни кодировок из руководства Infineon по набору команд, каждая раскладка сверена с ним (порядок маски и данных у `BFLDL` и `BFLDH` разный); 16 + 18 заводских образов ms4x-net разбираются и собираются обратно байт в байт, а код, достижимый от векторов и дальних вызовов (MS42: 471 функция, MS43: 650), разбирается без пропусков. GitHub Actions скачивает образы на каждый прогон (`tests/ms4x_images.txt`, закреплённые коммиты и SHA-256); здесь они не хранятся.
- README: состояние, структура; оглавление документов.

## 2026-10-28: repository set up

**EN**

- The repository for the engine control units Siemens MS42 (0110C6) and MS43 (430069) is set up after [gs860-5hp19](https://github.com/therudywolf/gs860-5hp19): README in English and Russian, contribution rules, issue and pull request templates, funding link, `CODEOWNERS`.
- Licences: code under the Apache License 2.0 with a `NOTICE` file, documents and data under CC BY-SA 4.0; the credit to keep is "rudywolf, https://github.com/therudywolf/MS4X". `CITATION.cff` for "Cite this repository".
- `tests/test_repo.py` checks the repository rules (no firmware images, nothing that looks like a VIN, documents in pairs, licence files and credit, SPDX lines, README links); GitHub Actions runs it on every pull request and push to `main`.

**RU**

- Репозиторий для блоков управления мотором Siemens MS42 (0110C6) и MS43 (430069) подготовлен по образцу [gs860-5hp19](https://github.com/therudywolf/gs860-5hp19): README на английском и русском, правила участия, шаблоны issue и pull request, ссылка на поддержку, `CODEOWNERS`.
- Лицензии: код под Apache License 2.0 с файлом `NOTICE`, документы и данные под CC BY-SA 4.0; указание автора, которое нужно сохранять: «rudywolf, https://github.com/therudywolf/MS4X». `CITATION.cff` для кнопки «Cite this repository».
- `tests/test_repo.py` проверяет правила репозитория (нет образов прошивок, нет ничего похожего на VIN, документы парами, файлы лицензий и указание автора, строки SPDX, ссылки README); GitHub Actions запускает его в каждом pull request и при push в `main`.
