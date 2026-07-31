from psycopg2 import IntegrityError

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged
from odoo.tools import mute_logger


@tagged("post_install", "-at_install")
class TestItemCode(TransactionCase):

    def _make(self, name):
        return self.env["product.product"].create({"name": name})

    def test_sequential_assignment(self):
        a = self._make("ITC Item A")
        b = self._make("ITC Item B")
        self.assertTrue(a.item_code)
        self.assertEqual(int(b.item_code), int(a.item_code) + 1)

    def test_manual_entry_blocked(self):
        # R3: nobody types an item code (admin is not the migration manager)
        with self.assertRaises(UserError):
            self.env["product.product"].create(
                {"name": "ITC Manual", "item_code": "1234567"}
            )

    def test_immutable(self):
        # R5
        a = self._make("ITC Item")
        with self.assertRaises(UserError):
            a.write({"item_code": "9999999"})

    def test_unique_db_level(self):
        # R4: DB index catches duplicates even past the ORM guards (sudo)
        a = self._make("ITC Item")
        with mute_logger("odoo.sql_db"), \
                self.assertRaises(IntegrityError), self.cr.savepoint():
            self.env["product.product"].sudo().create(
                {"name": "ITC Dup", "item_code": a.item_code}
            )
            self.env.flush_all()

    def test_copy_gets_new_code(self):
        # copy=False + create() assignment => duplicate gets its own code
        a = self._make("ITC Item")
        b = a.copy()
        self.assertTrue(b.item_code)
        self.assertNotEqual(b.item_code, a.item_code)

    def test_unlink_blocked_archive_keeps_code(self):
        # Lifecycle s.8 / R6
        a = self._make("ITC Item")
        code = a.item_code
        with self.assertRaises(UserError):
            a.unlink()
        a.action_archive()
        self.assertFalse(a.active)
        self.assertEqual(a.item_code, code)

    def test_template_mirror_and_search(self):
        a = self._make("ITC Item")
        self.assertEqual(a.product_tmpl_id.item_code, a.item_code)
        found = self.env["product.template"].search(
            [("item_code", "=", a.item_code)]
        )
        self.assertEqual(found, a.product_tmpl_id)
