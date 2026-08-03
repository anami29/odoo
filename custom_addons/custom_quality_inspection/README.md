# custom_quality_inspection

Implements **RLFB-FSD-QMS-001 v1.1** — stage-wise Quality Inspection for
Odoo 18 / 19 Community (also runs on Enterprise; does not use `quality`
Enterprise modules).

Companion module: `custom_quality_calibration_bridge` (auto-installs when
`custom_instrument_calibration` is present; see its docstring — the
instrument model name may need one-line adjustment).

## Install

1. Copy both folders to the addons path; update apps list; install
   *Custom Quality Inspection*.
2. Settings → Quality (Quality Manager group required):
   - **Quality Control Location** and **Non-Conformance Location**
     (create e.g. `WH/Quality` and `WH/NC` as internal locations). For
     physical QC routing, configure two-step receipts with QC as the
     intermediate destination; the module works with one-step receipts
     too, holding stock via the lot Quality Status gate.
   - Notification user, SLA hours, M-Report plant-approval limit,
     CAPA triggers, competence gate, GRR thresholds, sigma-shift,
     skip-lot count, AQL switching automation.
3. Assign groups: Inspector / Quality Engineer / Quality Manager /
   Plant-Level Approver.
4. Masters: defect codes, cause codes, sampling rules, inspector
   qualifications. AQL tables (ISO 2859-1 single, normal, Levels I–III,
   AQL 0.065–6.5) load automatically.

## Flow (happy path)

QIP (quotation-style lines, versioned, approve) → receipt/WO/MO trigger
creates an **Inspection Set** (sampling computed) → per-unit **IRs** →
Evaluate Set → release (lot Accepted, QC→Stock move) or **NCR** →
disposition Rework / Scrap (M Report, value-tiered approval) / RTV /
Deviation → CAPA where mandated → registers, SPC, capability, GRR,
DPMO/sigma.

## FR coverage

| Group | Status |
|---|---|
| 4.1 QIP | Done (versioning, freeze, variant-first lookup) |
| 4.2 Sampling | Done; AQL normal tables loaded; tightened rows loadable (severity column ready), switching auto per FR-SMP-05 (2-in-5 → tightened, 5 accepts → normal) |
| 4.3 Triggers & gates | Receipt / WO / FQC triggers done. Gates enforced at **validation and MO close** (outgoing pickings, MO raw consumption, WO start, MO done). Reservation-time blocking is not intercepted — see Limitations |
| 4.4 Per-unit IR | Done (freeze, immutability, supersede with reason, competence gate). Matrix entry view (FR-IR-06, S) not delivered — per-unit forms + set list instead |
| 4.5 Set evaluation | Done (Ac/Re, screening wizard, partial split of lot state) |
| 4.6 NCR dispositions | Done (repair / rework-MO, M Report two-tier approval + scrap posting, RTV via return wizard, deviation w/ concession) |
| 4.7 Accountability & loss | Done (mandatory codes/responsibility, material + prorated conversion cost, repeat-defect escalation) |
| 4.8 Numbering | Done |
| 4.9 Printouts | IR PDF, M Report PDF, Concession Note. Registers via list/pivot with native XLSX export (bespoke Z-format XLSX wizards can be added as in the register-report addons) |
| 4.10 Notifications | Activities on set/NCR creation, SLA cron, CAPA-overdue cron, SPC alerts |
| 4.11 SPC & capability | X̄–R, I–MR, p, np charts with WE/Nelson rules, lockable baseline limits; Cp/Cpk/Pp/Ppk; DPMO/σ/FPY/RTY wizard; raw export via list export. **c and u charts not implemented** |
| 4.12 CAPA/Competence/Records | CAPA workflow with effectiveness gate; qualification matrix warn/block; records immutable & archive-only. Retention-period automation and one-click audit pack are manual (filters + export) in this release |

## Known limitations (state these at UAT)

- Gates act at **validation time**, not at reservation time; a picking can
  reserve a pending lot but cannot be validated.
- **c / u control charts** pending; p / np / X̄–R / I–MR delivered.
- AQL **tightened** severity uses normal-table values until tightened rows
  are loaded into `quality.aql.plan` (column exists).
- Dashboard = pivot/graph views + Six Sigma wizard (no custom OWL widget).
- Per-line photos: attach via IR chatter (no binary per line).
- Repair completion detected via state write; if your repair flow ends
  differently, adjust `RepairOrder.write`.
- No automated tests shipped; module is lint-clean but was not runtime
  tested against a live Odoo instance — install on staging first.
