# -*- coding: utf-8 -*-
from statistics import NormalDist
from odoo import api, fields, models


class QualitySixSigmaWizard(models.TransientModel):
    """FR-SPC-05 - period DPMO, sigma level, FPY / RTY."""
    _name = 'quality.sixsigma.wizard'
    _description = 'Six Sigma Metrics'

    date_from = fields.Date(required=True,
                            default=lambda s: fields.Date.context_today(s).replace(day=1))
    date_to = fields.Date(required=True, default=fields.Date.context_today)
    product_tmpl_id = fields.Many2one('product.template', string='Product (optional)')
    line_ids = fields.One2many('quality.sixsigma.wizard.line', 'wizard_id', readonly=True)
    units = fields.Integer('Units Inspected', readonly=True)
    defects = fields.Integer('Defects (failed lines)', readonly=True)
    opportunities = fields.Integer('Opportunities', readonly=True)
    dpmo = fields.Float('DPMO', digits=(16, 0), readonly=True)
    rty = fields.Float('RTY %', digits=(16, 2), readonly=True)
    sigma_level = fields.Float('Sigma Level', digits=(16, 2), readonly=True)

    def action_compute(self):
        self.ensure_one()
        Report = self.env['quality.inspection.report']
        dom = [('state', '=', 'done'), ('superseded', '=', False),
               ('date_done', '>=', fields.Datetime.to_datetime(self.date_from)),
               ('date_done', '<=', fields.Datetime.to_datetime(self.date_to)
                .replace(hour=23, minute=59, second=59))]
        if self.product_tmpl_id:
            dom.append(('product_id.product_tmpl_id', '=', self.product_tmpl_id.id))
        reports = Report.search(dom)
        lines = reports.mapped('line_ids').filtered('mandatory')
        defects = len(lines.filtered(lambda l: l.result == 'fail'))
        opps = len(lines)
        dpmo = defects / opps * 1e6 if opps else 0.0
        # FPY per stage, RTY across stages
        cmds, rty = [], 1.0
        for stage, label in [('incoming', 'Incoming'), ('inprocess', 'In-Process'),
                             ('final', 'Final')]:
            st = reports.filtered(lambda r: r.stage == stage)
            if not st:
                continue
            passed = len(st.filtered(lambda r: r.verdict == 'pass'))
            fpy = passed / len(st) * 100.0
            rty *= fpy / 100.0
            cmds.append((0, 0, {'stage': label, 'inspected': len(st),
                                'passed': passed, 'fpy': fpy}))
        shift = 1.5 if self.env.company.quality_sigma_shift else 0.0
        sigma = 0.0
        if opps and dpmo < 1e6:
            sigma = NormalDist().inv_cdf(1.0 - dpmo / 1e6) + shift
        self.write({'line_ids': [(5, 0, 0)] + cmds, 'units': len(reports),
                    'defects': defects, 'opportunities': opps, 'dpmo': dpmo,
                    'rty': rty * 100.0, 'sigma_level': sigma})
        return {'type': 'ir.actions.act_window', 'res_model': self._name,
                'res_id': self.id, 'view_mode': 'form', 'target': 'new'}


class QualitySixSigmaWizardLine(models.TransientModel):
    _name = 'quality.sixsigma.wizard.line'
    _description = 'Six Sigma Metrics Line'

    wizard_id = fields.Many2one('quality.sixsigma.wizard', ondelete='cascade')
    stage = fields.Char(readonly=True)
    inspected = fields.Integer(readonly=True)
    passed = fields.Integer(readonly=True)
    fpy = fields.Float('FPY %', digits=(16, 2), readonly=True)
