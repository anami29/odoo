# -*- coding: utf-8 -*-
{
    'name': 'Quality Inspection - Instrument Calibration Bridge',
    'summary': 'Links QIP / IR / GRR lines to calibration instruments and '
               'enforces calibration validity at IR completion (FR-QIP-07).',
    'version': '18.0.1.0.0',
    'author': 'RLFB',
    'license': 'OPL-1',
    'category': 'Manufacturing/Quality',
    'depends': ['custom_quality_inspection', 'custom_instrument_calibration'],
    'data': ['views/bridge_views.xml'],
    'auto_install': True,
    'installable': True,
}
