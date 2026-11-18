"""DEV-only anonymous ticket reply utility for Ticket Tool (tickettool.xyz).

Uses one configured open-ticket category (or multiple expressly verified ones),
Ticket Tool's *actual bot ID* as a channel-origin witness, and Discord's live
per-channel permissions. No ticket creation/closure, SQL, webhooks or typing API.

The only EML-facing registration is anonymous_ticket_reply.register(bot).
Configuration and actual Ticket Tool layout are supplied via environment.
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone

import discord
from .anonymous_ticket_reply_core import (
    ReplyConfig,
    ReplyConfigurationError,
    ReplyValidationError,
    candidate_category_allowed,
    dashboard_button_label,
    dashboard_pages,
    player_visible_message,
    role_authorized,
    validate_body,
)

log = logging.getLogger(__name__)
_MAX_CANDIDATES = 120
_CENTER_TITLE = "EML Ticket Reply Center"
_DASHBOARD_MARKER = "eml:anonymous-ticket-reply:v2:page="
_BUTTON_MARKER = "eml:anonymous-ticket-reply:v2:ticket:"
_REFRESH_INTERVAL_SECONDS = 120
_PANEL_SEARCH_LIMIT = 200

# Audit content is a concise status cue. Stable actor/ticket/message identifiers,
# the moderator name, and the reply body live *once* in the private embed.
# Do not place those details in the message content again.
_AUDIT_HEADINGS = {
    "PREPARED": "Anonymous ticket reply — pending delivery",
    "ABORTED": "Anonymous ticket reply — not sent",
    "SEND_UNCONFIRMED": "Anonymous ticket reply — delivery unconfirmed",
    "DELIVERED": "Anonymous ticket reply delivered",
}


class PermissionDenied(Exception):
    pass


class TicketRejected(Exception):
    pass


def _role_names(member: discord.Member) -> set[str]:
    return {role.name for role in member.roles}


def _has_access(channel: discord.TextChannel, member: discord.Member) -> bool:
    perms = channel.permissions_for(member)
    return bool(perms.view_channel and perms.send_messages and perms.read_message_history)


def _staff_only(channel: discord.TextChannel, cfg: ReplyConfig) -> bool:
    """Conservative gate: never create private audit/center in public channels.

    Role-level effective permissions also catch an overly broad inherited role
    even when @everyone is denied. Admin roles inherently bypass overwrites.
    """
    guild = channel.guild
    if channel.permissions_for(guild.default_role).view_channel:
        return False
    for role in guild.roles:
        if role == guild.default_role or role.name in cfg.staff_role_names:
            continue
        if role.permissions.administrator:
            continue   # administrators can always see the channel
        if channel.permissions_for(role).view_channel:
            return False
    # Channel-specific member overwrites can grant access despite the role
    # checks above. They must not expose the center/audit to nonstaff users.
    # Fail closed on any individually granted View Channel except for this bot.
    # Operator should use staff roles, not per-member allows, for human staff.
    bot_id = guild.me.id if guild.me is not None else None
    for principal, overwrite in channel.overwrites.items():
        if isinstance(principal, discord.Member):
            if overwrite.view_channel is True and principal.id != bot_id:
                return False
        elif not isinstance(principal, discord.Role):
            return False  # Unrecognized overwrite principal: fail closed.
    return True


def _audit_moderator_name(member: discord.Member) -> str:
    """Staff-only, non-mentionable display-name snapshot for this audit event."""
    raw = getattr(member, "display_name", None) or getattr(member, "name", None) or "Unknown moderator"
    flat = " ".join(str(raw).split()).replace("|", "/") or "Unknown moderator"
    return discord.utils.escape_mentions(discord.utils.escape_markdown(flat))[:128]


class TicketReplyService:
    def __init__(self, bot: discord.Client, cfg: ReplyConfig):
        self.bot = bot
        self.cfg = cfg

    def guild(self, interaction: discord.Interaction) -> discord.Guild:
        guild = interaction.guild
        if guild is None or guild.id != self.cfg.guild_id:
            raise PermissionDenied("This reply center is not available in this server.")
        return guild

    async def member(self, interaction: discord.Interaction) -> discord.Member:
        guild = self.guild(interaction)
        try:
            # Fresh API snapshot; don't authorize using a cached interaction role list.
            member = await guild.fetch_member(interaction.user.id)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            raise PermissionDenied("Current staff authorization could not be verified.") from None
        if not role_authorized(_role_names(member), self.cfg):
            raise PermissionDenied("You do not have access to the ticket reply utility.")
        return member

    async def private_channel(self, ident: int) -> discord.TextChannel:
        try:
            channel = await self.bot.fetch_channel(ident)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            raise PermissionDenied("Private channel could not be verified.") from None
        if (
            not isinstance(channel, discord.TextChannel)
            or channel.guild.id != self.cfg.guild_id
            or not _staff_only(channel, self.cfg)
            or channel.category_id in self.cfg.open_category_ids
        ):
            raise PermissionDenied("Private channel has unsafe or unexpected permissions.")
        me = channel.guild.me
        if me is None or not _has_access(channel, me):
            raise PermissionDenied("Bot lacks required permissions in private channel.")
        return channel

    async def _ticket_tool_origin(self, channel: discord.TextChannel) -> bool:
        """Provider-origin witness, not a name check.

        An actual Ticket Tool-authored opening message near channel creation
        is required. Missing/deleted messages fail closed. No external API is
        assumed; this is a bounded EML DEV adapter, not general TT lifecycle API.
        """
        try:
            async for message in channel.history(limit=12, oldest_first=True):
                if (
                    message.author.id == self.cfg.ticket_tool_bot_id
                    and message.author.bot
                    and abs(message.created_at - channel.created_at) <= timedelta(hours=1)
                ):
                    return True
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            return False
        return False

    async def verify_ticket(self, channel_id: int, member: discord.Member) -> discord.TextChannel:
        try:
            channel = await self.bot.fetch_channel(channel_id)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            raise TicketRejected("Ticket is missing or inaccessible.") from None
        if not isinstance(channel, discord.TextChannel):
            raise TicketRejected("Destination is not a text ticket channel.")
        if channel.guild.id != self.cfg.guild_id:
            raise TicketRejected("Ticket belongs to a different server.")
        if not candidate_category_allowed(channel.category_id, self.cfg):
            raise TicketRejected("Ticket is closed or not in a verified open-ticket category.")
        if not _has_access(channel, member):
            raise TicketRejected("You do not have access to this particular ticket.")
        bot_member = channel.guild.me
        if bot_member is None or not _has_access(channel, bot_member):
            raise TicketRejected("The bot cannot view, send to, and inspect this ticket.")
        if not await self._ticket_tool_origin(channel):
            raise TicketRejected("Ticket Tool origin could not be verified; reply blocked.")
        return channel

    async def discover(self, member: discord.Member) -> list[tuple[int, str, str]]:
        guild = member.guild
        candidates = [
            c for c in guild.text_channels
            if candidate_category_allowed(c.category_id, self.cfg)
            and _has_access(c, member)
        ]
        if len(candidates) > _MAX_CANDIDATES:
            raise TicketRejected("More than 120 possible tickets; narrow the verified categories.")
        # Confirm Ticket Tool origin before showing the ticket to a staff member.
        found: list[tuple[int, str, str]] = []
        for candidate in sorted(candidates, key=lambda c: c.id, reverse=True):
            try:
                channel = await self.verify_ticket(candidate.id, member)
            except TicketRejected:
                continue
            found.append((channel.id, channel.name, channel.category.name if channel.category else "Ticket"))
        return found

    async def deliver(self, interaction: discord.Interaction, channel_id: int, raw_body: str) -> str:
        body = validate_body(raw_body)
        member = await self.member(interaction)
        # Neither the channel nor staff authorization from selector state is trusted.
        channel = await self.verify_ticket(channel_id, member)
        audit = await self.private_channel(self.cfg.audit_channel_id)
        if channel.id in (audit.id, self.cfg.center_channel_id):
            raise TicketRejected("Invalid destination channel.")
        now = datetime.now(timezone.utc)
        moderator_name = _audit_moderator_name(member)
        record = discord.Embed(
            title="Anonymous support response — private audit",
            description=body,
            color=discord.Color.dark_blue(),
            timestamp=now,
        )
        record.add_field(name="Moderator", value=moderator_name)
        record.add_field(name="Ticket channel ID", value=str(channel.id))
        record.add_field(name="Delivery status", value="PREPARED", inline=False)
        # Keep numeric identity as secondary, stable evidence when names change.
        record.add_field(name="Moderator Discord ID", value=str(member.id), inline=False)
        # Safety: create durable private PREPARED record *before* player delivery.
        # If audit creation fails, nothing is sent to the player.
        try:
            pending = await audit.send(
                content=_AUDIT_HEADINGS["PREPARED"],
                embed=record,
                allowed_mentions=discord.AllowedMentions.none(),
            )
        except (discord.Forbidden, discord.HTTPException):
            log.exception("Anonymous ticket reply audit preparation failed, delivery blocked")
            raise TicketRejected("Private audit is unavailable. No reply was sent.") from None

        # Revalidate immediately before send, after audit creation. Ticket Tool
        # may still change ticket state concurrently; there is no shared lock/API.
        try:
            member = await self.member(interaction)
            channel = await self.verify_ticket(channel_id, member)
        except (PermissionDenied, TicketRejected):
            record.set_field_at(2, name="Delivery status", value="ABORTED — authorization/ticket changed", inline=False)
            try:
                await pending.edit(content=_AUDIT_HEADINGS["ABORTED"], embed=record, allowed_mentions=discord.AllowedMentions.none())
            except (discord.Forbidden, discord.HTTPException):
                log.exception("Anonymous reply audit abort finalization failed | record=%s", pending.id)
            raise

        try:
            message = await channel.send(
                player_visible_message(body, self.cfg),
                allowed_mentions=discord.AllowedMentions.none(),
                suppress_embeds=True,
            )
        except (discord.Forbidden, discord.NotFound, discord.HTTPException):
            record.set_field_at(2, name="Delivery status", value="SEND_UNCONFIRMED — check ticket before retry", inline=False)
            try:
                await pending.edit(content=_AUDIT_HEADINGS["SEND_UNCONFIRMED"], embed=record, allowed_mentions=discord.AllowedMentions.none())
            except (discord.Forbidden, discord.HTTPException):
                log.exception("Anonymous reply audit uncertainty finalization failed | record=%s", pending.id)
            raise TicketRejected("Delivery not confirmed. Check the ticket and private audit before retrying.") from None

        record.set_field_at(2, name="Delivery status", value=f"DELIVERED — {message.id}", inline=False)
        record.add_field(name="Delivered message link", value=message.jump_url, inline=False)
        try:
            await pending.edit(
                content=_AUDIT_HEADINGS["DELIVERED"],
                embed=record,
                allowed_mentions=discord.AllowedMentions.none(),
            )
        except (discord.Forbidden, discord.HTTPException):
            # The PREPARED record persists. Never claim audited success.
            log.exception(
                "Anonymous reply delivered but audit finalization failed | actor=%s ticket=%s msg=%s audit=%s",
                member.id, channel.id, message.id, pending.id,
            )
            return (
                f"Reply delivered to <#{channel.id}> (message `{message.id}`), "
                f"but private audit finalization FAILED. Notify Board; do not resend. "
                f"Audit record `{pending.id}`."
            )
        log.info("Anonymous ticket reply delivered | ticket=%s message=%s audit=%s", channel.id, message.id, pending.id)
        return f"Reply sent to <#{channel.id}>. Message `{message.id}`. Private audit recorded."


class ReplyModal(discord.ui.Modal, title="Reply to Ticket"):
    reply = discord.ui.Label(
        text="Your anonymous reply",
        component=discord.ui.TextInput(
            placeholder="Enter the response the player should see...",
            style=discord.TextStyle.paragraph,
            min_length=1,
            max_length=1800,
            required=True,
        ),
    )

    def __init__(self, service: TicketReplyService, ticket_id: int, invoker_id: int):
        super().__init__(timeout=600)
        self.service = service
        self.ticket_id = ticket_id
        self.invoker_id = invoker_id
        self._attempted = False
        self._lock = asyncio.Lock()

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)
        if interaction.user.id != self.invoker_id:
            await interaction.followup.send("This reply form belongs to another staff member.", ephemeral=True)
            return
        async with self._lock:
            if self._attempted:
                await interaction.followup.send("This form was already submitted.", ephemeral=True)
                return
            self._attempted = True
        try:
            result = await self.service.deliver(interaction, self.ticket_id, str(self.reply.component.value))
        except (PermissionDenied, TicketRejected, ReplyValidationError) as exc:
            result = str(exc)
        except Exception:
            log.exception("Anonymous ticket reply unexpected delivery error")
            result = "Unexpected error. Delivery state is uncertain; check private audit and ticket before retrying."
        await interaction.followup.send(result, ephemeral=True, allowed_mentions=discord.AllowedMentions.none())


class DirectTicketButton(discord.ui.Button):
    """Direct-to-modal navigation, never an authorization decision."""

    def __init__(self, dashboard: "TicketDashboard", ticket_id: int, label: str, row: int):
        super().__init__(
            label=label,
            style=discord.ButtonStyle.primary,
            custom_id=f"{_BUTTON_MARKER}{ticket_id}",
            row=row,
        )
        self.dashboard = dashboard
        self.ticket_id = ticket_id

    async def callback(self, interaction: discord.Interaction) -> None:
        service = self.dashboard.service

        async def preflight() -> discord.Member:
            service.guild(interaction)
            if interaction.channel_id != service.cfg.center_channel_id:
                raise PermissionDenied("Ticket buttons may only be used in the designated staff center.")
            if not interaction.message or interaction.message.id not in self.dashboard.panel_ids:
                raise PermissionDenied("This ticket dashboard message is no longer current.")
            center = await service.private_channel(service.cfg.center_channel_id)
            member = await service.member(interaction)
            if not _has_access(center, member):
                raise PermissionDenied("You cannot access the staff reply center.")
            # Ticket Tool may have closed/moved/deleted the ticket since rendering.
            await service.verify_ticket(self.ticket_id, member)
            return member

        try:
            # send_modal must be the initial response within Discord's short
            # interaction window; it cannot follow a deferred response. Fail
            # closed quickly if the fresh REST permission/origin check is slow.
            member = await asyncio.wait_for(preflight(), timeout=1.8)
            await interaction.response.send_modal(ReplyModal(service, self.ticket_id, member.id))
        except asyncio.TimeoutError:
            await interaction.response.send_message(
                "Ticket verification timed out. No reply was sent; please try again.",
                ephemeral=True,
                allowed_mentions=discord.AllowedMentions.none(),
            )
        except (PermissionDenied, TicketRejected) as exc:
            await interaction.response.send_message(
                str(exc), ephemeral=True, allowed_mentions=discord.AllowedMentions.none()
            )
        except Exception:
            log.exception("Anonymous ticket dashboard button failed | ticket=%s", self.ticket_id)
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "Ticket verification failed. No reply was sent.",
                    ephemeral=True,
                    allowed_mentions=discord.AllowedMentions.none(),
                )


class TicketDashboardView(discord.ui.View):
    def __init__(self, dashboard: "TicketDashboard", tickets: list[tuple[int, str]]):
        super().__init__(timeout=None)
        for i, (ticket_id, ticket_label) in enumerate(tickets):
            self.add_item(DirectTicketButton(dashboard, ticket_id, ticket_label, i // 5))


class TicketDashboard:
    """Reconciles a private, bot-authored, button-only ticket dashboard.

    No SQL state; surviving panels are rediscovered by bot author + embed marker.
    An administrator first creates the panel using the existing setup command.
    Subsequent reconciliation edits that message in place and can add/remove
    overflow pages (25 buttons per Discord message, max 120 tickets).
    """

    def __init__(self, service: TicketReplyService):
        self.service = service
        self.bot = service.bot
        self.panel_ids: set[int] = set()
        self._lock = asyncio.Lock()
        self._periodic_task: asyncio.Task | None = None
        self._pending_task: asyncio.Task | None = None

    async def _verified_tickets(self) -> list[tuple[int, str]]:
        cfg = self.service.cfg
        guild = self.bot.get_guild(cfg.guild_id)
        if guild is None or guild.me is None:
            raise TicketRejected("Configured DEV guild or bot member is unavailable.")
        candidates = [
            ch for ch in guild.text_channels
            if candidate_category_allowed(ch.category_id, cfg)
        ]
        if len(candidates) > _MAX_CANDIDATES:
            raise TicketRejected("More than 120 candidate tickets; dashboard update blocked.")
        verified: list[tuple[int, str]] = []
        # A shared staff dashboard shows sanitized ticket numbers only. Per-staff
        # access is checked when a button is pressed, not used to publish labels.
        for ch in sorted(candidates, key=lambda item: item.id):
            try:
                confirmed = await self.service.verify_ticket(ch.id, guild.me)
            except TicketRejected:
                continue
            verified.append((confirmed.id, dashboard_button_label(confirmed.name, confirmed.id)))
        return verified

    async def _existing_panels(self, center: discord.TextChannel) -> list[discord.Message]:
        result: list[discord.Message] = []
        # The current RC1.1 message has the exact title but no V2 footer.
        # An old V1 panel must be edited, not left active alongside V2.
        observed = 0
        async for msg in center.history(limit=_PANEL_SEARCH_LIMIT):
            observed += 1
            if msg.author.id != self.bot.user.id:
                continue
            for embed in msg.embeds:
                if embed.title != _CENTER_TITLE:
                    continue
                footer = embed.footer.text or ""
                if not footer or footer.startswith(_DASHBOARD_MARKER):
                    result.append(msg)
                break
        if observed >= _PANEL_SEARCH_LIMIT:
            # History limit exhaustion could hide an older dashboard. Do not
            # create duplicate panels or leave undiscovered old buttons active.
            raise TicketRejected("Reply center history exceeds the safe panel scan; administrator review required.")
        return sorted(result, key=lambda msg: (msg.created_at, msg.id))

    def _embed(self, total: int, page: int, page_count: int) -> discord.Embed:
        description = (
            f"{total} verified open Ticket Tool ticket(s). "
            "Click a ticket to compose a private, bot-authored response. "
            "Replies are audited privately."
            if total else "No verified open Ticket Tool tickets. This panel updates automatically."
        )
        embed = discord.Embed(title=_CENTER_TITLE, description=description)
        embed.set_footer(text=f"{_DASHBOARD_MARKER}{page + 1}/{page_count}")
        return embed

    async def reconcile(self, *, allow_create: bool = False) -> str | None:
        async with self._lock:
            center = await self.service.private_channel(self.service.cfg.center_channel_id)
            # Avoid a public ticket board if the audit privacy gate fails later.
            await self.service.private_channel(self.service.cfg.audit_channel_id)
            existing = await self._existing_panels(center)
            if not existing and not allow_create:
                self.panel_ids.clear()
                return None  # No implicit first-time publication without Board/Commissioner setup.
            tickets = await self._verified_tickets()
            pages = dashboard_pages(tickets)
            if not pages:
                pages = [[]]
            total = len(tickets)
            new_panel_ids: set[int] = set()
            first_url: str | None = None
            for i, rows in enumerate(pages):
                view = TicketDashboardView(self, rows) if rows else None
                embed = self._embed(total, i, len(pages))
                if i < len(existing):
                    msg = existing[i]
                    await msg.edit(embed=embed, view=view, allowed_mentions=discord.AllowedMentions.none())
                else:
                    msg = await center.send(embed=embed, view=view, allowed_mentions=discord.AllowedMentions.none())
                new_panel_ids.add(msg.id)
                if first_url is None:
                    first_url = msg.jump_url
                if view is not None:
                    # Explicit persistent registration for bot restarts; views
                    # also get bound by discord.py during send/edit.
                    self.bot.add_view(view, message_id=msg.id)
            # Old overflow pages and duplicate V1 panels belong to this bot and
            # are safely removable; no human-authored channel messages touched.
            for msg in existing[len(pages):]:
                await msg.delete()
            self.panel_ids = new_panel_ids
            log.info("Anonymous ticket dashboard reconciled | tickets=%s pages=%s", total, len(pages))
            return first_url

    async def safe_reconcile(self) -> None:
        try:
            await self.reconcile()
        except (PermissionDenied, TicketRejected, discord.Forbidden, discord.HTTPException):
            log.warning("Anonymous ticket dashboard refresh blocked; existing button authorization remains enforced", exc_info=True)
        except Exception:
            log.exception("Anonymous ticket dashboard unexpected refresh failure")

    async def _delayed_reconcile(self, delay_seconds: float) -> None:
        await asyncio.sleep(delay_seconds)
        await self.safe_reconcile()

    def schedule_reconcile(self, delay_seconds: float = 3) -> None:
        if self._pending_task is None or self._pending_task.done():
            self._pending_task = asyncio.create_task(self._delayed_reconcile(delay_seconds))

    async def _periodic_reconcile(self) -> None:
        while not self.bot.is_closed():
            await asyncio.sleep(_REFRESH_INTERVAL_SECONDS)
            await self.safe_reconcile()

    async def on_ready(self) -> None:
        if self._periodic_task is None or self._periodic_task.done():
            self._periodic_task = asyncio.create_task(self._periodic_reconcile())
        await self.safe_reconcile()

    async def on_guild_channel_create(self, channel: discord.abc.GuildChannel) -> None:
        if channel.guild.id == self.service.cfg.guild_id:
            self.schedule_reconcile(12)  # Ticket Tool origin may arrive after channel creation.

    async def on_guild_channel_update(
        self, before: discord.abc.GuildChannel, after: discord.abc.GuildChannel
    ) -> None:
        if after.guild.id == self.service.cfg.guild_id:
            self.schedule_reconcile(3)

    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel) -> None:
        if channel.guild.id == self.service.cfg.guild_id:
            self.schedule_reconcile(3)

    async def on_message(self, message: discord.Message) -> None:
        cfg = self.service.cfg
        if (
            message.guild is not None
            and message.guild.id == cfg.guild_id
            and message.author.id == cfg.ticket_tool_bot_id
            and isinstance(message.channel, discord.TextChannel)
            and candidate_category_allowed(message.channel.category_id, cfg)
        ):
            self.schedule_reconcile(3)


def register(bot: discord.ext.commands.Bot, environ=None) -> bool:
    env = environ if environ is not None else os.environ
    if env.get("EML_ANON_TICKET_REPLIES_ENABLED", "0") != "1":
        log.info("Anonymous ticket replies disabled by feature flag")
        return False
    try:
        cfg = ReplyConfig.from_env(env)
    except ReplyConfigurationError:
        log.exception("Anonymous ticket replies enabled with invalid configuration; refusing registration")
        raise
    service = TicketReplyService(bot, cfg)
    dashboard = TicketDashboard(service)
    bot.add_listener(dashboard.on_ready, name="on_ready")
    bot.add_listener(dashboard.on_guild_channel_create, name="on_guild_channel_create")
    bot.add_listener(dashboard.on_guild_channel_update, name="on_guild_channel_update")
    bot.add_listener(dashboard.on_guild_channel_delete, name="on_guild_channel_delete")
    bot.add_listener(dashboard.on_message, name="on_message")

    @bot.tree.command(name="ticket_reply_center_setup", description="Board/Commissioner: initialize the private direct-ticket dashboard")
    async def ticket_reply_center_setup(interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            member = await service.member(interaction)
            if not ({"Board", "Commissioner"} & _role_names(member)):
                raise PermissionDenied("Only Board or Commissioner can initialize the reply center.")
            if interaction.channel_id != cfg.center_channel_id:
                raise PermissionDenied("Run setup in the configured staff reply center channel.")
            center = await service.private_channel(cfg.center_channel_id)
            if not _has_access(center, member):
                raise PermissionDenied("You cannot access the configured center.")
            url = await dashboard.reconcile(allow_create=True)
            await interaction.followup.send(
                f"Direct-ticket dashboard ready: {url}",
                ephemeral=True,
                allowed_mentions=discord.AllowedMentions.none(),
            )
        except (PermissionDenied, TicketRejected) as exc:
            await interaction.followup.send(str(exc), ephemeral=True)
        except (discord.Forbidden, discord.HTTPException):
            log.exception("Unable to initialize anonymous direct-ticket dashboard")
            await interaction.followup.send("Dashboard setup failed; check bot/channel permissions.", ephemeral=True)
        except Exception:
            log.exception("Anonymous dashboard initialization error")
            await interaction.followup.send("Dashboard setup failed safely. No reply was sent.", ephemeral=True)

    log.info("Anonymous ticket reply feature registered | guild=%s open_categories=%s dashboard=v2", cfg.guild_id, len(cfg.open_category_ids))
    return True
