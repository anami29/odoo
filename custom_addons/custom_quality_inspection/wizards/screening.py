# -*- coding: utf-8 -*-
from odoo import fields, models


class QualityScreeningWizard(models.TransientModel):
    """FR-EVAL-02 - sampling rejection: choose 100% screening or lot rejection."""
    _name = 'quality.screening.wizard'
    _description = 'Sampling Rejection Decision'

    set_id = fields.Many2one('quality.inspection.set', required=True)
    failed = fields.Integer(readonly=True)

    def action_full_screening(self):
        self.ensure_one()
        self.set_id.action_generate_screening_reports()
        return {'type': 'ir.actions.act_window', 'res_model': 'quality.inspection.set',
                'res_id': self.set_id.id, 'view_mode': 'form'}

    def action_reject_lot(self):
        self.ensure_one()
        fails = self.set_id.report_ids.filtered(
            lambda r: r.state == 'done' and not r.superseded and r.verdict == 'fail')
        self.set_id._finalize(fails, lot_rejected=True)
        return {'type': 'ir.actions.act_window', 'res_model': 'quality.inspection.set',
                'res_id': self.set_id.id, 'view_mode': 'form'}


class QualitySupersedeWizard(models.TransientModel):
    """FR-IR-05 - controlled correction of a Done IR."""
    _name = 'quality.supersede.wizard'
    _description = 'Supersede Inspection Report'

    report_id = fields.Many2one('quality.inspection.report', required=True)
    reason = fields.Text(required=True)

    def action_supersede(self):
        self.ensure_one()
        if not self.env.user.has_group(
                'custom_quality_inspection.group_quality_manager'):
            from odoo.exceptions import UserError
            raise UserError('Superseding requires Quality Manager permission.')
        old = self.report_id
        new = old.copy({'state': 'draft', 'superseded': False,
                        'superseded_by_id': False, 'name': 'New',
                        'unit_no': old.unit_no, 'serial_id': old.serial_id.id,
                        'set_id': old.set_id.id})
        old.write({'superseded': True, 'superseded_by_id': new.id})
        old.message_post(body='Superseded by %s. Reason: %s' % (new.name, self.reason))
        new.message_post(body='Supersedes %s. Reason: %s' % (old.name, self.reason))
        return {'type': 'ir.actions.act_window',
                'res_model': 'quality.inspection.report',
                'res_id': new.id, 'view_mode': 'form'}
