# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from datetime import timedelta
from freezegun import freeze_time
from odoo import Command, fields
from odoo.exceptions import ValidationError
from odoo.addons.helpdesk_mgmt_sla.tests.common import CommonHelpdeskMgmtSla


class TestSlaStatus(CommonHelpdeskMgmtSla):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env["ir.config_parameter"].sudo().set_param(
            "helpdesk_sla_traffic_light.warning_hours", 4
        )


    @freeze_time(fields.Datetime.now() + timedelta(hours=3))
    def test_status_expired(self):
        """
        Create a team with use_sla, SLA rule (1h deadline), ticket.
        Force SLA line deadline into the past.
        Assert sla_status == 'expired' and sla_expired is True.
        """
        # Create a new SLA with 1 hour
        self.sla.write({"hours": 1})
        ticket = self.get_ticket(self.team1)
        ticket.invalidate_recordset()
        ticket.ticket_sla_ids.invalidate_recordset()

        # Check that after 3 hours it is expired
        self.assertTrue(ticket.sla_expired)
        self.assertEqual(ticket.sla_status, "expired")

    def test_status_on_time(self):
        """
        Deadline in the future -> sla_status == 'on_time'.
        Deadline within 4h -> sla_status == 'warning'.
        """
        # Make the generic SLA non-conflicting (longer hours) so it starts as 'on_time' too
        self.sla.write({"hours": 10})
        # Create a 6 hour SLA
        sla_6h = self.env["helpdesk.sla"].create(
            {
                "name": "6 Hours SLA",
                "hours": 6,
                "stage_id": self.stage2.id,
                "team_ids": [Command.set([self.team1.id])],
            }
        )
        ticket = self.get_ticket(self.team1)
        ticket.invalidate_recordset()

        # Initial state should be 'on_time' (6 hours remaining, threshold is 4h)
        self.assertEqual(ticket.sla_status, "on_time")

        # Freeze time 3 hours in the future (remaining time is now 3 hours, which is <= 4h warning threshold)
        with freeze_time(fields.Datetime.now() + timedelta(hours=3)):
            ticket.invalidate_recordset()
            ticket.ticket_sla_ids.invalidate_recordset()
            self.assertEqual(ticket.sla_status, "warning")

    def test_status_no_sla(self):
        """
        Team with use_sla = False -> sla_status == 'no_sla' on all tickets.
        """
        team_no_sla = self.env["helpdesk.ticket.team"].create(
            {
                "name": "Team SLA Disabled",
                "use_sla": False,
            }
        )
        ticket = self.get_ticket(team_no_sla)
        self.assertEqual(ticket.sla_status, "no_sla")

    def test_search_status(self):
        """
        search([('sla_status', '=', 'expired')]) returns exactly the expected
        ticket set and no others.
        """
        # Setup SLA of 1 hour
        self.sla.write({"hours": 1})
        ticket_sla = self.get_ticket(self.team1)

        # Team with no SLA
        team_no_sla = self.env["helpdesk.ticket.team"].create(
            {
                "name": "Team SLA Disabled Search",
                "use_sla": False,
            }
        )
        ticket_no_sla = self.get_ticket(team_no_sla)

        with freeze_time(fields.Datetime.now() + timedelta(hours=3)):
            ticket_sla.invalidate_recordset()
            ticket_no_sla.invalidate_recordset()

            # Search for expired tickets
            expired_tickets = self.env["helpdesk.ticket"].search(
                [("sla_status", "=", "expired")]
            )
            self.assertIn(ticket_sla, expired_tickets)
            self.assertNotIn(ticket_no_sla, expired_tickets)

            # Search for no_sla tickets
            no_sla_tickets = self.env["helpdesk.ticket"].search(
                [("sla_status", "=", "no_sla")]
            )
            self.assertIn(ticket_no_sla, no_sla_tickets)
            self.assertNotIn(ticket_sla, no_sla_tickets)

    def test_unique_category_sla_constraint(self):
        """
        Assign a category to one SLA.
        Verify that:
        - The category is listed in excluded_category_ids of a new/other SLA.
        - Attempting to save another SLA with the same category raises a ValidationError.
        """
        # Assign category1 to the existing self.sla
        self.sla.write({"category_ids": [Command.set([self.category1.id])]})

        # Create a new SLA
        new_sla = self.env["helpdesk.sla"].new({"name": "Another SLA"})
        # The first category should be in excluded_category_ids
        self.assertIn(self.category1, new_sla.excluded_category_ids._origin)

        # Now try to write/create another SLA containing the same category (category1)
        with self.assertRaises(ValidationError):
            self.env["helpdesk.sla"].create({
                "name": "Conflicting SLA",
                "category_ids": [Command.set([self.category1.id])]
            })

        # Try to update an existing SLA to include category1
        another_sla = self.env["helpdesk.sla"].create({
            "name": "Non Conflicting SLA",
            "category_ids": [Command.set([self.category2.id])]
        })
        with self.assertRaises(ValidationError):
            another_sla.write({
                "category_ids": [Command.link(self.category1.id)]
            })
