from odoo import models


class StockQuant(models.Model):
    _inherit = 'stock.quant'

    def _gather(self, product_id, location_id, lot_id=None, package_id=None,
                owner_id=None, strict=False, **kwargs):
        """When an owned job is reserving (context set by
        stock.move._action_assign) and the product is owner-tracked,
        narrow gathering to that principal's quants (FR-12). Own
        consumables (non-chain categories) are untouched, as is every
        flow outside the job-work context."""
        jw_owner_id = self.env.context.get('jw_force_owner_id')
        if (jw_owner_id and owner_id is None
                and product_id.categ_id.is_jobwork_chain):
            owner_id = self.env['res.partner'].browse(jw_owner_id)
        return super()._gather(
            product_id, location_id, lot_id=lot_id, package_id=package_id,
            owner_id=owner_id, strict=strict, **kwargs)
