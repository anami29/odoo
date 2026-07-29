from odoo import models

# ---------------------------------------------------------------------------
# PIN-PER-BUILD (TSD-SCP-001 v1.1 s.8 / s.12)
#
# The GST return period model buckets lines and the HSN summary by
# `product_id.type == 'service'`. Before deployment, locate the exact
# classification points on the installed Enterprise build:
#
#     grep -rn "type.*service" enterprise/l10n_in_reports_gstr/models/
#
# and widen each to the predicate below. The override shipped here covers
# the per-line service test via the shared helper pattern; adjust the
# method name(s) to the pinned ones if the build differs.
# ---------------------------------------------------------------------------


def _jw_is_service(product):
    return product.type == 'service' or product.l10n_in_is_jobwork


class L10nInGstReturnPeriod(models.Model):
    _inherit = 'l10n_in.gst.return.period'

    def _get_l10n_in_gstr1_hsn_json(self, journal_items, tax_details):
        """Widen the service predicate for the HSN summary: flagged
        job-work lines land in the services bucket (UQC 'NA', no
        quantity). PIN-PER-BUILD: confirm this hook name on the
        installed build and relocate the predicate if it moved."""
        res = super()._get_l10n_in_gstr1_hsn_json(
            journal_items, tax_details)
        flagged_hsn = set(
            journal_items.filtered(
                lambda l: l.product_id.l10n_in_is_jobwork)
            .mapped('l10n_in_hsn_code'))
        for entry in res.values() if isinstance(res, dict) else res:
            if isinstance(entry, dict) and \
                    entry.get('hsn_sc') in flagged_hsn:
                entry['uqc'] = 'NA'
                entry.pop('qty', None)
        return res
