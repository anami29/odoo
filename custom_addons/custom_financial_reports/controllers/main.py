# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request, content_disposition

XLSX_MIME = ('application/vnd.openxmlformats-officedocument'
             '.spreadsheetml.sheet')


class FinancialReportController(http.Controller):

    @http.route('/custom_financial_reports/xlsx/<int:wizard_id>',
                type='http', auth='user')
    def download_xlsx(self, wizard_id, **kwargs):
        wizard = request.env['custom.financial.report.wizard'].browse(
            wizard_id).exists()
        if not wizard:
            return request.not_found()
        wizard.check_access('read')
        data = wizard.build_xlsx()
        return request.make_response(data, headers=[
            ('Content-Type', XLSX_MIME),
            ('Content-Length', len(data)),
            ('Content-Disposition',
             content_disposition(wizard.xlsx_filename())),
        ])
