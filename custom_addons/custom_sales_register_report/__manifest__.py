# -*- coding: utf-8 -*-
{
    'name': 'Z Sales Register Report',
    'version': '18.0.1.0.0',
    'summary': 'Custom Excel report for Sales Register (GSTR-1 matching)',
    'author': 'Antigravity',
    'depends': ['account', 'l10n_in'],
    'data': [
        'security/ir.model.access.csv',
        'wizard/z_sales_register_wizard_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
