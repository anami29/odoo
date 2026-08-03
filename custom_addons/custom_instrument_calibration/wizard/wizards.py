# -*- coding: utf-8 -*-
from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class CalibrationHistoricalWizard(models.TransientModel):
    _name = "calibration.historical.wizard"
    _description = "Record Historical Calibration"

    instrument_id = fields.Many2one("calibration.instrument", required=True)
    calibration_date = fields.Date(required=True)
    certificate_no = fields.Char(required=True)
    certificate_date = fields.Date()
    certificate_valid_until = fields.Date(required=True)
    calibration_type = fields.Selection(
        [("internal", "Internal"), ("external", "External")], default="external",
        required=True)
    agency_id = fields.Many2one("res.partner",
                                domain=[("is_calibration_agency", "=", True)])
    certificate_file = fields.Binary()
    certificate_filename = fields.Char()

    def action_confirm(self):
        self.ensure_one()
        order = self.env["calibration.order"].create({
            "instrument_id": self.instrument_id.id,
            "calibration_date": self.calibration_date,
            "calibration_type": self.calibration_type,
            "agency_id": self.agency_id.id,
            "certificate_no": self.certificate_no,
            "certificate_date": self.certificate_date or self.calibration_date,
            "certificate_valid_until": self.certificate_valid_until,
            "certificate_file": self.certificate_file,
            "certificate_filename": self.certificate_filename,
            "overall_result": "pass",
            "is_historical": True,
            "state": "done",
            "done_dt": fields.Datetime.now(),
        })
        order._apply_result()
        order.message_post(body=_("Historical calibration recorded by %s.",
                                  self.env.user.name))
        return {"type": "ir.actions.act_window_close"}


class CalibrationDamageWizard(models.TransientModel):
    _name = "calibration.damage.wizard"
    _description = "Report Instrument Damage"

    instrument_id = fields.Many2one("calibration.instrument", required=True)
    description = fields.Text(required=True)
    photo = fields.Image()

    def action_confirm(self):
        self.ensure_one()
        inst = self.instrument_id
        if inst.state in ("retired", "scrapped", "lost"):
            raise UserError(_("Instrument is already out of service."))
        inst.state = "quarantine"
        inst.message_post(body=_("DAMAGE REPORTED by %s: %s",
                                 self.env.user.name, self.description))
        managers = self.env.ref(
            "custom_instrument_calibration.group_calibration_manager").users
        for user in managers:
            inst.activity_schedule(
                "mail.mail_activity_data_todo", user_id=user.id,
                summary=_("Damage reported — decide repair / retirement"),
                note=self.description)
        return {"type": "ir.actions.act_window_close"}


class CalibrationRetirementWizard(models.TransientModel):
    _name = "calibration.retirement.wizard"
    _description = "Retirement Request"

    instrument_id = fields.Many2one("calibration.instrument", required=True)
    reason_id = fields.Many2one("calibration.retirement.reason", required=True)
    remarks = fields.Text()
    photo = fields.Image()

    def action_confirm(self):
        self.ensure_one()
        inst = self.instrument_id
        inst.write({
            "retirement_state": "pending",
            "retirement_reason_id": self.reason_id.id,
            "retirement_remarks": self.remarks,
            "retirement_photo": self.photo,
        })
        inst.message_post(body=_(
            "Retirement requested by %s. Reason: %s. %s",
            self.env.user.name, self.reason_id.name, self.remarks or ""))
        managers = self.env.ref(
            "custom_instrument_calibration.group_calibration_manager").users
        for user in managers:
            inst.activity_schedule(
                "mail.mail_activity_data_todo", user_id=user.id,
                summary=_("Retirement approval requested"),
                note=self.reason_id.name)
        return {"type": "ir.actions.act_window_close"}


class CalibrationStateOverrideWizard(models.TransientModel):
    _name = "calibration.state.override.wizard"
    _description = "Manual State Override"

    instrument_id = fields.Many2one("calibration.instrument", required=True)
    new_state = fields.Selection([
        ("draft", "Draft"), ("in_use", "In Use"), ("due", "Due"),
        ("overdue", "Overdue"), ("under_calibration", "Under Calibration"),
        ("quarantine", "Quarantine"), ("lost", "Lost")], required=True)
    reason = fields.Text(required=True)

    def action_confirm(self):
        self.ensure_one()
        self.instrument_id._check_manager()
        vals = {"state": self.new_state}
        if self.new_state == "lost":
            vals["lost_reason"] = self.reason
        self.instrument_id.write(vals)
        self.instrument_id.message_post(body=_(
            "MANUAL STATE OVERRIDE to '%s' by %s. Reason: %s",
            self.new_state, self.env.user.name, self.reason))
        return {"type": "ir.actions.act_window_close"}


