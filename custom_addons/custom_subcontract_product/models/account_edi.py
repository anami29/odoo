from odoo import models, _

# PIN-PER-BUILD (TSD-SCP-001 v1.1 s.12): on the target 18.0 build, confirm
# the l10n_in_edi per-line payload helper and the e-way bill configuration
# check hook (`grep -rn "IsServc" addons/l10n_in_edi`). The overrides below
# target the account.edi.format hooks as shipped on 18.0.


class AccountEdiFormat(models.Model):
    _inherit = 'account.edi.format'

    def _get_l10n_in_edi_line_details(self, index, line, line_tax_details):
        """FR-41: a flagged (sub-contract) line reports as a service.
        HsnCd already carries the SAC by product constraint."""
        res = super()._get_l10n_in_edi_line_details(
            index, line, line_tax_details)
        if line.product_id.l10n_in_is_jobwork:
            res['IsServc'] = 'Y'
        return res

    def _check_move_configuration(self, move):
        """FR-42: block the invoice-side e-way bill on a job-work invoice;
        the movement document is the delivery challan."""
        errors = super()._check_move_configuration(move)
        if 'ewaybill' in (self.code or ''):
            lines = move.invoice_line_ids.filtered(
                lambda l: l.product_id
                and l.display_type not in ('line_section', 'line_note'))
            if lines and all(
                    l.product_id.l10n_in_is_jobwork for l in lines):
                errors.append(_(
                    'Job-work invoice: goods move under the delivery '
                    'challan; generate the e-way bill against the '
                    'challan.'))
        return errors
