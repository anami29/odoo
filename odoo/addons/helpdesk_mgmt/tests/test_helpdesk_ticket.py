import time

from .common import TestHelpdeskTicketBase


class TestHelpdeskTicket(TestHelpdeskTicketBase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ticket = cls.ticket_a_unassigned

    def test_helpdesk_ticket_team_company(self):
        ticket_a = self.env["helpdesk.ticket"].create(
            {
                "name": "Test ticket A",
                "team_id": self.team_a.id,
                "description": "description",
            }
        )
        self.assertEqual(ticket_a.company_id, self.company)
        self.team_b.company_id = False
        ticket_b = self.env["helpdesk.ticket"].create(
            {
                "name": "Test ticket b",
                "team_id": self.team_b.id,
                "description": "description",
            }
        )
        self.assertEqual(ticket_b.company_id, self.company)

    def test_helpdesk_ticket_team_company_extra(self):
        company = self.env["res.company"].create({"name": "Test company"})
        team = self.env["helpdesk.ticket.team"].create(
            {"name": "Test team", "company_id": False}
        )
        ticket = (
            self.env["helpdesk.ticket"]
            .with_company(company)
            .create(
                {
                    "name": "Test ticket",
                    "team_id": team.id,
                    "description": "description",
                }
            )
        )
        self.assertEqual(ticket.company_id, company)
        team.company_id = self.company
        ticket = (
            self.env["helpdesk.ticket"]
            .with_company(company)
            .create(
                {
                    "name": "Test ticket",
                    "team_id": team.id,
                    "description": "description",
                }
            )
        )
        self.assertEqual(ticket.company_id, self.company)

    def test_helpdesk_ticket_datetimes(self):
        old_stage_update = self.ticket.last_stage_update
        self.assertTrue(
            self.ticket.last_stage_update,
            "Helpdesk Ticket: Helpdesk ticket should "
            "have a last_stage_update at all times.",
        )
        self.assertFalse(
            self.ticket.closed_date,
            "Helpdesk Ticket: No closed date "
            "should be set for a non closed "
            "ticket.",
        )
        time.sleep(1)
        self.ticket.write({"stage_id": self.stage_closed.id})
        self.assertTrue(
            self.ticket.closed_date,
            "Helpdesk Ticket: A closed ticket " "should have a closed_date value.",
        )
        self.assertTrue(
            old_stage_update < self.ticket.last_stage_update,
            "Helpdesk Ticket: The last_stage_update "
            "should be updated at every stage_id "
            "change.",
        )
        self.ticket.write({"user_id": self.user.id})
        self.assertTrue(
            self.ticket.assigned_date,
            "Helpdesk Ticket: An assigned ticket " "should contain a assigned_date.",
        )

    def test_helpdesk_ticket_number(self):
        self.assertNotEqual(
            self.ticket.number,
            "/",
            "Helpdesk Ticket: A ticket should have " "a number.",
        )
        ticket_number_1 = int(self.ticket._prepare_ticket_number(values={})[2:])
        ticket_number_2 = int(self.ticket._prepare_ticket_number(values={})[2:])
        self.assertEqual(ticket_number_1 + 1, ticket_number_2)

    def test_helpdesk_ticket_copy(self):
        old_ticket_number = self.ticket.number
        copy_ticket_number = self.ticket.copy().number
        self.assertTrue(
            copy_ticket_number != "/" and old_ticket_number != copy_ticket_number,
            "Helpdesk Ticket: A new ticket can not "
            "have the same number than the origin ticket.",
        )

    def test_helpdesk_ticket_message_new(self):
        Partner = self.env["res.partner"]
        Ticket = self.env["helpdesk.ticket"]

        newPartner = Partner.create(
            {
                "name": "Jill",
                "email": "jill@example.com",
            }
        )
        title = "Test Helpdesk ticket message new"
        msg_id = "0000000000007c50e905cf5b1f2a@example.com"
        msg_dict = {
            "message_id": msg_id,
            "subject": title,
            "email_from": "Bob <bob@example.com>",
            "to": "jill@example.com",
            "cc": "sally@example.com",
            "recipients": "jill@example.com+sally@example.com",
            "partner_ids": [newPartner.id],
            "body": "This the body",
            "date": "2021-10-10",
        }
        try:
            t = Ticket.message_new(msg_dict)
        except Exception as error:
            self.fail(f"{type(error)}: {error}")
        self.assertEqual(t.name, title, "The ticket should have the correct title.")

        title = "New title"
        update_vals = {"name": title}
        try:
            t.message_update(msg_dict, update_vals)
        except Exception as error:
            self.fail(f"{type(error)}: {error}")
        self.assertEqual(
            t.name, title, "The ticket should have the correct (new) title."
        )

    def test_ticket_with_team_stage(self):
        self.new_stage.team_ids = [(6, 0, [self.team_a.id, self.team_b.id])]
        in_progress_stage = self.env.ref(
            "helpdesk_mgmt.helpdesk_ticket_stage_in_progress"
        )
        in_progress_stage.team_ids = [(6, 0, [self.team_b.id])]
        new_ticket = self.env["helpdesk.ticket"].create(
            {
                "name": "New Ticket",
                "description": "Description",
                "team_id": self.team_a.id,
                "user_id": self.user.id,
                "priority": "1",
            }
        )
        self.assertEqual(new_ticket.stage_id, self.new_stage)
        self.new_stage.team_ids = [(6, 0, [self.team_a.id])]
        new_ticket.team_id = self.team_b
        self.assertEqual(new_ticket.stage_id, in_progress_stage)
        self.new_stage.team_ids = False
        new_ticket.team_id = False
        self.assertEqual(new_ticket.stage_id, self.new_stage)

    def test_ticket_without_team(self):
        new_ticket = self.env["helpdesk.ticket"].create(
            {
                "name": "New Ticket",
                "description": "Description",
                "user_id": self.user.id,
                "priority": "1",
            }
        )
        self.assertEqual(self.new_stage, new_ticket.stage_id)

    def test_ticket_sequence_access(self):
        # Find group
        group = self.env.ref("helpdesk_mgmt.group_helpdesk_sequence")

        # Create users
        user_with_access = self.user
        user_with_access.write({"groups_id": [(4, group.id)]})
        
        user_without_access = self.user_own
        user_without_access.write({"groups_id": [(3, group.id)]})

        # Test ticket with user who has access
        ticket_with_access = self.env["helpdesk.ticket"].create(
            {
                "name": "Ticket with access",
                "description": "Description",
                "user_id": user_with_access.id,
            }
        )
        self.assertTrue(ticket_with_access.user_access_sequence)

        # Test ticket with user who does not have access
        ticket_without_access = self.env["helpdesk.ticket"].create(
            {
                "name": "Ticket without access",
                "description": "Description",
                "user_id": user_without_access.id,
            }
        )
        self.assertFalse(ticket_without_access.user_access_sequence)

        # Test unassigned ticket
        ticket_unassigned = self.env["helpdesk.ticket"].create(
            {
                "name": "Unassigned ticket",
                "description": "Description",
                "user_id": False,
            }
        )
        self.assertFalse(ticket_unassigned.user_access_sequence)

        # Test computed/inverse of res.users access_sequence field
        self.assertTrue(user_with_access.access_sequence)
        self.assertFalse(user_without_access.access_sequence)

        user_with_access.access_sequence = False
        self.assertNotIn(group, user_with_access.groups_id)
        self.assertFalse(user_with_access.access_sequence)

        user_with_access.access_sequence = True
        self.assertIn(group, user_with_access.groups_id)
        self.assertTrue(user_with_access.access_sequence)

    def test_contact_access_rights(self):
        # Create external contact (non-employee)
        external_contact = self.env["res.partner"].create({
            "name": "External Customer Contact",
            "employee": False,
        })

        # Create internal/employee contact (employee = True)
        employee_contact = self.env["res.partner"].create({
            "name": "Company Employee Contact",
            "employee": True,
        })

        # Get access groups
        group_access_all = self.env.ref("helpdesk_mgmt.group_access_all_contacts")

        # Create two users: one with access all, one without
        user_all_contacts = self.user
        user_all_contacts.write({"groups_id": [(4, group_access_all.id)]})

        user_internal_only = self.user_own
        user_internal_only.write({"groups_id": [(3, group_access_all.id)]})

        # Read contacts as user_internal_only
        partners_internal = self.env["res.partner"].with_user(user_internal_only).search([("id", "in", (employee_contact.id, external_contact.id))])
        self.assertIn(employee_contact, partners_internal)
        self.assertNotIn(external_contact, partners_internal)

        # Read contacts as user_all_contacts
        partners_all = self.env["res.partner"].with_user(user_all_contacts).search([("id", "in", (employee_contact.id, external_contact.id))])
        self.assertIn(employee_contact, partners_all)
        self.assertIn(external_contact, partners_all)



