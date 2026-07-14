# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    "name": "Helpdesk SLA Traffic Light",
    "summary": "Visual indicators for SLA status and Average Handling Time reports",
    "version": "18.0.1.0.0",
    "category": "Helpdesk",
    "author": "Antigravity",
    "license": "AGPL-3",
    "depends": [
        "helpdesk_mgmt",
        "helpdesk_mgmt_sla",
    ],
    "data": [
        "security/helpdesk_sla_traffic_light_security.xml",
        "security/ir.model.access.csv",
        "views/helpdesk_ticket_views.xml",
        "views/helpdesk_ticket_report_aht_views.xml",
        "views/helpdesk_sla_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "helpdesk_sla_traffic_light/static/src/traffic_light/traffic_light.scss",
            "helpdesk_sla_traffic_light/static/src/traffic_light/traffic_light.js",
            "helpdesk_sla_traffic_light/static/src/traffic_light/traffic_light.xml",
        ],
    },
    "installable": True,
    "application": False,
}
