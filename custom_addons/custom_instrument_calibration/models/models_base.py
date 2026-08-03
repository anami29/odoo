# -*- coding: utf-8 -*-
from odoo import api, fields, models


class CalibrationInstrumentCategory(models.Model):
    _name = "calibration.instrument.category"
    _description = "Instrument Category"
    _order = "name"

    name = fields.Char(required=True)
    code_prefix = fields.Char(help="Prefix for instrument codes, e.g. VER")
    sequence_id = fields.Many2one("ir.sequence", string="Code Sequence", readonly=True, copy=False)
    default_frequency_interval = fields.Integer(default=12)
    default_frequency_uom = fields.Selection(
        [("days", "Days"), ("weeks", "Weeks"), ("months", "Months"), ("years", "Years")],
        default="months", required=True)
    default_calibration_type = fields.Selection(
        [("internal", "Internal"), ("external", "External"), ("both", "Both")],
        default="external", required=True)
    parameter_template_ids = fields.One2many("calibration.parameter.template", "category_id",
                                             string="Parameter Template")
    instrument_count = fields.Integer(compute="_compute_instrument_count")
    active = fields.Boolean(default=True)

    def _compute_instrument_count(self):
        data = self.env["calibration.instrument"].with_context(active_test=False)._read_group(
            [("category_id", "in", self.ids)], ["category_id"], ["__count"])
        counts = {cat.id: cnt for cat, cnt in data}
        for rec in self:
            rec.instrument_count = counts.get(rec.id, 0)

    @api.model_create_multi
    def create(self, vals_list):
        cats = super().create(vals_list)
        for cat in cats.filtered(lambda c: c.code_prefix and not c.sequence_id):
            cat.sequence_id = self.env["ir.sequence"].sudo().create({
                "name": "Instrument Code %s" % cat.name,
                "implementation": "no_gap",
                "prefix": "%s/" % cat.code_prefix,
                "padding": 4,
                "company_id": False,
            })
        return cats

    def next_code(self):
        self.ensure_one()
        if self.sequence_id:
            return self.sequence_id.next_by_id()
        return self.env["ir.sequence"].next_by_code("calibration.instrument.code")


class CalibrationParameterTemplate(models.Model):
    _name = "calibration.parameter.template"
    _description = "Calibration Parameter Template"
    _order = "sequence, id"

    sequence = fields.Integer(default=10)
    category_id = fields.Many2one("calibration.instrument.category", required=True, ondelete="cascade")
    parameter_name = fields.Char(required=True)
    uom_id = fields.Many2one("uom.uom", string="UoM")
    nominal_value = fields.Float(digits=(16, 4))
    tolerance_plus = fields.Float(digits=(16, 4))
    tolerance_minus = fields.Float(digits=(16, 4))


class CalibrationRetirementReason(models.Model):
    _name = "calibration.retirement.reason"
    _description = "Retirement Reason"
    _order = "name"

    name = fields.Char(required=True, translate=True)
    active = fields.Boolean(default=True)


class CalibrationRecordDisposition(models.Model):
    _name = "calibration.record.disposition"
    _description = "Record Disposition Log (post-retention)"
    _order = "disposition_date desc, id desc"

    name = fields.Char(string="Instrument Code", required=True, readonly=True)
    instrument_name = fields.Char(readonly=True)
    category_name = fields.Char(readonly=True)
    end_of_life_date = fields.Date(readonly=True)
    order_count = fields.Integer(readonly=True)
    disposition_date = fields.Date(default=fields.Date.context_today, readonly=True)
    user_id = fields.Many2one("res.users", default=lambda self: self.env.user, readonly=True)
    reason = fields.Text(required=True, readonly=True)
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company, readonly=True)


class CalibrationStateLog(models.Model):
    _name = "calibration.state.log"
    _description = "Instrument State Log"
    _order = "date_from desc, id desc"

    instrument_id = fields.Many2one("calibration.instrument", required=True, ondelete="cascade", index=True)
    state = fields.Char(required=True)
    date_from = fields.Datetime(required=True, default=fields.Datetime.now)
    date_to = fields.Datetime()


class ResPartner(models.Model):
    _inherit = "res.partner"

    is_calibration_agency = fields.Boolean(string="Calibration Agency")
    nabl_accreditation_no = fields.Char(string="NABL Accreditation No.")


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    cal_lead_days = fields.Integer(string="Default Lead Days",
                                   config_parameter="calibration.lead_days", default=15)
    cal_auto_create = fields.Boolean(string="Auto-create Draft Orders",
                                     config_parameter="calibration.auto_create")
    cal_auto_offset = fields.Integer(string="Auto-create Offset (days)",
                                     config_parameter="calibration.auto_offset", default=7)
    cal_escalation_days = fields.Integer(string="Overdue Escalation Days",
                                         config_parameter="calibration.escalation_days", default=7)
    cal_retention_years = fields.Integer(string="Record Retention (years)",
                                         config_parameter="calibration.retention_years", default=5,
                                         help="Counted from instrument end of life. 0 = indefinite.")
    cal_compliance_target = fields.Float(string="Compliance Target (%)",
                                         config_parameter="calibration.compliance_target", default=95.0)
    cal_dashboard_period = fields.Selection(
        [("fy", "Fiscal Year"), ("cy", "Calendar Year"), ("12m", "Rolling 12 Months")],
        string="Default Dashboard Period", config_parameter="calibration.dashboard_period", default="fy")
    cal_fy_start_month = fields.Integer(string="Fiscal Year Start Month",
                                        config_parameter="calibration.fy_start_month", default=4)
    cal_label_size = fields.Selection(
        [("50x25", "50 x 25 mm"), ("70x35", "70 x 35 mm")],
        string="Label Size", config_parameter="calibration.label_size", default="50x25")
