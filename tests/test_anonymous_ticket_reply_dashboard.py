"""RC1.2 DEV-only offline contract tests. No Discord token/network required."""
import ast
import pathlib
import unittest

from utils.anonymous_ticket_reply_core import (
    ReplyValidationError,
    dashboard_button_label,
    dashboard_pages,
)

ADAPTER = pathlib.Path(__file__).resolve().parent.parent / 'utils' / 'anonymous_ticket_reply.py'


class DashboardCoreTests(unittest.TestCase):
    def test_ticket_number_kept(self):
        self.assertEqual(dashboard_button_label('ticket-0001', 12345), 'ticket-0001')

    def test_player_name_not_leaked_into_label(self):
        self.assertEqual(dashboard_button_label('ticket-john-smith', 12345), 'ticket-12345')
        self.assertEqual(dashboard_button_label('ticket-0001-alice', 999), 'ticket-999')

    def test_nonstandard_empty_label_gets_numeric_fallback(self):
        self.assertEqual(dashboard_button_label('', 98765), 'ticket-98765')

    def test_zero_tickets(self):
        self.assertEqual(dashboard_pages([]), [])

    def test_one_ticket(self):
        self.assertEqual(dashboard_pages([(1, 'ticket-0001')]), [[(1, 'ticket-0001')]])

    def test_twenty_five_tickets_one_message(self):
        rows = [(i, f'ticket-{i:04d}') for i in range(25)]
        self.assertEqual([len(p) for p in dashboard_pages(rows)], [25])

    def test_twenty_six_tickets_two_messages(self):
        rows = [(i, f'ticket-{i:04d}') for i in range(26)]
        self.assertEqual([len(p) for p in dashboard_pages(rows)], [25, 1])

    def test_one_hundred_twenty_tickets_five_messages(self):
        rows = [(i, f'ticket-{i:04d}') for i in range(120)]
        self.assertEqual([len(p) for p in dashboard_pages(rows)], [25, 25, 25, 25, 20])

    def test_over_limit_rejected(self):
        rows = [(i, f'ticket-{i:04d}') for i in range(121)]
        with self.assertRaises(ReplyValidationError):
            dashboard_pages(rows)


class DashboardAdapterContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = ADAPTER.read_text(encoding='utf-8')
        cls.tree = ast.parse(cls.source)
        cls.classes = {node.name: node for node in cls.tree.body if isinstance(node, ast.ClassDef)}

    def _method(self, class_name, method_name):
        return next(n for n in self.classes[class_name].body if isinstance(n, ast.AsyncFunctionDef) and n.name == method_name)

    def test_direct_button_opens_modal_not_dropdown(self):
        src = ast.get_source_segment(self.source, self._method('DirectTicketButton', 'callback'))
        self.assertIn('interaction.response.send_modal(', src)
        self.assertNotIn('SelectOption', self.source)
        self.assertNotIn('ReplySelectionView', self.source)

    def test_ticket_permissions_reverified_before_modal(self):
        src = ast.get_source_segment(self.source, self._method('DirectTicketButton', 'callback'))
        self.assertIn('await service.member(interaction)', src)
        self.assertIn('await service.verify_ticket(self.ticket_id, member)', src)
        self.assertLess(src.index('await service.verify_ticket'), src.index('interaction.response.send_modal'))

    def test_ticket_permissions_reverified_at_submission(self):
        src = ast.get_source_segment(self.source, self._method('ReplyModal', 'on_submit'))
        self.assertIn('self.service.deliver(interaction, self.ticket_id', src)
        delivery = ast.get_source_segment(self.source, self._method('TicketReplyService', 'deliver'))
        self.assertIn('await self.verify_ticket(channel_id, member)', delivery)

    def test_dashboard_channel_is_private(self):
        src = ast.get_source_segment(self.source, self._method('TicketDashboard', 'reconcile'))
        self.assertIn('await self.service.private_channel(self.service.cfg.center_channel_id)', src)
        self.assertIn('await self.service.private_channel(self.service.cfg.audit_channel_id)', src)

    def test_no_unsolicited_initial_panel(self):
        src = ast.get_source_segment(self.source, self._method('TicketDashboard', 'reconcile'))
        self.assertIn('if not existing and not allow_create:', src)
        self.assertIn('return None', src)

    def test_existing_panel_edited_not_spammed(self):
        src = ast.get_source_segment(self.source, self._method('TicketDashboard', 'reconcile'))
        self.assertIn('await msg.edit(embed=embed, view=view', src)
        self.assertIn('msg = await center.send(', src)
        self.assertIn('await msg.delete()', src)

    def test_automatic_lifecycle_triggers(self):
        src = self.source
        for name in ('on_ready', 'on_guild_channel_create', 'on_guild_channel_update',
                     'on_guild_channel_delete', 'on_message'):
            self.assertIn(f'bot.add_listener(dashboard.{name}', src)
        self.assertIn('_REFRESH_INTERVAL_SECONDS = 120', src)

    def test_persistent_view_after_reconcile(self):
        self.assertIn('super().__init__(timeout=None)', self.source)
        self.assertIn('self.bot.add_view(view, message_id=msg.id)', self.source)

    def test_modal_preflight_has_bounded_response_window(self):
        src = ast.get_source_segment(self.source, self._method('DirectTicketButton', 'callback'))
        self.assertIn('await asyncio.wait_for(preflight(), timeout=1.8)', src)
        self.assertNotIn('interaction.response.defer(', src)

    def test_no_message_typing_or_webhooks(self):
        self.assertNotIn('trigger_typing', self.source)
        self.assertNotIn('Webhook.send', self.source)


if __name__ == '__main__':
    unittest.main()
