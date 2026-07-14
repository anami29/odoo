# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from datetime import timedelta
from odoo import fields
from odoo.addons.helpdesk_mgmt_sla.tests.common import CommonHelpdeskMgmtSla


class TestAhtReport(CommonHelpdeskMgmtSla):

    def test_aht_average(self):
        """
        Create two closed tickets in the same team, closed after 2h and 4h respectively.
        read_group on the report model returns avg resolution_hours == 3.0.
        """
        # Set stage2 as closed stage
        self.stage2.write({"closed": True})

        # Create two tickets
        ticket1 = self.get_ticket(self.team1)
        ticket2 = self.get_ticket(self.team1)

        # Move to closed stage
        ticket1.write({"stage_id": self.stage2.id})
        ticket2.write({"stage_id": self.stage2.id})

        # Flush first, so Odoo writes its memory state/inserts to database
        self.env.flush_all()
        # Set specific create_date and closed_date via SQL
        now = fields.Datetime.now()
        self.env.cr.execute(
            "UPDATE helpdesk_ticket SET create_date = %s, closed_date = %s WHERE id = %s",
            (now - timedelta(hours=5), now - timedelta(hours=3), ticket1.id),
        )
        self.env.cr.execute(
            "UPDATE helpdesk_ticket SET create_date = %s, closed_date = %s WHERE id = %s",
            (now - timedelta(hours=5), now - timedelta(hours=1), ticket2.id),
        )

        # Clear the memory cache so Odoo re-reads from database
        self.env.invalidate_all()

        # Read average resolution_hours on report model
        report = self.env["helpdesk.ticket.report.aht"].read_group(
            domain=[("ticket_id", "in", (ticket1 + ticket2).ids)],
            fields=["resolution_hours"],
            groupby=["team_id"],
        )
        self.assertTrue(report)
        self.assertAlmostEqual(report[0]["resolution_hours"], 3.0, places=2)

    def test_aht_open_ticket_excluded(self):
        """
        Open ticket (no closed_date) has resolution_hours = NULL in the SQL view
        and is excluded from averages.
        """
        # Set stage2 as closed stage
        self.stage2.write({"closed": True})

        # Ticket 1: Closed, resolution = 2 hours
        ticket1 = self.get_ticket(self.team1)
        ticket1.write({"stage_id": self.stage2.id})

        # Ticket 2: Open, no closed_date
        ticket2 = self.get_ticket(self.team1)

        # Flush first, so Odoo writes its memory state/inserts to database
        self.env.flush_all()
        # Set specific create_date and closed_date via SQL
        now = fields.Datetime.now()
        self.env.cr.execute(
            "UPDATE helpdesk_ticket SET create_date = %s, closed_date = %s WHERE id = %s",
            (now - timedelta(hours=5), now - timedelta(hours=3), ticket1.id),
        )

        # Clear the memory cache so Odoo re-reads from database
        self.env.invalidate_all()

        # Verify resolution_hours of open ticket in report model
        report_ticket2 = self.env["helpdesk.ticket.report.aht"].search(
            [("ticket_id", "=", ticket2.id)]
        )
        self.assertTrue(report_ticket2)
        # It must be False/0 (None in Python, which Odoo maps to False or 0 for floats in search results depending on mapping, but in SQL view it is NULL)
        self.assertFalse(report_ticket2.resolution_hours)

        # read_group average should only include the closed ticket (average = 2.0, not (2+0)/2 = 1.0)
        report = self.env["helpdesk.ticket.report.aht"].read_group(
            domain=[("ticket_id", "in", (ticket1 + ticket2).ids)],
            fields=["resolution_hours"],
            groupby=["team_id"],
        )
        self.assertTrue(report)
        self.assertAlmostEqual(report[0]["resolution_hours"], 2.0, places=2)
