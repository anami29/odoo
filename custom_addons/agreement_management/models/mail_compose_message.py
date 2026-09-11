# -*- coding: utf-8 -*-
from odoo import Command, api, models


class MailComposeMessage(models.TransientModel):
    _inherit = 'mail.compose.message'

    @api.depends('composition_mode', 'res_domain', 'res_ids', 'template_id')
    def _compute_attachment_ids(self):
        """Keep the stored executed PDF attached when the composer is opened from an
        agreement (BR-EMAIL-005): the official copy is attached, never regenerated."""
        parent = getattr(super(), '_compute_attachment_ids', None)
        if parent is not None:
            parent()
        forced = self.env.context.get('agreement_forced_attachment_ids')
        if forced:
            for composer in self:
                composer.attachment_ids = [Command.link(att_id) for att_id in forced]
