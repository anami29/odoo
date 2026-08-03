# -*- coding: utf-8 -*-
"""Z-register style XLSX builders (xlsxwriter ships with Odoo)."""
import io
from datetime import date, timedelta

from dateutil.relativedelta import relativedelta

from odoo import fields

IN_SERVICE = ["in_use", "due", "overdue", "under_calibration", "quarantine"]


def _styles(wb):
    base = {"font_name": "Calibri", "font_size": 10, "border": 1}
    return {
        "title": wb.add_format({"font_name": "Calibri", "font_size": 14, "bold": True}),
        "sub": wb.add_format({"font_name": "Calibri", "font_size": 10, "italic": True}),
        "head": wb.add_format(dict(base, bold=True, bg_color="#1F3864",
                                   font_color="#FFFFFF", text_wrap=True,
                                   valign="vcenter")),
        "cell": wb.add_format(dict(base)),
        "date": wb.add_format(dict(base, num_format="dd-mm-yyyy")),
        "num": wb.add_format(dict(base, num_format="#,##0.00")),
        "int": wb.add_format(dict(base, num_format="#,##0")),
        "pct": wb.add_format(dict(base, num_format="0.0")),
        "tot": wb.add_format(dict(base, bold=True, bg_color="#D9E2F3")),
    }


def _sheet(wb, st, env, wiz, name, headers, widths):
    ws = wb.add_worksheet(name[:31])
    ws.write(0, 0, name, st["title"])
    ws.write(1, 0, env.company.name, st["sub"])
    ws.write(2, 0, "Period: %s to %s    Generated: %s by %s" % (
        wiz.date_from or "-", wiz.date_to or "-",
        fields.Date.context_today(wiz), env.user.name), st["sub"])
    row = 4
    for col, (title, width) in enumerate(zip(headers, widths)):
        ws.write(row, col, title, st["head"])
        ws.set_column(col, col, width)
    ws.freeze_panes(row + 1, 0)
    ws.autofilter(row, 0, row, len(headers) - 1)
    return ws, row + 1


def _w(ws, st, row, values):
    """values: list of (value, kind) with kind in cell/date/num/int/pct/tot."""
    for col, (val, kind) in enumerate(values):
        fmt = st.get(kind, st["cell"])
        if val is None or val is False or val == "":
            ws.write(row, col, "", fmt)
        elif kind == "date":
            d = fields.Date.to_date(val) if isinstance(val, str) else val
            ws.write_datetime(row, col, d, st["date"])
        else:
            ws.write(row, col, val, fmt)
    return row + 1


def build(env, wiz):
    buf = io.BytesIO()
    import xlsxwriter
    wb = xlsxwriter.Workbook(buf, {"in_memory": True, "default_date_format": "dd-mm-yyyy"})
    st = _styles(wb)
    builder = BUILDERS[wiz.report_type]
    builder(env, wiz, wb, st)
    wb.close()
    label = dict(type(wiz)._fields["report_type"].selection).get(wiz.report_type)
    fname = "%s_%s.xlsx" % (label.replace(" ", "_").replace("/", "-"),
                            fields.Date.context_today(wiz))
    return fname, buf.getvalue()


# ---------------------------------------------------------------- helpers
def _instruments(env, wiz, states=None, active_test=True):
    dom = []
    if states:
        dom.append(("state", "in", states))
    if wiz.category_id:
        dom.append(("category_id", "=", wiz.category_id.id))
    if wiz.department_id:
        dom.append(("department_id", "=", wiz.department_id.id))
    if wiz.custodian_id:
        dom.append(("custodian_id", "=", wiz.custodian_id.id))
    Inst = env["calibration.instrument"]
    if wiz.include_archived or not active_test:
        Inst = Inst.with_context(active_test=False)
    return Inst.search(dom, order="code")


