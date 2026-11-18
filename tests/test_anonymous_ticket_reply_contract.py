"""Offline structural safety checks for the Discord adapter; live tests still required."""
import ast
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
ADAPTER = ROOT / 'utils' / 'anonymous_ticket_reply.py'


class AdapterContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = ADAPTER.read_text(encoding='utf-8')
        cls.tree = ast.parse(cls.text)

    def test_no_sql_or_unified_discipline_import(self):
        imported = [n.module for n in ast.walk(self.tree) if isinstance(n, ast.ImportFrom)]
        self.assertFalse(any(s and (s.startswith('discipline') or s.startswith('database')) for s in imported))

    def test_no_typing_events_or_webhooks(self):
        self.assertNotIn('trigger_typing', self.text)
        self.assertNotIn('typing()', self.text)
        self.assertNotIn('Webhook.send', self.text)

    def test_mentions_disabled_in_both_sends(self):
        self.assertGreaterEqual(self.text.count('AllowedMentions.none()'), 4)

    def test_staff_refetched_on_submission(self):
        self.assertIn('await guild.fetch_member(interaction.user.id)', self.text)
        self.assertIn('await self.member(interaction)', self.text)

    def test_origin_and_category_checks(self):
        self.assertIn('candidate_category_allowed(channel.category_id', self.text)
        self.assertIn('message.author.id == self.cfg.ticket_tool_bot_id', self.text)

    def test_prepared_audit_before_message_send(self):
        start = self.text.index('pending = await audit.send(')
        delivered = self.text.index('message = await channel.send(')
        self.assertLess(start, delivered)

    def test_runtime_activation_opt_in(self):
        self.assertIn('EML_ANON_TICKET_REPLIES_ENABLED", "0"', self.text)


if __name__ == '__main__': unittest.main()
