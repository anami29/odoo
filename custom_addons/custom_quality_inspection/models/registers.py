# -*- coding: utf-8 -*-
from odoo import fields, models, tools


class QualityRejectionAnalysis(models.Model):
    """FR-RPT-04 - Pareto / responsibility pivot source (read-only SQL view)."""
    _name = 'quality.rejection.analysis'
    _description = 'Rejection Analysis'
    _auto = False
    _order = 'total_loss desc'

    product_id = fields.Many2one('product.product', readonly=True)
    defect_id = fields.Many2one('quality.defect.code', readonly=True)
    cause_id = fields.Many2one('quality.cause.code', readonly=True)
    resp_type = fields.Char(readonly=True)
    partner_id = fields.Many2one('res.partner', 'Vendor', readonly=True)
    stage = fields.Char(readonly=True)
    qty = fields.Float(readonly=True)
    total_loss = fields.Float(readonly=True)
    date = fields.Date(readonly=True)
    company_id = fields.Many2one('res.company', readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                SELECT
                    row_number() OVER () AS id,
                    n.product_id,
                    rel.quality_defect_code_id AS defect_id,
                    n.cause_id,
                    n.resp_type,
                    n.partner_id,
                    s.stage,
                    n.qty,
                    n.total_loss,
                    n.create_date::date AS date,
                    n.company_id
                FROM quality_ncr n
                LEFT JOIN quality_inspection_set s ON s.id = n.set_id
                LEFT JOIN quality_defect_code_quality_ncr_rel rel
                       ON rel.quality_ncr_id = n.id
                WHERE n.state != 'cancel'
            )""" % self._table)