def _orders(env, wiz, extra=None):
    dom = [("state", "=", "done"), ("is_historical", "=", False)]
    if wiz.date_from:
        dom.append(("calibration_date", ">=", wiz.date_from))
    if wiz.date_to:
        dom.append(("calibration_date", "<=", wiz.date_to))
    if wiz.category_id:
        dom.append(("category_id", "=", wiz.category_id.id))
    if wiz.department_id:
        dom.append(("department_id", "=", wiz.department_id.id))
    if wiz.agency_id:
        dom.append(("agency_id", "=", wiz.agency_id.id))
    if wiz.custodian_id:
        dom.append(("custodian_id", "=", wiz.custodian_id.id))
    dom += extra or []
    return env["calibration.order"].search(dom, order="calibration_date")


def _months(d_from, d_to):
    out, cur = [], date(d_from.year, d_from.month, 1)
    while cur <= d_to:
        out.append(cur)
        cur += relativedelta(months=1)
    return out


def _ytd_cost(env, inst, upto):
    orders = inst.calibration_ids.filtered(
        lambda o: o.state == "done" and not o.is_historical
        and o.calibration_date and o.calibration_date.year == upto.year)
    return sum(orders.mapped("cost"))


STATE_LBL = {
    "draft": "Draft", "in_use": "In Use", "due": "Due", "overdue": "Overdue",
    "under_calibration": "Under Calibration", "quarantine": "Quarantine",
    "retired": "Retired", "scrapped": "Scrapped", "lost": "Lost"}


# ---------------------------------------------------------------- builders
def b_register(env, wiz, wb, st, states=None, name="Calibration Register"):
    heads = ["Code", "Name", "Category", "Make", "Model", "Serial", "Location",
             "Custodian", "Frequency", "Last Cal.", "Certificate No.",
             "Valid Until", "Next Due", "Effective Due", "Status", "Agency (last)",
             "YTD Cost"]
    widths = [12, 28, 16, 12, 12, 12, 14, 16, 12, 11, 16, 11, 11, 11, 14, 18, 12]
    ws, row = _sheet(wb, st, env, wiz, name, heads, widths)
    today = fields.Date.context_today(wiz)
    for r in _instruments(env, wiz, states=states):
        last = r.calibration_ids.filtered(lambda o: o.state == "done").sorted(
            key=lambda o: (o.calibration_date or today, o.id))
        agency = last[-1].agency_id.name if last and last[-1].agency_id else ""
        row = _w(ws, st, row, [
            (r.code, "cell"), (r.name, "cell"), (r.category_id.name, "cell"),
            (r.make, "cell"), (r.model_no, "cell"), (r.serial_no, "cell"),
            (r.location, "cell"), (r.custodian_id.name, "cell"),
            ("%s %s" % (r.frequency_interval, r.frequency_uom), "cell"),
            (r.last_calibration_date, "date"), (r.last_certificate_no, "cell"),
            (r.certificate_valid_until, "date"), (r.next_due_date, "date"),
            (r.effective_due_date, "date"), (STATE_LBL.get(r.state), "cell"),
            (agency, "cell"), (_ytd_cost(env, r, today), "num")])


def b_due_overdue(env, wiz, wb, st):
    b_register(env, wiz, wb, st, states=["due", "overdue"], name="Due - Overdue List")


def b_oot(env, wiz, wb, st):
    heads = ["Order", "Instrument", "Date", "Agency / By", "Impact From",
             "Impact To", "Product Action", "Impact Notes", "Review Done"]
    widths = [14, 22, 11, 20, 11, 11, 22, 45, 10]
    ws, row = _sheet(wb, st, env, wiz, "Out-of-Tolerance Register", heads, widths)
    sel = dict(env["calibration.order"]._fields["product_action"].selection)
    for o in _orders(env, wiz, extra=[("overall_result", "=", "fail")]):
        row = _w(ws, st, row, [
            (o.name, "cell"), (o.instrument_code, "cell"),
            (o.calibration_date, "date"),
            (o.agency_id.name or o.performed_by_id.name, "cell"),
            (o.impact_from, "date"), (o.impact_to, "date"),
            (sel.get(o.product_action, ""), "cell"), (o.impact_notes, "cell"),
            ("Yes" if o.failure_review_done else "No", "cell")])


