from odoo.addons.base.tests.common import BaseCommon  # pyrefly: ignore [missing-import]


class TestPartner(BaseCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner_obj = cls.env["res.partner"]
        cls.ticket_obj = cls.env["helpdesk.ticket"]
        cls.stage_id_closed = cls.env.ref("helpdesk_mgmt.helpdesk_ticket_stage_done")
        cls.parent_id = cls.partner_obj.create({"name": "Parent 1"})
        cls.child_id_1 = cls.partner_obj.create({"name": "Child 1"})
        cls.child_id_2 = cls.partner_obj.create({"name": "Child 2"})
        cls.child_id_3 = cls.partner_obj.create({"name": "Child 3"})
        cls.tickets = []
        cls.parent_id.child_ids = [
            (4, cls.child_id_1.id),
            (4, cls.child_id_2.id),
            (4, cls.child_id_3.id),
        ]
        for i in [69, 155, 314, 420]:
            cls.tickets.append(
                cls.ticket_obj.create(
                    {
                        "name": f"Nice ticket {i}",
                        "description": f"Nice ticket {i} description",
                    }
                )
            )
        cls.parent_id.helpdesk_ticket_ids = [(4, cls.tickets[0].id)]
        cls.child_id_1.helpdesk_ticket_ids = [(4, cls.tickets[1].id)]
        cls.child_id_2.helpdesk_ticket_ids = [(4, cls.tickets[2].id)]
        cls.child_id_3.helpdesk_ticket_ids = [(4, cls.tickets[3].id)]
        cls.child_id_3.helpdesk_ticket_ids[-1].stage_id = cls.stage_id_closed

    def test_ticket_count(self):
        self.assertEqual(self.parent_id.helpdesk_ticket_count, 4)

    def test_ticket_active_count(self):
        self.assertEqual(self.parent_id.helpdesk_ticket_active_count, 3)

    def test_ticket_string(self):
        self.assertEqual(self.parent_id.helpdesk_ticket_count_string, "3 / 4")

    def test_access_all_contacts_restriction(self):
        # Create a new company
        company_a = self.env["res.company"].create({"name": "Test Company A"})
        company_b = self.env["res.company"].create({"name": "Test Company B"})

        # Create a user for Company A
        user = self.env["res.users"].create({
            "name": "Restricted User",
            "login": "restricted_user_login",
            "email": "restricted@test.com",
            "company_id": company_a.id,
            "company_ids": [(6, 0, [company_a.id])],
            "groups_id": [(6, 0, [self.env.ref("base.group_user").id])],
        })

        # Create partner in same company
        partner_same = self.partner_obj.create({
            "name": "Partner Same Company",
            "company_id": company_a.id,
        })

        # Create partner in other company
        partner_other = self.partner_obj.create({
            "name": "Partner Other Company",
            "company_id": company_b.id,
        })

        # Create partner with no company (outside contact)
        partner_global = self.partner_obj.create({
            "name": "Partner Global Company",
            "company_id": False,
        })

        # Run as the restricted user
        Partner = self.partner_obj.with_user(user)

        # 1. Without the group, they should only see partners of their company
        visible_partners = Partner.search([("id", "in", [partner_same.id, partner_other.id, partner_global.id])])
        self.assertIn(partner_same.id, visible_partners.ids)
        self.assertNotIn(partner_other.id, visible_partners.ids)
        self.assertNotIn(partner_global.id, visible_partners.ids)

        # 2. Add the Access All Contacts group to the user
        group_access_all = self.env.ref("helpdesk_mgmt.group_access_all_contacts")
        user.write({"groups_id": [(4, group_access_all.id)]})

        # 3. With the group, they should see all partners
        visible_partners_all = Partner.search([("id", "in", [partner_same.id, partner_other.id, partner_global.id])])
        self.assertIn(partner_same.id, visible_partners_all.ids)
        self.assertIn(partner_other.id, visible_partners_all.ids)
        self.assertIn(partner_global.id, visible_partners_all.ids)

