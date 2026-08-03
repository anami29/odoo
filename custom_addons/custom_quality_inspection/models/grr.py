# -*- coding: utf-8 -*-
from collections import defaultdict
from odoo import api, fields, models
from odoo.exceptions import UserError


class QualityGrrStudy(models.Model):
    """FR-SPC-06 - crossed Gauge R&R, ANOVA method (AIAG)."""
    _name = 'quality.grr.study'
    _description = 'Gauge R&R Study'
    _inherit = ['mail.thread']

    name = fields.Char(default='New', copy=False)
    parameter = fields.Char(required=True)
    instrument_note = fields.Char('Instrument')
    uom_id = fields.Many2one('uom.uom', string='UoM')
    date = fields.Date(default=fields.Date.context_today)
    line_ids = fields.One2many('quality.grr.line', 'study_id')
    parts = fields.Integer(readonly=True)
    appraisers = fields.Integer(readonly=True)
    trials = fields.Integer(readonly=True)
    var_repeat = fields.Float('Var (Repeatability)', digits=(16, 8), readonly=True)
    var_reprod = fields.Float('Var (Reproducibility)', digits=(16, 8), readonly=True)
    var_part = fields.Float('Var (Part)', digits=(16, 8), readonly=True)
    grr_pct = fields.Float('%GRR', digits=(16, 2), readonly=True)
    contrib_pct = fields.Float('%Contribution', digits=(16, 2), readonly=True)
    ndc = fields.Float('ndc', digits=(16, 1), readonly=True)
    verdict = fields.Selection([('acceptable', 'Acceptable'),
                                ('conditional', 'Conditional'),
                                ('unacceptable', 'Unacceptable')], readonly=True)
    state = fields.Selection([('draft', 'Draft'), ('done', 'Done')], default='draft')
    company_id = fields.Many2one('res.company', default=lambda s: s.env.company)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('quality.grr') or 'New'
        return super().create(vals_list)

    def action_compute(self):
        for rec in self:
            data = defaultdict(list)      # (part, appraiser) -> [values]
            parts, apprs = set(), set()
            for l in rec.line_ids:
                data[(l.part_no, l.appraiser_id.id)].append(l.value)
                parts.add(l.part_no)
                apprs.add(l.appraiser_id.id)
            p, a = len(parts), len(apprs)
            r = min(len(v) for v in data.values()) if data else 0
            if p < 2 or a < 2 or r < 2:
                raise UserError('A crossed study needs >= 2 parts, >= 2 appraisers '
                                'and >= 2 trials each.')
            if len(data) != p * a:
                raise UserError('Unbalanced study: every appraiser must measure '
                                'every part.')
            cells = {k: v[:r] for k, v in data.items()}
            all_vals = [x for v in cells.values() for x in v]
            N = p * a * r
            grand = sum(all_vals) / N
            part_mean = {i: sum(sum(cells[(i, j)]) for j in apprs) / (a * r)
                         for i in parts}
            appr_mean = {j: sum(sum(cells[(i, j)]) for i in parts) / (p * r)
                         for j in apprs}
            cell_mean = {k: sum(v) / r for k, v in cells.items()}
            ss_part = a * r * sum((m - grand) ** 2 for m in part_mean.values())
            ss_appr = p * r * sum((m - grand) ** 2 for m in appr_mean.values())
            ss_cell = r * sum((m - grand) ** 2 for m in cell_mean.values())
            ss_int = ss_cell - ss_part - ss_appr
            ss_tot = sum((x - grand) ** 2 for x in all_vals)
            ss_equip = ss_tot - ss_cell
            ms_part = ss_part / (p - 1)
            ms_appr = ss_appr / (a - 1)
            ms_int = ss_int / ((p - 1) * (a - 1)) if (p - 1) * (a - 1) else 0.0
            ms_equip = ss_equip / (p * a * (r - 1))
            v_repeat = max(ms_equip, 0.0)
            v_int = max((ms_int - ms_equip) / r, 0.0)
            v_appr = max((ms_appr - ms_int) / (p * r), 0.0)
            v_part = max((ms_part - ms_int) / (a * r), 0.0)
            v_reprod = v_appr + v_int
            v_grr = v_repeat + v_reprod
            v_total = v_grr + v_part
            grr_pct = 100.0 * (v_grr / v_total) ** 0.5 if v_total else 0.0
            contrib = 100.0 * v_grr / v_total if v_total else 0.0
            ndc = 1.41 * (v_part / v_grr) ** 0.5 if v_grr else 0.0
            acc = rec.company_id.quality_grr_accept or 10.0
            cond = rec.company_id.quality_grr_cond or 30.0
            verdict = ('acceptable' if grr_pct < acc
                       else 'conditional' if grr_pct <= cond else 'unacceptable')
            rec.write({'parts': p, 'appraisers': a, 'trials': r,
                       'var_repeat': v_repeat, 'var_reprod': v_reprod,
                       'var_part': v_part, 'grr_pct': grr_pct,
                       'contrib_pct': contrib, 'ndc': ndc,
                       'verdict': verdict, 'state': 'done'})


class QualityGrrLine(models.Model):
    _name = 'quality.grr.line'
    _description = 'Gauge R&R Measurement'
    _order = 'part_no, appraiser_id, trial'

    study_id = fields.Many2one('quality.grr.study', required=True, ondelete='cascade')
    part_no = fields.Integer('Part', required=True)
    appraiser_id = fields.Many2one('hr.employee', 'Appraiser', required=True)
    trial = fields.Integer(default=1, required=True)
    value = fields.Float(digits=(16, 5), required=True)