def b_retired(env, wiz, wb, st):
    heads = ["Code", "Name", "Category", "Status", "Reason", "Remarks",
             "Retired On", "Approved By", "Disposal Ref.", "Disposal Date"]
    widths = [12, 26, 16, 10, 20, 34, 11, 16, 16, 11]
    ws, row = _sheet(wb, st, env, wiz, "Retired Instrument Register", heads, widths)
    for r in _instruments(env, wiz, states=["retired", "scrapped", "lost"],
                          active_test=False):
        row = _w(ws, st, row, [
            (r.code, "cell"), (r.name, "cell"), (r.category_id.name, "cell"),
            (STATE_LBL.get(r.state), "cell"),
            (r.retirement_reason_id.name or ("Lost" if r.state == "lost" else ""),
             "cell"),
            (r.retirement_remarks or r.lost_reason, "cell"),
            (r.retirement_date, "date"), (r.retirement_user_id.name, "cell"),
            (r.disposal_ref, "cell"), (r.disposal_date, "date")])


def b_disposition(env, wiz, wb, st):
    heads = ["Code", "Name", "Category", "End of Life", "Orders Disposed",
             "Disposition Date", "By", "Reason"]
    widths = [12, 26, 16, 11, 14, 13, 16, 44]
    ws, row = _sheet(wb, st, env, wiz, "Disposition Register", heads, widths)
    dom = []
    if wiz.date_from:
        dom.append(("disposition_date", ">=", wiz.date_from))
    if wiz.date_to:
        dom.append(("disposition_date", "<=", wiz.date_to))
    for d in env["calibration.record.disposition"].search(dom):
        row = _w(ws, st, row, [
            (d.name, "cell"), (d.instrument_name, "cell"),
            (d.category_name, "cell"), (d.end_of_life_date, "date"),
            (d.order_count, "int"), (d.disposition_date, "date"),
            (d.user_id.name, "cell"), (d.reason, "cell")])


def b_compliance(env, wiz, wb, st):
    heads = ["Department", "Category", "In Service", "Compliant (In Use+Due)",
             "Compliance %", "Overdue 1-7", "Overdue 8-30", "Overdue 31-90",
             "Overdue >90"]
    widths = [20, 18, 11, 18, 12, 11, 11, 11, 11]
    ws, row = _sheet(wb, st, env, wiz, "Compliance Summary", heads, widths)
    today = fields.Date.context_today(wiz)
    groups = {}
    for r in _instruments(env, wiz, states=IN_SERVICE):
        key = (r.department_id.name or "-", r.category_id.name)
        g = groups.setdefault(key, {"n": 0, "ok": 0, "b": [0, 0, 0, 0]})
        g["n"] += 1
        if r.state in ("in_use", "due"):
            g["ok"] += 1
        if r.state == "overdue" and r.effective_due_date:
            days = (today - r.effective_due_date).days
            idx = 0 if days <= 7 else 1 if days <= 30 else 2 if days <= 90 else 3
            g["b"][idx] += 1
    tot = {"n": 0, "ok": 0, "b": [0, 0, 0, 0]}
    for (dep, cat), g in sorted(groups.items()):
        pct = g["ok"] * 100.0 / g["n"] if g["n"] else 0.0
        row = _w(ws, st, row, [
            (dep, "cell"), (cat, "cell"), (g["n"], "int"), (g["ok"], "int"),
            (pct, "pct"), (g["b"][0], "int"), (g["b"][1], "int"),
            (g["b"][2], "int"), (g["b"][3], "int")])
        tot["n"] += g["n"]; tot["ok"] += g["ok"]
        tot["b"] = [a + b for a, b in zip(tot["b"], g["b"])]
    pct = tot["ok"] * 100.0 / tot["n"] if tot["n"] else 0.0
    _w(ws, st, row, [("TOTAL", "tot"), ("", "tot"), (tot["n"], "tot"),
                     (tot["ok"], "tot"), (round(pct, 1), "tot"),
                     (tot["b"][0], "tot"), (tot["b"][1], "tot"),
                     (tot["b"][2], "tot"), (tot["b"][3], "tot")])
    # monthly on-time / OOT trend sheet
    heads2 = ["Month", "Done", "On Time", "On-time %", "OOT", "OOT %"]
    ws2, row2 = _sheet(wb, st, env, wiz, "Monthly Trend", heads2,
                       [10, 8, 8, 10, 8, 10])
    dash = env["calibration.dashboard"]
    orders = _orders(env, wiz)
    for m in _months(wiz.date_from, wiz.date_to):
        m_end = m + relativedelta(months=1) - timedelta(days=1)
        mo = orders.filtered(lambda o: m <= o.calibration_date <= m_end)
        ot = sum(1 for o in mo if dash._on_time(o))
        oot = len(mo.filtered(lambda o: o.overall_result == "fail"))
        row2 = _w(ws2, st, row2, [
            (m.strftime("%b-%Y"), "cell"), (len(mo), "int"), (ot, "int"),
            (ot * 100.0 / len(mo) if mo else 0.0, "pct"), (oot, "int"),
            (oot * 100.0 / len(mo) if mo else 0.0, "pct")])


