# -*- coding: utf-8 -*-
import statistics
from odoo import api, fields, models
from odoo.exceptions import UserError

# Shewhart constants for subgroup sizes 2..9
D2 = {2: 1.128, 3: 1.693, 4: 2.059, 5: 2.326, 6: 2.534, 7: 2.704, 8: 2.847, 9: 2.970}
D3 = {2: 0.0, 3: 0.0, 4: 0.0, 5: 0.0, 6: 0.0, 7: 0.076, 8: 0.136, 9: 0.184}
D4 = {2: 3.267, 3: 2.574, 4: 2.282, 5: 2.114, 6: 2.004, 7: 1.924, 8: 1.864, 9: 1.816}
A2 = {2: 1.880, 3: 1.023, 4: 0.729, 5: 0.577, 6: 0.483, 7: 0.419, 8: 0.373, 9: 0.337}


class QualitySpcChart(models.Model):
    """FR-SPC-01..03 - control chart configuration + computation."""
    _name = 'quality.spc.chart'
    _description = 'SPC Control Chart'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(required=True)
    product_tmpl_id = fields.Many2one('product.template', required=True)
    balloon_ref = fields.Char('Balloon Ref.')
    parameter = fields.Char(required=True,
                            help='Must match the QIP line parameter name.')
    stage = fields.Selection([('incoming', 'Incoming'), ('inprocess', 'In-Process'),
                              ('final', 'Final')])
    chart_type = fields.Selection([('xbar_r', 'X-bar / R'), ('i_mr', 'I-MR'),
                                   ('p', 'p (proportion)'), ('np', 'np (count)')],
                                  default='xbar_r', required=True)
    subgroup_size = fields.Integer(default=5)
    rule_set = fields.Selection([('we', 'Western Electric'), ('nelson', 'Nelson')],
                                default='we', required=True)
    baseline_from = fields.Date()
    baseline_to = fields.Date()
    locked = fields.Boolean(tracking=True)
    cl = fields.Float('CL', digits=(16, 5), readonly=True)
    ucl = fields.Float('UCL', digits=(16, 5), readonly=True)
    lcl = fields.Float('LCL', digits=(16, 5), readonly=True)
    r_cl = fields.Float('R CL', digits=(16, 5), readonly=True)
    r_ucl = fields.Float('R UCL', digits=(16, 5), readonly=True)
    r_lcl = fields.Float('R LCL', digits=(16, 5), readonly=True)
    point_ids = fields.One2many('quality.spc.point', 'chart_id')
    alert_count = fields.Integer(readonly=True)
    company_id = fields.Many2one('res.company', default=lambda s: s.env.company)

    def action_lock(self):
        self._check_engineer()
        self.write({'locked': True})

    def action_unlock(self):
        self._check_engineer()
        self.write({'locked': False})

    def _check_engineer(self):
        if not self.env.user.has_group(
                'custom_quality_inspection.group_quality_engineer'):
            raise UserError('Quality Engineer group required.')

    def _fetch_values(self):
        """Ordered observations from Done IR lines matching the key
        (product template + parameter [+ balloon] [+ stage])."""
        self.ensure_one()
        dom = [('report_id.state', '=', 'done'),
               ('report_id.superseded', '=', False),
               ('report_id.product_id.product_tmpl_id', '=', self.product_tmpl_id.id),
               ('name', '=', self.parameter)]
        if self.balloon_ref:
            dom.append(('balloon_ref', '=', self.balloon_ref))
        if self.stage:
            dom.append(('report_id.stage', '=', self.stage))
        lines = self.env['quality.inspection.report.line'].search(
            dom, order='report_id asc, id asc')
        return lines

    def _fetch_sets(self):
        self.ensure_one()
        dom = [('product_id.product_tmpl_id', '=', self.product_tmpl_id.id),
               ('state', 'in', ('accepted', 'partially_accepted', 'rejected'))]
        if self.stage:
            dom.append(('stage', '=', self.stage))
        return self.env['quality.inspection.set'].search(dom, order='id asc')

    def action_recompute(self):
        """FR-SPC-02/03 - rebuild points, limits (baseline-aware) and rule flags."""
        self._check_engineer()
        Point = self.env['quality.spc.point']
        for chart in self:
            if chart.locked:
                raise UserError('Chart %s is locked; unlock to recompute limits.'
                                % chart.name)
            chart.point_ids.unlink()
            pts = []          # (date, value, range_val, ref)
            if chart.chart_type in ('xbar_r', 'i_mr'):
                lines = chart._fetch_values()
                data = [(l.report_id.date_done, l.observed_value, l.report_id.name)
                        for l in lines if l.char_type == 'variable']
                if chart.chart_type == 'i_mr':
                    prev = None
                    for d, v, ref in data:
                        mr = abs(v - prev) if prev is not None else 0.0
                        pts.append((d, v, mr, ref))
                        prev = v
                else:
                    n = max(2, min(chart.subgroup_size, 9))
                    for i in range(0, len(data) - len(data) % n, n):
                        grp = data[i:i + n]
                        vals = [g[1] for g in grp]
                        pts.append((grp[-1][0], sum(vals) / n,
                                    max(vals) - min(vals),
                                    '%s..%s' % (grp[0][2], grp[-1][2])))
            else:
                for iset in chart._fetch_sets():
                    size = iset.passed_count + iset.failed_count
                    if not size:
                        continue
                    val = (iset.failed_count / size) if chart.chart_type == 'p' \
                        else iset.failed_count
                    pts.append((iset.decision_date, val, size, iset.name))
            if not pts:
                raise UserError('No data for chart %s.' % chart.name)
            # limits from baseline subset
            base = [p for p in pts
                    if (not chart.baseline_from
                        or (p[0] and p[0].date() >= chart.baseline_from))
                    and (not chart.baseline_to
                         or (p[0] and p[0].date() <= chart.baseline_to))] or pts
            chart._compute_limits(base)
            sigma = (chart.ucl - chart.cl) / 3.0 if chart.ucl > chart.cl else 0.0
            values = [p[1] for p in pts]
            flags = chart._apply_rules(values, chart.cl, sigma)
            Point.create([{
                'chart_id': chart.id, 'sequence': i + 1, 'date': p[0],
                'value': p[1], 'range_val': p[2], 'ref': p[3],
                'violation': flags[i]} for i, p in enumerate(pts)])
            n_alerts = len([f for f in flags if f])
            chart.alert_count = n_alerts
            notify = chart.company_id.quality_notify_user_id
            if n_alerts and notify:
                chart.activity_schedule(
                    'mail.mail_activity_data_todo', user_id=notify.id,
                    summary='%s SPC rule violation(s) on %s' % (n_alerts, chart.name))

    def _compute_limits(self, base):
        self.ensure_one()
        vals = [p[1] for p in base]
        mean = sum(vals) / len(vals)
        if self.chart_type == 'xbar_r':
            n = max(2, min(self.subgroup_size, 9))
            rbar = sum(p[2] for p in base) / len(base)
            self.write({'cl': mean, 'ucl': mean + A2[n] * rbar,
                        'lcl': mean - A2[n] * rbar,
                        'r_cl': rbar, 'r_ucl': D4[n] * rbar, 'r_lcl': D3[n] * rbar})
        elif self.chart_type == 'i_mr':
            mrs = [p[2] for p in base[1:]] or [0.0]
            mrbar = sum(mrs) / len(mrs)
            sig = mrbar / D2[2]
            self.write({'cl': mean, 'ucl': mean + 3 * sig, 'lcl': mean - 3 * sig,
                        'r_cl': mrbar, 'r_ucl': D4[2] * mrbar, 'r_lcl': 0.0})
        elif self.chart_type == 'p':
            nbar = sum(p[2] for p in base) / len(base)
            pbar = mean
            sig = (pbar * (1 - pbar) / nbar) ** 0.5 if nbar else 0.0
            self.write({'cl': pbar, 'ucl': pbar + 3 * sig,
                        'lcl': max(0.0, pbar - 3 * sig),
                        'r_cl': 0, 'r_ucl': 0, 'r_lcl': 0})
        else:  # np
            nbar = sum(p[2] for p in base) / len(base)
            npbar = mean
            pbar = npbar / nbar if nbar else 0.0
            sig = (npbar * (1 - pbar)) ** 0.5
            self.write({'cl': npbar, 'ucl': npbar + 3 * sig,
                        'lcl': max(0.0, npbar - 3 * sig),
                        'r_cl': 0, 'r_ucl': 0, 'r_lcl': 0})

    def _apply_rules(self, values, cl, sigma):
        """Rule flags per point. WE: 1 beyond 3s; 2of3 beyond 2s; 4of5 beyond 1s;
        8 same side. Nelson: 1 beyond 3s; 9 same side; 6 trending; 14 alternating."""
        self.ensure_one()
        flags = ['' for _ in values]

        def add(i, code):
            flags[i] = (flags[i] + ',' + code).strip(',')
        for i, v in enumerate(values):
            if sigma and abs(v - cl) > 3 * sigma:
                add(i, 'R1>3s')
        if self.rule_set == 'we' and sigma:
            for i in range(len(values)):
                w3 = values[max(0, i - 2):i + 1]
                if len(w3) == 3 and sum(1 for x in w3 if x - cl > 2 * sigma) >= 2:
                    add(i, 'R2:2of3>2s')
                if len(w3) == 3 and sum(1 for x in w3 if cl - x > 2 * sigma) >= 2:
                    add(i, 'R2:2of3<2s')
                w5 = values[max(0, i - 4):i + 1]
                if len(w5) == 5 and sum(1 for x in w5 if x - cl > sigma) >= 4:
                    add(i, 'R3:4of5>1s')
                if len(w5) == 5 and sum(1 for x in w5 if cl - x > sigma) >= 4:
                    add(i, 'R3:4of5<1s')
                w8 = values[max(0, i - 7):i + 1]
                if len(w8) == 8 and (all(x > cl for x in w8) or all(x < cl for x in w8)):
                    add(i, 'R4:8side')
        elif self.rule_set == 'nelson':
            for i in range(len(values)):
                w9 = values[max(0, i - 8):i + 1]
                if len(w9) == 9 and (all(x > cl for x in w9) or all(x < cl for x in w9)):
                    add(i, 'N2:9side')
                w6 = values[max(0, i - 5):i + 1]
                if len(w6) == 6 and (all(w6[j] < w6[j + 1] for j in range(5))
                                     or all(w6[j] > w6[j + 1] for j in range(5))):
                    add(i, 'N3:6trend')
                w14 = values[max(0, i - 13):i + 1]
                if len(w14) == 14 and all(
                        (w14[j + 1] - w14[j]) * (w14[j + 2] - w14[j + 1]) < 0
                        for j in range(12)):
                    add(i, 'N4:14alt')
        return flags


