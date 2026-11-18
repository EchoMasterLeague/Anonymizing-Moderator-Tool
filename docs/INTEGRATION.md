# Integrating into an existing Discord bot

## Runtime prerequisites

This component originated in EML's Python/`discord.py` application. It requires an existing `discord.py` bot, compatible dependencies, and Discord/Ticket Tool configuration. This repository alone is **not runnable**.

The public repository uses this layout:

```text
utils/anonymous_ticket_reply.py
utils/anonymous_ticket_reply_core.py
tests/test_anonymous_ticket_reply_*.py
```

## Registration

Copy or merge the two files from `utils/` into the host bot's importable `utils` package. In the host bot's startup module, import the adapter and register it on the existing bot:

```python
from utils import anonymous_ticket_reply

# After the bot instance has been created, before bot.tree.sync():
anonymous_ticket_reply.register(bot)
```

The host bot must call `bot.tree.sync()` to publish the one-time `/ticket_reply_center_setup` command. The component installs five additional Discord event listeners; it does not replace the bot's existing event handlers. Do not create a second bot process or duplicate command synchronization.

Registration is disabled unless `EML_ANON_TICKET_REPLIES_ENABLED=1`. See [CONFIGURATION.md](CONFIGURATION.md).

## Persistent UI and delivery

- A Board/Commissioner first initializes the private dashboard through `/ticket_reply_center_setup` in the configured reply-center channel.
- After the first panel exists, startup and periodic reconciliation find/edit the existing bot-authored panel using its marker.
- The current adapter only includes candidate tickets in configured open categories for which the bot can confirm Ticket Tool origin in early channel history.
- Staff click a ticket button, enter a modal reply, and the bot posts it under its own identity with the `EML Support` heading.
- A private audit is recorded before attempting delivery and finalized on confirmed send.

## Tests

Seven dedicated test files are included, with **61/61** accepted in EML DEV verification. From the repository root, run `python -m unittest discover -s tests -p "test_anonymous_ticket_reply_*.py"` to execute the component tests. Some environments may need the host bot's development dependencies or test mocks.

This repo is a **reference component**, not an executable Discord bot or a substitute for testing an integration in its target server.

## Future changes

For EML production, changes still require approval and validation in the private operational bot repository before deployment. Third-party integrations should perform their own compatibility, permission, and end-to-end testing.
