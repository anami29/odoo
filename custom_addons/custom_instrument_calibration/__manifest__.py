# -*- coding: utf-8 -*-
{
    "name": "Instrument Calibration & Tool Lifecycle Management",
    "summary": "ISO 9001-aligned instrument calibration: lifecycle, certificates, "
               "records control & retrieval, retirement, dashboard and MIS registers.",
    "version": "18.0.1.2.0",  # for Odoo 19 deploy, change to 19.0.1.2.0 (no code change)
    "category": "Manufacturing/Quality",
    "author": "RLFB",
    "license": "LGPL-3",
    "depends": ["base", "mail", "hr", "uom", "web"],
    "data": [
        "security/calibration_security.xml",
        "security/ir.model.access.csv",
        "data/calibration_data.xml",
        "data/mail_templates.xml",
        "views/misc_views.xml",
        "views/calibration_instrument_views.xml",
        "views/calibration_order_views.xml",
        "views/dashboard_views.xml",
        "report/reports.xml",
        "views/menus.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "custom_instrument_calibration/static/src/dashboard/**/*",
        ],
    },
    "application": True,
    "installable": True,
}
