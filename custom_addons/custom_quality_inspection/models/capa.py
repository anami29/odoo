# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError


class QualityCapa(models.Model):
    """FR-CAPA-01..04 - corrective action with mandatory effectiveness check."""
    _name = 'quality.capa'
    _description = 'CAPA'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char(default='New', readonly=True, copy=False)
    ncr_ids = fields.Many2many('quality.ncr', string='Linked NCRs')
    problem = fields.Text('Problem Statement', required=True)
    containment = fields.Text('Containment / Correction')
    why1 = fields.Char('Why 1')
    why2 = fields.Char('Why 2')
    why3 = fields.Char('Why 3')
    why4 = fields.Char('Why 4')
    why5 = fields.Char('Why 5')
    root_cause = fields.Text('Root Cause', tracking=True)
    action_ids = fields.One2many('quality.capa.action', 'capa_id')
    state = fields.Selection([('draft', 'Draft'), ('in_progress', 'In Progress'),
                              ('implemented', 'Implemented'),
                              ('effect_check', 'Effectiveness Check'),
                              ('closed', 'Closed')],
                             default='draft', tracking=True, copy=False)
    eff_verifier_id = fields.Many2one('res.users', 'Verified By', readonly=True)
    eff_date = fields.Date('Verification Date', readonly=True)
    eff_result = fields.Selection([('pass', 'Effective'), ('fail', 'Not Effective')],
                                  tracking=True)
    eff_evidence = fields.Text('Effectiveness Evidence')
    company_id = fields.Many2one('res.company', default=lambda s: s.env.company, required=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('quality.capa') or 'New'
        return super().create(vals_list)

    def action_start(self):
        self.write({'state': 'in_progress'})

    def action_implemented(self):
        for rec in self:
            if not rec.root_cause:
                raise UserError('Record the root cause before marking implemented.')
            if not rec.action_ids:
                raise UserError('Define at least one corrective action.')
            open_actions = rec.action_ids.filtered(lambda a: not a.done)
            if open_actions:
                raise UserError('Open actions: %s'
                                % ', '.join(open_actions.mapped('name')))
        self.write({'state': 'implemented'})

    def action_to_effect_check(self):
        self.write({'state': 'effect_check'})

    def action_close(self):
        """FR-CAPA-02 - closure requires verified effectiveness."""
        for rec in self:
            if rec.state != 'effect_check':
                raise UserError('%s must be in Effectiveness Check.' % rec.name)
            if rec.eff_result != 'pass' or not rec.eff_evidence:
                raise UserError('Closure requires a passed effectiveness verification '
                                'with evidence (FR-CAPA-02).')
            rec.eff_verifier_id = self.env.user
            rec.eff_date = fields.Date.context_today(rec)
            rec.state = 'closed'

    def action_effect_failed(self):
        for rec in self:
            rec.eff_result = 'fail'
            rec.state = 'in_progress'
            rec.message_post(body='Effectiveness verification FAILED - CAPA reopened.')

    @api.model
    def _cron_overdue(self):
        """FR-CAPA-04 - overdue action escalation."""
        today = fields.Date.context_today(self)
        overdue = self.env['quality.capa.action'].search([
            ('done', '=', False), ('date_due', '!=', False), ('date_due', '<', today),
            ('capa_id.state', 'not in', ('closed',))])
        for act in overdue:
            user = act.owner_id or act.capa_id.company_id.quality_notify_user_id
            if user:
                act.capa_id.activity_schedule(
                    'mail.mail_activity_data_todo', user_id=user.id,
                    summary='CAPA action overdue: %s (%s)' % (act.name, act.date_due))


class QualityCapaAction(models.Model):
    _name = 'quality.capa.action'
    _description = 'CAPA Action'

    capa_id = fields.Many2one('quality.capa', required=True, ondelete='cascade')
    name = fields.Char('Action', required=True)
    owner_id = fields.Many2one('res.users', 'Owner')
    date_due = fields.Date('Due Date')
    done = fields.Boolean()
    date_done = fields.Date()

    def write(self, vals):
        if vals.get('done'):
            vals.setdefault('date_done', fields.Date.context_today(self))
        return super().write(vals)
