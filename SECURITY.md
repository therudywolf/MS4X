# Security and dangerous errors / Безопасность и опасные ошибки

**[English](#english) | [Русский](#русский)**

<a name="english"></a>
## English

This repository describes a safety-relevant control unit. A wrong address, a misread routine or a checker that reports a wrong state can lead someone to flash an image that damages an engine, drops the unit into limp mode or leaves a car immobile.

**If you find such an error, report it privately first**, not in a public issue: e-mail [alonerudywolf@gmail.com](mailto:alonerudywolf@gmail.com) or Telegram [t.me/rudy_wolf](https://t.me/rudy_wolf). Say what and where (tool, document and section) and give the evidence: the instruction address, a listing or a log. Once a fix is published, the report becomes a normal entry in `CHANGELOG.md`, with your name if you want it there.

Never send a firmware dump, a VIN or a unit serial in public, and do not put them into the report either unless a private exchange has been agreed. An MS42 or MS43 dump carries the immobilizer data.

The repository holds no firmware, no keys and no secrets; GitHub secret scanning with push protection is on.

<a name="русский"></a>
## Русский

Этот репозиторий описывает блок, отвечающий за безопасность. Неверный адрес, неправильно прочитанная подпрограмма или проверялка, которая показывает не то состояние, могут привести к тому, что кто-то прошьёт образ, который повредит мотор, отправит блок в аварийный режим или оставит машину без хода.

**Если нашли такую ошибку, сначала сообщите о ней лично**, а не в открытом issue: почта [alonerudywolf@gmail.com](mailto:alonerudywolf@gmail.com) или Telegram [t.me/rudy_wolf](https://t.me/rudy_wolf). Напишите, что и где (инструмент, документ и раздел), и приложите доказательство: адрес инструкции, листинг или лог. Когда исправление опубликовано, сообщение становится обычной записью в `CHANGELOG.md`, с вашим именем, если хотите.

Никогда не отправляйте дамп прошивки, VIN или серийный номер блока публично и не вставляйте их в сообщение, пока не договорились о приватном обмене. Дамп MS42 или MS43 содержит данные иммобилайзера.

В репозитории нет прошивок, ключей и секретов; сканирование секретов GitHub с защитой при push включено.
