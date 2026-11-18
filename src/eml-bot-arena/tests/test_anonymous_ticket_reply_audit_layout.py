"""DEV RC1.2b audit presentation regression: state changes remain private and unambiguous.

Loads the real service method with isolated fake Discord objects; no API or DB calls.
"""
from __future__ import annotations

from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock

if __package__:
    from .test_anonymous_ticket_reply_audit_names import (
        FakeChannel,
        FakeDiscord,
        load_audit_implementation,
    )
else:
    from test_anonymous_ticket_reply_audit_names import (
        FakeChannel,
        FakeDiscord,
        load_audit_implementation,
    )


class PrivateAuditLayoutTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.code = load_audit_implementation()
        service_cls = self.code['TicketReplyService']
        self.service = object.__new__(service_cls)
        self.service.cfg = SimpleNamespace(audit_channel_id=11, center_channel_id=12, header='EML Support')
        self.member = SimpleNamespace(id=614943840146554886, display_name='Doon', name='another_name')
        self.ticket = FakeChannel(42)
        self.audit = FakeChannel(11, is_audit=True)
        self.service.member = AsyncMock(return_value=self.member)
        self.service.verify_ticket = AsyncMock(return_value=self.ticket)
        self.service.private_channel = AsyncMock(return_value=self.audit)

    def assert_headline_is_only_status(self, expected: str):
        content = self.audit.record.content
        self.assertEqual(content, expected)
        for value in ('Doon', '614943840146554886', '42', '9999', 'test body'):
            self.assertNotIn(value, content)

    async def test_success_has_one_readable_audit_detail_set(self):
        result = await self.service.deliver(SimpleNamespace(), 42, 'test body')
        self.assertIn('Private audit recorded', result)
        self.assert_headline_is_only_status('Anonymous ticket reply delivered')
        embed = self.audit.record.embed
        self.assertEqual(embed.description, 'test body')
        self.assertEqual([f.name for f in embed.fields], [
            'Moderator', 'Ticket channel ID', 'Delivery status',
            'Moderator Discord ID', 'Delivered message link',
        ])
        self.assertEqual(embed.fields[0].value, 'Doon')
        self.assertEqual(embed.fields[1].value, '42')
        self.assertEqual(embed.fields[2].value, 'DELIVERED — 9999')
        self.assertEqual(embed.fields[3].value, '614943840146554886')
        self.assertIn('/42/9999', embed.fields[4].value)
        self.assertEqual(self.audit.record.edits[0]['allowed_mentions'], 'NO_MENTIONS')
        self.assertEqual(self.ticket.calls[0][0], '**EML Support**\n\ntest body')

    async def test_prepared_audit_precedes_send_and_is_not_duplicated(self):
        async def ticket_send(*args, **kwargs):
            self.assertEqual(self.audit.record.content, 'Anonymous ticket reply — pending delivery')
            self.assertEqual(self.audit.record.embed.fields[2].value, 'PREPARED')
            self.assertNotIn('Doon', self.audit.record.content)
            return SimpleNamespace(id=9999, jump_url='https://discord.com/channels/1/42/9999')
        self.ticket.send = ticket_send
        await self.service.deliver(SimpleNamespace(), 42, 'test body')
        self.assert_headline_is_only_status('Anonymous ticket reply delivered')

    async def test_abort_maintains_failure_status_without_player_send(self):
        exc = self.code['TicketRejected']
        self.service.verify_ticket = AsyncMock(side_effect=[self.ticket, exc('Ticket closed')])
        with self.assertRaises(exc):
            await self.service.deliver(SimpleNamespace(), 42, 'test body')
        self.assert_headline_is_only_status('Anonymous ticket reply — not sent')
        self.assertIn('ABORTED', self.audit.record.embed.fields[2].value)
        self.assertFalse(self.ticket.calls)
        self.assertEqual(self.audit.record.edits[0]['allowed_mentions'], 'NO_MENTIONS')

    async def test_send_unconfirmed_never_claims_delivery(self):
        self.ticket.send = AsyncMock(side_effect=FakeDiscord.HTTPException('send failed'))
        exc = self.code['TicketRejected']
        with self.assertRaises(exc):
            await self.service.deliver(SimpleNamespace(), 42, 'test body')
        self.assert_headline_is_only_status('Anonymous ticket reply — delivery unconfirmed')
        self.assertIn('SEND_UNCONFIRMED', self.audit.record.embed.fields[2].value)
        self.assertEqual(self.audit.record.edits[0]['allowed_mentions'], 'NO_MENTIONS')

    async def test_audit_finalization_failure_does_not_claim_audited_success(self):
        original_send = self.audit.send
        async def fail_finalize(*args, **kwargs):
            pending = await original_send(*args, **kwargs)
            pending.edit = AsyncMock(side_effect=FakeDiscord.HTTPException('audit unavailable'))
            return pending
        self.audit.send = fail_finalize
        result = await self.service.deliver(SimpleNamespace(), 42, 'test body')
        self.assertIn('finalization FAILED', result)
        self.assertEqual(self.audit.record.content, 'Anonymous ticket reply — pending delivery')
        self.assertEqual(self.audit.record.embed.fields[2].value, 'DELIVERED — 9999')
        self.assertEqual(len(self.ticket.calls), 1)


if __name__ == '__main__':
    unittest.main()
