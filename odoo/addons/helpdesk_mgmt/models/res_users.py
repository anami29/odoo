from odoo import fields, models  # pyrefly: ignore [missing-import]


class ResUsers(models.Model):
    _inherit = "res.users"

    # Records come from user_ids field of helpdesk.ticket.team.
    helpdesk_team_ids = fields.Many2many(
        comodel_name="helpdesk.ticket.team",
        relation="helpdesk_ticket_team_res_users_rel",
        column1="res_users_id",
        column2="helpdesk_ticket_team_id",
    )
    access_sequence = fields.Boolean(
        string="Access Sequence",
        default=False,
        help="Check this if the user is allowed to view the sequence field on helpdesk tickets.",
    )

