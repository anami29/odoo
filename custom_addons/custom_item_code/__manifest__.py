{
    "name": "Item Code (SAP-style Material Number)",
    "summary": "Sequential, unique, immutable item codes on product variants; "
               "Internal Reference freed for legacy / drawing / design codes.",
    "version": "18.0.1.0.0",  # 19.0.1.0.0 on the Odoo 19 branch — only line that changes
    "category": "Inventory/Inventory",
    "license": "LGPL-3",
    "author": "RLFB",
    "depends": ["product"],
    "data": [
        "security/item_code_security.xml",
        "data/ir_sequence_data.xml",
        "views/product_views.xml",
    ],
    "post_init_hook": "post_init_hook",
    "installable": True,
}
