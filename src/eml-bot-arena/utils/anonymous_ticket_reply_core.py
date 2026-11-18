"""Provider-independent validation/config for anonymous support replies.

No Discord, SQL, Ticket Tool API, EML or EchoVRCE imports. Reusable core.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Mapping


class ReplyConfigurationError(ValueError):
    """Unsafe or incomplete configuration; fail closed."""


class ReplyValidationError(ValueError):
    """Reply rejected before delivery."""


def _snowflake(value: str | None, key: str) -> int:
    raw = (value or "").strip()
    if not raw.isdecimal():
        raise ReplyConfigurationError(f"{key} must be a numeric Discord ID")
    number = int(raw)
    if number <= 0:
        raise ReplyConfigurationError(f"{key} must be positive")
    return number


def _ids(value: str | None, key: str) -> tuple[int, ...]:
    tokens = [s.strip() for s in (value or "").split(",") if s.strip()]
    if not tokens:
        raise ReplyConfigurationError(f"{key} must include one or more category IDs")
    numbers = tuple(_snowflake(token, key) for token in tokens)
    if len(numbers) != len(set(numbers)):
        raise ReplyConfigurationError(f"{key} must not contain duplicate IDs")
    return numbers


@dataclass(frozen=True)
class ReplyConfig:
    guild_id: int
    center_channel_id: int
    audit_channel_id: int
    ticket_tool_bot_id: int
    open_category_ids: tuple[int, ...]
    closed_category_ids: tuple[int, ...]
    staff_role_names: frozenset[str]
    header: str

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> "ReplyConfig":
        # Guild ID and role matching use existing EML conventions. Provider
        # identifiers and channel/category identifiers are not role IDs.
        roles = frozenset(
            token.strip() for token in
            env.get("EML_ANON_TICKET_STAFF_ROLE_NAMES", "League Mod,Commissioner,Board").split(",")
            if token.strip()
        )
        if not roles:
            raise ReplyConfigurationError("EML_ANON_TICKET_STAFF_ROLE_NAMES is empty")
        header = env.get("EML_ANON_TICKET_SUPPORT_HEADING", "EML Support").strip()
        if not header or len(header) > 80 or "\n" in header or "@" in header:
            raise ReplyConfigurationError("Invalid support heading")
        cfg = cls(
            guild_id=_snowflake(env.get("GUILD_ID"), "GUILD_ID"),
            center_channel_id=_snowflake(env.get("EML_ANON_TICKET_CENTER_CHANNEL_ID"), "CENTER_CHANNEL_ID"),
            audit_channel_id=_snowflake(env.get("EML_ANON_TICKET_AUDIT_CHANNEL_ID"), "AUDIT_CHANNEL_ID"),
            ticket_tool_bot_id=_snowflake(env.get("EML_TICKET_TOOL_BOT_ID"), "TICKET_TOOL_BOT_ID"),
            open_category_ids=_ids(env.get("EML_TICKET_OPEN_CATEGORY_IDS"), "OPEN_CATEGORY_IDS"),
            closed_category_ids=(
                _ids(env.get("EML_TICKET_CLOSED_CATEGORY_IDS"), "CLOSED_CATEGORY_IDS")
                if (env.get("EML_TICKET_CLOSED_CATEGORY_IDS") or "").strip()
                else ()
            ),
            staff_role_names=roles,
            header=header,
        )
        if cfg.center_channel_id == cfg.audit_channel_id:
            raise ReplyConfigurationError("Center and audit channels must be separate")
        all_categories = cfg.open_category_ids + cfg.closed_category_ids
        if len(all_categories) != len(set(all_categories)):
            raise ReplyConfigurationError("Open and closed categories must not overlap")
        if cfg.center_channel_id in all_categories or cfg.audit_channel_id in all_categories:
            raise ReplyConfigurationError("Center/audit IDs must not be ticket category IDs")
        return cfg


def role_authorized(role_names: set[str] | frozenset[str], config: ReplyConfig) -> bool:
    return bool(set(role_names).intersection(config.staff_role_names))


def candidate_category_allowed(category_id: int | None, config: ReplyConfig) -> bool:
    return category_id is not None and category_id in config.open_category_ids


def validate_body(value: str) -> str:
    body = value.strip()
    if not body:
        raise ReplyValidationError("Reply must contain text")
    if len(body) > 1800:
        raise ReplyValidationError("Reply exceeds 1,800 characters")
    return body


def player_visible_message(body: str, config: ReplyConfig) -> str:
    return f"**{config.header}**\n\n{validate_body(body)}"


def dashboard_button_label(channel_name: str, channel_id: int) -> str:
    """Never surface free-form ticket names (which may contain player names)."""
    if re.fullmatch(r"ticket-[0-9]{1,12}", channel_name):
        return channel_name
    return f"ticket-{channel_id}"


def dashboard_pages(rows: list[tuple[int, str]]) -> list[list[tuple[int, str]]]:
    """Discord supports at most 25 buttons (5 rows of 5) per message."""
    if len(rows) > 120:
        raise ReplyValidationError("Too many open tickets for the verified dashboard")
    return [rows[i:i + 25] for i in range(0, len(rows), 25)]
