# Integrating into the EML bot

## Runtime prerequisites

This component was implemented within the existing EML Python/`discord.py` application. Reuse the project's established interpreter, dependency lock, bot startup, and Compose configuration; this repository alone is **not runnable**.

The module locations match their locations in the EML repository:

```text
src/eml-bot-arena/utils/anonymous_ticket_reply.py
src/eml-bot-arena/utils/anonymous_ticket_reply_core.py
src/eml-bot-arena/tests/test_anonymous_ticket_reply_*.py
```

## Registration

In the EML application's existing `src/eml-bot-arena/main.py`, the accepted integration imports the adapter and registers it on the existing bot:

```python
from utils import anonymous_ticket_reply

# After the bot instance has been created, before bot.tree.sync():
anonymous_ticket_reply.register(bot)
```

The existing bot startup calls `bot.tree.sync()` to publish the one-time `/ticket_reply_center_setup` command. The component installs five additional Discord event listeners; it does not replace the bot's existing event handlers. Do not create a second bot process, duplicate command sync, or run a separate SQL authority.

Registration is disabled unless `EML_ANON_TICKET_REPLIES_ENABLED=1`. See [CONFIGURATION.md](CONFIGURATION.md).

## Persistent UI and delivery

- A Board/Commissioner first initializes the private dashboard through `/ticket_reply_center_setup` in the configured reply-center channel.
- After the first panel exists, startup and periodic reconciliation find/edit the existing bot-authored panel using its marker.
- The current adapter only includes candidate tickets in configured open categories for which the bot can confirm Ticket Tool origin in early channel history.
- Staff click a ticket button, enter a modal reply, and the bot posts it under its own identity with the `EML Support` heading.
- A private audit is recorded before attempting delivery and finalized on confirmed send.

## Tests

Seven dedicated test files are included. They were accepted as **61/61** in the EML DEV environment. These tests depend on portions of the EML runtime/test harness and may not run as a standalone suite outside that environment. The audit-layout test is the corrected package-import variant from the accepted harness repair.

This repo is a **reference implementation snapshot**, not a substitute for the originating EML Git commit or the full regression environment.

## Future changes

Make improvements first in the authoritative EML application repository under Supervisor/Owner governance, test there, and then publish an explicitly versioned update to this reference repository. Do not deploy directly from this repository without separate approval.
