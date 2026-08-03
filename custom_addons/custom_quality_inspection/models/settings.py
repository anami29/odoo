# -*- coding: utf-8 -*-
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    quality_qc_location_id = fields.Many2one(
        'stock.location', 'Quality Control Location',
        help='Source location for auto QC -> Stock / NC moves (FR-TRG-01).')
    quality_nc_location_id = fields.Many2one(
        'stock.location', 'Non-Conformance Location')
    quality_mr_approval_limit = fields.Monetary(
        'M Report Plant-Approval Limit',
        help='Losses above this need Plant-level approval in addition to QM '
             '(FR-ACC-03). 0 = QM alone approves.')
    quality_include_conversion = fields.Boolean(
        'Include Conversion Cost in Loss', default=True)
    quality_sla_hours = fields.Integer('Inspection SLA (hours)', default=24)
    quality_notify_user_id = fields.Many2one(
        'res.users', 'Quality Notification User',
        help='Receives inspection-due, NCR, SLA and SPC alert activities.')
    quality_capa_on_scrap = fields.Boolean('CAPA Mandatory on Scrap', default=True)
    quality_capa_on_deviation = fields.Boolean('CAPA Mandatory on Deviation',
                                               default=True)
    quality_competence_mode = fields.Selection(
        [('off', 'Off'), ('warn', 'Warn'), ('block', 'Block')],
        'Competence Gate', default='warn')
    quality_grr_accept = fields.Float('GRR Acceptable Below (%)', default=10.0)
    quality_grr_cond = fields.Float('GRR Conditional Up To (%)', default=30.0)
    quality_sigma_shift = fields.Boolean('Apply 1.5 Sigma Shift', default=True)
    quality_capability_min = fields.Integer('Capability Min. Observations', default=30)
    quality_switching_auto = fields.Boolean('Automate AQL Switching Rules',
                                            default=False)
    quality_skiplot_count = fields.Integer(
        'Skip-Lot After N Acceptances', default=0,
        help='0 disables skip-lot (FR-TRG-06).')


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    currency_id = fields.Many2one(related='company_id.currency_id')
    quality_qc_location_id = fields.Many2one(
        related='company_id.quality_qc_location_id', readonly=False)
    quality_nc_location_id = fields.Many2one(
        related='company_id.quality_nc_location_id', readonly=False)
    quality_mr_approval_limit = fields.Monetary(
        related='company_id.quality_mr_approval_limit', readonly=False)
    quality_include_conversion = fields.Boolean(
        related='company_id.quality_include_conversion', readonly=False)
    quality_sla_hours = fields.Integer(
        related='company_id.quality_sla_hours', readonly=False)
    quality_notify_user_id = fields.Many2one(
        related='company_id.quality_notify_user_id', readonly=False)
    quality_capa_on_scrap = fields.Boolean(
        related='company_id.quality_capa_on_scrap', readonly=False)
    quality_capa_on_deviation = fields.Boolean(
        related='company_id.quality_capa_on_deviation', readonly=False)
    quality_competence_mode = fields.Selection(
        related='company_id.quality_competence_mode', readonly=False)
    quality_grr_accept = fields.Float(
        related='company_id.quality_grr_accept', readonly=False)
    quality_grr_cond = fields.Float(
        related='company_id.quality_grr_cond', readonly=False)
    quality_sigma_shift = fields.Boolean(
        related='company_id.quality_sigma_shift', readonly=False)
    quality_capability_min = fields.Integer(
        related='company_id.quality_capability_min', readonly=False)
    quality_switching_auto = fields.Boolean(
        related='company_id.quality_switching_auto', readonly=False)
    quality_skiplot_count = fields.Integer(
        related='company_id.quality_skiplot_count', readonly=False)
