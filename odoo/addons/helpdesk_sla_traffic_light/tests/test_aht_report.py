# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from datetime import timedelta
from odoo import fields
from odoo.addons.helpdesk_mgmt_sla.tests.common import CommonHelpdeskMgmtSla


class TestAhtReport(CommonHelpdeskMgmtSla):

    def test_aht_average(self):
        team = self.team1
        now = fields.Datetime.now()

        # Create two tickets
        ticket1 = self.get_ticket(team)
        ticket2 = self.get_ticket(team)

        # Set stage to closed
        closed_stage = self.env["helpdesk.ticket.stage"].create(
            {
                "name": "Closed Stage",
                "closed": True,
            }
        )

        # Update dates via SQL
        self.env.cr.execute(
            "UPDATE helpdesk_ticket SET create_date = %s, closed_date = %s, stage_id = %s WHERE id = %s",
            [now - timedelta(hours=5), now - timedelta(hours=3), closed_stage.id, ticket1.id],
        )
        self.env.cr.execute(
            "UPDATE helpdesk_ticket SET create_date = %s, closed_date = %s, stage_id = %s WHERE id = %s",
            [now - timedelta(hours=5), now - timedelta(hours=1), closed_stage.id, ticket2.id],
        )

        # Invalidate cache to force reload
        self.env.invalidate_all()

        # Now read the report via read_group to check averages
        res = self.env["helpdesk.ticket.report.aht"].read_group(
            domain=[("ticket_id", "in", (ticket1 + ticket2).ids)],
            fields=["resolution_hours"],
            groupby=["team_id"],
        )
        self.assertTrue(res)
        self.assertAlmostEqual(res[0]["resolution_hours"], 3.0, places=2)

    def test_aht_open_ticket_excluded(self):
        team = self.team1
        ticket = self.get_ticket(team)

        # Set stage to non-closed
        open_stage = self.env["helpdesk.ticket.stage"].create(
            {
                "name": "Open Stage",
                "closed": False,
            }
        )
        ticket.write({"stage_id": open_stage.id, "closed_date": False})

        # Check report record
        report_record = self.env["helpdesk.ticket.report.aht"].search(
            [("ticket_id", "=", ticket.id)]
        )
        self.assertTrue(report_record)
        self.assertFalse(report_record.resolution_hours)
