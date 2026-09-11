# -*- coding: utf-8 -*-
from odoo import api, fields, models


class AgreementDistribution(models.Model):
    """Audit record of an executed document sent by email (BR-EMAIL-009)."""
    _name = 'agreement.distribution'
    _description = 'Executed Document Distribution'
    _order = 'sent_on desc, id desc'
    _rec_name = 'subject'

    agreement_id = fields.Many2one('agreement.agreement', ondelete='cascade', index=True)
    annexure_id = fields.Many2one('agreement.annexure', ondelete='cascade', index=True)
    document_name = fields.Char(compute='_compute_document', store=True, string='Document')
    document_type = fields.Selection([('agreement', 'Agreement'), ('annexure', 'Supplementary Annexure')],
                                     compute='_compute_document', store=True)
    company_id = fields.Many2one('res.company', compute='_compute_document', store=True)
    sent_on = fields.Datetime(default=fields.Datetime.now, required=True, readonly=True)
    sender_id = fields.Many2one('res.users', string='Sender', readonly=True)
    mode = fields.Selection([('auto', 'Automatic'), ('manual', 'Manual')], required=True, readonly=True)
    partner_ids = fields.Many2many('res.partner', 'agreement_distribution_partner_rel', string='Recipients', readonly=True)
    email_to = fields.Char(string='Recipient Emails', readonly=True)
    subject = fields.Char(readonly=True)
    attachment_id = fields.Many2one('ir.attachment', string='Executed PDF', readonly=True)
    mail_message_id = fields.Many2one('mail.message', string='Message', readonly=True, ondelete='set null')
    mail_mail_id = fields.Many2one('mail.mail', string='Email', readonly=True, ondelete='set null')
    state = fields.Selection([
        ('outgoing', 'Queued'),
        ('sent', 'Sent'),
        ('exception', 'Failed'),
        ('cancel', 'Cancelled'),
        ('unknown', 'Notified'),
    ], compute='_compute_state', string='Status')
    failure_reason = fields.Char(compute='_compute_state')

    @api.depends('agreement_id', 'annexure_id', 'agreement_id.number', 'annexure_id.number')
    def _compute_document(self):
        for rec in self:
            doc = rec.annexure_id or rec.agreement_id
            rec.document_name = doc.number if doc else ''
            rec.document_type = 'annexure' if rec.annexure_id else 'agreement'
            rec.company_id = doc.company_id if doc else False

    @api.depends('mail_mail_id.state', 'mail_message_id.mail_ids.state')
    def _compute_state(self):
        for rec in self:
            mails = rec.mail_mail_id or rec.mail_message_id.mail_ids
            if not mails:
                rec.state = 'unknown'
                rec.failure_reason = False
                continue
            states = set(mails.mapped('state'))
            if 'exception' in states:
                rec.state = 'exception'
                rec.failure_reason = ', '.join(m.failure_reason or '' for m in mails if m.state == 'exception')
            elif 'outgoing' in states:
                rec.state = 'outgoing'
                rec.failure_reason = False
            elif 'cancel' in states and len(states) == 1:
                rec.state = 'cancel'
                rec.failure_reason = False
            else:
                rec.state = 'sent'
                rec.failure_reason = False

    def action_open_document(self):
        self.ensure_one()
        doc = self.annexure_id or self.agreement_id
        return {
            'type': 'ir.actions.act_window',
            'res_model': doc._name,
            'res_id': doc.id,
            'view_mode': 'form',
            'target': 'current',
        }
