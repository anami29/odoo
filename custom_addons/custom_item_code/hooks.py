def post_init_hook(env):
    """Backfill (guidelines s.9): assign item codes to every pre-existing
    variant, ordered by id. default_code is untouched — it already holds
    the legacy / drawing codes."""
    products = env["product.product"].with_context(active_test=False).search(
        [("item_code", "=", False)], order="id asc"
    )
    seq = env["ir.sequence"].sudo()
    for product in products:
        product.item_code = seq.next_by_code("item.code")
