# custom_instrument_calibration

Instrument Calibration & Tool Lifecycle Management for Odoo 18 / 19
(Community-compatible). Implements FSD-CAL-001 v1.2.

## Odoo 18 vs 19
Single codebase. In `__manifest__.py`, set `version` to `18.0.1.2.0` or
`19.0.1.2.0` per target branch — no other change.

## Highlights
- Standalone instrument master, category-wise auto codes (VER/0001, ...),
  lifecycle Draft → In Use / Due / Overdue / Under Calibration / Quarantine /
  Retired / Scrapped / Lost with controlled transitions and Manager overrides.
- Effective due date = min(frequency-based next due, certificate validity);
  nightly cron derives Due / Overdue; custodian activities, manager escalation
  e-mail (mail template) and daily digest (built in code).
- Calibration orders: internal / external, parameter template loading,
  as-found / as-left readings with tolerance evaluation, master-standard
  validity enforcement + certificate snapshot, traceability basis, seal
  condition, environment, dispatch / receipt (gate pass) for TAT.
- Failure → Quarantine + OOT register + mandatory impact assessment and
  product action (ISO 9001 7.1.5.2); Conditional → restricted-use banner.
- Records control (ISO 9001 7.5): global Certificate Repository, SHA-1
  checksums, Manager-only certificate correction with preserved revisions,
  retention block on deletion, post-retention Disposition wizard + register,
  per-instrument Audit Bundle (merged PDF).
- QR status labels 50x25 / 70x35 with DO NOT USE band.
- OWL management dashboard (Community-clean): KPI tiles, drill-through,
  status / due-load / aging / OOT / plan-vs-actual / cost / TAT charts;
  cost widgets Manager-only.
- XLSX registers & MIS (xlsxwriter, Z-register format): Calibration Register,
  Due/Overdue, OOT, Retired, Disposition, Compliance Summary, Plan vs Actual,
  Due-Load Forecast, Cost Analysis, Agency Performance, Downtime,
  Failure/OOT Trend, Custodian Load.

## Configuration
Settings ▸ Calibration: lead days, auto-create draft orders + offset,
escalation days, retention years, compliance target, dashboard period +
fiscal-year start month (default 4 = April), label size.

## Notes
- The daily digest e-mail is composed in code (recipients: Calibration
  Manager group); the overdue escalation uses an editable mail.template.
- Dashboard KPIs are computed live (no snapshots); see FSD §17.4 for formulas.