def b_plan_actual(env, wiz, wb, st):
    heads = ["Month", "Due (Planned)", "Done", "Done On Time", "Adherence %"]
    ws, row = _sheet(wb, st, env, wiz, "Plan vs Actual", heads, [12, 12, 10, 12, 12])
    dash = env["calibration.dashboard"]
    Inst = env["calibration.instrument"].with_context(active_test=False)
    orders = _orders(env, wiz)
    for m in _months(wiz.date_from, wiz.date_to):
        m_end = m + relativedelta(months=1) - timedelta(days=1)
        due = Inst.search_count([("effective_due_date", ">=", m),
                                 ("effective_due_date", "<=", m_end)])
        mo = orders.filtered(lambda o: m <= o.calibration_date <= m_end)
        ot = sum(1 for o in mo if dash._on_time(o))
        adh = ot * 100.0 / due if due else (100.0 if mo else 0.0)
        row = _w(ws, st, row, [(m.strftime("%b-%Y"), "cell"), (due, "int"),
                               (len(mo), "int"), (ot, "int"), (adh, "pct")])
    ws2, row2 = _sheet(wb, st, env, wiz, "Slippage",
                       ["Order", "Instrument", "Done On", "Was Due (approx)"],
                       [14, 22, 11, 14])
    for o in orders:
        if not dash._on_time(o):
            row2 = _w(ws2, st, row2, [(o.name, "cell"), (o.instrument_code, "cell"),
                                      (o.calibration_date, "date"), ("", "cell")])


def b_forecast(env, wiz, wb, st):
    heads = ["Month", "Code", "Name", "Category", "Custodian", "Effective Due",
             "Cal. Type", "Est. External Cost"]
    widths = [10, 12, 26, 16, 16, 12, 10, 16]
    ws, row = _sheet(wb, st, env, wiz, "Annual Due-Load Forecast", heads, widths)
    today = fields.Date.context_today(wiz)
    start = date(today.year, today.month, 1)
    m_tot = {}
    for i in range(12):
        m = start + relativedelta(months=i)
        m_end = m + relativedelta(months=1) - timedelta(days=1)
        recs = _instruments(env, wiz, states=IN_SERVICE).filtered(
            lambda r: r.effective_due_date and m <= r.effective_due_date <= m_end)
        for r in recs:
            ext = r.calibration_ids.filtered(
                lambda o: o.state == "done" and o.calibration_type == "external"
                and o.cost).sorted(key=lambda o: (o.calibration_date, o.id))
            est = ext[-1].cost if ext else 0.0
            m_tot[m] = m_tot.get(m, [0, 0.0])
            m_tot[m][0] += 1
            m_tot[m][1] += est
            row = _w(ws, st, row, [
                (m.strftime("%b-%Y"), "cell"), (r.code, "cell"), (r.name, "cell"),
                (r.category_id.name, "cell"), (r.custodian_id.name, "cell"),
                (r.effective_due_date, "date"), (r.calibration_type, "cell"),
                (est, "num")])
    ws2, row2 = _sheet(wb, st, env, wiz, "Monthly Load",
                       ["Month", "Instruments Due", "Est. Cost"], [10, 14, 14])
    for m in sorted(m_tot):
        row2 = _w(ws2, st, row2, [(m.strftime("%b-%Y"), "cell"),
                                  (m_tot[m][0], "int"), (m_tot[m][1], "num")])


