from odoo import _, api, fields, models
from odoo.exceptions import UserError

GROUP_MANAGE = "custom_item_code.group_item_code_manage"


class ProductProduct(models.Model):
    _inherit = "product.product"

    item_code = fields.Char(
        string="Item Code",
        copy=False,
        readonly=True,
        index=True,
        help="System-assigned sequential item code (SAP MATNR equivalent). "
             "Unique across all companies, archived items included. "
             "Never edited, never reused. Legacy / drawing / design codes "
             "belong in the Internal Reference, not here.",
    )

    def init(self):
        # R4: unique across all companies, archived rows included.
        # Partial index so rows awaiting the post_init backfill (NULL)
        # do not block installation.
        self.env.cr.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS product_product_item_code_uniq
                ON product_product (item_code)
             WHERE item_code IS NOT NULL
            """
        )

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def _is_item_code_manager(self):
        """Migration-window bypass: superuser or the manage group."""
        return self.env.su or self.env.user.has_group(GROUP_MANAGE)

    # ------------------------------------------------------------------
    # ORM guards (guidelines R3, R5, R6)
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        manager = self._is_item_code_manager()
        Seq = self.env["ir.sequence"].sudo()
        for vals in vals_list:
            if vals.get("item_code"):
                # R3: no external numbering. Manager only for migration
                # imports of historic codes.
                if not manager:
                    raise UserError(_(
                        "Item Codes are system-assigned. Manual entry is "
                        "reserved for the migration window."
                    ))
            else:
                vals["item_code"] = Seq.next_by_code("item.code")
        return super().create(vals_list)

    def write(self, vals):
        # R5: immutable after first save.
        if "item_code" in vals and not self._is_item_code_manager():
            raise UserError(_(
                "The Item Code is permanent and cannot be changed. "
                "Corrections are archive-and-recreate, never renumber."
            ))
        return super().write(vals)

    def unlink(self):
        # Lifecycle (s.8): archive, never delete — the code stays with the
        # record forever (R6). Core variant cleanup catches this error in a
        # savepoint and archives impossible variants instead of deleting
        # them, so attribute changes on templates keep working.
        if self.filtered("item_code") and not self._is_item_code_manager():
            raise UserError(_(
                "Coded items are archived, never deleted. "
                "Use Archive instead."
            ))
        return super().unlink()

    # ------------------------------------------------------------------
    # search: typing '1000481' anywhere must resolve the item
    # ------------------------------------------------------------------
    @api.model
    def _name_search(self, name, domain=None, operator="ilike", limit=None,
                     order=None):
        if name and operator in ("=", "like", "=like", "ilike", "=ilike"):
            ids = list(self._search(
                [("item_code", "ilike", name)] + (domain or []),
                limit=limit, order=order,
            ))
            if ids:
                return ids
        return super()._name_search(
            name, domain=domain, operator=operator, limit=limit, order=order
        )


class ProductTemplate(models.Model):
    _inherit = "product.template"

    item_code = fields.Char(
        string="Item Code",
        compute="_compute_item_code",
        search="_search_item_code",
        help="Item code of the variant (shown when the template has a "
             "single variant).",
    )

    @api.depends("product_variant_ids.item_code")
    def _compute_item_code(self):
        # Same mechanism core uses for default_code on the template.
        self._compute_template_field_from_variant_field("item_code")

    def _search_item_code(self, operator, value):
        return [("product_variant_ids.item_code", operator, value)]
