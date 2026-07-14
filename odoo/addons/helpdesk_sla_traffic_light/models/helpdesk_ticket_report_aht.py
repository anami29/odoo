# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models, tools


class HelpdeskTicketReportAht(models.Model):
    _name = "helpdesk.ticket.report.aht"
    _description = "Average Handling Time Report"
    _auto = False
    _order = "create_date desc"

    ticket_id = fields.Many2one("helpdesk.ticket", string="Ticket", readonly=True)
    team_id = fields.Many2one("helpdesk.ticket.team", string="Team", readonly=True)
    category_id = fields.Many2one(
        "helpdesk.ticket.category", string="Category", readonly=True
    )
    user_id = fields.Many2one("res.users", string="Assigned User", readonly=True)
    stage_id = fields.Many2one("helpdesk.ticket.stage", string="Stage", readonly=True)
    company_id = fields.Many2one("res.company", string="Company", readonly=True)
    priority = fields.Selection(
        [
            ("0", "Low"),
            ("1", "Medium"),
            ("2", "High"),
            ("3", "Very High"),
        ],
        string="Priority",
        readonly=True,
    )
    create_date = fields.Datetime(string="Create Date", readonly=True)
    closed_date = fields.Datetime(string="Close Date", readonly=True)
    resolution_hours = fields.Float(
        string="Resolution Time (Hours)",
        readonly=True,
        group_operator="avg",
    )
    assign_hours = fields.Float(
        string="First Assignment Time (Hours)",
        readonly=True,
        group_operator="avg",
    )
    is_closed = fields.Boolean(string="Closed", readonly=True)
    sla_breached = fields.Boolean(string="SLA Breached", readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(
            """
            CREATE OR REPLACE VIEW %s AS (
                SELECT
                    t.id AS id,
                    t.id AS ticket_id,
                    t.team_id AS team_id,
                    t.category_id AS category_id,
                    t.user_id AS user_id,
                    t.stage_id AS stage_id,
                    t.company_id AS company_id,
                    t.priority AS priority,
                    t.create_date AS create_date,
                    t.closed_date AS closed_date,
                    CASE WHEN t.closed_date IS NOT NULL 
                         THEN EXTRACT(EPOCH FROM (t.closed_date - t.create_date)) / 3600.0 
                         ELSE NULL 
                    END AS resolution_hours,
                    EXTRACT(EPOCH FROM (t.assigned_date - t.create_date)) / 3600.0 AS assign_hours,
                    ts.closed AS is_closed,
                    COALESCE(BOOL_OR(s.state = 'expired'), FALSE) AS sla_breached
                FROM helpdesk_ticket t
                LEFT JOIN helpdesk_ticket_stage ts ON t.stage_id = ts.id
                LEFT JOIN helpdesk_ticket_sla s ON t.id = s.ticket_id
                WHERE t.active = TRUE
                GROUP BY t.id, ts.closed
            )
        """
            % self._table
        )
