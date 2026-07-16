# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from datetime import timedelta
from odoo import api, fields, models


class HelpdeskTicket(models.Model):
    _inherit = "helpdesk.ticket"

    sla_status = fields.Selection(
        selection=[
            ("expired", "SLA Expired"),
            ("warning", "SLA Warning"),
            ("on_time", "SLA On Time"),
            ("no_sla", "No SLA"),
        ],
        string="SLA Status",
        compute="_compute_sla_status",
        search="_search_sla_status",
        readonly=True,
    )

    resolution_hours = fields.Float(
        string="Resolution Time (Hours)",
        compute="_compute_handling_times",
        store=True,
        readonly=True,
    )

    assign_hours = fields.Float(
        string="First Assignment Time (Hours)",
        compute="_compute_handling_times",
        store=True,
        readonly=True,
    )

    @api.depends("sla_expired", "sla_deadline", "ticket_sla_ids.state", "ticket_sla_ids.deadline")
    def _compute_sla_status(self):
        warning_hours = float(
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("helpdesk_sla_traffic_light.warning_hours", 4)
        )
        now = fields.Datetime.now()
        for ticket in self:
            in_progress = ticket.ticket_sla_ids.filtered(lambda s: s.state == "in_progress")
            if not ticket.team_sla:
                ticket.sla_status = "no_sla"
            elif ticket.sla_expired:
                ticket.sla_status = "expired"
            elif in_progress and ticket.sla_deadline and ticket.sla_deadline <= now + timedelta(hours=warning_hours):
                ticket.sla_status = "warning"
            elif in_progress:
                ticket.sla_status = "on_time"
            else:
                ticket.sla_status = "no_sla"

    def _search_sla_status(self, operator, value):
        if operator not in ("=", "in", "!=", "not in"):
            raise NotImplementedError("Operator not supported")

        values = value if isinstance(value, list) else [value]
        is_negative = operator in ("!=", "not in")

        warning_hours = float(
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("helpdesk_sla_traffic_light.warning_hours", 4)
        )
        now = fields.Datetime.now()
        limit_time = now + timedelta(hours=warning_hours)

        # Flush pending writes to the database before running raw SQL query
        self.env["helpdesk.ticket"].flush_model()
        self.env["helpdesk.ticket.sla"].flush_model()
        self.env["helpdesk.ticket.team"].flush_model()

        query = """
            SELECT t.id,
                   team.use_sla as team_sla,
                   EXISTS(
                       SELECT 1 FROM helpdesk_ticket_sla s 
                       WHERE s.ticket_id = t.id 
                         AND (s.state = 'expired' OR (s.state = 'in_progress' AND s.deadline < %s))
                   ) AS expired,
                   EXISTS(
                       SELECT 1 FROM helpdesk_ticket_sla s 
                       WHERE s.ticket_id = t.id 
                         AND s.state = 'in_progress'
                   ) AS has_in_progress,
                   (
                       SELECT MIN(s.deadline) FROM helpdesk_ticket_sla s 
                       WHERE s.ticket_id = t.id 
                         AND s.state = 'in_progress'
                   ) AS min_deadline
            FROM helpdesk_ticket t
            LEFT JOIN helpdesk_ticket_team team ON t.team_id = team.id
        """
        self.env.cr.execute(query, [now])
        rows = self.env.cr.dictfetchall()

        matched_ids = []
        for r in rows:
            status = "no_sla"
            if not r["team_sla"]:
                status = "no_sla"
            elif r["expired"]:
                status = "expired"
            elif r["has_in_progress"]:
                if r["min_deadline"] and r["min_deadline"] <= limit_time:
                    status = "warning"
                else:
                    status = "on_time"
            else:
                status = "no_sla"

            if (status in values) != is_negative:
                matched_ids.append(r["id"])

        return [("id", "in", matched_ids)]

    @api.depends("closed_date", "assigned_date", "create_date")
    def _compute_handling_times(self):
        for ticket in self:
            if ticket.closed_date and ticket.create_date:
                dt = ticket.closed_date - ticket.create_date
                ticket.resolution_hours = dt.total_seconds() / 3600.0
            else:
                ticket.resolution_hours = False

            if ticket.assigned_date and ticket.create_date:
                dt = ticket.assigned_date - ticket.create_date
                ticket.assign_hours = dt.total_seconds() / 3600.0
            else:
                ticket.assign_hours = False

    sla_id = fields.Many2one(
        comodel_name="helpdesk.sla",
        string="SLA Type",
        compute="_compute_sla_id",
        store=True,
    )

    @api.depends("ticket_sla_ids.sla_id")
    def _compute_sla_id(self):
        for ticket in self:
            ticket.sla_id = ticket.ticket_sla_ids[:1].sla_id



class SpreadsheetDashboardHealer(models.AbstractModel):
    _name = "spreadsheet.dashboard.healer"
    _description = "Heals empty spreadsheet dashboards"

    @api.model
    def _register_hook(self):
        super()._register_hook()
        # Clean up database asset attachments to force recompilation of JS/CSS
        try:
            attachments = self.env["ir.attachment"].search([
                ("url", "like", "/web/assets/%")
            ])
            if attachments:
                attachments.unlink()
        except Exception:
            pass

        if "spreadsheet.dashboard" in self.env:
            try:
                dashboards = self.env["spreadsheet.dashboard"].search([])
                for dash in dashboards:
                    try:
                        data = dash.spreadsheet_data
                        if not data or not data.strip():
                            dash.write({"spreadsheet_data": "{}"})
                    except Exception:
                        dash.write({"spreadsheet_data": "{}"})
            except Exception:
                pass

