from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ProductCategory(models.Model):
    _inherit = 'product.category'

    is_jobwork_chain = fields.Boolean(
        string='Job Work Chain (owner tracked)',
        help='Products of this category are part of a sub-contract chain: '
             'reservation and stock keeping are principal-owner aware and '
             'the category must be configured with no automated valuation.',
    )


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    l10n_in_is_jobwork = fields.Boolean(
        string='Sub-contract Product',
        help='Goods-like logistics (stock, BOM, MRP) but invoiced as a '
             'service with a SAC on the Indian e-invoice (FR-01).',
    )
    l10n_in_goods_hsn_code = fields.Char(
        string='Goods HSN (Challan / e-Way Bill)',
        help='HSN of the processed article as goods. Printed on the '
             'delivery challan and used for the movement e-way bill; '
             'the SAC in the HSN/SAC field is used only on the invoice.',
    )
    l10n_in_jw_auto_return = fields.Boolean(
        string='Auto-return with dispatch',
        help='By-product/scrap material: quantities produced by job-work '
             'MOs are appended automatically to the order\'s outward '
             'challan for return to the principal (FR-33).',
    )
    product_kind = fields.Selection(
        selection=[
            ('consu', 'Goods'),
            ('service', 'Service'),
            ('combo', 'Combo'),
            ('subcontract', 'Sub-contract'),
        ],
        string='Product Type ',
        compute='_compute_product_kind',
        inverse='_inverse_product_kind',
        help='Presentation of the fourth pseudo-type. Sub-contract writes '
             "type='consu', is_storable=True and the job-work flag; the "
             'data model keeps the standard three-value type field.',
    )

    @api.depends('type', 'l10n_in_is_jobwork')
    def _compute_product_kind(self):
        for tmpl in self:
            if tmpl.l10n_in_is_jobwork:
                tmpl.product_kind = 'subcontract'
            else:
                tmpl.product_kind = tmpl.type

    @api.onchange('product_kind')
    def _onchange_product_kind(self):
        for tmpl in self:
            if tmpl.product_kind == 'subcontract':
                tmpl.type = 'consu'
                tmpl.is_storable = True
                tmpl.l10n_in_is_jobwork = True
                tmpl.invoice_policy = 'delivery'
            elif tmpl.product_kind:
                tmpl.type = tmpl.product_kind
                tmpl.l10n_in_is_jobwork = False

    def _inverse_product_kind(self):
        for tmpl in self:
            if tmpl.product_kind == 'subcontract':
                tmpl.type = 'consu'
                tmpl.is_storable = True
                tmpl.l10n_in_is_jobwork = True
            else:
                tmpl.type = tmpl.product_kind
                tmpl.l10n_in_is_jobwork = False

    @api.constrains('l10n_in_is_jobwork', 'l10n_in_hsn_code',
                    'l10n_in_goods_hsn_code', 'type', 'is_storable')
    def _check_jobwork_setup(self):
        for tmpl in self.filtered('l10n_in_is_jobwork'):
            if tmpl.type != 'consu' or not tmpl.is_storable:
                raise ValidationError(_(
                    'Sub-contract products must be Goods with inventory '
                    'tracking enabled.'))
            if not (tmpl.l10n_in_hsn_code or '').startswith('99'):
                raise ValidationError(_(
                    'Sub-contract products require a SAC '
                    '(HSN code starting with 99).'))
            goods_hsn = tmpl.l10n_in_goods_hsn_code or ''
            if not goods_hsn or goods_hsn.startswith('99'):
                raise ValidationError(_(
                    'Sub-contract products require a Goods HSN '
                    '(non-99 code) for the challan and e-way bill.'))
