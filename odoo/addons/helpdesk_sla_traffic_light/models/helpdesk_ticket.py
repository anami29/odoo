# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from datetime import timedelta
from odoo import api, fields, models


class HelpdeskTicket(models.Model):
    _inherit = "helpdesk.ticket"

    sla_status = fields.Selection(
        [
            ("expired", "SLA Expired"),
            ("warning", "SLA Warning"),
            ("on_time", "SLA On Time"),
            ("no_sla", "No SLA"),
        ],
        string="SLA Status",
        compute="_compute_sla_status",
        search="_search_sla_status",
    )

    resolution_hours = fields.Float(
        string="Resolution Time (Hours)",
        compute="_compute_handling_hours",
        store=True,
        group_operator="avg",
    )
    assign_hours = fields.Float(
        string="First Assignment Time (Hours)",
        compute="_compute_handling_hours",
        store=True,
        group_operator="avg",
    )

    @api.depends(
        "team_sla",
        "sla_expired",
        "sla_deadline",
        "ticket_sla_ids.state",
        "ticket_sla_ids.deadline",
    )
    def _compute_sla_status(self):
        warning_hours = float(
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("helpdesk_sla_traffic_light.warning_hours", 4)
        )
        now = fields.Datetime.now()
        for ticket in self:
            if not ticket.team_sla:
                ticket.sla_status = "no_sla"
                continue

            in_progress = ticket.ticket_sla_ids.filtered(
                lambda s: s.state == "in_progress"
            )

            if ticket.sla_expired:
                ticket.sla_status = "expired"
            elif (
                in_progress
                and ticket.sla_deadline
                and ticket.sla_deadline <= now + timedelta(hours=warning_hours)
            ):
                ticket.sla_status = "warning"
            elif in_progress:
                ticket.sla_status = "on_time"
            else:
                ticket.sla_status = "no_sla"

    def _search_sla_status(self, operator, value):
        self.env.flush_all()
        now = fields.Datetime.now()
        warning_hours = float(
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("helpdesk_sla_traffic_light.warning_hours", 4)
        )
        limit_datetime = now + timedelta(hours=warning_hours)

        statuses = ["expired", "warning", "on_time", "no_sla"]

        if isinstance(value, str):
            val_list = [value]
        elif isinstance(value, (list, tuple)):
            val_list = list(value)
        else:
            val_list = []

        if operator in ("=", "in"):
            target_statuses = [v for v in val_list if v in statuses]
        elif operator in ("!=", "not in"):
            target_statuses = [v for v in statuses if v not in val_list]
        else:
            raise ValueError(f"Unsupported operator {operator}")

        if not target_statuses:
            return [("id", "=", False)]

        # Run query to retrieve matching ticket IDs
        query = """
            SELECT t.id
            FROM helpdesk_ticket t
            WHERE (
                CASE
                    WHEN NOT EXISTS (
                        SELECT 1 FROM helpdesk_ticket_team tm
                        WHERE tm.id = t.team_id AND tm.use_sla = TRUE
                    ) THEN 'no_sla'
                    WHEN EXISTS (
                        SELECT 1 FROM helpdesk_ticket_sla s 
                        WHERE s.ticket_id = t.id 
                          AND (s.state = 'expired' OR (s.state = 'in_progress' AND s.deadline < %s))
                    ) THEN 'expired'
                    WHEN EXISTS (
                        SELECT 1 FROM helpdesk_ticket_sla s 
                        WHERE s.ticket_id = t.id 
                          AND s.state = 'in_progress' 
                          AND s.deadline <= %s
                    ) THEN 'warning'
                    WHEN EXISTS (
                        SELECT 1 FROM helpdesk_ticket_sla s 
                        WHERE s.ticket_id = t.id 
                          AND s.state = 'in_progress'
                    ) THEN 'on_time'
                    ELSE 'no_sla'
                END
            ) IN %s
        """
        self.env.cr.execute(query, (now, limit_datetime, tuple(target_statuses)))
        res = self.env.cr.fetchall()
        ticket_ids = [r[0] for r in res]
        return [("id", "in", ticket_ids)]

    @api.depends("closed_date", "assigned_date", "create_date")
    def _compute_handling_hours(self):
        for ticket in self:
            if ticket.create_date and ticket.closed_date:
                ticket.resolution_hours = (
                    ticket.closed_date - ticket.create_date
                ).total_seconds() / 3600.0
            else:
                ticket.resolution_hours = False

            if ticket.create_date and ticket.assigned_date:
                ticket.assign_hours = (
                    ticket.assigned_date - ticket.create_date
                ).total_seconds() / 3600.0
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
