from odoo import fields, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    jw_calloff_picking_ids = fields.One2many(
        'stock.picking', compute='_compute_jw_calloff_picking_ids',
        string='Pending Principal Material')

    def _compute_jw_calloff_picking_ids(self):
        Picking = self.env['stock.picking']
        for order in self:
            order.jw_calloff_picking_ids = Picking.search([
                ('group_id.sale_id', '=', order.id),
                ('picking_type_id.is_jw_challan', '=', True),
                ('picking_type_id.code', '=', 'incoming'),
                ('state', 'not in', ('done', 'cancel')),
            ])

    jw_inward_count = fields.Integer(compute='_compute_jw_inward_count')

    def _compute_jw_inward_count(self):
        Picking = self.env['stock.picking']
        for order in self:
            order.jw_inward_count = Picking.search_count([
                ('group_id.sale_id', '=', order.id),
                ('picking_type_id.is_jw_challan', '=', True),
                ('picking_type_id.code', '=', 'incoming'),
                ('state', '!=', 'cancel'),
            ])

    def action_view_jw_inward(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Inward Challans',
            'res_model': 'stock.picking',
            'view_mode': 'list,form',
            'domain': [
                ('group_id.sale_id', '=', self.id),
                ('picking_type_id.is_jw_challan', '=', True),
                ('picking_type_id.code', '=', 'incoming'),
            ],
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
