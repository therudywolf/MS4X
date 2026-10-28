# Contributing / Как участвовать

**[English](#english) | [Русский](#русский)**

<a name="english"></a>
## English

**New material is paused** (README, Status). Corrections of errors with evidence are still welcome and will be answered.

### What is welcome

- Dangerous errors (a wrong address or a misread routine that can damage an engine): report them privately first, see [`SECURITY.md`](SECURITY.md).
- Corrections with evidence: a disassembly excerpt, a table dump, a log, anything that lets somebody else re-check it. "I think X is Y" without a code reference goes into an issue as a hypothesis, not into the docs.
- Logs from a car (DS2) before and after a change, with the build named (SHA-256) and what was changed.
- Information about **other software versions and variants**: which community patches a stock image of yours carries, where its program differs from the 0110C6 / 430069 references of the [ms4x-net](https://github.com/ms4x-net) repositories.
- Translations and wording fixes.

### What is not accepted

- **Firmware dumps in issues or pull requests, in any form** (full 512K, partial 32K, hex pastes). A dump carries the immobilizer data and the VIN. If a comparison needs your dump, post the addresses that differ from a reference image, not its bytes, or agree on a private exchange with the maintainer directly. Issues that contain dumps are deleted.
- **VIN, unit serial numbers and owner names** anywhere: in text, logs, screenshots and file names. Dump files are often named after the VIN, rename them before you paste a command line or its output.
- **Anything about the immobilizer (EWS)**: bypasses, ISN, virginizing.
- **Switching off emissions monitoring** (catalyst, oxygen sensors, secondary air) **or the factory protections** (throttle monitoring, knock control, component protection, limp mode), and patches whose only purpose is that.
- Anything about the gearbox control unit: that is [gs860-5hp19](https://github.com/therudywolf/gs860-5hp19).
- Copies of parts of the community patchlists or of other authors' XDF files: reference them with a link instead.
- Copies of third-party AI-generated "findings" without verification against the binary.

### How to send a log or a difference

1. Software version (MS42 0110C6 or MS43 430069), car and engine, the community patches installed. No bytes of the dump itself.
2. For a log: CSV with a time column and the values read, plus the SHA-256 of the build it was recorded with.
3. Say what the car did (symptom) and what you expected.

### Tests

```bash
python3 tests/test_repo.py
```

The tests check the repository rules: no firmware images or dumps in the tree, nothing that looks like a VIN, the documents in `docs/en` and `docs/ru` come in pairs, the licence files and the credit, an SPDX line in every script, relative links of the README files. GitHub Actions runs them on every pull request and on every push to `main`. Tests of the tools come with the tools.

### Style

Same as the docs of [gs860-5hp19](https://github.com/therudywolf/gs860-5hp19): addresses in hex with `0x`, units for every number, a confidence label for every claim about semantics. What is not established is called not established. Russian and English versions of a document must say the same thing: if you change one, change the other or mark it `TODO translate`.

### Licence of contributions

A pull request is accepted under the licences of this repository: code (`tools/`, `tests/`) under Apache-2.0, documents and data.0 ([`NOTICE`](NOTICE)). Material taken from elsewhere comes with its source and a compatible licence.

### Collaborators with write access

- Work on a branch of this repository named `<name>/<topic>` and open a pull request into `main`. The maintainer reviews and merges; nobody pushes to `main` directly.
- `main` is protected. A pull request needs the `tests` check (GitHub Actions) and the maintainer's approval; a commit pushed after an approval needs a new one. Force pushes and deleting `main` are blocked, merges are squash-only.
- One topic per pull request. Paste the output of the tests into the description; receipts and run logs belong there, not in the tree.
- Scripts go into `tools/` with tests in `tests/`, documents into `docs/en` and `docs/ru`. There are no per-contributor folders: authorship is the commit author and a line in `CHANGELOG.md`.

<a name="русский"></a>
## Русский

**Новое наполнение на паузе** (README, «Статус»). Исправления ошибок с доказательствами по-прежнему принимаются, на них отвечу.

### Что приветствуется

- Опасные ошибки (неверный адрес или неправильно прочитанная подпрограмма, которые могут повредить мотор): сначала лично, см. [`SECURITY.md`](SECURITY.md).
- Исправления с доказательством: фрагмент дизассемблера, распечатка таблицы, лог, то, что позволит другому перепроверить. «Я думаю, что X это Y» без ссылки на код идёт в issue как гипотеза, а не в документацию.
- Логи с машины (DS2) до и после изменения, с указанием сборки (SHA-256) и того, что меняли.
- Сведения о **других версиях ПО и вариантах**: какие патчи сообщества стоят на вашем «заводском» образе, где его программа отличается от эталонов 0110C6 / 430069 из репозиториев [ms4x-net](https://github.com/ms4x-net).
- Переводы и правки формулировок.

### Что не принимается

- **Дампы прошивок в issue и pull request в любом виде** (полный 512K, частичный 32K, вставки hex). В дампе данные иммобилайзера и VIN. Если для сравнения нужен ваш дамп, пришлите адреса, которые отличаются от эталонного образа, а не его байты, или договоритесь с владельцем репозитория о приватном обмене. Issue с дампами удаляются.
- **VIN, серийные номера блоков и имена владельцев** где бы то ни было: в тексте, логах, скриншотах и именах файлов. Файлы дампов часто названы по VIN, переименуйте их, прежде чем вставлять командную строку или её вывод.
- **Всё про иммобилайзер (EWS)**: обходы, ISN, «обнуление».
- **Отключение контроля экологии** (катализатор, лямбда-зонды, вторичный воздух) **и заводских защит** (контроль дросселя, детонации, защита компонентов, аварийный режим), и патчи, которые нужны только для этого.
- Всё про блок коробки: это [gs860-5hp19](https://github.com/therudywolf/gs860-5hp19).
- Копии частей патчлистов сообщества и чужих XDF: вместо этого ссылка на них.
- Копии «находок» сторонних ИИ без проверки по бинарнику.

### Как прислать лог или отличия

1. Версия ПО (MS42 0110C6 или MS43 430069), машина и мотор, какие патчи сообщества стоят. Ни одного байта самого дампа.
2. Для лога: CSV со столбцом времени и прочитанными величинами плюс SHA-256 сборки, на которой он снят.
3. Что делала машина (симптом) и чего вы ожидали.

### Тесты

```bash
python3 tests/test_repo.py
```

Тесты проверяют правила репозитория: в дереве нет образов прошивок и дампов, нет ничего похожего на VIN, документы в `docs/en` и `docs/ru` идут парами, файлы лицензий и указание автора на месте, в каждом скрипте есть строка SPDX, относительные ссылки README ведут на существующие файлы. GitHub Actions запускает их в каждом pull request и при каждом push в `main`. Тесты инструментов появятся вместе с инструментами.

### Стиль

Как в документах [gs860-5hp19](https://github.com/therudywolf/gs860-5hp19): адреса в hex с `0x`, единицы у каждого числа, у каждого утверждения о смысле — уровень уверенности. Что не установлено, так и называется. Русская и английская версии документа говорят одно и то же: меняете одну — меняйте и другую или пометьте `TODO translate`.

### Лицензия вклада

Pull request принимается под лицензиями репозитория: код (`tools/`, `tests/`) под Apache-2.0, документы и данные.0 ([`NOTICE`](NOTICE)). Взятое из других источников приходит с указанием источника и совместимой лицензией.

### Участникам с правом записи

- Работа в ветке этого репозитория `<имя>/<тема>` и pull request в `main`. Проверяет и сливает владелец; напрямую в `main` никто не пушит.
- `main` защищён. Pull request нужна проверка `tests` (GitHub Actions) и одобрение владельца; коммит после одобрения требует нового одобрения. Force push и удаление `main` запрещены, слияние только squash.
- Одна тема на pull request. Вывод тестов вставляется в описание; квитанции и журналы запусков — туда же, не в дерево.
- Скрипты в `tools/` с тестами в `tests/`, документы в `docs/en` и `docs/ru`. Папок по участникам нет: авторство — это автор коммита и строка в `CHANGELOG.md`.
