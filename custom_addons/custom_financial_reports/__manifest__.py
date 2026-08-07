# -*- coding: utf-8 -*-
{
    'name': 'Financial Reports CE: Balance Sheet, P&L, Cash Flow',
    'summary': 'Enterprise-style on-screen Balance Sheet, Profit & Loss '
               'and Cash Flow Statement with fold/unfold, drill-down to '
               'journal items, PDF and XLSX export - for Odoo Community',
    'version': '18.0.2.0.0',
    'category': 'Accounting/Accounting',
    'author': 'RLFB',
    'license': 'LGPL-3',
    'depends': ['account'],
    'data': [
        'report/financial_report_templates.xml',
        'report/financial_report_action.xml',
        'views/financial_report_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'custom_financial_reports/static/src/**/*',
        ],
    },
    'installable': True,
    'application': False,
}
