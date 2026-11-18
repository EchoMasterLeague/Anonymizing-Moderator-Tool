"""Behavioral dashboard reconciliation tests without Discord API access."""
import ast
import asyncio
import pathlib
import types
import unittest
from datetime import datetime, timezone
from unittest.mock import AsyncMock

from utils.anonymous_ticket_reply_core import dashboard_pages

ADAPTER = pathlib.Path(__file__).resolve().parent.parent / 'utils' / 'anonymous_ticket_reply.py'


class FakeEmbed:
    def __init__(self, title=None, description=None):
        self.title = title
        self.description = description
        self.footer = types.SimpleNamespace(text=None)

    def set_footer(self, *, text):
        self.footer.text = text


class FakeMessage:
    def __init__(self, ident, embed, author_id=123):
        self.id = ident
        self.author = types.SimpleNamespace(id=author_id)
        self.embeds = [embed]
        self.created_at = datetime.now(timezone.utc)
        self.jump_url = f'https://discord.com/channels/1/2/{ident}'
        self.edit_calls = []
        self.deleted = False

    async def edit(self, *, embed, view, allowed_mentions):
        self.edit_calls.append((embed, view))
        self.embeds = [embed]

    async def delete(self):
        self.deleted = True


class FakeChannel:
    def __init__(self, messages):
        self.messages = messages
        self.sends = 0

    async def history(self, limit):
        for m in reversed(self.messages[-limit:]):
            if not m.deleted:
                yield m

    async def send(self, *, embed, view, allowed_mentions):
        self.sends += 1
        msg = FakeMessage(2000 + self.sends, embed)
        self.messages.append(msg)
        return msg


class DashboardBehaviorTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        tree = ast.parse(ADAPTER.read_text(encoding='utf-8'))
        dashboard_class = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'TicketDashboard')
        fake_discord = types.SimpleNamespace(
            Embed=FakeEmbed,
            AllowedMentions=types.SimpleNamespace(none=lambda: None),
            Forbidden=type('Forbidden', (Exception,), {}),
            HTTPException=type('HTTPException', (Exception,), {}),
        )
        namespace = {
            'asyncio': asyncio, 'discord': fake_discord,
            '_DASHBOARD_MARKER': 'eml:anonymous-ticket-reply:v2:page=',
            '_CENTER_TITLE': 'EML Ticket Reply Center',
            '_PANEL_SEARCH_LIMIT': 200,
            '_REFRESH_INTERVAL_SECONDS': 120,
            'dashboard_pages': dashboard_pages,
            'TicketRejected': type('TicketRejected', (Exception,), {}),
            'PermissionDenied': type('PermissionDenied', (Exception,), {}),
            'TicketDashboardView': lambda dash, rows: types.SimpleNamespace(rows=rows),
            'log': types.SimpleNamespace(info=lambda *a, **kw: None),
        }
        # Postpone annotations so no discord library is needed for offline tests.
        module = ast.Module(body=[ast.ImportFrom(module='__future__', names=[ast.alias(name='annotations')], level=0),dashboard_class],type_ignores=[])
        exec(compile(ast.fix_missing_locations(module), str(ADAPTER), 'exec'), namespace)
        self.dashboard_cls = namespace['TicketDashboard']
        legacy = FakeEmbed(title='EML Ticket Reply Center', description='old dropdown')
        self.legacy = FakeMessage(1001, legacy)
        self.center = FakeChannel([self.legacy])
        bot = types.SimpleNamespace(user=types.SimpleNamespace(id=123), add_view=lambda view, message_id: None)
        self.added_views = []
        bot.add_view = lambda view, message_id: self.added_views.append((view, message_id))
        service = types.SimpleNamespace(
            bot=bot,
            cfg=types.SimpleNamespace(center_channel_id=1, audit_channel_id=2),
        )

        async def private_channel(ident):
            return self.center if ident == 1 else FakeChannel([])

        service.private_channel = private_channel
        self.dashboard = self.dashboard_cls(service)

    async def test_existing_legacy_panel_is_edited_not_duplicated(self):
        self.dashboard._verified_tickets = AsyncMock(return_value=[(999, 'ticket-0001')])
        url = await self.dashboard.reconcile()
        self.assertEqual(url, self.legacy.jump_url)
        self.assertEqual(self.center.sends, 0)
        self.assertEqual(self.dashboard.panel_ids, {1001})
        self.assertEqual(self.legacy.edit_calls[-1][1].rows, [(999, 'ticket-0001')])
        self.assertEqual(self.added_views[-1][1], 1001)

    async def test_closed_ticket_removes_button_from_existing_panel(self):
        self.dashboard._verified_tickets = AsyncMock(side_effect=[[(999, 'ticket-0001')], []])
        await self.dashboard.reconcile()
        await self.dashboard.reconcile()
        self.assertIsNone(self.legacy.edit_calls[-1][1])
        self.assertEqual(self.center.sends, 0)
        self.assertIn('No verified', self.legacy.embeds[0].description)

    async def test_twenty_six_create_second_page_then_delete_when_shrunk(self):
        rows = [(i + 100, f'ticket-{i:04d}') for i in range(26)]
        self.dashboard._verified_tickets = AsyncMock(side_effect=[rows, rows[:1]])
        await self.dashboard.reconcile()
        self.assertEqual(self.center.sends, 1)
        extra = self.center.messages[-1]
        self.assertEqual(len(self.legacy.edit_calls[-1][1].rows), 25)
        self.assertEqual(len(self.added_views[-1][0].rows), 1)
        await self.dashboard.reconcile()
        self.assertTrue(extra.deleted)
        self.assertEqual(self.dashboard.panel_ids, {1001})

    async def test_no_first_panel_does_not_publish_without_setup(self):
        self.center.messages.clear()
        self.dashboard._verified_tickets = AsyncMock(return_value=[])
        self.assertIsNone(await self.dashboard.reconcile())
        self.assertEqual(self.center.sends, 0)
        self.dashboard._verified_tickets.assert_not_called()
        await self.dashboard.reconcile(allow_create=True)
        self.assertEqual(self.center.sends, 1)


if __name__ == '__main__':
    unittest.main()
