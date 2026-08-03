# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class CalibrationOrder(models.Model):
    _name = "calibration.order"
    _description = "Calibration Order"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "calibration_date desc, id desc"

    name = fields.Char(readonly=True, copy=False, default=lambda self: _("New"))
    instrument_id = fields.Many2one(
        "calibration.instrument", required=True, index=True, tracking=True,
        domain="[('state', 'not in', ('retired', 'scrapped', 'lost'))]")
    instrument_code = fields.Char(related="instrument_id.code", store=True)
    category_id = fields.Many2one(related="instrument_id.category_id", store=True)
    department_id = fields.Many2one(related="instrument_id.department_id", store=True)
    custodian_id = fields.Many2one(related="instrument_id.custodian_id", store=True)
    company_id = fields.Many2one(related="instrument_id.company_id", store=True)
    currency_id = fields.Many2one(related="company_id.currency_id")

    scheduled_date = fields.Date()
    calibration_date = fields.Date(tracking=True)
    calibration_type = fields.Selection(
        [("internal", "Internal"), ("external", "External")],
        required=True, default="external")
    performed_by_id = fields.Many2one("hr.employee", string="Performed By")
    calibrator_qualification_ref = fields.Char(string="Calibrator Qualification Ref.")
    agency_id = fields.Many2one("res.partner", domain=[("is_calibration_agency", "=", True)])
    nabl_accredited = fields.Boolean(string="NABL Accredited")
    accreditation_no = fields.Char()
    sent_date = fields.Date(string="Dispatched On")
    received_date = fields.Date(string="Received Back On")
    outward_ref = fields.Char(string="Outward / Gate Pass Ref.")
    master_standard_ids = fields.Many2many(
        "calibration.instrument", "calibration_order_master_rel", "order_id", "master_id",
        string="Master Standards", domain=[("is_master_standard", "=", True)])
    master_snapshot = fields.Char(readonly=True, copy=False,
                                  help="Master standards with their certificate numbers at Done.")
    traceability_basis = fields.Text(
        help="Documented basis for calibration where no traceable standard applies "
             "(ISO 9001 7.1.5.2 a).")
    seal_intact = fields.Selection(
        [("intact", "Intact"), ("broken", "Broken"), ("na", "Not Applicable")],
        string="Seal As Received", default="na")
    temperature_c = fields.Float(string="Temperature (°C)")
    humidity_pct = fields.Float(string="Humidity (%RH)")

    line_ids = fields.One2many("calibration.order.line", "order_id", copy=True)
    overall_result = fields.Selection(
        [("pass", "Pass"), ("conditional", "Conditional"), ("fail", "Fail")],
        compute="_compute_overall_result", store=True, readonly=False, tracking=True)
    conditional_remarks = fields.Char()

    certificate_no = fields.Char(copy=False, index=True, tracking=True)
    certificate_date = fields.Date(copy=False)
    certificate_valid_until = fields.Date(copy=False, tracking=True)
    certificate_file = fields.Binary(attachment=True, copy=False)
    certificate_filename = fields.Char(copy=False)
    certificate_checksum = fields.Char(compute="_compute_certificate_checksum")
    certificate_revision = fields.Integer(default=0, copy=False)

    cost = fields.Monetary(currency_field="currency_id")
    vendor_bill_ref = fields.Char()

    impact_from = fields.Date(copy=False)
    impact_to = fields.Date(copy=False)
    impact_notes = fields.Text(copy=False)
    product_action = fields.Selection([
        ("reinspect", "Re-inspection of Affected Product"),
        ("concession", "Concession / Deviation"),
        ("customer", "Customer Notification"),
        ("none", "No Action (Justified)"),
    ], copy=False)
    failure_review_done = fields.Boolean(copy=False)

    is_historical = fields.Boolean(readonly=True, copy=False)
    in_progress_dt = fields.Datetime(readonly=True, copy=False)
    done_dt = fields.Datetime(readonly=True, copy=False)
    tat_days = fields.Float(compute="_compute_tat", store=True, string="TAT (days)")
    remarks = fields.Text()
    cancel_reason = fields.Char(copy=False)

    state = fields.Selection([
        ("draft", "Draft"), ("in_progress", "In Progress"),
        ("done", "Done"), ("cancel", "Cancelled")],
        default="draft", tracking=True, copy=False, index=True)

    # ------------------------------------------------------------- computes
    @api.depends("line_ids.result")
    def _compute_overall_result(self):
        for rec in self:
            if not rec.line_ids:
                rec.overall_result = rec.overall_result or False
            elif any(l.result == "fail" for l in rec.line_ids):
                rec.overall_result = "fail"
            elif rec.overall_result != "conditional":
                rec.overall_result = "pass"

    @api.depends("sent_date", "received_date", "in_progress_dt", "done_dt",
                 "calibration_type")
    def _compute_tat(self):
        for rec in self:
            tat = 0.0
            if rec.calibration_type == "external" and rec.sent_date and rec.received_date:
                tat = (rec.received_date - rec.sent_date).days
            elif rec.in_progress_dt and rec.done_dt:
                tat = (rec.done_dt - rec.in_progress_dt).total_seconds() / 86400.0
            rec.tat_days = tat

    def _compute_certificate_checksum(self):
        atts = self.env["ir.attachment"].sudo().search([
            ("res_model", "=", self._name),
            ("res_field", "=", "certificate_file"),
            ("res_id", "in", self.ids)])
        by_res = {a.res_id: a.checksum for a in atts}
        for rec in self:
            rec.certificate_checksum = by_res.get(rec.id, False)

    # ---------------------------------------------------------- constraints
    @api.constrains("instrument_id", "state")
    def _check_single_open(self):
        for rec in self:
            if rec.state in ("draft", "in_progress"):
                if self.search_count([
                        ("instrument_id", "=", rec.instrument_id.id),
                        ("state", "in", ("draft", "in_progress")),
                        ("id", "!=", rec.id)]):
                    raise ValidationError(_(
                        "Only one open calibration order is allowed per instrument (%s).",
                        rec.instrument_id.code))

    # -------------------------------------------------------------- actions
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", _("New")) == _("New"):
                vals["name"] = self.env["ir.sequence"].next_by_code(
                    "calibration.order") or _("New")
        return super().create(vals_list)

    def action_in_progress(self):
        for rec in self:
            if rec.state != "draft":
                raise UserError(_("Only draft orders can be started."))
            rec.write({"state": "in_progress", "in_progress_dt": fields.Datetime.now()})
            rec.instrument_id.state = "under_calibration"

    def action_load_template(self):
        for rec in self:
            lines = [(5, 0, 0)]
            for t in rec.instrument_id.category_id.parameter_template_ids:
                lines.append((0, 0, {
                    "parameter_name": t.parameter_name, "uom_id": t.uom_id.id,
                    "nominal_value": t.nominal_value,
                    "tolerance_plus": t.tolerance_plus,
                    "tolerance_minus": t.tolerance_minus}))
            rec.line_ids = lines

    def _validate_done(self):
        self.ensure_one()
        errors = []
        if not self.calibration_date:
            errors.append(_("actual calibration date"))
        if not self.is_historical and not self.line_ids:
            errors.append(_("at least one reading line"))
        if any(not l.result for l in self.line_ids):
            errors.append(_("a result on every line"))
        if not self.overall_result:
            errors.append(_("overall result"))
        if self.calibration_type == "internal" and not self.performed_by_id:
            errors.append(_("performed by (internal)"))
        if self.calibration_type == "external":
            if not self.agency_id:
                errors.append(_("calibration agency"))
            if not self.certificate_no:
                errors.append(_("certificate number"))
            if not self.certificate_file:
                errors.append(_("certificate PDF"))
        if not self.certificate_valid_until:
            errors.append(_("certificate validity date"))
        if self.overall_result == "conditional" and not self.conditional_remarks:
            errors.append(_("conditional remarks"))
        if (not self.master_standard_ids
                and not (self.calibration_type == "external" and self.nabl_accredited)
                and not self.traceability_basis):
            errors.append(_("traceability basis (no master standard and agency not NABL)"))
        if errors:
            raise UserError(_("Cannot mark Done. Missing: %s.", ", ".join(errors)))
        for master in self.master_standard_ids:
            if not master.holds_valid_certification(self.calibration_date):
                raise UserError(_(
                    "Master standard %s does not hold valid certification on %s.",
                    master.code, self.calibration_date))

    def action_done(self):
        for rec in self:
            if rec.state not in ("draft", "in_progress"):
                raise UserError(_("Only open orders can be completed."))
            rec._validate_done()
            vals = {"state": "done", "done_dt": fields.Datetime.now()}
            if rec.calibration_type == "internal" and not rec.certificate_no:
                vals["certificate_no"] = self.env["ir.sequence"].next_by_code(
                    "calibration.certificate.internal")
            if not rec.certificate_date:
                vals["certificate_date"] = rec.calibration_date
            if rec.master_standard_ids:
                vals["master_snapshot"] = "; ".join(
                    "%s (%s)" % (m.code, m.last_certificate_no or "-")
                    for m in rec.master_standard_ids)
            rec.write(vals)
            rec._apply_result()
            if rec.seal_intact == "broken":
                rec.message_post(body=_("Seal received BROKEN — recorded on certificate."))

    def _apply_result(self):
        self.ensure_one()
        inst = self.instrument_id
        if self.overall_result in ("pass", "conditional"):
            inst.write({
                "last_calibration_date": self.calibration_date,
                "last_certificate_no": self.certificate_no,
                "certificate_valid_until": self.certificate_valid_until,
                "state": "in_use",
                "restricted_use": self.overall_result == "conditional",
                "restriction_note": self.conditional_remarks
                if self.overall_result == "conditional" else False,
                "due_notified": False, "overdue_escalated": False,
            })
        else:  # fail
            prev = inst.calibration_ids.filtered(
                lambda o: o.state == "done" and o.id != self.id).sorted(
                key=lambda o: (o.calibration_date, o.id))
            self.write({
                "impact_from": prev and prev[-1].calibration_date
                or inst.last_calibration_date,
                "impact_to": self.calibration_date,
            })
            inst.state = "quarantine"
            managers = self.env.ref(
                "custom_instrument_calibration.group_calibration_manager").users
            for user in managers:
                self.activity_schedule(
                    "mail.mail_activity_data_todo", user_id=user.id,
                    summary=_("Assess validity of previous measurement results"),
                    note=_("Instrument %s failed calibration. Impact window: %s to %s. "
                           "Record impact notes and product action, then press "
                           "'Complete Impact Assessment'.",
                           inst.code, self.impact_from or "-", self.impact_to or "-"))

    def action_complete_impact(self):
        for rec in self:
            if rec.overall_result != "fail":
                raise UserError(_("Impact assessment applies to failed orders only."))
            if not rec.impact_notes or not rec.product_action:
                raise UserError(_(
                    "Impact notes and product action are mandatory to close the "
                    "failure review (ISO 9001 7.1.5.2)."))
            rec.failure_review_done = True
            rec.activity_feedback(["mail.mail_activity_data_todo"],
                                  feedback=_("Impact assessment completed."))
            rec.message_post(body=_(
                "Impact assessment completed. Product action: %s.",
                dict(rec._fields["product_action"].selection).get(rec.product_action)))

    def action_cancel(self):
        for rec in self:
            if rec.state == "done":
                raise UserError(_(
                    "Done orders cannot be cancelled; use the Correct Certificate wizard."))
            if not rec.cancel_reason:
                raise UserError(_("Enter a cancellation reason first."))
            was_in_progress = rec.state == "in_progress"
            rec.state = "cancel"
            if was_in_progress and rec.instrument_id.state == "under_calibration":
                # fall back; nightly cron will re-derive due/overdue
                rec.instrument_id.state = "in_use"

    def unlink(self):
        if self.env.context.get("calibration_disposition"):
            return super().unlink()
        if any(rec.state == "done" for rec in self):
            raise UserError(_(
                "Done calibration orders are retained records and cannot be deleted "
                "within the retention period."))
        return super().unlink()


class CalibrationOrderLine(models.Model):
    _name = "calibration.order.line"
    _description = "Calibration Reading"
    _order = "id"

    order_id = fields.Many2one("calibration.order", required=True, ondelete="cascade")
    parameter_name = fields.Char(required=True)
    uom_id = fields.Many2one("uom.uom", string="UoM")
    nominal_value = fields.Float(digits=(16, 4))
    tolerance_plus = fields.Float(digits=(16, 4))
    tolerance_minus = fields.Float(digits=(16, 4))
    as_found_value = fields.Float(digits=(16, 4))
    as_left_value = fields.Float(digits=(16, 4))
    error = fields.Float(compute="_compute_result", store=True, digits=(16, 4))
    result = fields.Selection([("pass", "Pass"), ("fail", "Fail")],
                              compute="_compute_result", store=True, readonly=False)
    override_remark = fields.Char()

    @api.depends("nominal_value", "tolerance_plus", "tolerance_minus", "as_left_value")
    def _compute_result(self):
        for line in self:
            line.error = line.as_left_value - line.nominal_value
            lo = line.nominal_value - line.tolerance_minus
            hi = line.nominal_value + line.tolerance_plus
            line.result = "pass" if lo <= line.as_left_value <= hi else "fail"
