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

    def button_mark_done(self):
        res = super().button_mark_done()
        for mo in self.filtered('subcontract_owner_id'):
            mo._jw_append_byproducts_to_delivery()
        return res

    def _jw_append_byproducts_to_delivery(self):
        """Append auto-return by-products of this job MO to the open
        outward challan of the same procurement chain (FR-33)."""
        self.ensure_one()
        byprods = self.move_finished_ids.filtered(
            lambda mv: mv.state == 'done'
            and mv.product_id != self.product_id
            and mv.product_id.categ_id.is_jobwork_chain
            and mv.product_id.l10n_in_jw_auto_return)
        if not byprods or not self.procurement_group_id:
            return
        sale = self._jw_find_sale()
        delivery = self.env['stock.picking'].search([
            ('sale_id', '=', sale.id),
            ('picking_type_id.is_jw_challan', '=', True),
            ('picking_type_id.code', '=', 'outgoing'),
            ('state', 'not in', ('done', 'cancel')),
        ], limit=1) if sale else self.env['stock.picking']
        if not delivery:
            return  # dispatch already closed: periodic manual challan
        for bmove in byprods:
            existing = delivery.move_ids.filtered(
                lambda mv: mv.product_id == bmove.product_id
                and mv.state not in ('done', 'cancel'))
            if existing:
                existing[0].product_uom_qty += bmove.quantity
                continue
            new_move = self.env['stock.move'].create({
                'name': bmove.product_id.display_name,
                'product_id': bmove.product_id.id,
                'product_uom': bmove.product_uom.id,
                'product_uom_qty': bmove.quantity,
                'location_id': delivery.location_id.id,
                'location_dest_id': delivery.location_dest_id.id,
                'picking_id': delivery.id,
                'picking_type_id': delivery.picking_type_id.id,
                'group_id': delivery.group_id.id,
                'company_id': delivery.company_id.id,
            })
            new_move._action_confirm()
            new_move._action_assign()

    def _jw_find_sale(self):
        """Climb the move_dest chain (child MO -> parent MO -> delivery)
        to the sale order. Group-based lookup fails on 1-step warehouses
        where every MO owns a fresh group (defect #6)."""
        self.ensure_one()
        mo, guard = self, 0
        while mo and guard < 10:
            dest = mo.move_finished_ids.move_dest_ids or mo.move_dest_ids
            sale = dest.group_id.sale_id or dest.picking_id.sale_id
            if sale:
                return sale[:1]
            mo, guard = dest.raw_material_production_id[:1], guard + 1
        return self.procurement_group_id.sale_id

    def _resolve_jw_owner(self):
        self.ensure_one()
        parent = self.move_dest_ids.raw_material_production_id[:1]
        if parent.subcontract_owner_id:
            return parent.subcontract_owner_id
        sale = self._jw_find_sale()
        if not sale:
            return False
        chain = (self.product_id.l10n_in_is_jobwork
                 or self.product_id.categ_id.is_jobwork_chain)
        flagged = sale.order_line.filtered(
            lambda l: l.product_id.l10n_in_is_jobwork)
        if chain and flagged:
            return sale.partner_id
        return False
