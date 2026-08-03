# -*- coding: utf-8 -*-
from datetime import timedelta

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

IN_SERVICE = ["in_use", "due", "overdue", "under_calibration", "quarantine"]
NO_USE_STATES = ["overdue", "quarantine", "retired", "scrapped", "lost"]


class CalibrationInstrument(models.Model):
    _name = "calibration.instrument"
    _description = "Instrument"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "code"

    # ------------------------------------------------------------- identity
    name = fields.Char(required=True, tracking=True)
    code = fields.Char(readonly=True, copy=False, index=True)
    category_id = fields.Many2one("calibration.instrument.category", required=True, tracking=True)
    instrument_type = fields.Selection(
        [("measuring", "Measuring"), ("monitoring", "Monitoring"), ("reference", "Reference Standard")],
        default="measuring", required=True)
    is_master_standard = fields.Boolean(string="Master Standard", tracking=True)
    make = fields.Char()
    model_no = fields.Char(string="Model No.")
    serial_no = fields.Char(string="Serial No.")
    range_min = fields.Float(digits=(16, 4))
    range_max = fields.Float(digits=(16, 4))
    range_uom_id = fields.Many2one("uom.uom", string="Range UoM")
    least_count = fields.Char()
    accuracy_class = fields.Char()
    calibration_procedure_ref = fields.Char(string="Calibration Procedure / SOP Ref.")
    safeguard_note = fields.Text(string="Handling & Safeguarding Instructions")
    location = fields.Char()
    department_id = fields.Many2one("hr.department")
    custodian_id = fields.Many2one("hr.employee", required=True, tracking=True)
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company)
    purchase_date = fields.Date()
    vendor_id = fields.Many2one("res.partner")
    purchase_cost = fields.Monetary(currency_field="currency_id")
    purchase_ref = fields.Char()
    currency_id = fields.Many2one("res.currency", related="company_id.currency_id")
    notes = fields.Text()
    image_128 = fields.Image(max_width=128, max_height=128)

    # ------------------------------------------------------------ frequency
    calibration_type = fields.Selection(
        [("internal", "Internal"), ("external", "External"), ("both", "Both")],
        required=True, default="external")
    frequency_interval = fields.Integer(required=True, default=12, tracking=True)
    frequency_uom = fields.Selection(
        [("days", "Days"), ("weeks", "Weeks"), ("months", "Months"), ("years", "Years")],
        required=True, default="months", tracking=True)
    lead_days = fields.Integer(default=lambda self: self._default_lead_days())

    # ------------------------------------------------------------- tracking
    last_calibration_date = fields.Date(readonly=True, copy=False)
    last_certificate_no = fields.Char(readonly=True, copy=False)
    certificate_valid_until = fields.Date(readonly=True, copy=False)
    next_due_date = fields.Date(compute="_compute_due_dates", store=True)
    effective_due_date = fields.Date(compute="_compute_due_dates", store=True, index=True)
    restricted_use = fields.Boolean(readonly=True, copy=False)
    restriction_note = fields.Char(readonly=True, copy=False)

    state = fields.Selection([
        ("draft", "Draft"),
        ("in_use", "In Use"),
        ("due", "Due"),
        ("overdue", "Overdue"),
        ("under_calibration", "Under Calibration"),
        ("quarantine", "Quarantine"),
        ("retired", "Retired"),
        ("scrapped", "Scrapped"),
        ("lost", "Lost"),
    ], default="draft", tracking=True, copy=False, index=True)
    active = fields.Boolean(default=True)

    calibration_ids = fields.One2many("calibration.order", "instrument_id")
    calibration_count = fields.Integer(compute="_compute_counts")
    certificate_count = fields.Integer(compute="_compute_counts")
    state_log_ids = fields.One2many("calibration.state.log", "instrument_id")

    # ----------------------------------------------------------- retirement
    retirement_state = fields.Selection(
        [("none", "None"), ("pending", "Pending Approval")], default="none", copy=False)
    retirement_reason_id = fields.Many2one("calibration.retirement.reason", copy=False)
    retirement_remarks = fields.Text(copy=False)
    retirement_photo = fields.Image(copy=False)
    retirement_date = fields.Date(readonly=True, copy=False)
    retirement_user_id = fields.Many2one("res.users", readonly=True, copy=False)
    disposal_ref = fields.Char(string="Scrap Note / Gate Pass Ref.", copy=False)
    disposal_date = fields.Date(readonly=True, copy=False)
    lost_reason = fields.Text(readonly=True, copy=False)
    end_of_life_date = fields.Date(readonly=True, copy=False)

    # cron helper flags
    due_notified = fields.Boolean(copy=False)
    overdue_escalated = fields.Boolean(copy=False)

    _sql_constraints = [
        ("code_company_uniq", "unique(code, company_id)", "Instrument code must be unique per company."),
    ]

    # ------------------------------------------------------------ defaults
    @api.model
    def _default_lead_days(self):
        return int(self.env["ir.config_parameter"].sudo().get_param("calibration.lead_days", 15))

    @api.onchange("category_id")
    def _onchange_category(self):
        if self.category_id:
            self.frequency_interval = self.category_id.default_frequency_interval
            self.frequency_uom = self.category_id.default_frequency_uom
            self.calibration_type = self.category_id.default_calibration_type

    # ------------------------------------------------------------- compute
    @api.depends("last_calibration_date", "frequency_interval", "frequency_uom",
                 "certificate_valid_until")
    def _compute_due_dates(self):
        for rec in self:
            next_due = False
            if rec.last_calibration_date and rec.frequency_interval:
                delta = {
                    "days": relativedelta(days=rec.frequency_interval),
                    "weeks": relativedelta(weeks=rec.frequency_interval),
                    "months": relativedelta(months=rec.frequency_interval),
                    "years": relativedelta(years=rec.frequency_interval),
                }[rec.frequency_uom]
                next_due = rec.last_calibration_date + delta
            rec.next_due_date = next_due
            effective = next_due
            if rec.certificate_valid_until and (not effective or rec.certificate_valid_until < effective):
                effective = rec.certificate_valid_until
            rec.effective_due_date = effective

    def _compute_counts(self):
        for rec in self:
            done = rec.calibration_ids.filtered(lambda o: o.state == "done")
            rec.calibration_count = len(rec.calibration_ids)
            rec.certificate_count = len(done)

    def holds_valid_certification(self, at_date=None):
        self.ensure_one()
        at_date = at_date or fields.Date.context_today(self)
        done = self.calibration_ids.filtered(lambda o: o.state == "done").sorted(
            key=lambda o: (o.calibration_date or fields.Date.today(), o.id))
        if not done:
            return False
        last = done[-1]
        return (last.overall_result in ("pass", "conditional")
                and self.effective_due_date and at_date <= self.effective_due_date)

    # -------------------------------------------------------------- guards
    def write(self, vals):
        if "code" in vals:
            for rec in self:
                if rec.code and rec.calibration_ids.filtered(lambda o: o.state == "done"):
                    raise UserError(_("The instrument code is immutable once a calibration is done."))
        if vals.get("active") is False:
            bad = self.filtered(lambda r: r.state not in ("retired", "scrapped", "lost"))
            if bad:
                raise UserError(_("Only Retired / Scrapped / Lost instruments can be archived."))
        state_changing = "state" in vals
        old_states = {rec.id: rec.state for rec in self} if state_changing else {}
        res = super().write(vals)
        if state_changing:
            now = fields.Datetime.now()
            for rec in self:
                if old_states.get(rec.id) != rec.state:
                    open_logs = rec.state_log_ids.filtered(lambda l: not l.date_to)
                    open_logs.write({"date_to": now})
                    self.env["calibration.state.log"].create({
                        "instrument_id": rec.id, "state": rec.state, "date_from": now})
                    if rec.state in ("retired", "scrapped", "lost") and not rec.end_of_life_date:
                        super(CalibrationInstrument, rec).write(
                            {"end_of_life_date": fields.Date.context_today(rec)})
        return res

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("code") and vals.get("category_id"):
                vals["code"] = self.env["calibration.instrument.category"].browse(
                    vals["category_id"]).next_code()
        recs = super().create(vals_list)
        for rec in recs:
            self.env["calibration.state.log"].create({
                "instrument_id": rec.id, "state": rec.state})
        return recs

    def unlink(self):
        if self.env.context.get("calibration_disposition"):
            return super().unlink()
        for rec in self:
            if rec.state != "draft" or rec.calibration_ids:
                raise UserError(_(
                    "Calibration records are retained for the configured retention period. "
                    "Only draft instruments without calibration history can be deleted; "
                    "use the retirement workflow, and post-retention Disposition for removal."))
        return super().unlink()

    # ------------------------------------------------------------- actions
    def action_view_calibrations(self):
        self.ensure_one()
        action = self.env["ir.actions.act_window"]._for_xml_id(
            "custom_instrument_calibration.action_calibration_order")
        action["domain"] = [("instrument_id", "=", self.id)]
        action["context"] = {"default_instrument_id": self.id}
        return action

    def action_view_certificates(self):
        self.ensure_one()
        action = self.env["ir.actions.act_window"]._for_xml_id(
            "custom_instrument_calibration.action_certificate_repository")
        action["domain"] = [("instrument_id", "=", self.id), ("state", "=", "done")]
        return action

    def action_plan_calibration(self):
        orders = self.env["calibration.order"]
        for rec in self:
            if rec.state in ("retired", "scrapped", "lost"):
                continue
            if rec.calibration_ids.filtered(lambda o: o.state in ("draft", "in_progress")):
                continue
            orders |= self.env["calibration.order"].create({
                "instrument_id": rec.id,
                "scheduled_date": rec.effective_due_date or fields.Date.context_today(rec),
            })
        return {
            "type": "ir.actions.act_window",
            "res_model": "calibration.order",
            "view_mode": "list,form",
            "domain": [("id", "in", orders.ids)],
            "name": _("Planned Calibrations"),
        }

    def action_print_label(self):
        size = self.env["ir.config_parameter"].sudo().get_param("calibration.label_size", "50x25")
        ref = ("custom_instrument_calibration.action_report_label_70"
               if size == "70x35" else
               "custom_instrument_calibration.action_report_label_50")
        return self.env.ref(ref).report_action(self)

    def action_audit_bundle(self):
        self.ensure_one()
        return {"type": "ir.actions.act_url",
                "url": "/calibration/audit_bundle/%d" % self.id,
                "target": "self"}

    # --------------------------------------------------- retirement workflow
    def action_approve_retirement(self):
        self._check_manager()
        for rec in self:
            if rec.retirement_state != "pending":
                raise UserError(_("No pending retirement request."))
            if rec.calibration_ids.filtered(lambda o: o.state in ("draft", "in_progress")):
                raise UserError(_("Close open calibration orders before retirement."))
            rec.write({
                "state": "retired", "retirement_state": "none", "active": False,
                "retirement_date": fields.Date.context_today(rec),
                "retirement_user_id": self.env.user.id,
            })
            rec.message_post(body=_("Retirement approved. Reason: %s",
                                    rec.retirement_reason_id.name or "-"))

    def action_reject_retirement(self):
        self._check_manager()
        self.write({"retirement_state": "none"})
        for rec in self:
            rec.message_post(body=_("Retirement request rejected."))

    def action_scrap(self):
        self._check_manager()
        for rec in self:
            if rec.state != "retired":
                raise UserError(_("Only retired instruments can be scrapped."))
            if not rec.disposal_ref:
                raise UserError(_("Enter the scrap note / gate pass reference first."))
            rec.write({"state": "scrapped",
                       "disposal_date": fields.Date.context_today(rec)})

    def action_reactivate(self):
        self._check_manager()
        for rec in self:
            if rec.state not in ("retired", "lost"):
                raise UserError(_("Only Retired or Lost instruments can be reactivated."))
            rec.write({"state": "under_calibration", "active": True})
            rec.message_post(body=_(
                "Reactivated by manager; a fresh passed calibration is required before use."))

    def _check_manager(self):
        if not self.env.user.has_group(
                "custom_instrument_calibration.group_calibration_manager"):
            raise UserError(_("Only a Calibration Manager may perform this action."))

    # ---------------------------------------------------------------- crons
    @api.model
    def cron_update_states(self):
        today = fields.Date.context_today(self)
        for rec in self.search([("state", "in", ["in_use", "due", "overdue"])]):
            eff = rec.effective_due_date
            if not eff:
                continue
            lead = rec.lead_days or self._default_lead_days()
            if today > eff:
                new = "overdue"
            elif today >= eff - timedelta(days=lead):
                new = "due"
            else:
                new = "in_use"
            if new != rec.state:
                rec.state = new
                if new == "in_use":
                    rec.write({"due_notified": False, "overdue_escalated": False})

    @api.model
    def cron_notifications(self):
        icp = self.env["ir.config_parameter"].sudo()
        today = fields.Date.context_today(self)
        esc_days = int(icp.get_param("calibration.escalation_days", 7))
        managers = self.env.ref(
            "custom_instrument_calibration.group_calibration_manager").users

        # custodian activity on entering Due
        for rec in self.search([("state", "=", "due"), ("due_notified", "=", False)]):
            user = rec.custodian_id.user_id or self.env.user
            rec.activity_schedule(
                "mail.mail_activity_data_todo", user_id=user.id,
                summary=_("Calibration due"),
                note=_("Instrument %s is due for calibration by %s.",
                       rec.code, rec.effective_due_date))
            rec.due_notified = True

        # escalation
        esc = self.search([("state", "=", "overdue"), ("overdue_escalated", "=", False)]).filtered(
            lambda r: r.effective_due_date
            and (today - r.effective_due_date).days >= esc_days)
        template = self.env.ref(
            "custom_instrument_calibration.mail_template_overdue_escalation",
            raise_if_not_found=False)
        for rec in esc:
            for user in managers:
                rec.activity_schedule(
                    "mail.mail_activity_data_todo", user_id=user.id,
                    summary=_("Calibration OVERDUE"),
                    note=_("Instrument %s is overdue since %s.",
                           rec.code, rec.effective_due_date))
            if template:
                emails = ",".join(u.email for u in managers if u.email)
                if emails:
                    template.send_mail(rec.id, force_send=False,
                                       email_values={"email_to": emails})
            rec.overdue_escalated = True

        # auto-create draft orders
        if icp.get_param("calibration.auto_create"):
            offset = int(icp.get_param("calibration.auto_offset", 7))
            horizon = today + timedelta(days=offset)
            for rec in self.search([
                    ("state", "in", ["in_use", "due", "overdue"]),
                    ("effective_due_date", "!=", False),
                    ("effective_due_date", "<=", horizon)]):
                if not rec.calibration_ids.filtered(
                        lambda o: o.state in ("draft", "in_progress")):
                    order = self.env["calibration.order"].create({
                        "instrument_id": rec.id,
                        "scheduled_date": rec.effective_due_date})
                    user = rec.custodian_id.user_id
                    if user:
                        order.activity_schedule(
                            "mail.mail_activity_data_todo", user_id=user.id,
                            summary=_("Arrange calibration"),
                            note=_("Auto-planned for %s.", rec.code))

        # manager digest
        due = self.search([("state", "=", "due")])
        overdue = self.search([("state", "=", "overdue")])
        expiring = self.search([
            ("state", "in", ["in_use", "due"]),
            ("certificate_valid_until", "!=", False),
            ("certificate_valid_until", "<=", today + timedelta(days=30))])
        if (due or overdue or expiring) and managers:
            def _rows(recs):
                return "".join(
                    "<li>%s — %s (eff. due %s)</li>" % (
                        r.code, r.name, r.effective_due_date or "-")
                    for r in recs[:50])
            body = (
                "<p>Calibration daily digest</p>"
                "<p><b>Due (%d)</b></p><ul>%s</ul>"
                "<p><b>Overdue (%d)</b></p><ul>%s</ul>"
                "<p><b>Certificates expiring in 30 days (%d)</b></p><ul>%s</ul>"
            ) % (len(due), _rows(due), len(overdue), _rows(overdue),
                 len(expiring), _rows(expiring))
            emails = ",".join(u.email for u in managers if u.email)
            if emails:
                self.env["mail.mail"].sudo().create({
                    "subject": _("Calibration Digest — %s", today),
                    "email_to": emails,
                    "body_html": body,
                    "auto_delete": True,
                }).send()
