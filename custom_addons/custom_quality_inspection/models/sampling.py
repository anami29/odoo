# -*- coding: utf-8 -*-
import math
from odoo import api, fields, models
from odoo.exceptions import UserError

LETTER_ORDER = 'ABCDEFGHJKLMNPQR'
AQL_VALUES = [('0.065', '0.065'), ('0.1', '0.10'), ('0.15', '0.15'), ('0.25', '0.25'),
              ('0.4', '0.40'), ('0.65', '0.65'), ('1.0', '1.0'), ('1.5', '1.5'),
              ('2.5', '2.5'), ('4.0', '4.0'), ('6.5', '6.5')]


class QualityAqlLetter(models.Model):
    """ISO 2859-1 Table 1: lot size range + inspection level -> code letter."""
    _name = 'quality.aql.letter'
    _description = 'AQL Sample Size Code Letter'
    _order = 'level, lot_min'

    level = fields.Selection([('1', 'General I'), ('2', 'General II'), ('3', 'General III')],
                             required=True)
    lot_min = fields.Integer(required=True)
    lot_max = fields.Integer(required=True, help='0 = no upper limit')
    letter = fields.Char(required=True, size=1)


class QualityAqlPlan(models.Model):
    """ISO 2859-1 Table 2-A: code letter + AQL -> n, Ac, Re (single sampling).
    Rows are loaded for normal severity; tightened rows may be added later
    (severity column provided) - lookup falls back to normal when absent."""
    _name = 'quality.aql.plan'
    _description = 'AQL Single Sampling Plan'
    _order = 'sample_size, aql'

    letter = fields.Char(required=True, size=1)
    sample_size = fields.Integer(required=True)
    aql = fields.Selection(AQL_VALUES, required=True)
    severity = fields.Selection([('normal', 'Normal'), ('tightened', 'Tightened'),
                                 ('reduced', 'Reduced')], default='normal', required=True)
    ac = fields.Integer('Ac', required=True)
    re = fields.Integer('Re', required=True)


class QualitySamplingRule(models.Model):
    _name = 'quality.sampling.rule'
    _description = 'Quality Sampling Rule'

    name = fields.Char(required=True)
    rule_type = fields.Selection([
        ('full', '100% Inspection'), ('fixed', 'Fixed Sample'),
        ('percent', 'Percentage'), ('aql', 'AQL (ISO 2859-1)')],
        required=True, default='full')
    fixed_qty = fields.Integer(default=5)
    percent = fields.Float(default=10.0)
    min_qty = fields.Integer(default=1)
    aql_level = fields.Selection([('1', 'General I'), ('2', 'General II'), ('3', 'General III')],
                                 default='2')
    aql_value = fields.Selection(AQL_VALUES, default='1.0')
    note = fields.Text()
    active = fields.Boolean(default=True)

    def compute_sample(self, lot_qty, severity='normal'):
        """FR-SMP-01/02. Returns dict(basis, qty, ac, re, letter)."""
        self.ensure_one()
        lot_qty = int(math.ceil(lot_qty or 0))
        if lot_qty <= 0:
            return {'basis': 'full', 'qty': 0, 'ac': 0, 're': 1, 'letter': ''}
        if self.rule_type == 'full':
            return {'basis': 'full', 'qty': lot_qty, 'ac': 0, 're': 1, 'letter': ''}
        if self.rule_type == 'fixed':
            n = min(max(self.fixed_qty, 1), lot_qty)
            return {'basis': 'sampling' if n < lot_qty else 'full',
                    'qty': n, 'ac': 0, 're': 1, 'letter': ''}
        if self.rule_type == 'percent':
            n = int(math.ceil(lot_qty * self.percent / 100.0))
            n = min(max(n, self.min_qty, 1), lot_qty)
            return {'basis': 'sampling' if n < lot_qty else 'full',
                    'qty': n, 'ac': 0, 're': 1, 'letter': ''}
        # AQL
        Letter = self.env['quality.aql.letter']
        Plan = self.env['quality.aql.plan']
        row = Letter.search([('level', '=', self.aql_level), ('lot_min', '<=', lot_qty),
                             '|', ('lot_max', '=', 0), ('lot_max', '>=', lot_qty)], limit=1)
        if not row:
            raise UserError('No AQL code letter defined for lot size %s / level %s.'
                            % (lot_qty, self.aql_level))
        idx = LETTER_ORDER.index(row.letter)

        def find(sev):
            # exact letter, else walk to larger n (down-arrow), else smaller (up-arrow)
            for i in list(range(idx, len(LETTER_ORDER))) + list(range(idx - 1, -1, -1)):
                p = Plan.search([('letter', '=', LETTER_ORDER[i]),
                                 ('aql', '=', self.aql_value), ('severity', '=', sev)], limit=1)
                if p:
                    return p
            return Plan
        plan = find(severity if severity in ('normal', 'tightened') else 'normal')
        if not plan and severity == 'tightened':
            plan = find('normal')
        if not plan:
            raise UserError('No AQL plan row for AQL %s.' % self.aql_value)
        n = min(plan.sample_size, lot_qty)
        return {'basis': 'sampling', 'qty': n, 'ac': plan.ac, 're': plan.re,
                'letter': plan.letter}


class QualitySamplingSwitch(models.Model):
    """FR-SMP-05 / FR-TRG-06 - per vendor-product severity state, switching
    counters and skip-lot counter."""
    _name = 'quality.sampling.switch'
    _description = 'Sampling Switching State'
    _rec_name = 'product_id'

    partner_id = fields.Many2one('res.partner', required=True, index=True)
    product_id = fields.Many2one('product.product', required=True, index=True)
    company_id = fields.Many2one('res.company', default=lambda s: s.env.company)
    severity = fields.Selection([('normal', 'Normal'), ('tightened', 'Tightened'),
                                 ('reduced', 'Reduced')], default='normal', tracking=False)
    last_results = fields.Char(default='', help="Rolling last five lot results, e.g. 'AARAA'")
    consec_accept = fields.Integer(default=0)
    log = fields.Text(default='')

    _sql_constraints = [('vendor_product_uniq', 'unique(partner_id, product_id, company_id)',
                         'One switching record per vendor and product.')]

    @api.model
    def _get(self, partner, product, company):
        rec = self.search([('partner_id', '=', partner.id), ('product_id', '=', product.id),
                           ('company_id', '=', company.id)], limit=1)
        return rec or self.create({'partner_id': partner.id, 'product_id': product.id,
                                   'company_id': company.id})

    def register_result(self, accepted):
        """Update counters and, when automation is enabled, apply ISO 2859-1
        switching: normal -> tightened on 2 rejections within last 5 lots;
        tightened -> normal after 5 consecutive acceptances."""
        for rec in self:
            rec.last_results = ((rec.last_results or '') + ('A' if accepted else 'R'))[-5:]
            rec.consec_accept = rec.consec_accept + 1 if accepted else 0
            if not rec.company_id.quality_switching_auto:
                continue
            old = rec.severity
            if rec.severity == 'normal' and rec.last_results.count('R') >= 2:
                rec.severity = 'tightened'
            elif rec.severity == 'tightened' and rec.consec_accept >= 5:
                rec.severity = 'normal'
            if rec.severity != old:
                rec.log = (rec.log or '') + '\n%s: %s -> %s (auto, results %s)' % (
                    fields.Datetime.now(), old, rec.severity, rec.last_results)
