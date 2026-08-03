# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

STAGES = [('incoming', 'Incoming'), ('inprocess', 'In-Process'), ('final', 'Final')]


class QualityInspectionPlan(models.Model):
    """FR-QIP-01..07 - versioned, stage-wise inspection plan."""
    _name = 'quality.inspection.plan'
    _description = 'Quality Inspection Plan (QIP)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char(default='New', readonly=True, copy=False)
    product_tmpl_id = fields.Many2one('product.template', required=True, tracking=True)
    product_id = fields.Many2one(
        'product.product', string='Specific Variant',
        domain="[('product_tmpl_id', '=', product_tmpl_id)]", tracking=True)
    stage = fields.Selection(STAGES, required=True, default='incoming', tracking=True)
    operation_id = fields.Many2one('mrp.routing.workcenter', string='BoM Operation',
                                   help='Required for in-process plans.')
    workcenter_id = fields.Many2one(related='operation_id.workcenter_id', store=True)
    drawing_no = fields.Char(tracking=True)
    drawing_rev = fields.Char(tracking=True)
    sampling_rule_id = fields.Many2one('quality.sampling.rule', required=True, tracking=True)
    version = fields.Integer(default=1, readonly=True, copy=False)
    previous_id = fields.Many2one('quality.inspection.plan', readonly=True, copy=False)
    state = fields.Selection([('draft', 'Draft'), ('approved', 'Approved'),
                              ('obsolete', 'Obsolete')],
                             default='draft', tracking=True, copy=False)
    valid_from = fields.Date()
    line_ids = fields.One2many('quality.inspection.plan.line', 'plan_id', copy=True)
    company_id = fields.Many2one('res.company', default=lambda s: s.env.company, required=True)
    active = fields.Boolean(default=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('quality.plan') or 'New'
        return super().create(vals_list)

    def write(self, vals):
        protected = {'line_ids', 'sampling_rule_id', 'stage', 'product_tmpl_id',
                     'product_id', 'operation_id', 'drawing_no', 'drawing_rev'}
        for plan in self:
            if plan.state != 'draft' and protected & set(vals):
                raise UserError(
                    'Approved/obsolete plans are frozen (FR-QIP-05). '
                    'Create a new version to change %s.' % plan.name)
        return super().write(vals)

    @api.constrains('stage', 'operation_id')
    def _check_operation(self):
        for plan in self:
            if plan.stage == 'inprocess' and not plan.operation_id:
                raise ValidationError('In-process plans require a BoM operation.')

    def action_approve(self):
        self = self.filtered(lambda p: p.state == 'draft')
        for plan in self:
            if not plan.line_ids:
                raise UserError('Plan %s has no lines.' % plan.name)
            others = self.search([
                ('id', '!=', plan.id), ('state', '=', 'approved'),
                ('product_tmpl_id', '=', plan.product_tmpl_id.id),
                ('product_id', '=', plan.product_id.id),
                ('stage', '=', plan.stage),
                ('operation_id', '=', plan.operation_id.id),
                ('company_id', '=', plan.company_id.id)])
            others.write({'state': 'obsolete'})
            plan.state = 'approved'
            plan.message_post(body='Plan approved (v%s). Superseded: %s'
                                   % (plan.version, ', '.join(others.mapped('name')) or '-'))

    def action_obsolete(self):
        self.write({'state': 'obsolete'})

    def action_new_version(self):
        self.ensure_one()
        new = self.copy({'version': self.version + 1, 'previous_id': self.id,
                         'state': 'draft', 'name': 'New'})
        new.name = '%s/v%s' % (self.name.split('/v')[0], new.version)
        return {'type': 'ir.actions.act_window', 'res_model': self._name,
                'res_id': new.id, 'view_mode': 'form'}

    @api.model
    def find_plan(self, product, stage, operation=None, company=None):
        """Approved plan lookup: exact variant first, then template-wide."""
        company = company or self.env.company
        base = [('state', '=', 'approved'), ('stage', '=', stage),
                ('product_tmpl_id', '=', product.product_tmpl_id.id),
                ('company_id', '=', company.id)]
        if stage == 'inprocess':
            base.append(('operation_id', '=', operation.id if operation else False))
        plan = self.search(base + [('product_id', '=', product.id)], limit=1)
        return plan or self.search(base + [('product_id', '=', False)], limit=1)


class QualityInspectionPlanLine(models.Model):
    """FR-QIP-03/04 - quotation-style characteristic line."""
    _name = 'quality.inspection.plan.line'
    _description = 'QIP Line'
    _order = 'sequence, id'

    plan_id = fields.Many2one('quality.inspection.plan', required=True, ondelete='cascade')
    sequence = fields.Integer(default=10)
    balloon_ref = fields.Char('Balloon Ref.')
    name = fields.Char('Parameter / Characteristic', required=True)
    char_type = fields.Selection([('variable', 'Variable'), ('attribute', 'Attribute'),
                                  ('visual', 'Visual'), ('functional', 'Functional')],
                                 default='variable', required=True)
    specification = fields.Char()
    nominal_value = fields.Float(digits=(16, 4))
    tol_min = fields.Float('LSL', digits=(16, 4))
    tol_max = fields.Float('USL', digits=(16, 4))
    uom_id = fields.Many2one('uom.uom', string='UoM')
    instrument_note = fields.Char('Instrument',
                                  help='Free text; with the calibration bridge installed use '
                                       'the Instrument record field instead.')
    method = fields.Char()
    mandatory = fields.Boolean(default=True)

    @api.constrains('char_type', 'tol_min', 'tol_max')
    def _check_limits(self):
        for line in self:
            if line.char_type == 'variable' and line.tol_min > line.tol_max:
                raise ValidationError('LSL must not exceed USL (%s).' % line.name)