class CalibrationCertificateCorrectionWizard(models.TransientModel):
    _name = "calibration.certificate.correction.wizard"
    _description = "Correct Certificate (audited)"

    order_id = fields.Many2one("calibration.order", required=True)
    new_certificate_no = fields.Char()
    new_certificate_date = fields.Date()
    new_certificate_valid_until = fields.Date()
    new_certificate_file = fields.Binary()
    new_certificate_filename = fields.Char()
    reason = fields.Text(required=True)

    def action_confirm(self):
        self.ensure_one()
        order = self.order_id
        order.instrument_id._check_manager()
        if order.state != "done":
            raise UserError(_("Corrections apply to done orders only."))
        old = (order.certificate_no, order.certificate_date,
               order.certificate_valid_until)
        # preserve prior file as a plain attachment revision
        if self.new_certificate_file and order.certificate_file:
            att = self.env["ir.attachment"].sudo().search([
                ("res_model", "=", "calibration.order"),
                ("res_field", "=", "certificate_file"),
                ("res_id", "=", order.id)], limit=1)
            if att:
                rev = order.certificate_revision + 1
                att.copy({
                    "res_field": False,
                    "name": _("Certificate rev %s — %s") % (
                        rev, order.certificate_filename or "certificate.pdf"),
                })
                order.certificate_revision = rev
        vals = {}
        if self.new_certificate_no:
            vals["certificate_no"] = self.new_certificate_no
        if self.new_certificate_date:
            vals["certificate_date"] = self.new_certificate_date
        if self.new_certificate_valid_until:
            vals["certificate_valid_until"] = self.new_certificate_valid_until
        if self.new_certificate_file:
            vals["certificate_file"] = self.new_certificate_file
            vals["certificate_filename"] = self.new_certificate_filename
        order.write(vals)
        if self.new_certificate_valid_until or self.new_certificate_no:
            order._apply_result()  # refresh instrument writeback
        order.message_post(body=_(
            "CERTIFICATE CORRECTED by %s. Reason: %s. Previous values — no: %s, "
            "date: %s, valid until: %s.",
            self.env.user.name, self.reason, old[0] or "-", old[1] or "-",
            old[2] or "-"))
        return {"type": "ir.actions.act_window_close"}


class CalibrationDispositionWizard(models.TransientModel):
    _name = "calibration.disposition.wizard"
    _description = "Post-retention Record Disposition"

    eligible_ids = fields.Many2many(
        "calibration.instrument", string="Eligible Instruments",
        default=lambda self: self._default_eligible())
    reason = fields.Text(required=True)

    @api.model
    def _default_eligible(self):
        icp = self.env["ir.config_parameter"].sudo()
        years = int(icp.get_param("calibration.retention_years", 0))
        if not years:
            return []
        today = fields.Date.context_today(self)
        cutoff = today - relativedelta(years=years)
        recs = self.env["calibration.instrument"].with_context(
            active_test=False).search([
                ("state", "in", ("retired", "scrapped", "lost")),
                ("end_of_life_date", "!=", False),
                ("end_of_life_date", "<=", cutoff)])
        return recs.ids

    def action_confirm(self):
        self.ensure_one()
        self.env["calibration.instrument"]._check_manager()
        eligible = set(self._default_eligible())
        for inst in self.eligible_ids:
            if inst.id not in eligible:
                raise UserError(_(
                    "%s is still within the retention period.", inst.code))
            self.env["calibration.record.disposition"].create({
                "name": inst.code, "instrument_name": inst.name,
                "category_name": inst.category_id.name,
                "end_of_life_date": inst.end_of_life_date,
                "order_count": len(inst.calibration_ids),
                "reason": self.reason,
                "company_id": inst.company_id.id,
            })
            ctx = {"calibration_disposition": True}
            inst.calibration_ids.with_context(**ctx).unlink()
            inst.with_context(**ctx).unlink()
        return {"type": "ir.actions.act_window_close"}


REPORTS = [
    ("register", "Calibration Register"),
    ("due_overdue", "Due / Overdue List"),
    ("oot", "Out-of-Tolerance Register"),
    ("retired", "Retired Instrument Register"),
    ("disposition", "Disposition Register"),
    ("compliance", "Compliance Summary (MIS)"),
    ("plan_actual", "Plan vs Actual (MIS)"),
    ("forecast", "Annual Due-Load Forecast (MIS)"),
    ("cost", "Cost Analysis (MIS)"),
    ("agency", "Agency Performance (MIS)"),
    ("downtime", "Instrument Downtime (MIS)"),
    ("failure_trend", "Failure / OOT Trend (MIS)"),
    ("custodian_load", "Custodian / Department Load (MIS)"),
]

COST_REPORTS = {"cost", "agency"}


class CalibrationRegisterWizard(models.TransientModel):
    _name = "calibration.register.wizard"
    _description = "Calibration Register / MIS Export"

    report_type = fields.Selection(REPORTS, required=True, default="register")
    date_from = fields.Date(default=lambda self: self._default_from())
    date_to = fields.Date(default=fields.Date.context_today)
    category_id = fields.Many2one("calibration.instrument.category")
    department_id = fields.Many2one("hr.department")
    agency_id = fields.Many2one("res.partner",
                                domain=[("is_calibration_agency", "=", True)])
    custodian_id = fields.Many2one("hr.employee")
    include_archived = fields.Boolean(string="Include Retired / Archived", default=True)

    @api.model
    def _default_from(self):
        d_from, _to, _k = self.env["calibration.dashboard"]._period("fy")
        return d_from

    def action_export(self):
        self.ensure_one()
        if (self.report_type in COST_REPORTS
                and not self.env.user.has_group(
                    "custom_instrument_calibration.group_calibration_manager")):
            raise UserError(_("Cost reports are restricted to Calibration Managers."))
        return {"type": "ir.actions.act_url",
                "url": "/calibration/export/%d" % self.id,
                "target": "self"}