def b_cost(env, wiz, wb, st):
    orders = _orders(env, wiz)
    for label, keyf in [("By Month", lambda o: o.calibration_date.strftime("%b-%Y")),
                        ("By Category", lambda o: o.category_id.name or "-"),
                        ("By Department", lambda o: o.department_id.name or "-"),
                        ("By Agency", lambda o: o.agency_id.name or "Internal")]:
        ws, row = _sheet(wb, st, env, wiz, "Cost %s" % label,
                         [label.replace("By ", ""), "Calibrations", "Cost",
                          "Cost / Calibration"], [18, 12, 14, 16])
        groups = {}
        for o in orders:
            g = groups.setdefault(keyf(o), [0, 0.0])
            g[0] += 1
            g[1] += o.cost
        for k in sorted(groups):
            n, c = groups[k]
            row = _w(ws, st, row, [(k, "cell"), (n, "int"), (c, "num"),
                                   (c / n if n else 0.0, "num")])
    prev_wiz = wiz.copy({"date_from": wiz.date_from - relativedelta(years=1),
                         "date_to": wiz.date_to - relativedelta(years=1)})
    prev = _orders(env, prev_wiz)
    ws, row = _sheet(wb, st, env, wiz, "YTD vs Previous Year",
                     ["Period", "Calibrations", "Cost"], [22, 12, 14])
    row = _w(ws, st, row, [("Selected period", "cell"), (len(orders), "int"),
                           (sum(orders.mapped("cost")), "num")])
    _w(ws, st, row, [("Same period, previous year", "cell"), (len(prev), "int"),
                     (sum(prev.mapped("cost")), "num")])


def b_agency(env, wiz, wb, st):
    heads = ["Agency", "NABL", "Calibrations", "Avg TAT (days)", "OOT", "OOT %",
             "Total Cost", "Avg Cost", "Short-validity Certs"]
    widths = [24, 8, 12, 13, 8, 9, 13, 12, 18]
    ws, row = _sheet(wb, st, env, wiz, "Agency Performance", heads, widths)
    orders = _orders(env, wiz, extra=[("calibration_type", "=", "external")])
    groups = {}
    for o in orders:
        g = groups.setdefault(o.agency_id, {"n": 0, "tat": [], "oot": 0,
                                            "cost": 0.0, "short": 0})
        g["n"] += 1
        if o.tat_days:
            g["tat"].append(o.tat_days)
        if o.overall_result == "fail":
            g["oot"] += 1
        g["cost"] += o.cost
        if (o.certificate_valid_until and o.instrument_id.next_due_date
                and o.certificate_valid_until < o.instrument_id.next_due_date):
            g["short"] += 1
    for agency, g in sorted(groups.items(), key=lambda kv: kv[0].name or ""):
        avg_tat = sum(g["tat"]) / len(g["tat"]) if g["tat"] else 0.0
        row = _w(ws, st, row, [
            (agency.name, "cell"), ("Yes" if agency.nabl_accreditation_no else "",
                                    "cell"),
            (g["n"], "int"), (round(avg_tat, 1), "num"), (g["oot"], "int"),
            (g["oot"] * 100.0 / g["n"] if g["n"] else 0.0, "pct"),
            (g["cost"], "num"), (g["cost"] / g["n"] if g["n"] else 0.0, "num"),
            (g["short"], "int")])


