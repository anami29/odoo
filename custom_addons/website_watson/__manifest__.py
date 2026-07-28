{
    'name': 'Watson Logistics Website',
    'version': '18.0.1.0.0',
    'category': 'Website/Website',
    'summary': 'Watson Logistics corporate site — sections, services, branches, team and quote capture.',
    'description': """
Watson Logistics website
========================
Corporate site for Watson Logistics Pvt. Ltd., ported from the approved design.

* Homepage assembled from QWeb templates using the brand design system.
* Structured content (services, branches, team, certifications, counters) lives
  in dedicated models, editable from the backend — no template editing needed.
* Quote requests are captured as CRM leads via ``website_crm``.
* Blog styling layered on top of ``website_blog``.
""",
    'author': 'RLFB',
    'website': 'https://watson-logistics.com',
    'license': 'OPL-1',
    'depends': [
        'website',
        'website_blog',
        'website_crm',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/backend_views.xml',
        'views/templates/layout.xml',
        'views/templates/homepage.xml',
        'views/templates/snippets.xml',
        'data/website_data.xml',
        'data/content_services.xml',
        'data/content_branches.xml',
        'data/content_team.xml',
        'data/content_misc.xml',
        'data/pages.xml',
    ],
    'assets': {
        'web._assets_primary_variables': [
            'website_watson/static/src/scss/primary_variables.scss',
        ],
        'web.assets_frontend': [
            'website_watson/static/src/scss/watson.scss',
            'website_watson/static/src/js/watson.js',
        ],
    },
    'images': ['static/description/cover.png'],
    'installable': True,
    'application': False,
}
