from collections import defaultdict

from odoo import models


class StockMove(models.Model):
    _inherit = 'stock.move'

    def _jw_owner(self):
        """Principal owner governing this move, or an empty recordset."""
        self.ensure_one()
        mo = self.raw_material_production_id or self.production_id
        if mo and mo.subcontract_owner_id:
            return mo.subcontract_owner_id
        if self.picking_id.owner_id:
            return self.picking_id.owner_id
        if self.picking_type_id.is_jw_challan and self.group_id.sale_id:
            return self.group_id.sale_id.partner_id
        return self.env['res.partner']

    def _adjust_procure_method(self, picking_type_code=False):
        """Odoo 18: this hook lives on stock.move and matches rules on the
        raw move's own lane (source -> Production). Data-side, each chain
        route now carries a Principal Stock -> Production MTO rule so core
        flips naturally; this override is the belt-and-braces guarantee
        for chain products on Job Work Manufacturing MOs (defect #4)."""
        super()._adjust_procure_method(picking_type_code=picking_type_code)
        jw_type = self.env.ref(
            'custom_subcontract_product.picking_type_jw_mfg',
            raise_if_not_found=False)
        if not jw_type:
            return
        Route = self.env['stock.route']
        jw_routes = Route
        for xmlid in (
                'custom_subcontract_product.route_supplied_by_principal',
                'custom_subcontract_product.route_jw_issue',
                'custom_subcontract_product.route_jw_manufacture'):
            jw_routes |= self.env.ref(
                xmlid, raise_if_not_found=False) or Route
        for move in self:
            mo = move.raw_material_production_id
            if not mo or mo.picking_type_id != jw_type:
                continue
            routes = (move.product_id.route_ids
                      | move.product_id.categ_id.total_route_ids)
            if routes & jw_routes:
                move.procure_method = 'make_to_order'

    def _action_assign(self, force_qty=False):
        """Owner-strict reservation (FR-12): assign owned moves under a
        context that narrows quant gathering to the job owner for
        owner-tracked (job-chain) products."""
        by_owner = defaultdict(lambda: self.env['stock.move'])
        plain = self.env['stock.move']
        for move in self:
            owner = move._jw_owner()
            if owner:
                by_owner[owner.id] |= move
            else:
                plain |= move
        res = True
        if plain:
            res = super(StockMove, plain)._action_assign(force_qty=force_qty)
        for owner_id, moves in by_owner.items():
            super(StockMove, moves.with_context(
                jw_force_owner_id=owner_id))._action_assign(
                    force_qty=force_qty)
        return res

    def _prepare_move_line_vals(self, quantity=None, reserved_quant=None):
        """Owner stamping (FR-13): production outputs, inter-stage moves and
        challan moves carry the job owner on their move lines."""
        vals = super()._prepare_move_line_vals(
            quantity=quantity, reserved_quant=reserved_quant)
        if not vals.get('owner_id'):
            owner = self._jw_owner()
            if owner and (self.product_id.categ_id.is_jobwork_chain
                          or self.product_id.l10n_in_is_jobwork):
                vals['owner_id'] = owner.id
        return vals
