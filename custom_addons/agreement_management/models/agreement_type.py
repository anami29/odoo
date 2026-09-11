# -*- coding: utf-8 -*-
from odoo import api, fields, models


class AgreementType(models.Model):
    _name = "agreement.type"
    _description = "Agreement Type / Category"
    _order = "sequence, name"

    name = fields.Char(required=True, translate=True)
    code = fields.Char(help="Short code used in reports and searches, e.g. COM, CONF, VND.")
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    description = fields.Text()
    template_ids = fields.One2many("agreement.template", "type_id", string="Templates")
    template_count = fields.Integer(compute="_compute_counts")
    agreement_count = fields.Integer(compute="_compute_counts")

    _sql_constraints = [
        ("name_uniq", "unique(name)", "An agreement type with this name already exists."),
    ]

    def _compute_counts(self):
        template_data = self.env["agreement.template"]._read_group(
            [("type_id", "in", self.ids)], ["type_id"], ["__count"])
        agreement_data = self.env["agreement.agreement"]._read_group(
            [("type_id", "in", self.ids)], ["type_id"], ["__count"])
        t_map = {t.id: count for t, count in template_data}
        a_map = {t.id: count for t, count in agreement_data}
        for rec in self:
            rec.template_count = t_map.get(rec.id, 0)
            rec.agreement_count = a_map.get(rec.id, 0)

    def action_view_agreements(self):
        self.ensure_one()
        action = self.env["ir.actions.act_window"]._for_xml_id("agreement_management.action_agreement")
        action["domain"] = [("type_id", "=", self.id)]
        action["context"] = {"default_type_id": self.id}
        return action


class AgreementAnnexureType(models.Model):
    _name = "agreement.annexure.type"
    _description = "Supplementary Annexure Type"
    _order = "sequence, name"

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    description = fields.Text()

    _sql_constraints = [
        ("name_uniq", "unique(name)", "An annexure type with this name already exists."),
    ]
