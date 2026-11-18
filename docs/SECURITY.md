# Security and confidentiality — RC1.2b

## What "anonymous" means

The player-facing message is posted by **EML League Bot (Primary)** with the configurable support heading, normally **EML Support**. This hides **which human moderator** authored the reply; it does *not* hide that the response comes from the EML bot or prevent authorized staff from auditing the author.

## Authorization checks

- The interaction must originate from the configured guild and designated reply-center channel.
- The human must currently have at least one configured staff role name and effective channel access. The implementation uses a fresh Discord API member fetch before relevant actions rather than relying exclusively on old UI state.
- The channel must be an open category member, accessible to both current moderator and bot; the bot must verify Ticket Tool origin using a bot-authored opening message near channel creation.
- Ticket state and staff authorization are rechecked immediately before sending, after the private audit has been prepared.
- Form submissions are bound to their initiator and guarded against repeated submission.

## Confidentiality gates

The reply-center and audit channels must be separate, both staff-private, and not located inside an open-ticket category. The runtime rejects unsafe effective visibility from `@everyone`, nonstaff roles, and explicit individual member View Channel grants other than the bot itself. **Discord Administrator permissions are an inherent exception**; administrators can view private channels and must be included in the governance review.

A `League Mod` role with View Channel access to the audit channel can see moderator attribution; limit that access according to the EML Board's actual policy. Screenshots showing a private category are useful but do not replace effective permission verification, particularly individual overrides and administrators.

## Audit delivery state machine

| Status | Meaning | Operator response |
|---|---|---|
| `PREPARED` | Private record created *before* player send. | Wait for final status; do not infer delivery. |
| `ABORTED` | Authorization or ticket eligibility changed before send. | No reply should have been sent; investigate. |
| `SEND_UNCONFIRMED` | Discord send returned an error; actual delivery may be uncertain. | Inspect ticket and audit before retry. |
| `DELIVERED` | Message send returned successfully and audit record was finalized with the delivered message ID/link. | No retry needed. |

If the player message was delivered but the final audit edit fails, the bot returns a special warning and does *not* misreport fully audited success. The initial PREPARED record remains and must be reconciled manually.

## Boundaries / residual risks

- Human-readable author anonymity depends on no other workflow exposing staff identity; Ticket Tool closure events can independently disclose who closed a ticket.
- A message sent from the bot may still be linked to the public bot identity. The feature does not use webhooks or impersonation.
- The EML app does not control Discord's administrator bypass or external Ticket Tool access policy.
- A successful one-ticket PROD test does not prove permissions will remain correct after future Discord/Ticket Tool configuration changes.
- Full privacy acceptance requires checking effective visibility with an unauthorized member or an equally conclusive Discord permission audit; a successful send alone does not prove such negative access.

Never publish real private audit records, moderator IDs, message bodies, Discord bot tokens, or `.env` credentials in this document or public issue trackers.
