# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class HelpdeskSla(models.Model):
    _inherit = "helpdesk.sla"

    excluded_category_ids = fields.Many2many(
        comodel_name="helpdesk.ticket.category",
        compute="_compute_excluded_category_ids",
        string="Excluded Categories",
    )
    allowed_category_ids = fields.Many2many(
        comodel_name="helpdesk.ticket.category",
        compute="_compute_allowed_category_ids",
        string="Allowed Categories",
    )

    @api.depends("team_ids", "team_ids.category_ids")
    def _compute_allowed_category_ids(self):
        for record in self:
            if record.team_ids:
                record.allowed_category_ids = record.team_ids.mapped("category_ids")
            else:
                record.allowed_category_ids = self.env["helpdesk.ticket.category"].search([])


    @api.depends("category_ids")
    def _compute_excluded_category_ids(self):
        for record in self:
            record_id = record._origin.id if isinstance(record.id, models.NewId) else record.id
            domain = [("id", "!=", record_id)] if record_id else []
            other_slas = self.env["helpdesk.sla"].search(domain)
            record.excluded_category_ids = other_slas.mapped("category_ids")

    @api.constrains("category_ids")
    def _check_unique_category_sla(self):
        for record in self:
            record_id = record._origin.id if isinstance(record.id, models.NewId) else record.id
            domain = [("id", "!=", record_id)] if record_id else []
            other_slas = self.env["helpdesk.sla"].search(domain)
            all_other_categories = other_slas.mapped("category_ids")
            conflicting_categories = record.category_ids & all_other_categories
            if conflicting_categories:
                conflicting_names = ", ".join(conflicting_categories.mapped("display_name") or conflicting_categories.mapped("name"))
                conflict_details = []
                for category in conflicting_categories:
                    sla_names = other_slas.filtered(lambda s: category in s.category_ids).mapped("name")
                    conflict_details.append(f"{category.display_name or category.name} (assigned to: {', '.join(sla_names)})")
                raise ValidationError(_(
                    "Each category can only be assigned to one SLA policy. The following categories are already assigned to other SLA(s):\n%s"
                ) % "\n".join(conflict_details))
