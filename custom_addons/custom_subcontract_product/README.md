# Sub-contract (Job Work) Product — Odoo 18

Implements FSD/TSD-SCP-001 v1.1: goods logistics with MRP cascaded from the
sales order, principal-owned stock throughout, invoiced as a service with a
SAC on the Indian e-invoice.

## Product configuration
| Role                     | Category                        | Routes                                             |
|--------------------------|---------------------------------|----------------------------------------------------|
| Finished (flagged) FG    | Job Work Chain (SF / FG)        | Deliver on Outward Challan + Job Work Manufacture  |
| Stage semi-finished      | Job Work Chain (SF / FG)        | Job Work Manufacture                               |
| Principal RM             | Principal Materials (Nil Value) | Supplied by Principal                              |
| Own consumables          | (normal valued category)        | Issue to Job Work                                  |

Set the Sub-contract pseudo-type on the FG (writes `type='consu'`,
`is_storable=True`, `l10n_in_is_jobwork=True`); SAC (99xxxx) in HSN/SAC.

## Deployment notes
- Enable Inventory > Consignment. Configure both chain categories with NO
  automated valuation and standard cost 0 (backstop; owner exclusion is the
  primary mechanism).
- Resolve the PIN-PER-BUILD markers (`grep -rn PIN-PER-BUILD`) against the
  exact 18.0 build: l10n_in_edi line helper, e-way bill check hook, GSTR
  return classification points (bridge), and JW-EWB-CHECK (challan-side
  e-way bill availability).
- Fix the six FSD open points before UAT: billing basis, scrap path per
  principal, batching per stage, WIP treatment, challan numbering, EWB
  mechanism.

## Demo dataset
`demo/demo_gear_jobwork.xml` — gear-casting job work: stage products named after the operations (Machining SF -> Grinding FG), two-MO cascade, no work centers.
Staging: add it to the manifest `data` list and upgrade; set FG Sales Taxes after load.
Required settings before the first run: Storage Locations, Multi-Step Routes,
Consignment (Work Orders only if routed operations are added later).

By-products: enable Settings > Manufacturing > By-Products; chips demo by-product
(MS Chips — Principal, kg, HSN 7204) posts owner-tagged from the Machining BOM;
leftover/chips/scrap return on outward challans against the original inward challan.
