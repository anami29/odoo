# custom_item_code — Odoo 18 / 19

Implements Item Coding Guidelines v2.0 (two-key model):

* `item_code` on `product.product` — sequential from one global
  `ir.sequence` (`item.code`, start 1000001), unique across all
  companies **including archived** (partial SQL unique index),
  immutable, never reused, system-assigned only (R1-R8).
* `default_code` (Internal Reference) left native and free-form for
  legacy / drawing / design codes; relabeled "Legacy / Drawing Code".
* Variant-level numbering (D2-rec). Plain numeric series (D1-rec).
  Native `[default_code] Name` display kept (D3-rec).
* `post_init_hook` backfills existing items ordered by `id`;
  `default_code` untouched (s.9). Export the item_code <-> default_code
  <-> name mapping to XLSX as a migration-window activity.
* `group_item_code_manage`: migration-window imports/corrections only.

One codebase; on the 19 branch change only the manifest version to
`19.0.1.0.0`. Item Code columns on the Z register reports are added in
those modules, not here (s.10).

Run tests: `--test-tags /custom_item_code`
