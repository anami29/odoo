# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    "name": "Helpdesk SLA Traffic Lights & AHT Reports",
    "summary": "Visual SLA status indicators and Average Handling Time reports.",
    "version": "18.0.1.0.0",
    "license": "AGPL-3",
    "category": "After-Sales",
    "author": "Odoo Community Association (OCA)",
    "depends": [
        "helpdesk_mgmt",
        "helpdesk_mgmt_sla",
        "board",
    ],
    "data": [
        "security/ir.model.access.csv",
        "security/helpdesk_sla_traffic_light_security.xml",
        "views/helpdesk_ticket_views.xml",
        "views/helpdesk_ticket_report_aht_views.xml",
        "views/helpdesk_sla_dashboard_views.xml",
        "views/helpdesk_sla_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "helpdesk_sla_traffic_light/static/src/traffic_light/traffic_light.js",
            "helpdesk_sla_traffic_light/static/src/traffic_light/traffic_light.xml",
            "helpdesk_sla_traffic_light/static/src/traffic_light/traffic_light.scss",
        ],
    },
    "installable": True,
}
