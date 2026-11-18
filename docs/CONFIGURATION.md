# Configuration reference — RC1.2b

The `register(bot)` function is **disabled by default**; it activates only when `EML_ANON_TICKET_REPLIES_ENABLED=1`. Configuration is read from the environment on bot startup. Missing or malformed required values cause fail-closed registration.

| Variable | Required | Meaning |
|---|---:|---|
| `GUILD_ID` | Yes | Target Discord guild ID; must match the bot's actual guild. |
| `EML_ANON_TICKET_REPLIES_ENABLED` | Yes | Set exactly `1` to register the feature. Otherwise disabled. |
| `EML_ANON_TICKET_CENTER_CHANNEL_ID` | Yes | Staff-only text channel containing the persistent dashboard. |
| `EML_ANON_TICKET_AUDIT_CHANNEL_ID` | Yes | Separate private staff-only text channel holding audit records. |
| `EML_TICKET_TOOL_BOT_ID` | Yes | Actual Ticket Tool bot account ID, used to verify ticket origin. |
| `EML_TICKET_OPEN_CATEGORY_IDS` | Yes | Comma-separated, nonduplicate IDs of eligible open-ticket categories. PROD policy currently limits this to **League Support**. |
| `EML_TICKET_CLOSED_CATEGORY_IDS` | No | Comma-separated closed categories if used; may be absent. Cannot overlap open categories. |
| `EML_ANON_TICKET_STAFF_ROLE_NAMES` | Optional | Defaults to `League Mod,Commissioner,Board`. Names must match Discord role names exactly. |
| `EML_ANON_TICKET_SUPPORT_HEADING` | Optional | Defaults to `EML Support`; nonempty, <=80 characters, no newline or `@`. |

Example (placeholder values; **never commit the actual production `.env.bot`**):

```dotenv
GUILD_ID=<PROD_GUILD_ID>
EML_ANON_TICKET_REPLIES_ENABLED=1
EML_ANON_TICKET_CENTER_CHANNEL_ID=<STAFF_CENTER_CHANNEL_ID>
EML_ANON_TICKET_AUDIT_CHANNEL_ID=<PRIVATE_AUDIT_CHANNEL_ID>
EML_TICKET_TOOL_BOT_ID=<TICKET_TOOL_BOT_ID>
EML_TICKET_OPEN_CATEGORY_IDS=<OPEN_LEAGUE_SUPPORT_CATEGORY_ID>
EML_ANON_TICKET_STAFF_ROLE_NAMES=League Mod,Commissioner,Board
EML_ANON_TICKET_SUPPORT_HEADING=EML Support
```

**Constraints:** center/audit must be different channels, neither can equal a ticket category ID, and open/closed category IDs must be disjoint. Only Discord text channels in the configured guild qualify. Staff channels must not be inside the configured open-ticket category.

## Docker Compose integration

The established PROD Compose `bot` service uses its existing environment files (one nonsecret bot configuration file and a separate secrets file). Keep this separation. In the November 17 activation, the operator appended the new ticket variables to the existing bot config file, verified `docker compose config --format json` without exposing secrets, then recreated **only** the bot container with existing Compose tooling. No application-code rebuild, data migration, or SQL update was involved.

**Before any future activation:** inspect effective service environment, confirm `GUILD_ID` and intended categories, check channel permissions, and follow the Owner's established backup and rollout procedure. A running process must be recreated to read changed environment values; changing the file alone does not update an already-running container.

## Ticket Tool integration

For the **League Support** panel, Ticket Tool's **Support Team Roles** include the existing human support roles and `League Bot`, the Discord role held by EML League Bot (Primary). Confirm the role is not inadvertently held by humans. Ticket Tool then grants that role visibility on newly generated ticket channels; their channel permissions are frequently intentionally *not synchronized* with the parent category. Do not use Discord's **Sync Now** on a real ticket as a shortcut.

The feature does **not** anonymize other ticket categories unless those IDs are expressly configured.
