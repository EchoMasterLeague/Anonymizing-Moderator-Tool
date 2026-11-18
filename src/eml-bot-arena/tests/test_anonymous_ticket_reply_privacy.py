"""Run _staff_only logic using offline mock principals (no Discord credential)."""
import ast
import pathlib
import types
import unittest

ADAPTER = pathlib.Path(__file__).resolve().parent.parent / 'utils/anonymous_ticket_reply.py'

class Role:
    def __init__(self, name):
        self.name=name
        self.permissions=types.SimpleNamespace(administrator=False)

class Member:
    def __init__(self, ident): self.id=ident

class FakeChannel:
    def __init__(self, extra_overwrites=None):
        self.default_role=Role('@everyone')
        self.staff_role=Role('League Mod')
        self.bot=Member(111)
        self.guild=types.SimpleNamespace(default_role=self.default_role,
                                         roles=[self.default_role,self.staff_role], me=self.bot)
        self.overwrites=extra_overwrites or {}
    def permissions_for(self, role):
        return types.SimpleNamespace(view_channel=(role is self.staff_role))

class PrivateChannelPrivacyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tree=ast.parse(ADAPTER.read_text(encoding='utf-8'))
        fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='_staff_only')
        for arg in fn.args.args: arg.annotation=None
        fn.returns=None
        scope={'discord':types.SimpleNamespace(Member=Member,Role=Role)}
        exec(compile(ast.fix_missing_locations(ast.Module(body=[fn],type_ignores=[])),str(ADAPTER),'exec'),scope)
        cls.fn=staticmethod(scope['_staff_only'])
        cls.cfg=types.SimpleNamespace(staff_role_names=frozenset({'League Mod','Commissioner','Board'}))

    def test_role_based_staff_channel_allowed(self):
        self.assertTrue(self.fn(FakeChannel(),self.cfg))

    def test_individual_nonstaff_allow_is_blocked(self):
        member=Member(222)
        ch=FakeChannel({member:types.SimpleNamespace(view_channel=True)})
        self.assertFalse(self.fn(ch,self.cfg))

    def test_explicit_bot_member_allow_is_allowed(self):
        bot=Member(111)
        ch=FakeChannel({bot:types.SimpleNamespace(view_channel=True)})
        self.assertTrue(self.fn(ch,self.cfg))

    def test_unknown_overwrite_principal_is_blocked(self):
        ch=FakeChannel({object():types.SimpleNamespace(view_channel=True)})
        self.assertFalse(self.fn(ch,self.cfg))

if __name__=='__main__': unittest.main()
