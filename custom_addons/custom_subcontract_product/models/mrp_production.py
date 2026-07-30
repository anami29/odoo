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

    def _adjust_procure_method(self):
        """Core's heuristics flip raw moves to make-to-order only for the
        standard MTO route; the job-work chain uses its own rules at
        Principal Stock, so force the flip deterministically (fix for:
        SO confirm created the FG MO but no stage MO / no inward challan).
        """
        super()._adjust_procure_method()
        Route = self.env['stock.route']
        jw_routes = Route
        for xmlid in (
                'custom_subcontract_product.route_supplied_by_principal',
                'custom_subcontract_product.route_jw_issue',
                'custom_subcontract_product.route_jw_manufacture'):
            jw_routes |= self.env.ref(
                xmlid, raise_if_not_found=False) or Route
        jw_type = self.env.ref(
            'custom_subcontract_product.picking_type_jw_mfg',
            raise_if_not_found=False)
        for production in self:
            if not jw_type or production.picking_type_id != jw_type:
                continue
            for move in production.move_raw_ids:
                product = move.product_id
                routes = (product.route_ids
                          | product.categ_id.total_route_ids)
                if routes & jw_routes:
                    move.procure_method = 'make_to_order'

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
