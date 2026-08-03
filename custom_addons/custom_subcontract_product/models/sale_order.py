from odoo import fields, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    jw_calloff_picking_ids = fields.One2many(
        'stock.picking', compute='_compute_jw_pickings',
        string='Pending Principal Material')
    jw_inward_count = fields.Integer(compute='_compute_jw_pickings')

    def _jw_chain_pickings(self):
        """All pickings in this order's logistics chain, found by walking
        move origins (group-agnostic: MOs carry their own procurement
        groups on 1-step warehouses — defect #6)."""
        self.ensure_one()
        seen = self.env['stock.move']
        frontier = self.order_line.move_ids
        while frontier:
            seen |= frontier
            productions = (frontier.raw_material_production_id
                           | frontier.production_id)
            frontier = (frontier.move_orig_ids
                        | productions.move_raw_ids
                        | productions.move_finished_ids) - seen
        return seen.picking_id

    def _compute_jw_pickings(self):
        for order in self:
            chain = order._jw_chain_pickings()
            inward = chain.filtered(
                lambda pk: pk.picking_type_id.is_jw_challan
                and pk.picking_type_id.code == 'incoming')
            order.jw_inward_count = len(
                inward.filtered(lambda pk: pk.state != 'cancel'))
            order.jw_calloff_picking_ids = inward.filtered(
                lambda pk: pk.state not in ('done', 'cancel'))

    def action_view_jw_inward(self):
        self.ensure_one()
        inward = self._jw_chain_pickings().filtered(
            lambda pk: pk.picking_type_id.is_jw_challan
            and pk.picking_type_id.code == 'incoming')
        return {
            'type': 'ir.actions.act_window',
            'name': 'Inward Challans',
            'res_model': 'stock.picking',
            'view_mode': 'list,form',
            'domain': [('id', 'in', inward.ids)],
        }

    def action_send_rm_calloff(self):
        """FR-22: consolidated RM call-off to the principal."""
        self.ensure_one()
        template = self.env.ref(
            'custom_subcontract_product.mail_template_rm_calloff',
            raise_if_not_found=False)
        ctx = {
            'default_model': 'sale.order',
            'default_res_ids': self.ids,
            'default_template_id': template and template.id or False,
            'default_composition_mode': 'comment',
        }
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'mail.compose.message',
            'view_mode': 'form',
            'target': 'new',
            'context': ctx,
        }
