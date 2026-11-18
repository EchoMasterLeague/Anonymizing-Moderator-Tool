"""Pure offline security/configuration tests, no Discord credentials required."""
import unittest
from utils.anonymous_ticket_reply_core import (
    ReplyConfig, ReplyConfigurationError, ReplyValidationError,
    candidate_category_allowed, role_authorized, player_visible_message, validate_body,
)

ENV = {
    "GUILD_ID": "1239973059675553808",  # DEV
    "EML_ANON_TICKET_CENTER_CHANNEL_ID": "1530000000000000001",
    "EML_ANON_TICKET_AUDIT_CHANNEL_ID": "1530000000000000002",
    "EML_TICKET_TOOL_BOT_ID": "1530000000000000003",
    "EML_TICKET_OPEN_CATEGORY_IDS": "1530000000000000004",
    "EML_TICKET_CLOSED_CATEGORY_IDS": "1530000000000000005",
}


class ConfigTest(unittest.TestCase):
    def test_valid(self):
        c = ReplyConfig.from_env(ENV)
        self.assertEqual(c.header, "EML Support")
        self.assertEqual(c.open_category_ids, (1530000000000000004,))
        self.assertEqual(c.closed_category_ids, (1530000000000000005,))

    def test_missing_provider_id_fails(self):
        env = dict(ENV); env.pop("EML_TICKET_TOOL_BOT_ID")
        with self.assertRaises(ReplyConfigurationError): ReplyConfig.from_env(env)

    def test_blank_open_categories_fails(self):
        env = dict(ENV); env["EML_TICKET_OPEN_CATEGORY_IDS"] = ""
        with self.assertRaises(ReplyConfigurationError): ReplyConfig.from_env(env)

    def test_closed_overlap_fails(self):
        env = dict(ENV); env["EML_TICKET_CLOSED_CATEGORY_IDS"] = env["EML_TICKET_OPEN_CATEGORY_IDS"]
        with self.assertRaises(ReplyConfigurationError): ReplyConfig.from_env(env)

    def test_same_audit_center_fails(self):
        env = dict(ENV); env["EML_ANON_TICKET_AUDIT_CHANNEL_ID"] = env["EML_ANON_TICKET_CENTER_CHANNEL_ID"]
        with self.assertRaises(ReplyConfigurationError): ReplyConfig.from_env(env)

    def test_non_numeric_ids_fail(self):
        for key in ("GUILD_ID", "EML_ANON_TICKET_CENTER_CHANNEL_ID", "EML_TICKET_TOOL_BOT_ID"):
            with self.subTest(key=key):
                env=dict(ENV); env[key]="abc"
                with self.assertRaises(ReplyConfigurationError): ReplyConfig.from_env(env)

    def test_duplicate_open_categories_fail(self):
        env=dict(ENV); env["EML_TICKET_OPEN_CATEGORY_IDS"] += "," + env["EML_TICKET_OPEN_CATEGORY_IDS"]
        with self.assertRaises(ReplyConfigurationError): ReplyConfig.from_env(env)

    def test_no_staff_roles_fails(self):
        env=dict(ENV); env["EML_ANON_TICKET_STAFF_ROLE_NAMES"]=" , "
        with self.assertRaises(ReplyConfigurationError): ReplyConfig.from_env(env)

    def test_unsafe_branding_fails(self):
        env=dict(ENV); env["EML_ANON_TICKET_SUPPORT_HEADING"]="@everyone"
        with self.assertRaises(ReplyConfigurationError): ReplyConfig.from_env(env)

    def test_optional_closed_categories(self):
        env=dict(ENV); env.pop("EML_TICKET_CLOSED_CATEGORY_IDS")
        self.assertEqual(ReplyConfig.from_env(env).closed_category_ids, ())


class SecurityContractTest(unittest.TestCase):
    def setUp(self): self.cfg=ReplyConfig.from_env(ENV)

    def test_role_names(self):
        self.assertTrue(role_authorized({"Board"},self.cfg))
        self.assertTrue(role_authorized({"League Mod"},self.cfg))
        self.assertTrue(role_authorized({"Commissioner"},self.cfg))
        self.assertFalse(role_authorized({"Player"},self.cfg))
        self.assertFalse(role_authorized({"league mod"},self.cfg))

    def test_open_vs_closed(self):
        self.assertTrue(candidate_category_allowed(self.cfg.open_category_ids[0],self.cfg))
        self.assertFalse(candidate_category_allowed(self.cfg.closed_category_ids[0],self.cfg))
        self.assertFalse(candidate_category_allowed(None,self.cfg))
        self.assertFalse(candidate_category_allowed(22,self.cfg))

    def test_empty_body(self):
        for body in ("", " ", "\n\t"):
            with self.assertRaises(ReplyValidationError): validate_body(body)

    def test_body_size(self):
        self.assertEqual(len(validate_body("x"*1800)),1800)
        with self.assertRaises(ReplyValidationError): validate_body("x"*1801)

    def test_player_message_has_branding_not_actor(self):
        m=player_visible_message("  Hello  ",self.cfg)
        self.assertEqual(m,"**EML Support**\n\nHello")
        self.assertNotIn("actor=",m)


if __name__=="__main__":unittest.main()