def b_downtime(env, wiz, wb, st):
    heads = ["Code", "Name", "Category", "Custodian", "Days Under Calibration",
             "Days Quarantine", "Total Downtime"]
    widths = [12, 26, 16, 16, 18, 14, 14]
    ws, row = _sheet(wb, st, env, wiz, "Instrument Downtime", heads, widths)
    d_from = wiz.date_from or fields.Date.context_today(wiz).replace(month=1, day=1)
    d_to = wiz.date_to or fields.Date.context_today(wiz)
    dt_from = fields.Datetime.to_datetime(d_from)
    dt_to = fields.Datetime.to_datetime(d_to) + timedelta(days=1)
    data = []
    for r in _instruments(env, wiz):
        uc = qa = 0.0
        for log in r.state_log_ids.filtered(
                lambda l: l.state in ("under_calibration", "quarantine")):
            start = max(log.date_from, dt_from)
            end = min(log.date_to or fields.Datetime.now(), dt_to)
            if end > start:
                days = (end - start).total_seconds() / 86400.0
                if log.state == "under_calibration":
                    uc += days
                else:
                    qa += days
        if uc or qa:
            data.append((r, uc, qa))
    for r, uc, qa in sorted(data, key=lambda t: -(t[1] + t[2])):
        row = _w(ws, st, row, [
            (r.code, "cell"), (r.name, "cell"), (r.category_id.name, "cell"),
            (r.custodian_id.name, "cell"), (round(uc, 1), "num"),
            (round(qa, 1), "num"), (round(uc + qa, 1), "num")])


def b_failure_trend(env, wiz, wb, st):
    ws, row = _sheet(wb, st, env, wiz, "Failure Trend",
                     ["Month", "Done", "OOT", "OOT %"], [12, 8, 8, 10])
    orders = _orders(env, wiz)
    for m in _months(wiz.date_from, wiz.date_to):
        m_end = m + relativedelta(months=1) - timedelta(days=1)
        mo = orders.filtered(lambda o: m <= o.calibration_date <= m_end)
        oot = len(mo.filtered(lambda o: o.overall_result == "fail"))
        row = _w(ws, st, row, [(m.strftime("%b-%Y"), "cell"), (len(mo), "int"),
                               (oot, "int"),
                               (oot * 100.0 / len(mo) if mo else 0.0, "pct")])
    ws2, row2 = _sheet(wb, st, env, wiz, "Repeat Failures (24m)",
                       ["Code", "Name", "Failures (rolling 24m)",
                        "Retirement-review Candidate"], [12, 28, 18, 22])
    today = fields.Date.context_today(wiz)
    cutoff = today - relativedelta(months=24)
    Order = env["calibration.order"]
    fails = Order.search([("state", "=", "done"),
                          ("overall_result", "=", "fail"),
                          ("calibration_date", ">=", cutoff)])
    counts = {}
    for o in fails:
        counts[o.instrument_id] = counts.get(o.instrument_id, 0) + 1
    for inst, n in sorted(counts.items(), key=lambda kv: -kv[1]):
        if n >= 2:
            row2 = _w(ws2, st, row2, [(inst.code, "cell"), (inst.name, "cell"),
                                      (n, "int"), ("YES", "cell")])


def b_custodian_load(env, wiz, wb, st):
    heads = ["Custodian", "Department", "Instruments Held", "Due", "Overdue"]
    ws, row = _sheet(wb, st, env, wiz, "Custodian - Department Load", heads,
                     [20, 20, 14, 8, 9])
    groups = {}
    for r in _instruments(env, wiz, states=IN_SERVICE):
        key = (r.custodian_id.name or "-", r.department_id.name or "-")
        g = groups.setdefault(key, [0, 0, 0])
        g[0] += 1
        if r.state == "due":
            g[1] += 1
        if r.state == "overdue":
            g[2] += 1
    for (cust, dep), g in sorted(groups.items()):
        row = _w(ws, st, row, [(cust, "cell"), (dep, "cell"), (g[0], "int"),
                               (g[1], "int"), (g[2], "int")])


BUILDERS = {
    "register": b_register,
    "due_overdue": b_due_overdue,
    "oot": b_oot,
    "retired": b_retired,
    "disposition": b_disposition,
    "compliance": b_compliance,
    "plan_actual": b_plan_actual,
    "forecast": b_forecast,
    "cost": b_cost,
    "agency": b_agency,
    "downtime": b_downtime,
    "failure_trend": b_failure_trend,
    "custodian_load": b_custodian_load,
}
