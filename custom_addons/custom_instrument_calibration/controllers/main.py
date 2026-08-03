# -*- coding: utf-8 -*-
from odoo import _, http
from odoo.exceptions import UserError
from odoo.http import content_disposition, request


class CalibrationController(http.Controller):

    @http.route("/calibration/export/<int:wizard_id>", type="http", auth="user")
    def export_register(self, wizard_id, **kw):
        wiz = request.env["calibration.register.wizard"].browse(wizard_id).exists()
        if not wiz or not request.env.user.has_group(
                "custom_instrument_calibration.group_calibration_user"):
            return request.not_found()
        from odoo.addons.custom_instrument_calibration.report import xlsx_engine
        fname, data = xlsx_engine.build(request.env, wiz)
        return request.make_response(data, headers=[
            ("Content-Type",
             "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
            ("Content-Disposition", content_disposition(fname)),
        ])

    @http.route("/calibration/audit_bundle/<int:instrument_id>", type="http",
                auth="user")
    def audit_bundle(self, instrument_id, **kw):
        env = request.env
        if not env.user.has_group(
                "custom_instrument_calibration.group_calibration_user"):
            return request.not_found()
        inst = env["calibration.instrument"].with_context(
            active_test=False).browse(instrument_id).exists()
        if not inst:
            return request.not_found()
        pdf, _type = env["ir.actions.report"]._render_qweb_pdf(
            "custom_instrument_calibration.action_report_history_card", [inst.id])
        parts = [pdf]
        orders = inst.calibration_ids.filtered(
            lambda o: o.state == "done").sorted(
            key=lambda o: (o.calibration_date or o.create_date.date(), o.id))
        atts = env["ir.attachment"].sudo().search([
            ("res_model", "=", "calibration.order"),
            ("res_field", "=", "certificate_file"),
            ("res_id", "in", orders.ids)])
        by_res = {a.res_id: a for a in atts}
        for order in orders:
            att = by_res.get(order.id)
            if att and att.mimetype == "application/pdf":
                parts.append(att.raw)
            elif order.calibration_type == "internal":
                cert_pdf, _t = env["ir.actions.report"]._render_qweb_pdf(
                    "custom_instrument_calibration.action_report_certificate",
                    [order.id])
                parts.append(cert_pdf)
        from odoo.tools.pdf import merge_pdf
        merged = merge_pdf(parts) if len(parts) > 1 else parts[0]
        fname = "Audit_Bundle_%s.pdf" % (inst.code or inst.id)
        return request.make_response(merged, headers=[
            ("Content-Type", "application/pdf"),
            ("Content-Disposition", content_disposition(fname)),
        ])