class QualitySpcPoint(models.Model):
    _name = 'quality.spc.point'
    _description = 'SPC Point'
    _order = 'chart_id, sequence'

    chart_id = fields.Many2one('quality.spc.chart', required=True, ondelete='cascade')
    sequence = fields.Integer()
    date = fields.Datetime()
    value = fields.Float(digits=(16, 5))
    range_val = fields.Float('Range / MR / n', digits=(16, 5))
    ref = fields.Char('Source')
    violation = fields.Char()


class QualityCapabilityStudy(models.Model):
    """FR-SPC-04 - Cp/Cpk (within) and Pp/Ppk (overall)."""
    _name = 'quality.capability.study'
    _description = 'Process Capability Study'
    _inherit = ['mail.thread']

    name = fields.Char(default='New', copy=False)
    product_tmpl_id = fields.Many2one('product.template', required=True)
    balloon_ref = fields.Char('Balloon Ref.')
    parameter = fields.Char(required=True)
    date_from = fields.Date()
    date_to = fields.Date()
    subgroup_size = fields.Integer(default=5)
    lsl = fields.Float('LSL', digits=(16, 5))
    usl = fields.Float('USL', digits=(16, 5))
    n = fields.Integer(readonly=True)
    mean = fields.Float(digits=(16, 5), readonly=True)
    sigma_within = fields.Float(digits=(16, 6), readonly=True)
    sigma_overall = fields.Float(digits=(16, 6), readonly=True)
    cp = fields.Float('Cp', digits=(16, 3), readonly=True)
    cpk = fields.Float('Cpk', digits=(16, 3), readonly=True)
    pp = fields.Float('Pp', digits=(16, 3), readonly=True)
    ppk = fields.Float('Ppk', digits=(16, 3), readonly=True)
    note = fields.Char(readonly=True)
    state = fields.Selection([('draft', 'Draft'), ('done', 'Done')], default='draft')
    company_id = fields.Many2one('res.company', default=lambda s: s.env.company)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'quality.capability') or 'New'
        return super().create(vals_list)

    def action_compute(self):
        for rec in self:
            dom = [('report_id.state', '=', 'done'),
                   ('report_id.superseded', '=', False),
                   ('report_id.product_id.product_tmpl_id', '=', rec.product_tmpl_id.id),
                   ('name', '=', rec.parameter), ('char_type', '=', 'variable')]
            if rec.balloon_ref:
                dom.append(('balloon_ref', '=', rec.balloon_ref))
            if rec.date_from:
                dom.append(('report_id.date_done', '>=', rec.date_from))
            if rec.date_to:
                dom.append(('report_id.date_done', '<=', rec.date_to))
            lines = self.env['quality.inspection.report.line'].search(
                dom, order='report_id asc, id asc')
            vals = lines.mapped('observed_value')
            n_min = rec.company_id.quality_capability_min or 30
            if len(vals) < max(n_min, 2):
                raise UserError('FR-SPC-04: at least %s observations required '
                                '(found %s).' % (n_min, len(vals)))
            if not rec.lsl and not rec.usl:
                pl = lines[:1].plan_line_id
                rec.lsl, rec.usl = pl.tol_min, pl.tol_max
            mean = statistics.fmean(vals)
            overall = statistics.stdev(vals)
            k = max(2, min(rec.subgroup_size, 9))
            ranges = [max(vals[i:i + k]) - min(vals[i:i + k])
                      for i in range(0, len(vals) - len(vals) % k, k)]
            within = (sum(ranges) / len(ranges)) / D2[k] if ranges else overall
            span = rec.usl - rec.lsl
            rec.write({
                'n': len(vals), 'mean': mean, 'sigma_within': within,
                'sigma_overall': overall,
                'cp': span / (6 * within) if within else 0.0,
                'cpk': min(rec.usl - mean, mean - rec.lsl) / (3 * within)
                       if within else 0.0,
                'pp': span / (6 * overall) if overall else 0.0,
                'ppk': min(rec.usl - mean, mean - rec.lsl) / (3 * overall)
                       if overall else 0.0,
                'note': 'Normality assumed - verify distribution before relying on '
                        'indices.',
                'state': 'done'})
