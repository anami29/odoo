# -*- coding: utf-8 -*-
from odoo import models


class ReportFinancial(models.AbstractModel):
    _name = 'report.custom_financial_reports.report_financial'
    _description = 'Financial Report (BS / P&L / Cash Flow)'

    def _get_report_values(self, docids, data=None):
        wizards = self.env['custom.financial.report.wizard'].browse(docids)
        return {
            'doc_ids': docids,
            'doc_model': 'custom.financial.report.wizard',
            'docs': wizards,
            'render_data': {w.id: w._prepare_render_data() for w in wizards},
        }
