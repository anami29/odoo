from odoo import api, fields, models  # pyrefly: ignore [missing-import]


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
        compute="_compute_access_sequence",
        inverse="_inverse_access_sequence",
    )

    @api.depends("groups_id")
    def _compute_access_sequence(self):
        group = self.env.ref("helpdesk_mgmt.group_helpdesk_sequence", raise_if_not_found=False)
        for user in self:
            user.access_sequence = (group and group in user.groups_id) or False

    def _inverse_access_sequence(self):
        group = self.env.ref("helpdesk_mgmt.group_helpdesk_sequence", raise_if_not_found=False)
        if not group:
            return
        for user in self:
            if user.access_sequence:
                user.groups_id = [(4, group.id)]
            else:
                user.groups_id = [(3, group.id)]
