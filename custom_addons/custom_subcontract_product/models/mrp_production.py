from odoo import api, fields, models


class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    subcontract_owner_id = fields.Many2one(
        'res.partner', string='Job Owner (Principal)',
        index=True, copy=False, tracking=True,
        help='Principal whose material this job processes. Reservation is '
             'restricted to this owner and outputs are stamped with it '
             '(FR-11/12/13).',
    )

    @api.model_create_multi
    def create(self, vals_list):
        productions = super().create(vals_list)
        for mo in productions.filtered(lambda m: not m.subcontract_owner_id):
            mo.subcontract_owner_id = mo._resolve_jw_owner()
        return productions

    def _resolve_jw_owner(self):
        self.ensure_one()
        sale = self.procurement_group_id.sale_id
        if not sale:
            return False
        chain = (self.product_id.l10n_in_is_jobwork
                 or self.product_id.categ_id.is_jobwork_chain)
        flagged = sale.order_line.filtered(
            lambda l: l.product_id.l10n_in_is_jobwork)
        if chain and flagged:
            return sale.partner_id
        return False
