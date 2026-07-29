from odoo import fields, models, _
from odoo.exceptions import UserError

JW_SEQ_BY_CODE = {
    'incoming': 'jobwork.challan.in',
    'outgoing': 'jobwork.challan.out',
}


class StockPickingType(models.Model):
    _inherit = 'stock.picking.type'

    is_jw_challan = fields.Boolean(
        string='Job Work Challan Type',
        help='Pickings of this type are delivery challans: they carry the '
             'statutory challan series and print the Rule 55 document.',
    )


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    is_jw_challan = fields.Boolean(related='picking_type_id.is_jw_challan')
    jobwork_challan_no = fields.Char(
        string='Challan Number', copy=False, readonly=True)
    principal_challan_no = fields.Char(
        string="Principal's Challan No.", copy=False)
    principal_challan_date = fields.Date(
        string="Principal's Challan Date", copy=False)
    ewaybill_no = fields.Char(
        string='e-Way Bill No.', copy=False,
        help='e-Way bill generated for this movement (JW-EWB-CHECK: filled '
             'by the stock e-way bill flow where present on the build, '
             'manually from the NIC portal otherwise).')

    def button_validate(self):
        for picking in self:
            if picking.is_jw_challan:
                if (picking.picking_type_id.code == 'incoming'
                        and not picking.principal_challan_no):
                    raise UserError(_(
                        "Record the principal's challan number before "
                        'validating the inward challan (FR-23).'))
                if not picking.jobwork_challan_no:
                    seq = JW_SEQ_BY_CODE.get(picking.picking_type_id.code)
                    if seq:
                        picking.jobwork_challan_no = \
                            self.env['ir.sequence'].next_by_code(seq)
        return super().button_validate()
