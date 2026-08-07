# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request, content_disposition

XLSX_MIME = ('application/vnd.openxmlformats-officedocument'
             '.spreadsheetml.sheet')

OPTION_KEYS = ('report_type', 'date_from', 'date_to', 'target_move',
               'comparison', 'detail_level')


class FinancialReportController(http.Controller):

    @http.route('/custom_financial_reports/xlsx', type='http', auth='user')
    def download_xlsx(self, **kwargs):
        options = {key: kwargs.get(key) for key in OPTION_KEYS
                   if kwargs.get(key)}
        Engine = request.env['custom.financial.report']
        data = Engine.build_xlsx(options)
        filename = Engine.xlsx_filename(options)
        return request.make_response(data, headers=[
            ('Content-Type', XLSX_MIME),
            ('Content-Length', len(data)),
            ('Content-Disposition', content_disposition(filename)),
        ])
