# Financial Reports CE — Balance Sheet, P&L, Cash Flow (v2)

Enterprise-style **on-screen** financial statements for Odoo Community
(18.0 / 19.0): Balance Sheet, Profit & Loss and Cash Flow Statement as a
dynamic view with fold/unfold and drill-down, plus PDF and XLSX export.
No OCA dependencies.

## Features
- Accounting/Invoicing > Reporting > Financial Statements — opens the
  statement **on screen** (OWL client action), not a wizard
- Enterprise-style filter bar: date presets (month/quarter/financial
  year), Comparison (Previous Period / Same Period Last Year / Specific
  Date, up to 12 periods), Journals filter, Posted/Draft toggle,
  Hide lines at 0, Unfold/Fold All, currency pill
- "Unposted Journal Entries" banner (click-through to the draft moves)
- Collapse/expand groups; Expand All / Collapse All
- Click an account row (BS / P&L) to open the matching journal items
- PDF and XLSX buttons render the same computed line set
- Virtual Current/Previous Years Unallocated Earnings (correct with or
  without closing entries); cash-flow classification by standard tags
  with account_type fallback

## Access
Menus and server API are gated on `account.group_account_invoice`
(Billing) — visible to normal Invoicing users, full-accounting technical
groups not required.

## Upgrade from 1.x
Replace the module folder, restart, Apps > Upgrade, then hard-refresh
the browser (new JS assets). The 1.x wizard is removed automatically;
the module stores no data, so uninstall/reinstall is equally safe.

## Odoo 19
Same codebase; the 19.0 zip only changes the manifest `version`.
