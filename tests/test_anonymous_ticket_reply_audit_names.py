"""Offline DEV RC1.2a audit-name regression tests; no Discord API access."""
from __future__ import annotations

import ast
import asyncio
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock

from utils.anonymous_ticket_reply_core import player_visible_message, validate_body

SOURCE = Path(__file__).resolve().parent.parent / 'utils' / 'anonymous_ticket_reply.py'


class FakeDiscord:
    class utils:
        @staticmethod
        def escape_markdown(value):
            return value.replace('*', '\\*').replace('`', '\\`')

        @staticmethod
        def escape_mentions(value):
            return value.replace('@', '@\u200b')

    class Color:
        @staticmethod
        def dark_blue():
            return None

    class AllowedMentions:
        @staticmethod
        def none():
            return 'NO_MENTIONS'

    class Embed:
        def __init__(self, title, description, color, timestamp):
            self.title, self.description = title, description
            self.fields = []

        def add_field(self, name, value, inline=True):
            self.fields.append(SimpleNamespace(name=name, value=value, inline=inline))

        def set_field_at(self, idx, name, value, inline=True):
            self.fields[idx] = SimpleNamespace(name=name, value=value, inline=inline)

    class Forbidden(Exception):
        pass

    class NotFound(Exception):
        pass

    class HTTPException(Exception):
        pass


class FakeChannel:
    def __init__(self, channel_id, is_audit=False):
        self.id = channel_id
        self.is_audit = is_audit
        self.calls = []
        self.record = None

    async def send(self, content, embed=None, allowed_mentions=None, suppress_embeds=False):
        self.calls.append((content, embed, allowed_mentions))
        assert allowed_mentions == 'NO_MENTIONS'
        if self.is_audit:
            self.record = SimpleNamespace(id=8888, content=content, embed=embed, edits=[])

            async def edit(**kw):
                self.record.edits.append(kw)
                self.record.content = kw['content']
                self.record.embed = kw['embed']
            self.record.edit = edit
            return self.record
        return SimpleNamespace(id=9999, jump_url='https://discord.com/channels/1/42/9999')


def load_audit_implementation():
    tree = ast.parse(SOURCE.read_text(encoding='utf-8'))
    name_helper = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == '_audit_moderator_name')
    service_class = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'TicketReplyService')
    headings = next(
        node for node in tree.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == '_AUDIT_HEADINGS' for target in node.targets)
    )
    module = ast.Module(body=[
        ast.ImportFrom(module='__future__', names=[ast.alias(name='annotations')], level=0),
        headings, name_helper, service_class,
    ], type_ignores=[])
    ns = {
        'discord': FakeDiscord,
        'datetime': datetime, 'timezone': timezone,
        'validate_body': validate_body,
        'player_visible_message': player_visible_message,
        'PermissionDenied': type('PermissionDenied', (Exception,), {}),
        'TicketRejected': type('TicketRejected', (Exception,), {}),
        'log': SimpleNamespace(exception=lambda *args, **kwargs: None, info=lambda *args, **kwargs: None),
    }
    exec(compile(ast.fix_missing_locations(module), str(SOURCE), 'exec'), ns)
    return ns


class ModeratorNameTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.code = load_audit_implementation()

    def test_prefers_current_server_display_name(self):
        member = SimpleNamespace(display_name='Doon', name='other_username')
        self.assertEqual(self.code['_audit_moderator_name'](member), 'Doon')

    def test_falls_back_to_username(self):
        member = SimpleNamespace(display_name=None, name='modname')
        self.assertEqual(self.code['_audit_moderator_name'](member), 'modname')

    def test_sanitizes_markup_mention_newlines_and_delimiter(self):
        member = SimpleNamespace(display_name='@everyone | **Mod**\nName', name='modname')
        result = self.code['_audit_moderator_name'](member)
        self.assertNotIn('@everyone', result)
        self.assertNotIn('|', result)
        self.assertNotIn('\n', result)
        self.assertIn('Mod', result)

    def test_empty_display_name_does_not_make_empty_audit(self):
        member = SimpleNamespace(display_name='\n  ', name='fallback')
        self.assertEqual(self.code['_audit_moderator_name'](member), 'Unknown moderator')

    def test_capped_name_length(self):
        member = SimpleNamespace(display_name='a' * 500, name='fallback')
        self.assertLessEqual(len(self.code['_audit_moderator_name'](member)), 128)


class ModeratorAuditDeliveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_delivered_audit_has_name_and_id_player_message_has_neither(self):
        code = load_audit_implementation()
        Service = code['TicketReplyService']
        service = object.__new__(Service)
        service.cfg = SimpleNamespace(audit_channel_id=11, center_channel_id=12, header='EML Support')
        member = SimpleNamespace(id=614943840146554886, display_name='Doon', name='discord_username')
        ticket = FakeChannel(42)
        audit = FakeChannel(11, is_audit=True)
        service.member = AsyncMock(return_value=member)
        service.verify_ticket = AsyncMock(return_value=ticket)
        service.private_channel = AsyncMock(return_value=audit)
        result = await service.deliver(SimpleNamespace(), 42, 'test message')
        self.assertIn('Private audit recorded', result)
        self.assertEqual(len(ticket.calls), 1)
        self.assertEqual(ticket.calls[0][0], '**EML Support**\n\ntest message')
        self.assertNotIn('Doon', ticket.calls[0][0])
        self.assertNotIn(str(member.id), ticket.calls[0][0])
        self.assertEqual(audit.record.embed.fields[0].name, 'Moderator')
        self.assertEqual(audit.record.embed.fields[0].value, 'Doon')
        self.assertEqual(audit.record.embed.fields[2].name, 'Delivery status')
        self.assertIn('DELIVERED', audit.record.embed.fields[2].value)
        self.assertEqual(audit.record.embed.fields[3].name, 'Moderator Discord ID')
        self.assertEqual(audit.record.embed.fields[3].value, str(member.id))
        self.assertEqual(audit.record.content, 'Anonymous ticket reply delivered')
        self.assertNotIn('Doon', audit.record.content)
        self.assertNotIn(str(member.id), audit.record.content)
        self.assertNotIn(str(ticket.id), audit.record.content)

    async def test_audit_prepared_before_player_delivery(self):
        code = load_audit_implementation()
        Service = code['TicketReplyService']
        service = object.__new__(Service)
        service.cfg = SimpleNamespace(audit_channel_id=11, center_channel_id=12, header='EML Support')
        member = SimpleNamespace(id=3, display_name='Test Mod', name='user')
        calls = []
        ticket, audit = FakeChannel(42), FakeChannel(11, is_audit=True)
        ticket_send = ticket.send
        audit_send = audit.send

        async def tsend(*args, **kwargs):
            calls.append('ticket')
            return await ticket_send(*args, **kwargs)

        async def asend(*args, **kwargs):
            calls.append('audit')
            return await audit_send(*args, **kwargs)

        ticket.send = tsend
        audit.send = asend
        service.member = AsyncMock(return_value=member)
        service.verify_ticket = AsyncMock(return_value=ticket)
        service.private_channel = AsyncMock(return_value=audit)
        await service.deliver(SimpleNamespace(), 42, 'test')
        self.assertEqual(calls, ['audit', 'ticket'])


if __name__ == '__main__':
    unittest.main()
