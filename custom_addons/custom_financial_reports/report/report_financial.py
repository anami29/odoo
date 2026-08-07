# -*- coding: utf-8 -*-
from odoo import models


class ReportFinancial(models.AbstractModel):
    _name = 'report.custom_financial_reports.report_financial'
    _description = 'Financial Report PDF (BS / P&L / Cash Flow)'

    def _get_report_values(self, docids, data=None):
        Engine = self.env['custom.financial.report']
        Engine._check_group()
        options = Engine._normalize_options(data or {})
        return {
            'doc_ids': [],
            'doc_model': 'custom.financial.report',
            'render': Engine._prepare_render_data(options),
            'company': self.env.company,
        }
