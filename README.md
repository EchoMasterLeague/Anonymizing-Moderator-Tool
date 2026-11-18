# Anonymizing Moderator Tool — Echo Master League

**Status:** RC1.2b reference component (November 17, 2026).
**Scope:** Anonymous moderator replies in Ticket Tool-generated **League Support** tickets.
**Not a standalone bot:** This is a component extracted from the existing EML Discord bot. It requires integration into the EML application and its installed `discord.py` dependencies.

## What it does

Authorized staff use a **persistent, private EML Ticket Reply Center** dashboard to select an open ticket and compose a reply. The player-facing message is sent by the EML bot under the **EML Support** heading; the individual staff author is recorded separately in a restricted audit channel. Ticket origin, current staff access, ticket status, and destination permissions are checked at delivery time.

A Board or Commissioner performs a **one-time** `/ticket_reply_center_setup` slash-command initialization to create the first persistent dashboard. The bot subsequently reconciles and updates that message automatically; staff reply using buttons and forms.

## Repository layout

- [`src/eml-bot-arena/utils/anonymous_ticket_reply.py`](src/eml-bot-arena/utils/anonymous_ticket_reply.py) — Discord interaction adapter, persistent dashboard, delivery, audit, permission gates.
- [`src/eml-bot-arena/utils/anonymous_ticket_reply_core.py`](src/eml-bot-arena/utils/anonymous_ticket_reply_core.py) — configuration and validation logic independent of Discord.
- [`src/eml-bot-arena/tests/`](src/eml-bot-arena/tests/) — seven feature-test modules; 61 tests in accepted DEV verification.
- [`docs/INTEGRATION.md`](docs/INTEGRATION.md) — exact registration points and integration boundaries.
- [`docs/CONFIGURATION.md`](docs/CONFIGURATION.md) — environment settings and Ticket Tool panel role configuration.
- [`docs/OPERATIONS.md`](docs/OPERATIONS.md) — setup, dashboard use and failure recovery.
- [`docs/SECURITY.md`](docs/SECURITY.md) — authorization, anonymity and audit state machine.
- [`docs/VERIFICATION.md`](docs/VERIFICATION.md) — accepted regression and operational demonstration evidence.
- [`SOURCE_MANIFEST.json`](SOURCE_MANIFEST.json) — provenance and SHA-256 hashes for the nine Python files.

## Quick integration summary

The existing EML bot calls `anonymous_ticket_reply.register(bot)` **after bot construction and before** its established `bot.tree.sync()` startup workflow. The feature is disabled by default unless `EML_ANON_TICKET_REPLIES_ENABLED=1` and all required IDs and permissions are correctly configured. See [integration](docs/INTEGRATION.md) and [configuration](docs/CONFIGURATION.md) for details.

**Do not paste this snapshot over a live MAIN/PROD deployment.** Follow the EML release and rollback procedures. This repository preserves the reviewed RC1.2b component, not the entire running bot.

## Evidence and limitations

The accepted DEV evidence includes **61/61 dedicated feature tests**. A November 17, 2026 production demonstration showed a new Ticket Tool-generated ticket appearing in the dashboard, a bot-authored `EML Support` message in the ticket, and a private audit recording delivery and the moderator identity. This does **not** prove all future permissions or an exhaustive negative-access confidentiality test. See [verification](docs/VERIFICATION.md).

## Security and publication

This repository intentionally excludes real `.env` files, credentials, player ticket transcripts, moderator audit screenshots, production SQL, and operational backups. All configuration examples use placeholders. There is no standalone executable launcher and no license grant is implied by making this repository public.
