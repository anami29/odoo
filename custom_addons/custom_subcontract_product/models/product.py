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
                    'type', 'is_storable')
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
