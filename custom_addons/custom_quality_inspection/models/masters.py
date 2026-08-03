# -*- coding: utf-8 -*-
from datetime import timedelta
from odoo import api, fields, models


class QualityDefectCode(models.Model):
    _name = 'quality.defect.code'
    _description = 'Quality Defect Code'
    _order = 'code'

    code = fields.Char(required=True)
    name = fields.Char(required=True)
    category = fields.Char()
    active = fields.Boolean(default=True)

    _sql_constraints = [('code_uniq', 'unique(code)', 'Defect code must be unique.')]

    @api.depends('code', 'name')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = '[%s] %s' % (rec.code, rec.name)


class QualityCauseCode(models.Model):
    _name = 'quality.cause.code'
    _description = 'Quality Cause Code'
    _order = 'code'

    code = fields.Char(required=True)
    name = fields.Char(required=True)
    category = fields.Char()
    active = fields.Boolean(default=True)

    _sql_constraints = [('code_uniq', 'unique(code)', 'Cause code must be unique.')]

    @api.depends('code', 'name')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = '[%s] %s' % (rec.code, rec.name)


class QualityInspectorQualification(models.Model):
    """FR-CMP-01/02 - inspector competence matrix (ISO 9001 §7.2)."""
    _name = 'quality.inspector.qualification'
    _description = 'Inspector Qualification'
    _rec_name = 'employee_id'

    employee_id = fields.Many2one('hr.employee', required=True, index=True)
    categ_id = fields.Many2one('product.category', string='Product Category', required=True)
    stage = fields.Selection([
        ('any', 'All Stages'), ('incoming', 'Incoming'),
        ('inprocess', 'In-Process'), ('final', 'Final')], default='any', required=True)
    valid_until = fields.Date()
    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', default=lambda s: s.env.company)

    @api.model
    def is_qualified(self, employee, product, stage):
        """True when the employee holds a valid qualification for the product's
        category (or any parent category) and stage."""
        if not employee or not product:
            return False
        categ = product.categ_id
        categ_ids = []
        while categ:
            categ_ids.append(categ.id)
            categ = categ.parent_id
        today = fields.Date.context_today(self)
        return bool(self.search_count([
            ('employee_id', '=', employee.id),
            ('categ_id', 'in', categ_ids),
            ('stage', 'in', ['any', stage]),
            '|', ('valid_until', '=', False), ('valid_until', '>=', today),
        ]))

    @api.model
    def _cron_expiry_alerts(self):
        soon = fields.Date.context_today(self) + timedelta(days=30)
        expiring = self.search([('valid_until', '!=', False), ('valid_until', '<=', soon)])
        if not expiring:
            return
        body = 'Inspector qualifications expiring within 30 days: %s' % ', '.join(
            '%s (%s)' % (q.employee_id.name, q.valid_until) for q in expiring)
        self.env['ir.logging'].sudo().create({
            'name': 'custom_quality_inspection', 'type': 'server', 'level': 'INFO',
            'dbname': self.env.cr.dbname, 'message': body,
            'path': 'quality.inspector.qualification', 'func': '_cron_expiry_alerts', 'line': '0',
        })


class ProductCategory(models.Model):
    _inherit = 'product.category'

    quality_rework_vehicle = fields.Selection(
        [('repair', 'Repair Order'), ('mo', 'Rework Manufacturing Order')],
        string='Rework Vehicle', default='repair',
        help='Document created when an NCR of this category is dispositioned Rework (FR-NCR-03).')
