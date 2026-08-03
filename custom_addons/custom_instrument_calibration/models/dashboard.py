# -*- coding: utf-8 -*-
from datetime import date, timedelta

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models

IN_SERVICE = ["in_use", "due", "overdue", "under_calibration", "quarantine"]


def month_label(d):
    return d.strftime("%b %y")


class CalibrationDashboard(models.AbstractModel):
    _name = "calibration.dashboard"
    _description = "Calibration Dashboard Data Provider"

    @api.model
    def _period(self, key):
        icp = self.env["ir.config_parameter"].sudo()
        today = fields.Date.context_today(self)
        key = key or icp.get_param("calibration.dashboard_period", "fy")
        if key == "cy":
            return date(today.year, 1, 1), date(today.year, 12, 31), key
        if key == "12m":
            return today - relativedelta(months=12) + timedelta(days=1), today, key
        fy_month = int(icp.get_param("calibration.fy_start_month", 4))
        start = date(today.year, fy_month, 1)
        if today < start:
            start = date(today.year - 1, fy_month, 1)
        return start, start + relativedelta(years=1) - timedelta(days=1), "fy"

    @api.model
    def get_data(self, filters=None):
        filters = filters or {}
        today = fields.Date.context_today(self)
        d_from, d_to, period_key = self._period(filters.get("period"))

        Inst = self.env["calibration.instrument"]
        Order = self.env["calibration.order"]

        inst_dom = [("state", "in", IN_SERVICE)]
        order_dom = [("state", "=", "done"), ("is_historical", "=", False),
                     ("calibration_date", ">=", d_from),
                     ("calibration_date", "<=", d_to)]
        for key, field_i, field_o in [
                ("category_id", "category_id", "category_id"),
                ("department_id", "department_id", "department_id"),
                ("agency_id", None, "agency_id"),
                ("custodian_id", "custodian_id", "custodian_id")]:
            val = filters.get(key)
            if val:
                if field_i:
                    inst_dom.append((field_i, "=", val))
                order_dom.append((field_o, "=", val))

        instruments = Inst.search(inst_dom)
        orders = Order.search(order_dom)

        by_state = {}
        for rec in instruments:
            by_state[rec.state] = by_state.get(rec.state, 0) + 1
        in_service = len(instruments)
        compliant = by_state.get("in_use", 0) + by_state.get("due", 0)
        compliance = round(compliant * 100.0 / in_service, 1) if in_service else 0.0

        on_time = sum(1 for o in orders if self._on_time(o))
        on_time_rate = round(on_time * 100.0 / len(orders), 1) if orders else 0.0

        fails = orders.filtered(lambda o: o.overall_result == "fail")
        oot_rate = round(len(fails) * 100.0 / len(orders), 1) if orders else 0.0

        ext = orders.filtered(lambda o: o.calibration_type == "external" and o.tat_days)
        internal = orders.filtered(lambda o: o.calibration_type == "internal" and o.tat_days)
        tat_ext = round(sum(ext.mapped("tat_days")) / len(ext), 1) if ext else 0.0
        tat_int = round(sum(internal.mapped("tat_days")) / len(internal), 1) if internal else 0.0

        overdue = instruments.filtered(lambda r: r.state == "overdue")
        worst_aging = max(
            [(today - r.effective_due_date).days
             for r in overdue if r.effective_due_date], default=0)
        aging_buckets = {"1-7": 0, "8-30": 0, "31-90": 0, ">90": 0}
        for r in overdue:
            if not r.effective_due_date:
                continue
            days = (today - r.effective_due_date).days
            if days <= 7:
                aging_buckets["1-7"] += 1
            elif days <= 30:
                aging_buckets["8-30"] += 1
            elif days <= 90:
                aging_buckets["31-90"] += 1
            else:
                aging_buckets[">90"] += 1

        cost_period = sum(orders.mapped("cost"))
        fy_from, fy_to, _k = self._period("fy")
        ytd_orders = Order.search([
            ("state", "=", "done"), ("is_historical", "=", False),
            ("calibration_date", ">=", fy_from), ("calibration_date", "<=", today)])
        cost_ytd = sum(ytd_orders.mapped("cost"))

        exp = {}
        for days in (30, 60, 90):
            exp[str(days)] = Inst.search_count(inst_dom + [
                ("certificate_valid_until", "!=", False),
                ("certificate_valid_until", ">=", today),
                ("certificate_valid_until", "<=", today + timedelta(days=days))])

        # ---- charts -------------------------------------------------------
        months = []
        cur = date(d_from.year, d_from.month, 1)
        while cur <= d_to:
            months.append(cur)
            cur = cur + relativedelta(months=1)
        months = months[-12:]

        due_load = []
        forecast_months = [date(today.year, today.month, 1) + relativedelta(months=i)
                           for i in range(12)]
        for m in forecast_months:
            m_end = m + relativedelta(months=1) - timedelta(days=1)
            cnt = Inst.search_count(inst_dom + [
                ("effective_due_date", ">=", m), ("effective_due_date", "<=", m_end)])
            due_load.append({"label": month_label(m), "value": cnt})

        plan_actual, oot_trend, cost_trend = [], [], []
        for m in months:
            m_end = m + relativedelta(months=1) - timedelta(days=1)
            m_orders = orders.filtered(
                lambda o: o.calibration_date and m <= o.calibration_date <= m_end)
            due_cnt = Inst.with_context(active_test=False).search_count([
                ("effective_due_date", ">=", m), ("effective_due_date", "<=", m_end)])
            plan_actual.append({"label": month_label(m), "due": due_cnt,
                                "done": len(m_orders)})
            m_fails = len(m_orders.filtered(lambda o: o.overall_result == "fail"))
            oot_trend.append({"label": month_label(m), "value": m_fails})
            cost_trend.append({"label": month_label(m),
                               "value": round(sum(m_orders.mapped("cost")), 2)})

        cost_by_agency, tat_by_agency = [], []
        ag_data = {}
        for o in orders.filtered(lambda o: o.agency_id):
            d = ag_data.setdefault(o.agency_id.name, {"cost": 0.0, "tat": [], "n": 0})
            d["cost"] += o.cost
            d["n"] += 1
            if o.tat_days:
                d["tat"].append(o.tat_days)
        for name, d in sorted(ag_data.items(), key=lambda kv: -kv[1]["cost"])[:8]:
            cost_by_agency.append({"label": name, "value": round(d["cost"], 2)})
            tat_by_agency.append({
                "label": name,
                "value": round(sum(d["tat"]) / len(d["tat"]), 1) if d["tat"] else 0.0})

        status_labels = {
            "in_use": "In Use", "due": "Due", "overdue": "Overdue",
            "under_calibration": "Under Calibration", "quarantine": "Quarantine"}
        status_chart = [{"label": lbl, "value": by_state.get(key, 0), "state": key}
                        for key, lbl in status_labels.items()]

        is_manager = self.env.user.has_group(
            "custom_instrument_calibration.group_calibration_manager")
        target = float(self.env["ir.config_parameter"].sudo().get_param(
            "calibration.compliance_target", 95.0))

        def inst_action(dom, name):
            return {"model": "calibration.instrument", "name": name,
                    "domain": inst_dom + dom}

        domains = {
            "in_service": inst_action([], "In-service Instruments"),
            "due": inst_action([("state", "=", "due")], "Due"),
            "overdue": inst_action([("state", "=", "overdue")], "Overdue"),
            "under_calibration": inst_action(
                [("state", "=", "under_calibration")], "Under Calibration"),
            "quarantine": inst_action([("state", "=", "quarantine")], "Quarantine"),
            "in_use": inst_action([("state", "=", "in_use")], "In Use"),
            "orders": {"model": "calibration.order", "name": "Calibrations (period)",
                       "domain": order_dom},
            "fails": {"model": "calibration.order", "name": "Out of Tolerance",
                      "domain": order_dom + [("overall_result", "=", "fail")]},
            "expiring30": inst_action(
                [("certificate_valid_until", "!=", False),
                 ("certificate_valid_until", ">=", today.isoformat()),
                 ("certificate_valid_until", "<=",
                  (today + timedelta(days=30)).isoformat())],
                "Certificates expiring in 30 days"),
        }

        Cat = self.env["calibration.instrument.category"].search([])
        Dep = self.env["hr.department"].search([])
        Ag = self.env["res.partner"].search([("is_calibration_agency", "=", True)])

        return {
            "period": {"key": period_key, "from": d_from.isoformat(),
                       "to": d_to.isoformat()},
            "is_manager": is_manager,
            "currency": self.env.company.currency_id.symbol or "",
            "kpis": {
                "in_service": in_service,
                "by_state": by_state,
                "compliance": compliance,
                "target": target,
                "on_time": on_time_rate,
                "overdue": len(overdue),
                "worst_aging": worst_aging,
                "oot_rate": oot_rate,
                "tat_ext": tat_ext,
                "tat_int": tat_int,
                "out_of_service": by_state.get("under_calibration", 0)
                + by_state.get("quarantine", 0),
                "cost_period": round(cost_period, 2),
                "cost_ytd": round(cost_ytd, 2),
                "expiring": exp,
            },
            "charts": {
                "status": status_chart,
                "due_load": due_load,
                "plan_actual": plan_actual,
                "aging": [{"label": k, "value": v} for k, v in aging_buckets.items()],
                "oot_trend": oot_trend,
                "cost_trend": cost_trend,
                "cost_by_agency": cost_by_agency,
                "tat_by_agency": tat_by_agency,
            },
            "domains": domains,
            "options": {
                "categories": [{"id": c.id, "name": c.name} for c in Cat],
                "departments": [{"id": d.id, "name": d.name} for d in Dep],
                "agencies": [{"id": a.id, "name": a.name} for a in Ag],
            },
        }

    @api.model
    def _on_time(self, order):
        inst = order.instrument_id
        prev = inst.calibration_ids.filtered(
            lambda o: o.state == "done" and o.calibration_date
            and o.calibration_date < (order.calibration_date or fields.Date.today()))
        if not prev:
            return True
        # due at the time = previous calibration + frequency (approximation
        # consistent with §17.4; certificate validity of the previous order caps it)
        last = prev.sorted(key=lambda o: (o.calibration_date, o.id))[-1]
        from dateutil.relativedelta import relativedelta as rd
        delta = {"days": rd(days=inst.frequency_interval),
                 "weeks": rd(weeks=inst.frequency_interval),
                 "months": rd(months=inst.frequency_interval),
                 "years": rd(years=inst.frequency_interval)}[inst.frequency_uom]
        due = last.calibration_date + delta
        if last.certificate_valid_until and last.certificate_valid_until < due:
            due = last.certificate_valid_until
        return order.calibration_date and order.calibration_date <= due
