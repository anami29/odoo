# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.http import request

PARTY_LABEL = {'a': 'Party A', 'b': 'Party B'}


class AgreementSignWizard(models.TransientModel):
    """Signing screen: the designated signatory signs every area assigned to their
    party (touch / stylus / pen via the signature pad). Party B areas are only
    reachable once Party A has completed (BR-SIGN-A-008)."""
    _name = 'agreement.sign.wizard'
    _description = 'Agreement Signing Screen'

    res_model = fields.Char(required=True)
    res_id = fields.Integer(required=True)
    party = fields.Selection([('a', 'Party A'), ('b', 'Party B')], required=True)
    party_label = fields.Char(compute='_compute_document_info')
    document_name = fields.Char(compute='_compute_document_info')
    document_label = fields.Char(compute='_compute_document_info')
    party_partner_id = fields.Many2one('res.partner', compute='_compute_document_info', string='Signing For')
    signatory_id = fields.Many2one('res.partner', compute='_compute_document_info', string='Signatory')
    signatory_name = fields.Char(compute='_compute_document_info')
    master_signature = fields.Binary(string='Adopted Signature',
                                     help="Sign once here, then apply the adopted signature to every remaining area.")
    line_ids = fields.One2many('agreement.sign.wizard.line', 'wizard_id', string='Signature Areas')
    required_count = fields.Integer(compute='_compute_progress')
    signed_count = fields.Integer(compute='_compute_progress')
    optional_count = fields.Integer(compute='_compute_progress')
    optional_signed_count = fields.Integer(compute='_compute_progress')
    all_required_signed = fields.Boolean(compute='_compute_progress')
    confirm_identity = fields.Boolean(
        string='I confirm that I am the designated signatory (or that the signatory is signing in person).')

    @api.depends('res_model', 'res_id', 'party')
    def _compute_document_info(self):
        for wizard in self:
            doc = wizard._get_document()
            wizard.party_label = PARTY_LABEL.get(wizard.party, '')
            wizard.document_name = doc.number if doc else ''
            wizard.document_label = doc._document_label() if doc else ''
            wizard.party_partner_id = doc._get_party_partner(wizard.party) if doc else False
            wizard.signatory_id = doc._get_signatory(wizard.party) if doc else False
            wizard.signatory_name = wizard.signatory_id.name if wizard.signatory_id else ''

    @api.depends('line_ids.signature', 'line_ids.required')
    def _compute_progress(self):
        for wizard in self:
            required = wizard.line_ids.filtered('required')
            optional = wizard.line_ids - required
            wizard.required_count = len(required)
            wizard.signed_count = len(required.filtered('signature'))
            wizard.optional_count = len(optional)
            wizard.optional_signed_count = len(optional.filtered('signature'))
            wizard.all_required_signed = bool(required) and wizard.signed_count == wizard.required_count

    def _get_document(self):
        self.ensure_one()
        if self.res_model in self.env and self.res_id:
            return self.env[self.res_model].browse(self.res_id).exists()
        return False

    @api.model_create_multi
    def create(self, vals_list):
        wizards = super().create(vals_list)
        for wizard in wizards:
            if not wizard.line_ids:
                wizard._populate_lines()
        return wizards

    def _populate_lines(self):
        self.ensure_one()
        doc = self._get_document()
        if not doc:
            raise UserError(_("The document to sign could not be found."))
        expected = 'pending_a' if self.party == 'a' else 'pending_b'
        if doc.state != expected:
            if self.party == 'b' and doc.state == 'pending_a':
                raise UserError(_("Party A must complete all required signatures before Party B can sign."))
            raise UserError(_("This document is not awaiting the signature of %s.", PARTY_LABEL[self.party]))
        areas = doc.signature_ids.filtered(lambda s: s.party == self.party).sorted(lambda s: (s.sequence, s.id))
        self.line_ids = [(0, 0, {
            'signature_id': area.id,
            'sequence': area.sequence,
            'code': area.code,
            'name': area.name,
            'page': area.page,
            'position': area.position,
            'kind': area.kind,
            'required': area.required,
            'signature': area.signature,
        }) for area in areas]

    def _get_action(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Sign as %s — %s', PARTY_LABEL[self.party], self.document_name),
            'res_model': 'agreement.sign.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'context': dict(self.env.context, agreement_sign_wizard=True),
        }

    def action_apply_master(self):
        """Apply the adopted signature to every remaining area of this party."""
        self.ensure_one()
        if not self.master_signature:
            raise UserError(_("Draw or type your signature first."))
        self.line_ids.filtered(lambda l: not l.signature).write({'signature': self.master_signature})
        return self._get_action()

    def action_clear(self):
        self.ensure_one()
        self.line_ids.write({'signature': False})
        self.master_signature = False
        return self._get_action()

    def action_complete(self):
        """BR-SIGN-A-006 / BR-SIGN-B-004: complete only when every required area is signed."""
        self.ensure_one()
        doc = self._get_document()
        if not doc:
            raise UserError(_("The document to sign could not be found."))
        if not self.confirm_identity:
            raise UserError(_("Please confirm the identity of the signatory before completing the signing."))
        missing = self.line_ids.filtered(lambda l: l.required and not l.signature)
        if missing:
            if self.party == 'a':
                raise UserError(_("Party A must complete all required signatures before Party B can sign. "
                                  "Missing: %s.", ', '.join(missing.mapped('name'))))
            raise UserError(_("All required Party B signatures must be completed before the agreement can be "
                              "executed. Missing: %s.", ', '.join(missing.mapped('name'))))
        values = {line.signature_id.id: line.signature for line in self.line_ids if line.signature}
        ip = False
        try:
            ip = request.httprequest.remote_addr if request else False
        except Exception:  # pragma: no cover - outside an HTTP request
            ip = False
        doc._register_signatures(self.party, values, signer_ip=ip)
        return {'type': 'ir.actions.act_window_close'}


class AgreementSignWizardLine(models.TransientModel):
    _name = 'agreement.sign.wizard.line'
    _description = 'Agreement Signing Screen Line'
    _order = 'sequence, id'

    wizard_id = fields.Many2one('agreement.sign.wizard', required=True, ondelete='cascade')
    signature_id = fields.Many2one('agreement.signature', string='Signature Area', required=True, ondelete='cascade')
    sequence = fields.Integer(default=10)
    code = fields.Char()
    name = fields.Char(string='Section / Anchor')
    page = fields.Integer()
    position = fields.Char()
    kind = fields.Selection([('signature', 'Full signature'), ('initials', 'Initials')])
    required = fields.Boolean()
    signature = fields.Binary(string='Signature')
    signatory_name = fields.Char(related='wizard_id.signatory_name')
    is_signed = fields.Boolean(compute='_compute_is_signed')

    @api.depends('signature')
    def _compute_is_signed(self):
        for line in self:
            line.is_signed = bool(line.signature)
