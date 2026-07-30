# -*- coding: utf-8 -*-
{
    'name': 'Sales & Purchase Register Dashboard',
    'version': '18.0.1.0.0',
    'category': 'Accounting/Reporting',
    'summary': 'Interactive, fully responsive dashboard for Sales and Purchase Registers (GSTR matching)',
    'description': """
Sales & Purchase Register Dashboard
===================================
Provides key financial indicators, graphical charts (using Chart.js), and mobile-responsive tabular data for:
- Sales Register (GSTR-1 matching)
- Purchase Register (GSTR-2B matching)
    """,
    'author': 'Antigravity',
    'license': 'LGPL-3',
    'depends': ['account', 'l10n_in'],
    'data': [
        'security/ir.model.access.csv',
        'views/dashboard_menu_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'custom_sales_purchase_dashboard/static/src/css/dashboard.css',
            'custom_sales_purchase_dashboard/static/src/js/dashboard.js',
            'custom_sales_purchase_dashboard/static/src/xml/dashboard.xml',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
}
