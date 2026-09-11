# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    agreement_auto_email = fields.Boolean(related='company_id.agreement_auto_email', readonly=False)
    agreement_email_party_a = fields.Boolean(related='company_id.agreement_email_party_a', readonly=False)
    agreement_email_party_b = fields.Boolean(related='company_id.agreement_email_party_b', readonly=False)
    agreement_email_signatory_a = fields.Boolean(related='company_id.agreement_email_signatory_a', readonly=False)
    agreement_email_signatory_b = fields.Boolean(related='company_id.agreement_email_signatory_b', readonly=False)
    agreement_email_extra_partner_ids = fields.Many2many(
        related='company_id.agreement_email_extra_partner_ids', readonly=False)
    agreement_executed_template_id = fields.Many2one(
        related='company_id.agreement_executed_template_id', readonly=False)
    agreement_annexure_template_id = fields.Many2one(
        related='company_id.agreement_annexure_template_id', readonly=False)
    agreement_allow_same_party = fields.Boolean(related='company_id.agreement_allow_same_party', readonly=False)
    agreement_allow_facilitated_signing = fields.Boolean(
        related='company_id.agreement_allow_facilitated_signing', readonly=False)
