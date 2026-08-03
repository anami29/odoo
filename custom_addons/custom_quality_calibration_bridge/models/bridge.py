# -*- coding: utf-8 -*-
"""Bridge to custom_instrument_calibration.

ADJUST HERE IF NEEDED: the instrument model is assumed to be
'calibration.instrument'. If your calibration addon exposes a different
model name (check its models/ directory), change INSTRUMENT_MODEL below and
the three Many2one comodel strings. The validity check probes common field
names (calibration_state / state / next_calibration_date / due_date) via
hasattr, so it degrades gracefully whatever the schema.
"""
from odoo import fields, models
from odoo.exceptions import UserError

INSTRUMENT_MODEL = 'calibration.instrument'


class QualityInspectionPlanLine(models.Model):
    _inherit = 'quality.inspection.plan.line'

    instrument_id = fields.Many2one(INSTRUMENT_MODEL, string='Instrument (record)')


class QualityGrrStudy(models.Model):
    _inherit = 'quality.grr.study'

    instrument_id = fields.Many2one(INSTRUMENT_MODEL, string='Instrument (record)')


class QualityInspectionReportLine(models.Model):
    _inherit = 'quality.inspection.report.line'

    instrument_id = fields.Many2one(INSTRUMENT_MODEL, string='Instrument (record)')

    def _calibration_valid(self):
        """Best-effort validity probe across likely schemas."""
        self.ensure_one()
        inst = self.instrument_id
        if not inst:
            return True
        for state_field in ('calibration_state', 'state'):
            if state_field in inst._fields:
                val = inst[state_field]
                if val in ('valid', 'calibrated', 'ok', 'in_calibration_validity'):
                    return True
                if val in ('expired', 'overdue', 'retired', 'scrapped'):
                    return False
        for date_field in ('next_calibration_date', 'calibration_due_date', 'due_date'):
            if date_field in inst._fields and inst[date_field]:
                return inst[date_field] >= fields.Date.context_today(self)
        return True  # schema unknown - do not block


class QualityInspectionSet(models.Model):
    _inherit = 'quality.inspection.set'

    def _prepare_ir_line(self, pl):
        vals = super()._prepare_ir_line(pl)
        vals['instrument_id'] = pl.instrument_id.id
        return vals


class QualityInspectionReport(models.Model):
    _inherit = 'quality.inspection.report'

    def _check_instruments(self):
        """FR-QIP-07 / FR-IR-04 - block or warn on invalid calibration."""
        res = super()._check_instruments()
        for rec in self:
            bad = rec.line_ids.filtered(
                lambda l: l.instrument_id and not l._calibration_valid())
            if not bad:
                continue
            names = ', '.join(bad.mapped('instrument_id.display_name'))
            mode = rec.company_id.quality_competence_mode  # reuse warn/block policy
            msg = ('Instrument(s) outside calibration validity on %s: %s '
                   '(FR-QIP-07).' % (rec.name, names))
            if mode == 'block':
                raise UserError(msg)
            rec.message_post(body='Calibration warning: ' + msg)
        return res
