# -*- coding: utf-8 -*-
{
    'name': 'Financial Reports CE: Balance Sheet, P&L, Cash Flow',
    'summary': 'Balance Sheet, Profit & Loss and Cash Flow Statement '
               '(PDF + XLSX) for Odoo Community accounting',
    'version': '18.0.1.0.0',
    'category': 'Accounting/Accounting',
    'author': 'RLFB',
    'license': 'LGPL-3',
    'depends': ['account'],
    'data': [
        'security/ir.model.access.csv',
        'report/financial_report_templates.xml',
        'report/financial_report_action.xml',
        'views/financial_report_wizard_views.xml',
    ],
    'installable': True,
    'application': False,
}
