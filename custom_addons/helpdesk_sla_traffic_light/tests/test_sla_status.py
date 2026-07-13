# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from datetime import timedelta
from odoo import fields
from odoo.addons.helpdesk_mgmt_sla.tests.common import CommonHelpdeskMgmtSla


class TestSlaStatus(CommonHelpdeskMgmtSla):

    def test_status_expired(self):
        team = self.team1
        self.sla.write({"hours": 1})
        ticket = self.get_ticket(team)

        # Check SLA lines
        self.assertTrue(ticket.ticket_sla_ids)
        sla_line = ticket.ticket_sla_ids[0]

        # Force deadline in the past
        now = fields.Datetime.now()
        sla_line.write({"deadline": now - timedelta(hours=2)})

        # Recompute computed fields (non-stored ones like sla_status and sla_expired)
        ticket._compute_sla_data()
        ticket._compute_sla_status()

        self.assertTrue(ticket.sla_expired)
        self.assertEqual(ticket.sla_status, "expired")

    def test_status_on_time(self):
        team = self.team1
        self.sla.write({"hours": 10})  # 10h in the future
        ticket = self.get_ticket(team)

        ticket._compute_sla_data()
        ticket._compute_sla_status()

        self.assertFalse(ticket.sla_expired)
        self.assertEqual(ticket.sla_status, "on_time")

        # Now change the deadline to within 2 hours (warning window defaults to 4h)
        sla_line = ticket.ticket_sla_ids[0]
        now = fields.Datetime.now()
        sla_line.write({"deadline": now + timedelta(hours=2)})

        ticket._compute_sla_data()
        ticket._compute_sla_status()

        self.assertEqual(ticket.sla_status, "warning")

    def test_status_no_sla(self):
        team_no_sla = self.env["helpdesk.ticket.team"].create(
            {
                "name": "Team No SLA",
                "use_sla": False,
            }
        )
        ticket = self.get_ticket(team_no_sla)

        ticket._compute_sla_data()
        ticket._compute_sla_status()

        self.assertEqual(ticket.sla_status, "no_sla")

    def test_search_status(self):
        # We have ticket1 and ticket2 in CommonHelpdeskMgmtSla
        # Let's force ticket1's SLA to expire
        sla_line1 = self.ticket1.ticket_sla_ids[0]
        now = fields.Datetime.now()
        sla_line1.write({"deadline": now - timedelta(hours=2)})

        # Ensure ticket2 is not expired (set deadline to future)
        sla_line2 = self.ticket2.ticket_sla_ids[0]
        sla_line2.write({"deadline": now + timedelta(hours=5)})

        expired_tickets = self.env["helpdesk.ticket"].search([("sla_status", "=", "expired")])
        self.assertIn(self.ticket1.id, expired_tickets.ids)
        self.assertNotIn(self.ticket2.id, expired_tickets.ids)

        on_time_tickets = self.env["helpdesk.ticket"].search([("sla_status", "=", "on_time")])
        self.assertIn(self.ticket2.id, on_time_tickets.ids)
        self.assertNotIn(self.ticket1.id, on_time_tickets.ids)


