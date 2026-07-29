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
