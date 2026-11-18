# Operations and support runbook — RC1.2b

## Initial setup (per guild)

1. Create or identify two private text channels outside the Ticket Tool open-ticket categories: reply center and private audit.
2. Restrict `@everyone` from **View Channel**. Allow authorized staff role(s) and the production EML bot account/role sufficient access. Audit viewers must be deliberately approved; administrators inherently bypass channel overwrites.
3. Ensure the bot can **View Channel**, **Send Messages**, **Read Message History**, and **Embed Links** in both staff channels. The bot also needs equivalent relevant permissions in Ticket Tool-created ticket channels.
4. Configure the environment variables in [CONFIGURATION.md](CONFIGURATION.md), verify effective Compose settings and perform a controlled restart/recreate if required.
5. Verify startup reports `Anonymous ticket reply feature registered` and successful Discord command synchronization.
6. In the **configured reply-center channel**, a member holding **Board or Commissioner** runs the **one-time** `/ticket_reply_center_setup` slash command. It publishes the first **EML Ticket Reply Center** message.
7. Verify the persistent panel appears and displays eligible open tickets. Later reconciliations edit the existing panel in place. *Do not repeatedly run setup to address a missing ticket button.*

## Normal moderator workflow

1. Navigate to the persistent dashboard message in the staff reply-center channel.
2. Click the target ticket button. The bot performs live staff, ticket-state, origin and channel-access checks before opening a form.
3. Enter a response of **1–1,800 characters**, then submit once.
4. Verify the private confirmation: successful delivery reports the destination and Discord message ID. The player-facing message is authored by the EML bot with the heading `EML Support`; the moderator's identity is **not included in that message**.
5. Check the separate private audit for `DELIVERED`, moderator identity, ticket ID, body, and delivered message link if needed.

## Refresh and lifecycle

- Automatic reconciliation runs approximately every **120 seconds** and is scheduled after applicable ticket/channel events.
- The panel displays up to **120 verified open tickets**, at most **25 buttons per panel page**; it can create/update overflow pages.
- Buttons for closed, moved, inaccessible or unverified tickets fail closed; submitting from a stale panel is rejected.
- The first panel **is not created automatically** on startup when none exists; this is intentional in the RC1.2b source. The setup command creates it once. Existing panels are rediscovered on restart by their marker.

## Missing-ticket diagnostic

Check in this order:

1. Is the dashboard initialized? If no panel exists, the one-time setup command is required.
2. Does the ticket belong to `EML_TICKET_OPEN_CATEGORY_IDS`? Closed and unrelated categories are ignored.
3. Can the EML bot actually **view, send to, and read history** in this specific ticket? Ticket Tool may override parent category permissions when it creates tickets.
4. Has Ticket Tool actually authored one of the earliest 12 ticket messages within one hour of channel creation? Missing/deleted origin evidence results in exclusion.
5. Is the ticket still open and within the candidate limit? Ticket Tool may move/close channels at any time.
6. Inspect *filtered* feature startup and warning logs without dumping credentials or ticket bodies. Permission failures may appear as `Private channel could not be verified` or `Anonymous ticket dashboard refresh blocked`.

## Incident handling

- **Audit channel unavailable:** reply is not sent if the initial private PREPARED record cannot be created.
- **`SEND_UNCONFIRMED`:** check the ticket and audit before any retry; a network failure may occur after Discord accepted a message.
- **Player delivery confirmed but audit finalization failed:** the bot tells the moderator delivery occurred but audit finalization failed; **do not resend**. Notify Board and preserve the PREPARED audit record and message ID.
- **Duplicate/stale form:** do not re-submit blindly. Inspect ticket and audit first.
- **Unexpected visibility:** disable feature through the established controlled configuration/deployment procedure and preserve evidence; review channel permissions and the audit record before further use.

The component makes no independent changes to SQL authority, league records, Ticket Tool ticket lifecycles, or existing transcript machinery.
